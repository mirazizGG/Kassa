import asyncio
from sqlalchemy import select
from database import SessionLocal, Shift

async def check_and_close_all():
    async with SessionLocal() as db:
        # Barcha ochiq smenalarni topish
        result = await db.execute(select(Shift).where(Shift.status == "open"))
        shifts = result.scalars().all()
        
        print(f"\n📊 Ochiq smenalar: {len(shifts)}")
        for shift in shifts:
            print(f"  - ID: {shift.id}, Kassir ID: {shift.cashier_id}, Boshlang'ich: {shift.opening_balance}")
        
        # Barchasini yopish
        if shifts:
            choice = input("\nBarcha ochiq smenalarni yopishni xohlaysizmi? (y/n): ")
            if choice.lower() == 'y':
                for shift in shifts:
                    shift.status = "closed"
                await db.commit()
                print("✅ Barcha smenalar yopildi!")

if __name__ == "__main__":
    asyncio.run(check_and_close_all())
