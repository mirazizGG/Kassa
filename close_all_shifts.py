import asyncio
from sqlalchemy import select, update
from database import SessionLocal, Shift

async def close_all_shifts():
    async with SessionLocal() as db:
        # Barcha ochiq smenalarni yopish
        await db.execute(
            update(Shift)
            .where(Shift.status == "open")
            .values(status="closed")
        )
        await db.commit()
        print("✅ Barcha ochiq smenalar yopildi!")

if __name__ == "__main__":
    asyncio.run(close_all_shifts())
