from main import get_password_hash
from database import SessionLocal, Employee
from sqlalchemy.future import select
import asyncio

async def reset_admin():
    async with SessionLocal() as db:
        result = await db.execute(select(Employee).where(Employee.username == "admin"))
        user = result.scalars().first()
        if user:
            user.hashed_password = get_password_hash("123")
            await db.commit()
            print("Admin password reset to '123'")
        else:
            # Create if not exists
            new_user = Employee(
                username="admin", 
                hashed_password=get_password_hash("123"),
                role="admin",
                permissions="all"
            )
            db.add(new_user)
            await db.commit()
            print("Admin user created with password '123'")

if __name__ == "__main__":
    asyncio.run(reset_admin())
