import asyncio
from sqlalchemy import select
from database import SessionLocal, Employee, init_db
from core import get_password_hash

async def reset_admin():
    await init_db()
    async with SessionLocal() as db:
        result = await db.execute(select(Employee).where(Employee.username == "admin"))
        admin = result.scalars().first()
        if admin:
            print("Resetting admin password to 123...")
            admin.hashed_password = get_password_hash("123")
            await db.commit()
            print("Done.")
        else:
            print("Creating admin with password 123...")
            new_admin = Employee(
                username="admin",
                hashed_password=get_password_hash("123"),
                role="admin",
                permissions="all"
            )
            db.add(new_admin)
            await db.commit()
            print("Done.")

if __name__ == "__main__":
    asyncio.run(reset_admin())
