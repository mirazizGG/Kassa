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
    
    if current_user.role != "admin":
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
