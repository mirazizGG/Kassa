from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from typing import List, Optional
from datetime import datetime, timezone, date, time


# ... (imports)
from database import get_db, Sale, SaleItem, Product, Shift, Employee, Client
from schemas import SaleCreate, SaleOut, ShiftOpen, ShiftClose, ShiftOut
from core import get_current_user

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("/shifts/history", response_model=List[ShiftOut])
async def get_shifts_history(
    limit: int = 50,
    offset: int = 0,
    employee_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get history of shifts. Admins see all, others see only their own."""
    query = select(Shift).options(joinedload(Shift.cashier))
    
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Shift.cashier_id == current_user.id)
    elif employee_id:
        query = query.where(Shift.cashier_id == employee_id)
        
    if start_date:
        start_dt = datetime.combine(start_date, time.min)
        query = query.where(Shift.opened_at >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, time.max)
        query = query.where(Shift.opened_at <= end_dt)
    
    result = await db.execute(
        query.order_by(Shift.opened_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()

@router.get("/shifts/active", response_model=Optional[ShiftOut])
async def get_active_shift(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if the current user has an active (open) shift and return it with totals."""
    from sqlalchemy import func
    from database import Sale
    
    result = await db.execute(
        select(Shift)
        .where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    shift = result.scalars().first()
    
    if shift:
        # Calculate totals from sales since the shift started
        sales_query = select(
            func.sum(Sale.cash_amount).label("total_cash"),
            func.sum(Sale.card_amount + Sale.transfer_amount).label("total_card"),
            func.sum(Sale.debt_amount).label("total_debt")
        ).where(
            Sale.cashier_id == current_user.id,
            Sale.created_at >= shift.opened_at,
            Sale.status == "completed"
        )
        
        sales_result = await db.execute(sales_query)
        totals = sales_result.one()
        
        shift.total_cash = totals.total_cash or 0
        shift.total_card = totals.total_card or 0
        shift.total_debt = totals.total_debt or 0
        
    return shift

@router.post("/shifts/open", response_model=ShiftOut)
async def open_shift(
    shift_data: ShiftOpen,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Open a new shift for the current cashier."""
    # Check if there's already an open shift
    active = await db.execute(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    if active.scalars().first():
        raise HTTPException(status_code=400, detail="Sizda allaqachon ochiq smena bor")

    db_shift = Shift(
        cashier_id=current_user.id,
        opening_balance=shift_data.opening_balance,
        status="open",
        opened_at=datetime.now()
    )
    db.add(db_shift)
    await db.commit()
    await db.refresh(db_shift)
    
    # Reload with cashier info
    result = await db.execute(select(Shift).where(Shift.id == db_shift.id).options(joinedload(Shift.cashier)))
    return result.scalars().first()

@router.post("/shifts/close", response_model=ShiftOut)
async def close_shift(
    shift_data: ShiftClose,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Close the currently active shift."""
    result = await db.execute(
        select(Shift)
        .where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    db_shift = result.scalars().first()
    
    if not db_shift:
        raise HTTPException(status_code=404, detail="Ochiq smena topilmadi")

    db_shift.closing_balance = shift_data.closing_balance
    db_shift.closed_at = datetime.now()
    db_shift.status = "closed"
    
    await db.commit()
    await db.refresh(db_shift)
    
    # Reload with cashier info
    result = await db.execute(select(Shift).where(Shift.id == db_shift.id).options(joinedload(Shift.cashier)))
    shift_final = result.scalars().first()

    # Send Notification to Admin
    try:
        from bot import bot
        admin_result = await db.execute(select(Employee).where(Employee.role == "admin", Employee.telegram_id.isnot(None)))
        admins = admin_result.scalars().all()
        
        if admins and shift_final:
            msg = (
                f"📊 <b>Smena Yakunlandi</b>\n"
                f"👤 Kassir: {shift_final.cashier.full_name}\n"
                f"📅 Yopildi: {shift_final.closed_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"💰 Yakuniy balans: {shift_final.closing_balance:,.0f} so'm"
            )
            for admin in admins:
                await bot.send_message(admin.telegram_id, msg)

    except Exception as e:
        print(f"Shift notification error: {e}")

    return shift_final
