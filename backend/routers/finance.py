from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from database import get_db, Expense, Payment, Employee, Client, Product, Sale, SaleItem, StoreSetting, Task
from schemas import ExpenseCreate, ExpenseOut, PaymentCreate
from core import get_current_user
# from sqlalchemy import func # Already imported above
from sqlalchemy.orm import joinedload
from routers.audit import log_action
import io

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
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Allow admin, manager, and cashier (but cashier is restricted)
    if current_user.role not in ["admin", "manager", "cashier"]:
         raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    
    # CASHIER RESTRICTION: Can only see their own stats
    if current_user.role == "cashier":
        employee_id = current_user.id
    
    # RBAC v3: Manager cannot spy on Admin stats
    if employee_id and current_user.role == "manager":
        # Check if the target employee is an admin
        target_emp_res = await db.execute(select(Employee).where(Employee.id == employee_id))
        target_emp = target_emp_res.scalars().first()
        if target_emp and target_emp.role == "admin":
             raise HTTPException(status_code=403, detail="Menejer admin hisobotini ko'ra olmaydi")
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

    # If manager, hide sensitive profit/cost data
    # If manager or cashier, hide sensitive profit/cost data
    if current_user.role in ["manager", "cashier"]:
        total_cost = 0
        net_profit = 0
    else:
        net_profit = sales_total - total_cost - total_expenses

    # 2. Client Count
    client_query = select(func.count(Client.id))
    client_result = await db.execute(client_query)
    client_count = client_result.scalar() or 0
    
    # 3. Low Stock Items List
    settings_result = await db.execute(select(StoreSetting))
    settings = settings_result.scalars().first()
    threshold = settings.low_stock_threshold if settings else 5

    stock_query = select(Product).where(Product.stock <= threshold).limit(10)
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

@router.get("/expenses-by-category")
async def get_expenses_by_category(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    start_date = parse_date(start_date, datetime.min.time())
    end_date = parse_date(end_date, datetime.max.time())
    
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)
        
    query = (
        select(Expense.category, func.sum(Expense.amount))
        .where(Expense.created_at >= start_date, Expense.created_at <= end_date)
        .group_by(Expense.category)
    )
    result = await db.execute(query)
    return [{"category": row[0], "amount": row[1]} for row in result.all()]

@router.get("/employee-performance")
async def get_employee_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sales and task statistics for all employees (Admin/Manager only)"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
        
    start_date_parsed = parse_date(start_date, datetime.min.time())
    end_date_parsed = parse_date(end_date, datetime.max.time())
    
    if not start_date_parsed:
        start_date_parsed = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date_parsed:
        end_date_parsed = datetime.now(timezone.utc)
        
    # Get employees (Managers don't see Admin performance)
    query = select(Employee)
    if current_user.role == "manager":
        query = query.where(Employee.role != "admin")
        
    employees_result = await db.execute(query)
    employees = employees_result.scalars().all()
    
    performance_data = []
    
    for emp in employees:
        # Sales count and total
        sales_query = (
            select(func.count(Sale.id), func.sum(Sale.total_amount))
            .where(Sale.cashier_id == emp.id, Sale.created_at >= start_date_parsed, Sale.created_at <= end_date_parsed)
        )
        sales_result = await db.execute(sales_query)
        sale_count, sale_total = sales_result.first()
        
        # Tasks count (completed / total)
        task_query = (
            select(
                func.count(Task.id),
                func.sum(case((Task.status == 'completed', 1), else_=0))
            )
            .where(Task.assigned_to == emp.id)
        )
        task_result = await db.execute(task_query)
        total_tasks, completed_tasks = task_result.first()
        
        performance_data.append({
            "id": emp.id,
            "username": emp.username,
            "full_name": emp.full_name,
            "role": emp.role,
            "sale_count": sale_count or 0,
            "sale_total": float(sale_total or 0),
            "total_tasks": total_tasks or 0,
            "completed_tasks": int(completed_tasks or 0)
        })
        
    return performance_data

