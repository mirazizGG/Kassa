from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional

from database import get_db, Product, Category, Employee, Supply, StockMove
from schemas import ProductCreate, ProductOut, CategoryCreate, CategoryOut, SupplyCreate, SupplyOut, StockMoveOut
from core import get_current_user

from routers.audit import log_action

router = APIRouter(prefix="/inventory", tags=["inventory"])

# --- SUPPLIES ---
@router.post("/supplies", response_model=SupplyOut)
async def create_supply(
    supply: SupplyCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # 1. Mahsulotni topish
    result = await db.execute(select(Product).where(Product.id == supply.product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Kirim tarixi yaratish
    db_supply = Supply(
        product_id=supply.product_id,
        quantity=supply.quantity,
        buy_price=supply.buy_price
    )
    db.add(db_supply)

    # 3. Mahsulot sonini va tannarxini yangilash
    product.stock += supply.quantity
    product.buy_price = supply.buy_price # Oxirgi kelgan narxni o'rnatamiz (yoki o'rtacha hisoblash ham mumkin)

    # 4. Stock Movement Log
    db_move = StockMove(
        product_id=product.id,
        quantity=supply.quantity,
        type="restock",
        reason=f"Yangi kirim (ID: {db_supply.id})",
        created_by=current_user.id
    )
    db.add(db_move)

    await log_action(db, current_user.id, "OMBOR_KIRIM", f"Mahsulot: {product.name}. Soni: {supply.quantity}. Narxi: {supply.buy_price}")

    await db.commit()
    await db.refresh(db_supply)
    return db_supply

@router.get("/supplies", response_model=List[SupplyOut])
async def get_supplies(
    product_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Supply).order_by(Supply.created_at.desc())
    if product_id:
        stmt = stmt.where(Supply.product_id == product_id)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/logs", response_model=List[StockMoveOut])
async def get_stock_logs(
    product_id: Optional[int] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
        
    stmt = select(StockMove).options(joinedload(StockMove.product), joinedload(StockMove.user)).order_by(StockMove.created_at.desc())
    if product_id:
        stmt = stmt.where(StockMove.product_id == product_id)
        
    result = await db.execute(stmt)
    return result.scalars().all()

# --- PRODUCTS ---
@router.get("/products", response_model=List[ProductOut])
async def get_products(
    category_id: Optional[int] = None,
    query: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Product)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if query:
        stmt = stmt.where(Product.name.contains(query) | Product.barcode.contains(query))
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/products", response_model=ProductOut)
async def create_product(
    product: ProductCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    db_product = Product(**product.model_dump())
    db.add(db_product)
    
    # Stock Log if initial stock > 0
    if db_product.stock > 0:
        db_move = StockMove(
            product_id=db_product.id,
            quantity=db_product.stock,
            type="adjustment",
            reason="Dastlabki qoldiq (mahsulot yaratilganda)",
            created_by=current_user.id
        )
        db.add(db_move)

    await log_action(db, current_user.id, "YANGI_MAHSULOT", f"Mahsulot: {db_product.name}. Sklad: {db_product.stock}. Narx: {db_product.sell_price}")

    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    product: ProductCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    result = await db.execute(select(Product).where(Product.id == product_id))
    db_product = result.scalars().first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    old_stock = db_product.stock
    new_stock = product.stock

    # Update product fields
    for key, value in product.model_dump().items():
        setattr(db_product, key, value)

    # Stock Log if stock changed
    if old_stock != new_stock:
        diff = new_stock - old_stock
        db_move = StockMove(
            product_id=db_product.id,
            quantity=diff,
            type="adjustment",
            reason="Ombor tahrirlandi (adjustment)",
            created_by=current_user.id
        )
        db.add(db_move)

    await log_action(db, current_user.id, "MAHSULOT_TAHRIR", f"Mahsulot: {db_product.name} (ID: {product_id}). Sklad: {old_stock} -> {new_stock}")

    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can delete products")

    result = await db.execute(select(Product).where(Product.id == product_id))
    db_product = result.scalars().first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.delete(db_product)
    
    # Audit Log
    try:
        from routers.audit import log_action
        await log_action(db, current_user.id, "DELETE_PRODUCT", f"Mahsulot o'chirildi: {db_product.name} (ID: {product_id})")
    except:
        pass

    await db.commit()
    return {"status": "success", "message": "Product deleted"}

# --- CATEGORIES ---
@router.get("/categories", response_model=List[CategoryOut])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category))
    return result.scalars().all()

@router.post("/categories", response_model=CategoryOut)
async def create_category(
    category: CategoryCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_category = Category(name=category.name)
    db.add(db_category)
    await log_action(db, current_user.id, "YANGI_KATEGORIYA", f"Kategoriya: {category.name}")
    await db.commit()
    await db.refresh(db_category)
    return db_category
@router.post("/products/{product_id}/toggle-favorite", response_model=ProductOut)
async def toggle_favorite(
    product_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    result = await db.execute(select(Product).where(Product.id == product_id))
    db_product = result.scalars().first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    db_product.is_favorite = not db_product.is_favorite
    await db.commit()
    await db.refresh(db_product)
    return db_product
