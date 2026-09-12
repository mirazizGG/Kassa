from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload

from database import get_db, Client, Employee, Payment, Sale, SaleItem
from utils.timezone import utc_now
from schemas import ClientCreate, ClientOut, ClientUpdate
from core import get_current_user
from routers.audit import log_action

router = APIRouter(prefix="/crm", tags=["crm"])

# pos.py dagi CASH_METHODS bilan bir xil bo'lishi shart: smena kassasi aynan
# shu usullardagi to'lovlarni hisoblaydi.
CASH_PAYMENT_METHODS = ("cash", "naqd")

@router.get("/clients", response_model=List[ClientOut])
async def get_clients(current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
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
    now = utc_now()
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

    # Tarixga bog'langan mijozni ham o'chirib bo'lmaydi: sotuv va to'lov satrlari
    # yetim qolardi (SQLite tashqi kalitni majburlamaydi), PostgreSQL da esa bu
    # chaqiruv IntegrityError bilan 500 bo'lardi.
    linked_sales = await db.scalar(
        select(func.count(Sale.id)).where(Sale.client_id == client_id)
    )
    if linked_sales:
        raise HTTPException(
            status_code=409,
            detail=f"Bu mijozda {linked_sales} ta savdo tarixi bor — o'chirib bo'lmaydi.",
        )

    linked_payments = await db.scalar(
        select(func.count(Payment.id)).where(Payment.client_id == client_id)
    )
    if linked_payments:
        raise HTTPException(
            status_code=409,
            detail=f"Bu mijozda {linked_payments} ta to'lov tarixi bor — o'chirib bo'lmaydi.",
        )

    await db.delete(db_client)
    await log_action(db, current_user.id, "MIJOZ_OCHIRILDI", f"Mijoz o'chirildi: {db_client.name} (ID: {client_id})")
    await db.commit()
    return {"message": "Client deleted"}

from schemas import PaymentCreate
from database import Payment, Shift

@router.delete("/payments/{payment_id}")
async def void_payment(
    payment_id: int,
    reason: str = Query(min_length=3, max_length=300, description="Bekor qilish sababi"),
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Xato qabul qilingan qarz to'lovini bekor qilish.

    Ilgari to'lovni tuzatishning HECH QANDAY yo'li yo'q edi: noto'g'ri summa
    kiritilsa yoki to'lov boshqa mijozga yozilsa, mijoz balansi abadiy noto'g'ri
    qolardi. Endi to'lov o'chiriladi va balans ATOMIK ravishda qaytariladi.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Faqat admin to'lovni bekor qila oladi")

    payment = await db.scalar(select(Payment).where(Payment.id == payment_id))
    if not payment:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")

    client = await db.scalar(select(Client).where(Client.id == payment.client_id))

    # Balansni teskariga qaytaramiz: to'lov balansni oshirgan edi.
    await db.execute(
        update(Client)
        .where(Client.id == payment.client_id)
        .values(balance=Client.balance - payment.amount)
        .execution_options(synchronize_session=False)
    )

    note = ""
    if payment.shift_id:
        shift = await db.scalar(select(Shift).where(Shift.id == payment.shift_id))
        if shift and shift.status == "closed":
            note = f" DIQQAT: yopilgan smena #{shift.id} da qabul qilingan edi."

    await log_action(
        db, current_user.id, "TOLOV_BEKOR_QILINDI",
        f"To'lov #{payment_id} bekor qilindi: {payment.amount:,.0f} so'm, "
        f"mijoz {client.name if client else payment.client_id}. Sabab: {reason}.{note}"
    )
    await db.delete(payment)
    await db.commit()

    new_balance = None
    if client:
        await db.refresh(client)
        new_balance = client.balance

    return {
        "message": "To'lov bekor qilindi",
        "new_balance": new_balance,
        "warning": note.strip() or None,
    }


@router.post("/clients/{client_id}/pay")
async def pay_debt(
    client_id: int,
    payment_data: PaymentCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Qarzni yopish — pul bilan ishlash. Ombochida smena ham bo'lmaydi,
    # ya'ni uning "to'lovi" hech qaysi kassada ko'rinmasdi.
    if current_user.role not in ["admin", "manager", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    # 1. Mijozni tekshirish
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")

    # 2. Ochiq smenani topish
    shift_result = await db.execute(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    shift = shift_result.scalars().first()

    # NAQD to'lov uchun ochiq smena SHART.
    #
    # Ilgari smena topilmasa shift_id NULL bo'lib qolardi: pul jismonan
    # kassaga tushadi, lekin uni hech qaysi smena kutmaydi. Yopilishda
    # tushunarsiz ORTIQCHA chiqadi va kassirdan tushuntirish xati talab
    # qilinadi — ya'ni xarajatlar tuzatilgandan keyin ham kamomad/ortiqcha
    # signali yana shovqinga aylanardi. Bunday to'lovlarni ko'rsatadigan
    # birorta hisobot ham yo'q.
    if payment_data.payment_method in CASH_PAYMENT_METHODS and shift is None:
        raise HTTPException(
            status_code=409,
            detail="Naqd to'lovni qabul qilish uchun avval smenani oching",
        )

    # 3. Balansni ATOMIK yangilash (qarz kamayadi, ya'ni balans oshadi).
    #    "o'qi -> qo'sh -> yoz" bo'lsa, bir vaqtda kelgan ikki to'lovdan biri
    #    yo'qolib ketardi va mijoz qarzi kamaymay qolardi.
    await db.execute(
        update(Client)
        .where(Client.id == client_id)
        .values(balance=Client.balance + payment_data.amount)
        .execution_options(synchronize_session=False)
    )

    # Qarz to'liq yopilgan bo'lsa, muddatni ham TOZALAYMIZ. Aks holda bot
    # qarzi yo'q mijozga "muddati o'tgan" deb yozib turardi.
    await db.execute(
        update(Client)
        .where(Client.id == client_id, Client.balance >= 0)
        .values(debt_due_date=None)
        .execution_options(synchronize_session=False)
    )

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
