"""Bazani tayyorlash: sxema + birinchi admin.

Nima uchun alohida skript
-------------------------
Oddiy ishga tushirishda buni `main.py` ning lifespan bloki bajaradi. Ammo
cPanel/Passenger ostida ilova `a2wsgi` orqali ishlaydi va u lifespan
hodisalarini CHAQIRMAYDI — ya'ni jadval ham yaratilmaydi, admin ham
qo'shilmaydi. Shuning uchun bu qadam qo'lda, bir marta bajariladi.

Ishlatish (backend/ papkasidan):

    /opt/alt/python312/bin/python3 setup_db.py

Skript idempotent: qayta ishlatish xavfsiz. Sxema yangilanganda (yangi ustun
qo'shilganda) ham shuni qayta ishlatish kerak.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from core import (  # noqa: E402
    APP_ENV,
    DEV_ADMIN_PASSWORD,
    PRIMARY_ADMIN_PASSWORD,
    PRIMARY_ADMIN_USERNAME,
    get_password_hash,
)
from database import Employee, SessionLocal, engine, init_db  # noqa: E402


async def main() -> int:
    print("Sxema tayyorlanmoqda...")
    await init_db()
    print("  jadval va indekslar joyida.")

    async with SessionLocal() as db:
        admin = (
            await db.execute(select(Employee).where(Employee.role == "admin"))
        ).scalars().first()

        if admin:
            print(f"  admin allaqachon bor: {admin.username} — tegilmadi.")
        else:
            password = PRIMARY_ADMIN_PASSWORD
            if not password:
                if APP_ENV == "production":
                    print(
                        "XATO: PRIMARY_ADMIN_PASSWORD o'rnatilmagan va bazada admin yo'q.\n"
                        "backend/.env ga  PRIMARY_ADMIN_PASSWORD=<kuchli-parol>  qo'shing."
                    )
                    await engine.dispose()
                    return 1
                password = DEV_ADMIN_PASSWORD

            db.add(Employee(
                username=PRIMARY_ADMIN_USERNAME,
                hashed_password=get_password_hash(password),
                role="admin",
                permissions="all",
            ))
            try:
                await db.commit()
                print(f"  admin yaratildi: {PRIMARY_ADMIN_USERNAME}")
            except IntegrityError:
                await db.rollback()
                print("  admin boshqa jarayon tomonidan yaratilgan.")

    await engine.dispose()
    print("Tayyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
