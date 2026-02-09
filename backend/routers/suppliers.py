from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from sqlalchemy.orm import joinedload
from typing import List, Optional
import os
import uuid
from datetime import datetime

from database import get_db, Supplier, SupplyReceipt, SupplierPayment, Employee
from core import get_current_user
from pydantic import BaseModel

from routers.audit import log_action

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

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
    total_amount: float = Form(...),
    note: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    # Check if supplier exists
    res = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = res.scalars().first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Firma topilmadi")

    image_path = None
    if image:
        # Save image
        ext = os.path.splitext(image.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        save_dir = "uploads/invoices"
        os.makedirs(save_dir, exist_ok=True)
        image_path = os.path.join(save_dir, filename)
        
        with open(image_path, "wb") as f:
            f.write(await image.read())
        
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
    
    # Update supplier balance (Increase debt)
    supplier.balance += total_amount
    
    await log_action(db, current_user.id, "FIRMA_KIRIM", f"Firma: {supplier.name}. Summa: {total_amount} so'm. Izoh: {note or '-'}")
    
    await db.commit()
    return {"message": "Kirim muvaffaqiyatli saqlandi", "new_balance": supplier.balance}

@router.post("/payments")
async def add_payment(
    supplier_id: int = Form(...),
    amount: float = Form(...),
    payment_method: str = Form("cash"),
    note: Optional[str] = Form(None),
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
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
    
    # Update supplier balance (Decrease debt)
    supplier.balance -= amount
    
    await log_action(db, current_user.id, "FIRMA_TOLOV", f"Firma: {supplier.name}. Summa: {amount} so'm. Usul: {payment_method}. Izoh: {note or '-'}")
    
    await db.commit()
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
