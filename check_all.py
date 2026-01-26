import asyncio
from sqlalchemy import select
from database import SessionLocal, Shift, Employee

async def check_status():
    async with SessionLocal() as db:
        # Barcha foydalanuvchilar
        emp_result = await db.execute(select(Employee))
        employees = emp_result.scalars().all()
        
        print("\n👥 Barcha foydalanuvchilar:")
        for emp in employees:
            print(f"  ID: {emp.id}, Login: {emp.username}, Rol: {emp.role}")
        
        # Barcha smenalar
        shift_result = await db.execute(select(Shift))
        shifts = shift_result.scalars().all()
        
        print(f"\n📊 Barcha smenalar ({len(shifts)} ta):")
        for shift in shifts:
            print(f"  ID: {shift.id}, Kassir ID: {shift.cashier_id}, Status: {shift.status}, Boshlang'ich: {shift.opening_balance}")

if __name__ == "__main__":
    asyncio.run(check_status())
