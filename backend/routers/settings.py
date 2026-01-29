from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db, StoreSetting, Employee
from schemas import StoreSettingBase, StoreSettingOut
from core import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=StoreSettingOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Do'kon sozlamalarini olish. Agar bo'sh bo'lsa, default yaratadi."""
    result = await db.execute(select(StoreSetting))
    settings = result.scalars().first()
    
    if not settings:
        settings = StoreSetting(name="Mening Do'konim")
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        
    return settings

@router.put("", response_model=StoreSettingOut)
async def update_settings(
    data: StoreSettingBase,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Do'kon sozlamalarini yangilash (Faqat Admin uchun)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
        
    result = await db.execute(select(StoreSetting))
    settings = result.scalars().first()
    
    if not settings:
        settings = StoreSetting()
        db.add(settings)
    
    for key, value in data.model_dump().items():
        setattr(settings, key, value)
        
    await db.commit()
    await db.refresh(settings)
    return settings
