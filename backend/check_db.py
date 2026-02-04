
import asyncio
from database import SessionLocal, Employee
from sqlalchemy import select

async def check():
    async with SessionLocal() as db:
        result = await db.execute(select(Employee))
        employees = result.scalars().all()
        for e in employees:
            print(f"ID: {e.id}, User: {e.username}, Role: {e.role}, Active: {e.is_active}")

if __name__ == "__main__":
    asyncio.run(check())
