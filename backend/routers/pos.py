from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from datetime import datetime, timezone

from database import get_db, Sale, SaleItem, Product, Shift, Employee, Client
from schemas import SaleCreate, SaleOut, ShiftOpen, ShiftClose, ShiftOut
from core import get_current_user

router = APIRouter(prefix="/pos", tags=["pos"])

@router.get("/sales", response_model=List[SaleOut])
async def get_sales(
    limit: int = 50,
    offset: int = 0,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sales history with pagination"""
    result = await db.execute(
        select(Sale)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client)
        )
        .order_by(Sale.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.unique().scalars().all()

@router.post("/sales", response_model=SaleOut)
async def create_sale(
    sale_data: SaleCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if there is an open shift for this cashier
    result = await db.execute(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    shift = result.scalars().first()
    if not shift:
         raise HTTPException(status_code=400, detail="Smena ochilmagan! Iltimos, oldin smenani oching.")

    # Create Sale
    db_sale = Sale(
        total_amount=sale_data.total_amount,
        payment_method=sale_data.payment_method,
        cashier_id=current_user.id,
        client_id=sale_data.client_id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_sale)
    await db.flush() # Get sale ID

    # Process items and update stock
    for item in sale_data.items:
        # Update stock
        product_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = product_result.scalars().first()
        if not product:
            continue
        
        if product.stock < item.quantity:
             raise HTTPException(status_code=400, detail=f"Sklad da yetarli mahsulot yo'q: {product.name}. Qoldiq: {product.stock}")

        product.stock -= item.quantity
        
        # Create SaleItem
        db_item = SaleItem(
            sale_id=db_sale.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price=item.price
        )
        db.add(db_item)

    # If client and payment method is debt (nasiya), update client balance
    if sale_data.client_id and sale_data.payment_method == "debt":
        client_result = await db.execute(select(Client).where(Client.id == sale_data.client_id))
        client = client_result.scalars().first()
        if client:
            client.balance -= sale_data.total_amount # Negative balance means debt

    await db.commit()
    
    # Reload with relationships
    result = await db.execute(
        select(Sale)
        .where(Sale.id == db_sale.id)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client)
        )
    )
    return result.unique().scalars().first()

@router.post("/shifts/open", response_model=ShiftOut)
async def open_shift(
    data: ShiftOpen,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if already has an open shift
    result = await db.execute(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Sizda allaqachon ochiq smena bor.")

    db_shift = Shift(
        cashier_id=current_user.id,
        opening_balance=data.opening_balance,
        note=data.note,
        status="open",
        opened_at=datetime.now(timezone.utc)
    )
    db.add(db_shift)
    await db.commit()
    await db.refresh(db_shift)
    return db_shift

@router.get("/shifts/current", response_model=Optional[ShiftOut])
async def get_current_shift(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current open shift for the authenticated user"""
    result = await db.execute(
        select(Shift).options(joinedload(Shift.cashier))
        .where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    return result.scalars().first()

@router.post("/shifts/close", response_model=ShiftOut)
async def close_shift(
    data: ShiftClose,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    db_shift = result.scalars().first()
    if not db_shift:
        raise HTTPException(status_code=400, detail="Ochiq smena topilmadi.")

    db_shift.closing_balance = data.closing_balance
    db_shift.closed_at = datetime.now(timezone.utc)
    db_shift.status = "closed"
    db_shift.note = (db_shift.note or "") + (f"\nClosing Note: {data.note}" if data.note else "")

    await db.commit()
    await db.refresh(db_shift)
    return db_shift

from sqlalchemy.orm import joinedload

@router.get("/shifts/history", response_model=List[ShiftOut])
async def get_shifts_history(
    limit: int = 50,
    offset: int = 0,
    employee_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get history of shifts. Admins see all, others see only their own."""
    query = select(Shift).options(joinedload(Shift.cashier))
    
    if current_user.role != "admin":
        query = query.where(Shift.cashier_id == current_user.id)
    elif employee_id:
        query = query.where(Shift.cashier_id == employee_id)
        
    if start_date:
        query = query.where(Shift.opened_at >= start_date)
    if end_date:
        query = query.where(Shift.opened_at <= end_date)
    
    result = await db.execute(
        query.order_by(Shift.opened_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
