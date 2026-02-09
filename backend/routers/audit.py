from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Optional

from database import get_db, AuditLog, Employee
from schemas import EmployeeOut # For reference if needed
from core import get_current_user
from pydantic import BaseModel, ConfigDict
from datetime import datetime, date, time

router = APIRouter(prefix="/audit", tags=["audit"])

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
        query = query.where(AuditLog.details.contains(search))
    if start_date:
        start_dt = datetime.combine(start_date, time.min)
        query = query.where(AuditLog.created_at >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, time.max)
        query = query.where(AuditLog.created_at <= end_dt)
        
    result = await db.execute(
        query.order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
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
        query = query.where(AuditLog.details.contains(search))
    if start_date:
        start_dt = datetime.combine(start_date, time.min)
        query = query.where(AuditLog.created_at >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, time.max)
        query = query.where(AuditLog.created_at <= end_dt)

    result = await db.execute(query.order_by(AuditLog.created_at.desc()))
    logs = result.scalars().all()

    data = []
    for log in logs:
        data.append({
            "ID": log.id,
            "Sana": log.created_at.strftime("%d.%m.%Y %H:%M:%S"),
            "Xodim": log.user.username if log.user else f"ID: {log.user_id}",
            "Amal": log.action,
            "Tafsilotlar": log.details
        })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='AuditLog')

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=audit_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )


async def log_action(db: AsyncSession, user_id: int, action: str, details: str):
    log = AuditLog(user_id=user_id, action=action, details=details)
    db.add(log)
    await db.flush()
