from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload

from database import get_db, Client, Employee, Payment, Sale, SaleItem
from schemas import ClientCreate, ClientOut, ClientUpdate
from core import get_current_user
from routers.audit import log_action

router = APIRouter(prefix="/crm", tags=["crm"])

@router.get("/clients", response_model=List[ClientOut])
async def get_clients(current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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

@router.get("/clients/debts")
async def get_debtors(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return debtors with a UI-ready due-date status."""
    result = await db.execute(select(Client).where(Client.balance < 0).order_by(Client.debt_due_date.asc()))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    debtors = []

    for client in result.scalars().all():
        days_until_due = (client.debt_due_date.date() - now.date()).days if client.debt_due_date else None
        status = "no_due_date"
        if days_until_due is not None:
            status = "overdue" if days_until_due < 0 else "due_today" if days_until_due == 0 else "due_soon" if days_until_due <= 3 else "upcoming"

        debtors.append({
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
            "debt_amount": abs(client.balance),
            "due_date": client.debt_due_date,
            "days_until_due": days_until_due,
            "status": status,
        })

    return debtors


@router.get("/clients/{client_id}/history")
async def get_client_history(
    client_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a customer's credit sales and debt-payment history."""
    client_result = await db.execute(select(Client).where(Client.id == client_id))
    client = client_result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")

    sales_result = await db.execute(
        select(Sale)
        .options(joinedload(Sale.cashier), joinedload(Sale.items).joinedload(SaleItem.product))
        .where(Sale.client_id == client_id)
        .order_by(Sale.created_at.desc())
    )
    payments_result = await db.execute(
        select(Payment)
        .options(joinedload(Payment.employee))
        .where(Payment.client_id == client_id)
        .order_by(Payment.created_at.desc())
    )

    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "balance": client.balance,
            "debt_due_date": client.debt_due_date,
        },
        "sales": [
            {
                "id": sale.id,
                "created_at": sale.created_at,
                "total_amount": sale.total_amount,
                "debt_amount": sale.debt_amount,
                "status": sale.status,
                "cashier": sale.cashier.username if sale.cashier else None,
                "items": [
                    {
                        "name": item.product.name if item.product else "Mahsulot o'chirilgan",
                        "quantity": item.quantity,
                        "price": item.price,
                    }
                    for item in sale.items
                ],
            }
            for sale in sales_result.unique().scalars().all()
        ],
        "payments": [
            {
                "id": payment.id,
                "created_at": payment.created_at,
                "amount": payment.amount,
                "payment_method": payment.payment_method,
                "note": payment.note,
                "employee": payment.employee.username if payment.employee else None,
            }
            for payment in payments_result.unique().scalars().all()
        ],
    }

@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.patch("/clients/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
        
    result = await db.execute(select(Client).where(Client.id == client_id))
    db_client = result.scalars().first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    update_data = client_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_client, key, value)
        
    await log_action(db, current_user.id, "MIJOZ_TAHRIR", f"Mijoz tahrirlandi: {db_client.name} (ID: {client_id})")
    
    await db.commit()
    await db.refresh(db_client)
    return db_client

@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Faqat admin mijozlarni o'chira oladi")
        
    result = await db.execute(select(Client).where(Client.id == client_id))
    db_client = result.scalars().first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    if db_client.balance != 0:
        raise HTTPException(status_code=400, detail="Qarzi yoki balansi bor mijozni o'chirib bo'lmaydi")
        
    await db.delete(db_client)
    await log_action(db, current_user.id, "MIJOZ_OCHIRILDI", f"Mijoz o'chirildi: {db_client.name} (ID: {client_id})")
    await db.commit()
    return {"message": "Client deleted"}

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
