from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from sqlalchemy.orm import joinedload
from typing import List, Optional
import os
import uuid
from datetime import datetime

from database import get_db, Supplier, SupplyReceipt, SupplierPayment, Employee
from core import get_current_user, verify_password, verify_approver
from pydantic import BaseModel

from routers.audit import log_action
from utils.backup import UPLOAD_DIR

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

# Nakladnoy fayli uchun ruxsat etilgan kengaytmalar va hajm chegarasi.
ALLOWED_INVOICE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
MAX_INVOICE_BYTES = 10 * 1024 * 1024  # 10 MB

# --- Schemas ---
class SupplierBase(BaseModel):
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierOut(SupplierBase):
    id: int
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True

class ReceiptOut(BaseModel):
    id: int
    supplier_id: int
    total_amount: float
    invoice_image: Optional[str] = None
    date: datetime
    note: Optional[str] = None

    class Config:
        from_attributes = True

class PaymentOut(BaseModel):
    id: int
    supplier_id: int
    amount: float
    payment_method: str
    date: datetime
    note: Optional[str] = None

    class Config:
        from_attributes = True

# --- Endpoints ---

async def verify_confirming_employee(db: AsyncSession, requester: Employee,
                                     username: str, password: str) -> Employee:
    """Firma bilan pul harakatini TASDIQLOVCHI xodim.

    Ilgari bu funksiya na rolni, na tasdiqlovchi BOSHQA odam ekanini
    tekshirardi: omborchi o'z login-parolini kiritib, o'z amalini o'zi
    "tasdiqlab" qo'yardi. Ikki kishilik nazorat umuman ishlamasdi.
    """
    if username == requester.username:
        raise HTTPException(
            status_code=403,
            detail="Amalni o'zingiz tasdiqlay olmaysiz — menejer yoki admin tasdig'i kerak",
        )
    return await verify_approver(db, requester, username, password)

@router.get("/", response_model=List[SupplierOut])
async def get_suppliers(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    result = await db.execute(select(Supplier).order_by(Supplier.name))
    return result.scalars().all()

@router.post("/", response_model=SupplierOut)
async def create_supplier(
    supplier: SupplierCreate, 
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    db_supplier = Supplier(**supplier.model_dump())
    db.add(db_supplier)
    await db.commit()
    await db.refresh(db_supplier)
    
    await log_action(db, current_user.id, "YANGI_FIRMA", f"Firma qo'shildi: {db_supplier.name} (ID: {db_supplier.id})")
    await db.commit() # Commit again to save log
    
    return db_supplier

@router.post("/receipts")
async def add_receipt(
    supplier_id: int = Form(...),
    # Manfiy yoki NaN summa firma balansini qaytarib bo'lmaydigan darajada
    # buzardi (NaN butun "Firmalar" sahifasini 500 ga olib borardi). Bu — pul
    # bilan ishlaydigan yagona joy edi, unga son cheklovlari yetib bormagan.
    total_amount: float = Form(..., gt=0, allow_inf_nan=False),
    note: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    confirm_username: str = Form(...),
    confirm_password: str = Form(...),
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    confirming_employee = await verify_confirming_employee(db, current_user, confirm_username, confirm_password)
    # Check if supplier exists
    res = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = res.scalars().first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Firma topilmadi")

    image_path = None
    if image:
        # Kengaytmani foydalanuvchi bergan fayl nomidan olardik va uni
        # o'zgartirmasdan saqlardik. /uploads papkasi ilovaning O'Z domenidan
        # beriladi, shuning uchun ".html" yuklab, keyin o'sha havolani ochgan
        # xodimning tokenini o'g'irlash mumkin edi. Endi faqat rasm va PDF.
        ext = os.path.splitext(image.filename or "")[1].lower()
        if ext not in ALLOWED_INVOICE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Nakladnoy uchun faqat rasm yoki PDF yuklash mumkin "
                    f"({', '.join(sorted(ALLOWED_INVOICE_EXTENSIONS))})"
                ),
            )

        payload = await image.read()
        if len(payload) > MAX_INVOICE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Fayl juda katta (maksimum {MAX_INVOICE_BYTES // (1024 * 1024)} MB)",
            )

        filename = f"{uuid.uuid4()}{ext}"
        save_dir = UPLOAD_DIR / "invoices"
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / filename).write_bytes(payload)

        # Use URL path for DB
        image_path = f"/uploads/invoices/{filename}"

    # Create receipt
    receipt = SupplyReceipt(
        supplier_id=supplier_id,
        total_amount=total_amount,
        invoice_image=image_path,
        note=note
    )
    db.add(receipt)
    
    # Firma balansini ATOMIK oshiramiz (qarzimiz ortadi).
    await db.execute(
        update(Supplier)
        .where(Supplier.id == supplier_id)
        .values(balance=Supplier.balance + total_amount)
        .execution_options(synchronize_session=False)
    )
    
    await log_action(db, current_user.id, "FIRMA_KIRIM", f"Firma: {supplier.name}. Summa: {total_amount} so'm. Izoh: {note or '-'}. Tasdiqladi: @{confirming_employee.username}")
    
    await db.commit()
    await db.refresh(supplier)
    return {"message": "Kirim muvaffaqiyatli saqlandi", "new_balance": supplier.balance}

@router.post("/payments")
async def add_payment(
    supplier_id: int = Form(...),
    amount: float = Form(..., gt=0, allow_inf_nan=False),
    payment_method: str = Form("cash"),
    note: Optional[str] = Form(None),
    confirm_username: str = Form(...),
    confirm_password: str = Form(...),
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    confirming_employee = await verify_confirming_employee(db, current_user, confirm_username, confirm_password)
    res = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = res.scalars().first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Firma topilmadi")

    payment = SupplierPayment(
        supplier_id=supplier_id,
        amount=amount,
        payment_method=payment_method,
        note=note
    )
    db.add(payment)
    
    # Firma balansini ATOMIK kamaytiramiz (qarzimiz kamayadi).
    await db.execute(
        update(Supplier)
        .where(Supplier.id == supplier_id)
        .values(balance=Supplier.balance - amount)
        .execution_options(synchronize_session=False)
    )
    
    await log_action(db, current_user.id, "FIRMA_TOLOV", f"Firma: {supplier.name}. Summa: {amount} so'm. Usul: {payment_method}. Izoh: {note or '-'}. Tasdiqladi: @{confirming_employee.username}")
    
    await db.commit()
    await db.refresh(supplier)
    return {"message": "To'lov muvaffaqiyatli saqlandi", "new_balance": supplier.balance}

@router.get("/{supplier_id}/history")
async def get_supplier_history(
    supplier_id: int, 
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    # Get receipts
    receipts_res = await db.execute(
        select(SupplyReceipt).where(SupplyReceipt.supplier_id == supplier_id).order_by(desc(SupplyReceipt.date))
    )
    receipts = receipts_res.scalars().all()

    # Get payments
    payments_res = await db.execute(
        select(SupplierPayment).where(SupplierPayment.supplier_id == supplier_id).order_by(desc(SupplierPayment.date))
    )
    payments = payments_res.scalars().all()

    # Merge and sort
    history = []
    for r in receipts:
        history.append({
            "type": "receipt",
            "id": r.id,
            "amount": r.total_amount,
            "date": r.date,
            "image": r.invoice_image,
            "note": r.note
        })
    for p in payments:
        history.append({
            "type": "payment",
            "id": p.id,
            "amount": p.amount,
            "date": p.date,
            "method": p.payment_method,
            "note": p.note
        })
    
    history.sort(key=lambda x: x["date"], reverse=True)
    return history
