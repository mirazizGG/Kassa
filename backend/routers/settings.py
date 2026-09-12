import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db, StoreSetting, Employee
from schemas import StoreSettingBase, StoreSettingOut
from core import get_current_user

from core import get_current_user
from routers.audit import log_action

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=StoreSettingOut)
async def get_settings(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Settingsni barcha xodimlar o'qiy olishi kerak (masalan, low_stock_threshold uchun)
    # Ruxsat tekshiruvi olib tashlandi, chunki get_current_user allaqachon loginni tekshiradi.
    """Do'kon sozlamalarini olish. Agar bo'sh bo'lsa, default yaratadi.

    `.order_by(id).limit(1)` shart: StoreSetting yagona satr bo'lishi kerak,
    lekin buni faqat kelishuv ushlab turadi. Tartibsiz `.first()` da PostgreSQL
    satrlar ketma-ketligini KAFOLATLAMAYDI — agar ikkinchi satr paydo bo'lsa,
    sozlamalar so'rovdan so'rovga "sakrab" turardi.
    """
    result = await db.execute(select(StoreSetting).order_by(StoreSetting.id).limit(1))
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
        
    result = await db.execute(select(StoreSetting).order_by(StoreSetting.id).limit(1))
    settings = result.scalars().first()
    
    if not settings:
        settings = StoreSetting()
        db.add(settings)
    
    for key, value in data.model_dump().items():
        setattr(settings, key, value)
        
    await log_action(db, current_user.id, "SOZLAMALAR_OZGARDI", f"Do'kon sozlamalari yangilandi: {settings.name}")
        
    await db.commit()
    await db.refresh(settings)
    return settings

@router.post("/backup")
async def manual_backup(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Qo'lda zahira nusxasi: lokal + bulut papka + GitHub + Telegram.

    Admin, menejer va omborchi bosishi mumkin (kassir omborga kira olmaydi).
    """
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    from utils.backup import run_full_backup
    try:
        from bot import bot as tg_bot
    except Exception:
        tg_bot = None

    try:
        res = await run_full_backup(tg_bot)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Zahira olishda xatolik: {exc}")

    parts = ["Lokal ✓"]
    if res.get("mirror") is True:
        parts.append("Bulut papka ✓")
    elif res.get("mirror") is False:
        parts.append("Bulut papka ✗")
    if res.get("github") is True:
        parts.append("GitHub ✓")
    elif res.get("github") is False:
        parts.append("GitHub ✗")
    if res.get("telegram") is True:
        parts.append("Telegram ✓")
    elif res.get("telegram") is False:
        parts.append("Telegram ✗")

    filename = os.path.basename(res["local"])
    await log_action(db, current_user.id, "ZAHIRA_NUSXA", f"Qo'lda zahira: {filename}. Manzillar: {', '.join(parts)}")
    await db.commit()

    return {
        "status": "success",
        "message": "Zahira nusxasi olindi — " + ", ".join(parts),
        "filename": filename,
        "detail": res,
    }
