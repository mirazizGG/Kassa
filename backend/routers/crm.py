from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from database import get_db, Client, Employee
from schemas import ClientCreate, ClientOut
from core import get_current_user
from routers.audit import log_action

router = APIRouter(prefix="/crm", tags=["crm"])

@router.get("/clients", response_model=List[ClientOut])
async def get_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client))
    return result.scalars().all()

@router.post("/clients", response_model=ClientOut)
async def create_client(
    client: ClientCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_client = Client(**client.model_dump())
    db.add(db_client)
    
    await log_action(db, current_user.id, "YANGI_MIJOZ", f"Mijoz qo'shildi: {db_client.name} (Tel: {db_client.phone or '-'})")
    
    await db.commit()
    await db.refresh(db_client)
    return db_client

@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

from schemas import PaymentCreate
from database import Payment, Shift

@router.post("/clients/{client_id}/pay")
async def pay_debt(
    client_id: int,
    payment_data: PaymentCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Mijozni tekshirish
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")

    # 2. Ochiq smenani topish (ixtiyoriy)
    shift_result = await db.execute(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    shift = shift_result.scalars().first()

    # 3. Balansni yangilash (Qarz kamayadi, ya'ni balans oshadi)
    client.balance += payment_data.amount

    # 4. To'lov tarixini yaratish
    db_payment = Payment(
        client_id=client_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        note=payment_data.note,
        created_by=current_user.id,
        shift_id=shift.id if shift else None
    )
    
    db.add(db_payment)
    
    await log_action(db, current_user.id, "MIJOZ_TOLOV", f"Mijoz: {client.name}. Summa: {payment_data.amount:,.0f} so'm. Usul: {payment_data.payment_method}")
    
    await db.commit()
    await db.refresh(client)
    
    return {"message": "To'lov qabul qilindi", "new_balance": client.balance}
