
import asyncio
from database import SessionLocal, Employee
from sqlalchemy import select, update

async def activate():
    async with SessionLocal() as db:
        await db.execute(update(Employee).where(Employee.username == "miraziz").values(is_active=True))
        await db.commit()
        print("miraziz activated")

if __name__ == "__main__":
    asyncio.run(activate())
