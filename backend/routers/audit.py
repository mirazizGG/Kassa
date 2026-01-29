from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Optional

from database import get_db, AuditLog, Employee
from schemas import EmployeeOut # For reference if needed
from core import get_current_user
from pydantic import BaseModel, ConfigDict
from datetime import datetime

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
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Barcha tizim amallari tarixini ko'rish (Faqat Admin uchun)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
        
    result = await db.execute(
        select(AuditLog)
        .options(joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()

async def log_action(db: AsyncSession, user_id: int, action: str, details: str):
    log = AuditLog(user_id=user_id, action=action, details=details)
    db.add(log)
    await db.flush()
