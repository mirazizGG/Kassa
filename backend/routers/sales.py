from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from datetime import datetime

from database import get_db, Product, Sale, SaleItem, Employee, Client, StoreSetting, StockMove
from schemas import SaleCreate, SaleOut
from core import get_current_user

from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/sales", tags=["sales"])

def parse_date(date_val: Optional[str], default_time=datetime.min.time()):
    if not date_val:
        return None
    try:
        if len(date_val) <= 10:
            d = datetime.strptime(date_val, "%Y-%m-%d")
            return datetime.combine(d.date(), default_time)
        
        dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except ValueError:
        return None

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
            raise HTTPException(status_code=400, detail=f"Mahsulot yetarli emas: {product.name}. Mavjud: {product.stock}")
        
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
        total_amount=sale.total_amount, 
        payment_method=sale.payment_method,
        cashier_id=current_user.id,
        client_id=sale.client_id,
        status="completed",
        cash_amount=sale.cash_amount,
        card_amount=sale.card_amount,
        transfer_amount=sale.transfer_amount,
        debt_amount=sale.debt_amount
    )
    db.add(db_sale)
    await db.flush() # Get ID

    # 4. Create Sale Items and Stock Logs
    for sale_item in sale_items_data:
        sale_item.sale_id = db_sale.id
        db.add(sale_item)
        
        # Log Stock Movement (Negative for sale)
        db_move = StockMove(
            product_id=sale_item.product_id,
            quantity=-sale_item.quantity,
            type="sale",
            reason=f"Sotuv (Chek ID: {db_sale.id})",
            created_by=current_user.id
        )
        db.add(db_move)

    # 5. Handle Client Balance and Bonuses
    if sale.client_id:
        result = await db.execute(select(Client).where(Client.id == sale.client_id))
        client = result.scalars().first()
        if client:
            # Handle Debt
            if sale.debt_amount > 0:
                client.balance -= sale.debt_amount
            
            # 5.1 Handle Bonuses
            # Get bonus setting
            settings_res = await db.execute(select(StoreSetting))
            settings = settings_res.scalars().first()
            bonus_percent = settings.bonus_percentage if settings else 1.0
            
            # Calculate earned bonus (from the amount actually paid or total?) 
            # Usually from total non-debt amount or just total? Let's do from (total - debt)
            paid_amount = db_sale.total_amount - db_sale.debt_amount
            if paid_amount > 0:
                earned = (paid_amount * bonus_percent) / 100
                db_sale.bonus_earned = earned
                client.bonus_balance += earned
            
            # Handle spent bonus
            if sale.bonus_spent > 0:
                if client.bonus_balance < sale.bonus_spent:
                    raise HTTPException(status_code=400, detail="Bonus balansi yetarli emas")
                client.bonus_balance -= sale.bonus_spent
                db_sale.bonus_spent = sale.bonus_spent
    
    await db.commit()
    
    # 6. Safety Backup (Automatic)
    try:
        from utils.backup import create_backup
        create_backup()
    except:
        pass
    
    # Reload with relationships for response_model
    result = await db.execute(
        select(Sale)
        .where(Sale.id == db_sale.id)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client)
        )
    )
    db_sale_full = result.unique().scalars().first()
    return db_sale_full

@router.get("/", response_model=List[SaleOut])
async def get_sales(
    skip: int = 0, 
    limit: int = 100,
    employee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Enforce RBAC
    if current_user.role == "cashier":
        employee_id = current_user.id
        
    start_date = parse_date(start_date, datetime.min.time())
    end_date = parse_date(end_date, datetime.max.time())
    
    query = (
        select(Sale)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client)
        )
    )
    if employee_id:
        query = query.where(Sale.cashier_id == employee_id)
        
    # Manager restriction: Filter out Admin sales if viewing 'all' or specific admin
    if current_user.role == "manager":
         # Join with Employee to check role of the cashier
         # This is a bit complex for a simple list, but let's just do a simple check if employee_id is provided
         if employee_id:
             target_emp = await db.scalar(select(Employee).where(Employee.id == employee_id))
             if target_emp and target_emp.role == "admin":
                 # Return empty or error? Empty seems safer for list view
                 return []
         else:
             # If listing all, exclude sales made by admins
             # We need to join with Employee table to filter by role
             query = query.join(Employee, Sale.cashier_id == Employee.id).where(Employee.role != "admin")

    if start_date:
        query = query.where(Sale.created_at >= start_date)
    if end_date:
        query = query.where(Sale.created_at <= end_date)
        
    result = await db.execute(query.offset(skip).limit(limit).order_by(Sale.created_at.desc()))
    return result.unique().scalars().all()

@router.post("/{sale_id}/refund", response_model=SaleOut)
async def refund_sale(
    sale_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Security: Only admin and manager can refund
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Faqat administrator yoki menejer savdoni qaytara oladi")

    # 1. Fetch the sale with items
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.client)
        )
    )
    db_sale = result.unique().scalars().first()
    
    if not db_sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    if db_sale.status == "refunded":
        raise HTTPException(status_code=400, detail="Sale already refunded")

    # 2. Restore stock for each item and Log
    for item in db_sale.items:
        if item.product:
            item.product.stock += item.quantity
            
            # Log Stock Movement (Positive for refund)
            db_move = StockMove(
                product_id=item.product_id,
                quantity=item.quantity,
                type="refund",
                reason=f"Vozvrat (Chek ID: {db_sale.id})",
                created_by=current_user.id
            )
            db.add(db_move)
    
    # 3. Handle Client Balance and Bonuses (Deduct earned bonuses)
    if db_sale.client:
        if db_sale.debt_amount > 0:
            db_sale.client.balance += db_sale.debt_amount 
        
        # Deduct earned bonus
        if db_sale.bonus_earned > 0:
            db_sale.client.bonus_balance -= db_sale.bonus_earned

    # 4. Update Sale Status
    db_sale.status = "refunded"
    
    await db.commit()
    
    # Reload for response
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client)
        )
    )
    return result.unique().scalars().first()
