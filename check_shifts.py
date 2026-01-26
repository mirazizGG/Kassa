import asyncio
from sqlalchemy import select
from database import SessionLocal, Shift

async def check_shifts():
    async with SessionLocal() as db:
        result = await db.execute(select(Shift).where(Shift.status == "open"))
        shifts = result.scalars().all()
        
        print(f"\n📊 Ochiq smenalar: {len(shifts)}")
        for shift in shifts:
            print(f"  - ID: {shift.id}, Kassir ID: {shift.cashier_id}, Boshlang'ich: {shift.opening_balance}")

if __name__ == "__main__":
    asyncio.run(check_shifts())
