import asyncio
from sqlalchemy import select
from database import SessionLocal, Employee
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

async def list_users():
    async with SessionLocal() as db:
        result = await db.execute(select(Employee))
        users = result.scalars().all()
        print(f"Total users in DB: {len(users)}")
        for u in users:
            print(f"- ID: {u.id}, Login: {u.username}, Role: {u.role}")

if __name__ == "__main__":
    asyncio.run(list_users())
