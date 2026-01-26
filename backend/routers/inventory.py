from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional

from database import get_db, Product, Category, Employee
from schemas import ProductCreate, ProductOut, CategoryCreate, CategoryOut
from core import get_current_user

router = APIRouter(prefix="/inventory", tags=["inventory"])

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
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_product = Product(**product.model_dump())
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product

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
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_category = Category(name=category.name)
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category
