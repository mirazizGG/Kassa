from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from database import get_db, Expense, Payment, Employee, Client, Product, Sale, SaleItem
from schemas import ExpenseCreate, ExpenseOut, PaymentCreate
from core import get_current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/finance", tags=["finance"])

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    # 1. Daily Sales
    today = datetime.now(timezone.utc).date()
    # Note: SQLite stores dates as strings or separate logic might be needed, but assume standard alchemy behavior for now.
    # We might need to filter by range for today.
    # For now, let's just get total sales as 'dailySales' mock-up or implement properly if possible.
    # Let's try to query sales created >= today's start.
    
    start_of_day = datetime.combine(today, datetime.min.time())
    
    sales_query = select(func.sum(Sale.total_amount)).where(Sale.created_at >= start_of_day)
    sales_result = await db.execute(sales_query)
    daily_sales = sales_result.scalar() or 0
    
    # 2. Client Count
    client_query = select(func.count(Client.id))
    client_result = await db.execute(client_query)
    client_count = client_result.scalar() or 0
    
    # 3. Low Stock
    stock_query = select(func.count(Product.id)).where(Product.stock < 5)
    stock_result = await db.execute(stock_query)
    low_stock = stock_result.scalar() or 0
    
    # 4. Total Products
    product_query = select(func.count(Product.id))
    product_result = await db.execute(product_query)
    total_products = product_result.scalar() or 0
    
    return {
        "dailySales": f"{daily_sales:,.0f} so'm",
        "clientCount": str(client_count),
        "lowStock": str(low_stock),
        "totalProducts": str(total_products)
    }

@router.get("/dashboard-chart")
async def get_dashboard_chart(db: AsyncSession = Depends(get_db)):
    # Returns last 7 days sales
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=6) # 7 days including today
    
    # We need to construct a robust query. Since sqlite dates are tricky, 
    # ensuring consistent date formatting in DB is key.
    # Assuming Sale.created_at is stored correctly as DateTime.
    
    # Simple list of last 7 days
    labels = []
    data = []
    
    # This loop is not efficient for huge datasets but fine for small POS
    for i in range(7):
        day = start_date + timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        # We need to filter sales for this specific day
        # Note: If sqlite stores as naive dates, this comparison might need adjustment
        query = select(func.sum(Sale.total_amount)).where(
            Sale.created_at >= day_start,
            Sale.created_at <= day_end
        )
        result = await db.execute(query)
        total = result.scalar() or 0
        
        labels.append(day.strftime("%d.%m"))
        data.append(total)
        
    return {"labels": labels, "data": data}

@router.get("/top-products")
async def get_top_products(db: AsyncSession = Depends(get_db)):
    # Top 5 products by quantity sold
    query = (
        select(Product.name, func.sum(SaleItem.quantity).label("total_qty"))
        .join(SaleItem, Product.id == SaleItem.product_id)
        .group_by(Product.id)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(5)
    )
    result = await db.execute(query)
    # result.all() returns list of rows (name, total_qty)
    items = [{"name": row[0], "value": row[1]} for row in result.all()]
    return items

@router.get("/expenses", response_model=List[ExpenseOut])
async def get_expenses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Expense))
    return result.scalars().all()

@router.post("/expenses", response_model=ExpenseOut)
async def create_expense(
    expense: ExpenseCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_expense = Expense(
        **expense.model_dump(),
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_expense)
    await db.commit()
    await db.refresh(db_expense)
    return db_expense

@router.post("/payments")
async def create_payment(
    payment: PaymentCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Payment usually means client paying back debt
    db_payment = Payment(
        **payment.model_dump(),
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_payment)
    
    # Update client balance
    result = await db.execute(select(Client).where(Client.id == payment.client_id))
    client = result.scalars().first()
    if client:
        client.balance += payment.amount
        
    await db.commit()
    return {"status": "success", "message": "To'lov qabul qilindi"}

import csv
import io
from fastapi.responses import StreamingResponse

@router.get("/reports/export")
async def export_sales(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Sotuvlar tarixini CSV formatda yuklab olish"""
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    # Fetch sales with items and products
    query = (
        select(Sale)
        .options(joinedload(Sale.items).joinedload(SaleItem.product), joinedload(Sale.cashier), joinedload(Sale.client))
        .where(Sale.created_at >= start_date, Sale.created_at <= end_date)
        .order_by(Sale.created_at.desc())
    )
    
    result = await db.execute(query)
    sales = result.unique().scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["ID", "Sana", "Kassir", "Mijoz", "Summa", "To'lov usuli", "Mahsulotlar"])
    
    for s in sales:
        items_str = "; ".join([f"{item.product.name} ({item.quantity} {item.product.unit})" for item in s.items if item.product])
        writer.writerow([
            s.id,
            s.created_at.strftime("%d.%m.%Y %H:%M"),
            s.cashier.username if s.cashier else "-",
            s.client.name if s.client else "-",
            s.total_amount,
            s.payment_method,
            items_str
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')), # byte order mark for Excel
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sotuvlar_{datetime.now().strftime('%Y%m%d')}.csv"}
    )
