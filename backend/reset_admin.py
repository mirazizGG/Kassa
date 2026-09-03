"""Bosh admin (miraziz) parolini serverda tiklash / kuchaytirish.

Ishlatish (backend/ papkasidan):

    python reset_admin.py                  -> yangi parolni so'raydi
    python reset_admin.py "YangiKuchliParol"  -> parolni to'g'ridan-to'g'ri beradi

Parolni bermasangiz va hech narsa kiritmasangiz — "8038434" qo'yiladi.
Bu skript parolni hech qayerga yozib qo'ymaydi (faqat bazadagi hash yangilanadi).
"""

import asyncio
import sys
from sqlalchemy import select
from database import SessionLocal, Employee, init_db
from core import get_password_hash, PRIMARY_ADMIN_USERNAME

ADMIN_USERNAME = PRIMARY_ADMIN_USERNAME
DEFAULT_PASSWORD = "8038434"


def _get_password() -> str:
    # 1) buyruq qatoridan
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    # 2) so'rab olamiz
    try:
        entered = input(f"Yangi parol ('{ADMIN_USERNAME}' uchun, bo'sh = '{DEFAULT_PASSWORD}'): ").strip()
    except EOFError:
        entered = ""
    return entered or DEFAULT_PASSWORD


async def reset_admin(password: str):
    await init_db()
    async with SessionLocal() as db:
        # Avval nomi bo'yicha, keyin har qanday admin rolidagi hisobni topamiz
        result = await db.execute(select(Employee).where(Employee.username == ADMIN_USERNAME))
        admin = result.scalars().first()
        if not admin:
            result = await db.execute(
                select(Employee).where(Employee.role == "admin").order_by(Employee.id)
            )
            admin = result.scalars().first()

        if admin:
            admin.username = ADMIN_USERNAME
            admin.hashed_password = get_password_hash(password)
            admin.role = "admin"
            admin.permissions = "all"
            admin.is_active = True
            await db.commit()
            print(f"Tayyor. Login: {ADMIN_USERNAME} — parol yangilandi.")
        else:
            new_admin = Employee(
                username=ADMIN_USERNAME,
                hashed_password=get_password_hash(password),
                role="admin",
                permissions="all",
            )
            db.add(new_admin)
            await db.commit()
            print(f"Tayyor. Yangi admin yaratildi. Login: {ADMIN_USERNAME}")


if __name__ == "__main__":
    asyncio.run(reset_admin(_get_password()))
