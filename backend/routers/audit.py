import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from typing import List, Optional

from database import get_db, AuditLog, Employee
from schemas import EmployeeOut # For reference if needed
from core import get_current_user
from utils.timezone import day_start_utc, day_end_utc, to_shop_time
from pydantic import BaseModel, ConfigDict
from datetime import datetime, date, time, timezone

router = APIRouter(prefix="/audit", tags=["audit"])


def local_day_boundary(value: date, is_end: bool) -> datetime:
    """Do'kon kunining chegarasi, naive-UTC.

    Ilgari bu modulda o'z vaqt mintaqasi qat'iy yozilgan edi, finance.py da
    esa yana bittasi. Mintaqa uch joyda takrorlangani uchun SHOP_TIMEZONE
    sozlamasi ularga ta'sir qilmasdi va "bugun" sahifalarda turlicha edi.
    """
    return day_end_utc(value) if is_end else day_start_utc(value)

class AuditLogOut(BaseModel):
    id: int
    user_id: int
    user: Optional[EmployeeOut] = None
    action: str
    details: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.get("/logs", response_model=List[AuditLogOut])
async def get_audit_logs(
    response: Response,
    limit: int = 100,
    offset: int = 0,
    employee_id: Optional[int] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Barcha tizim amallari tarixini ko'rish (Faqat Admin uchun)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
        
    query = select(AuditLog).options(joinedload(AuditLog.user))
    
    if employee_id:
        query = query.where(AuditLog.user_id == employee_id)
    if action:
        query = query.where(AuditLog.action == action)
    if search:
        query = query.where(AuditLog.details.icontains(search))
    if start_date:
        start_dt = local_day_boundary(start_date, is_end=False)
        query = query.where(AuditLog.created_at >= start_dt)
    if end_date:
        end_dt = local_day_boundary(end_date, is_end=True)
        query = query.where(AuditLog.created_at <= end_dt)
        
    # Jami sonni sarlavhada qaytaramiz. Ilgari frontend faqat birinchi 100 ta
    # yozuvni olib, o'sha sonni "hammasi" deb ko'rsatardi — ya'ni tekshiruv
    # paytida audit jurnali jimgina qirqilib, hech narsa qoldirilmagandek
    # ko'rinardi.
    total = await db.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    response.headers["X-Total-Count"] = str(total or 0)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    result = await db.execute(
        query.order_by(AuditLog.created_at.desc())
        .limit(max(1, min(limit, 500)))
        .offset(max(0, offset))
    )
    return result.scalars().all()


@router.get("/export-excel")
async def export_audit_excel(
    employee_id: Optional[int] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Audit jurnallarini Excel formatda yuklab olish"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse

    query = select(AuditLog).options(joinedload(AuditLog.user))
    
    if employee_id:
        query = query.where(AuditLog.user_id == employee_id)
    if action:
        query = query.where(AuditLog.action == action)
    if search:
        query = query.where(AuditLog.details.icontains(search))
    if start_date:
        start_dt = local_day_boundary(start_date, is_end=False)
        query = query.where(AuditLog.created_at >= start_dt)
    if end_date:
        end_dt = local_day_boundary(end_date, is_end=True)
        query = query.where(AuditLog.created_at <= end_dt)

    result = await db.execute(query.order_by(AuditLog.created_at.desc()))
    logs = result.scalars().all()

    data = []
    for log in logs:
        data.append({
            "ID": log.id,
            "Sana": to_shop_time(log.created_at).strftime("%d.%m.%Y %H:%M:%S"),
            "Xodim": csv_safe(log.user.username if log.user else f"ID: {log.user_id}"),
            "Amal": csv_safe(log.action),
            "Tafsilotlar": csv_safe(log.details)
        })

    # Excel yozish ALOHIDA OQIMDA. pandas + openpyxl sinxron ishlaydi va
    # to'g'ridan-to'g'ri async handlerda chaqirilsa butun event loop'ni ushlab
    # turadi: admin hisobotni yuklab olayotganda hamma kassa kutib qoladi.
    def _render() -> io.BytesIO:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(data).to_excel(writer, index=False, sheet_name="AuditLog")
        buffer.seek(0)
        return buffer

    output = await asyncio.to_thread(_render)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=audit_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )


def csv_safe(value):
    """Jadval faylida FORMULA sifatida bajarilib ketmasligi uchun tayyorlaydi.

    Excel va LibreOffice `=`, `+`, `-`, `@` bilan boshlanadigan katakni formula
    deb o'qiydi. Mijoz ismi Telegram orqali kiritiladi, mahsulot nomi esa
    xodim tomonidan — ya'ni bu matnlar ishonchsiz. Ilgari ular hisobotga
    o'zgarishsiz tushardi va faylni ochgan admin kompyuterida bajarilardi.
    """
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


async def log_action(db: AsyncSession, user_id: int, action: str, details: str):
    log = AuditLog(user_id=user_id, action=action, details=details)
    db.add(log)
    await db.flush()
