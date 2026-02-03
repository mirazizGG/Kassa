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

def parse_date(date_val: Optional[str], default_time=datetime.min.time()):
    if not date_val:
        return None
    try:
        # If it's just a date (YYYY-MM-DD)
        if len(date_val) <= 10:
            d = datetime.strptime(date_val, "%Y-%m-%d")
            return datetime.combine(d.date(), default_time)
        
        # Try ISO format
        dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except ValueError:
        return None

@router.get("/stats")
async def get_stats(
    employee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    start_date = parse_date(start_date, datetime.min.time())
    end_date = parse_date(end_date, datetime.max.time())
    # 1. Daily Sales or custom range
    if not start_date:
        today = datetime.now(timezone.utc).date()
        start_date = datetime.combine(today, datetime.min.time())
    if not end_date:
        end_date = datetime.now(timezone.utc)
    
    sales_query = select(func.sum(Sale.total_amount)).where(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date,
        Sale.status == "completed"
    )
    if employee_id:
        sales_query = sales_query.where(Sale.cashier_id == employee_id)
        
    sales_result = await db.execute(sales_query)
    sales_total = sales_result.scalar() or 0
    
    # 1.1 Total Cost (Buy Price * Quantity)
    cost_query = (
        select(func.sum(SaleItem.quantity * Product.buy_price))
        .join(Product, SaleItem.product_id == Product.id)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == "completed"
        )
    )
    if employee_id:
        cost_query = cost_query.where(Sale.cashier_id == employee_id)
    
    cost_result = await db.execute(cost_query)
    total_cost = cost_result.scalar() or 0

    # 1.2 Total Expenses
    expense_query = select(func.sum(Expense.amount)).where(
        Expense.created_at >= start_date,
        Expense.created_at <= end_date
    )
    if employee_id:
        expense_query = expense_query.where(Expense.created_by == employee_id)
    
    expense_result = await db.execute(expense_query)
    total_expenses = expense_result.scalar() or 0

    net_profit = sales_total - total_cost - total_expenses

    # 2. Client Count
    client_query = select(func.count(Client.id))
    client_result = await db.execute(client_query)
    client_count = client_result.scalar() or 0
    
    # 3. Low Stock Items List
    stock_query = select(Product).where(Product.stock < 5).limit(10)
    stock_result = await db.execute(stock_query)
    low_stock_items = stock_result.scalars().all()
    
    # 4. Total Products Count
    product_query = select(func.count(Product.id))
    product_result = await db.execute(product_query)
    total_products = product_result.scalar() or 0
    
    return {
        "dailySales": sales_total,
        "dailySalesFormatted": f"{sales_total:,.0f} so'm",
        "totalCost": total_cost,
        "totalExpenses": total_expenses,
        "netProfit": net_profit,
        "netProfitFormatted": f"{net_profit:,.0f} so'm",
        "clientCount": str(client_count),
        "lowStock": str(len(low_stock_items)),
        "lowStockItems": [
            {
                "id": p.id,
                "name": p.name,
                "stock": p.stock,
                "unit": p.unit,
                "sell_price": p.sell_price
            } for p in low_stock_items
        ],
        "totalProducts": str(total_products)
    }

@router.get("/dashboard-chart")
async def get_dashboard_chart(
    employee_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    # Returns last 7 days sales
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=6) # 7 days including today
    
    labels = []
    data = []
    
    for i in range(7):
        day = start_date + timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        query = select(func.sum(Sale.total_amount)).where(
            Sale.created_at >= day_start,
            Sale.created_at <= day_end,
            Sale.status == "completed"
        )
        if employee_id:
            query = query.where(Sale.cashier_id == employee_id)
            
        result = await db.execute(query)
        total = result.scalar() or 0
        
        labels.append(day.strftime("%d.%m"))
        data.append(total)
        
    return {"labels": labels, "data": data}

@router.get("/top-products")
async def get_top_products(
    limit: int = 5,
    employee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    start_date = parse_date(start_date, datetime.min.time())
    end_date = parse_date(end_date, datetime.max.time())
    query = (
        select(Product.name, func.sum(SaleItem.quantity).label("total_qty"))
        .join(SaleItem, Product.id == SaleItem.product_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.status == "completed")
        .group_by(Product.id)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(limit)
    )
    if employee_id:
        query = query.where(Sale.cashier_id == employee_id)
    if start_date:
        query = query.where(Sale.created_at >= start_date)
    if end_date:
        query = query.where(Sale.created_at <= end_date)
        
    result = await db.execute(query)
    items = [{"name": row[0], "value": row[1]} for row in result.all()]
    return items

@router.get("/expenses", response_model=List[ExpenseOut])
async def get_expenses(
    category: Optional[str] = None,
    employee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    start_date = parse_date(start_date, datetime.min.time())
    end_date = parse_date(end_date, datetime.max.time())
    query = select(Expense).options(joinedload(Expense.creator))
    if employee_id:
        query = query.where(Expense.created_by == employee_id)
    if category:
        query = query.where(Expense.category == category)
    if start_date:
        query = query.where(Expense.created_at >= start_date)
    if end_date:
        query = query.where(Expense.created_at <= end_date)
        
    result = await db.execute(query.order_by(Expense.created_at.desc()))
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

@router.get("/export-sales")
async def export_sales(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    start_date = parse_date(start_date, datetime.min.time())
    end_date = parse_date(end_date, datetime.max.time())
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

@router.get("/categories")
async def get_expense_categories(db: AsyncSession = Depends(get_db)):
    # You might have an ExpenseCategory table, let's check database.py
    # From database.py: class ExpenseCategory(Base): __tablename__ = "expense_categories"
    from database import ExpenseCategory
    result = await db.execute(select(ExpenseCategory))
    return result.scalars().all()
