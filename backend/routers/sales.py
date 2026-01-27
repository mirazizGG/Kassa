from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List

from database import get_db, Product, Sale, SaleItem, Employee, Client
from schemas import SaleCreate, SaleOut
from core import get_current_user

router = APIRouter(prefix="/sales", tags=["sales"])

@router.post("/", response_model=SaleOut)
async def create_sale(
    sale: SaleCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Start a transaction implicit in async session
    
    # 2. Check stock availability
    total_amount_check = 0
    sale_items_data = []

    for item in sale.items:
        result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = result.scalars().first()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for {product.name}. Available: {product.stock}")
        
        # Deduct stock
        product.stock -= item.quantity
        total_amount_check += item.quantity * item.price
        
        # Prepare item data for DB
        sale_items_data.append(SaleItem(
            product_id=product.id,
            quantity=item.quantity,
            price=item.price
        ))

    # 3. Create Sale Record
    db_sale = Sale(
        total_amount=sale.total_amount, # Trust frontend total or use total_amount_check? Let's use frontend for flexible pricing, but validation is good practice.
        payment_method=sale.payment_method,
        cashier_id=current_user.id,
        client_id=sale.client_id,
        status="completed"
    )
    db.add(db_sale)
    await db.flush() # Get ID

    # 4. Create Sale Items
    for sale_item in sale_items_data:
        sale_item.sale_id = db_sale.id
        db.add(sale_item)

    # 5. Handle Client Balance (if credit sale)
    if sale.payment_method == "qarz" and sale.client_id:
        result = await db.execute(select(Client).where(Client.id == sale.client_id))
        client = result.scalars().first()
        if client:
            client.balance -= sale.total_amount # Increase debt (negative balance)
    
    await db.commit()
    await db.refresh(db_sale)
    return db_sale

@router.get("/", response_model=List[SaleOut])
async def get_sales(
    skip: int = 0, 
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Sale).offset(skip).limit(limit).order_by(Sale.created_at.desc()))
    return result.scalars().all()
