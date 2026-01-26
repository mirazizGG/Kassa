from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from database import get_db, Expense, Payment, Employee, Client
from schemas import ExpenseCreate, ExpenseOut, PaymentCreate
from core import get_current_user

router = APIRouter(prefix="/finance", tags=["finance"])

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
        created_at=datetime.utcnow()
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
        created_at=datetime.utcnow()
    )
    db.add(db_payment)
    
    # Update client balance
    result = await db.execute(select(Client).where(Client.id == payment.client_id))
    client = result.scalars().first()
    if client:
        client.balance += payment.amount
        
    await db.commit()
    return {"status": "success", "message": "To'lov qabul qilindi"}