@router.get("/profit-chart")
async def get_profit_chart(
    days: int = 7,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    # Returns last N days profit/revenue/expense
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days-1)
    
    results = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        # Revenue
        rev_query = select(func.sum(Sale.total_amount)).where(
            Sale.created_at >= day_start,
            Sale.created_at <= day_end,
            Sale.status == "completed"
        )
        rev_result = await db.execute(rev_query)
        revenue = rev_result.scalar() or 0
        
        # Expenses
        exp_query = select(func.sum(Expense.amount)).where(
            Expense.created_at >= day_start,
            Expense.created_at <= day_end
        )
        exp_result = await db.execute(exp_query)
        expenses = exp_result.scalar() or 0
        
        # Cost of Goods Sold (COGS)
        cost_query = (
            select(func.sum(SaleItem.quantity * Product.buy_price))
            .join(Product, SaleItem.product_id == Product.id)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(
                Sale.created_at >= day_start,
                Sale.created_at <= day_end,
                Sale.status == "completed"
            )
        )
        cost_result = await db.execute(cost_query)
        cogs = cost_result.scalar() or 0
        
        if current_user.role in ["manager", "cashier"]:
            display_expenses = expenses # Only store expenses
            display_profit = 0
        else:
            display_expenses = expenses + cogs
            display_profit = revenue - cogs - expenses
        
        results.append({
            "date": day.strftime("%d.%m"),
            "revenue": revenue,
            "expenses": display_expenses,
            "profit": display_profit
        })
        
    return results

@router.get("/dashboard-chart")
async def get_dashboard_chart(
    employee_id: Optional[int] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Cashier can only see their own chart
    if current_user.role == "cashier":
        employee_id = current_user.id
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
    
    await log_action(db, current_user.id, "YANGI_XARAJAT", f"Xarajat: {db_expense.amount:,.0f} so'm ({db_expense.category}). Izoh: {db_expense.reason}")

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
        
    await log_action(db, current_user.id, "MIJOZ_TOLOV", f"Mijoz: {client.name if client else 'Nomalum'}. Summa: {payment.amount:,.0f} so'm. Usul: {payment.payment_method}")
        
    await db.commit()
    return {"status": "success", "message": "To'lov qabul qilindi"}

import csv
import io
from fastapi.responses import StreamingResponse

@router.get("/export-sales")
async def export_sales(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
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

@router.get("/export-sales-excel")
async def export_sales_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    import pandas as pd
    
    start_date = parse_date(start_date, datetime.min.time())
    end_date = parse_date(end_date, datetime.max.time())
    
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    query = (
        select(Sale)
        .options(joinedload(Sale.items).joinedload(SaleItem.product), joinedload(Sale.cashier), joinedload(Sale.client))
        .where(Sale.created_at >= start_date, Sale.created_at <= end_date)
        .order_by(Sale.created_at.desc())
    )
    
    result = await db.execute(query)
    sales = result.unique().scalars().all()

    data = []
    for s in sales:
        items_str = ", ".join([f"{item.product.name} ({item.quantity} {item.product.unit})" for item in s.items if item.product])
        data.append({
            "ID": s.id,
            "Sana": s.created_at.strftime("%d.%m.%Y %H:%M"),
            "Kassir": s.cashier.username if s.cashier else "-",
            "Mijoz": s.client.name if s.client else "-",
            "Summa": s.total_amount,
            "To'lov usuli": s.payment_method,
            "Mahsulotlar": items_str
        })
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Savdolar')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=sotuvlar_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )

@router.get("/categories")
async def get_expense_categories(db: AsyncSession = Depends(get_db)):
    # You might have an ExpenseCategory table, let's check database.py
    # From database.py: class ExpenseCategory(Base): __tablename__ = "expense_categories"
    from database import ExpenseCategory
    result = await db.execute(select(ExpenseCategory))
    return result.scalars().all()
