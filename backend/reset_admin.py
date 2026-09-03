import asyncio
from sqlalchemy import select
from database import SessionLocal, Employee, init_db
from core import get_password_hash, PRIMARY_ADMIN_USERNAME

ADMIN_USERNAME = PRIMARY_ADMIN_USERNAME
ADMIN_PASSWORD = "8434"


async def reset_admin():
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
            print(f"Admin yangilanmoqda -> login: {ADMIN_USERNAME} / parol: {ADMIN_PASSWORD}")
            admin.username = ADMIN_USERNAME
            admin.hashed_password = get_password_hash(ADMIN_PASSWORD)
            admin.role = "admin"
            admin.permissions = "all"
            admin.is_active = True
            await db.commit()
            print("Tayyor.")
        else:
            print(f"Admin yaratilmoqda -> login: {ADMIN_USERNAME} / parol: {ADMIN_PASSWORD}")
            new_admin = Employee(
                username=ADMIN_USERNAME,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                role="admin",
                permissions="all",
            )
            db.add(new_admin)
            await db.commit()
            print("Tayyor.")


if __name__ == "__main__":
    asyncio.run(reset_admin())
