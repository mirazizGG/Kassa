"""
Check all database data counts
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from database import (
    DATABASE_URL, Employee, Category, Product, Client,
    Sale, SaleItem, Expense, Shift, Task, Payment, Supply
)

async def check_all_data():
    """Check counts of all tables"""
    print(f"DEBUG: Using DATABASE_URL = {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Check all tables
        tables = [
            ("Employees", Employee),
            ("Categories", Category),
            ("Products", Product),
            ("Clients", Client),
            ("Sales", Sale),
            ("SaleItems", SaleItem),
            ("Expenses", Expense),
            ("Shifts", Shift),
            ("Tasks", Task),
            ("Payments", Payment),
            ("Supplies", Supply)
        ]

        print("\n" + "="*50)
        print("DATABASE DATA COUNTS")
        print("="*50)

        for table_name, model in tables:
            result = await db.execute(select(func.count(model.id)))
            count = result.scalar()
            print(f"{table_name:20} : {count}")

        print("="*50)
        print("\nDetailed Sales Data:")
        print("-"*50)
        result = await db.execute(select(Sale))
        sales = result.scalars().all()
        if sales:
            for sale in sales:
                print(f"Sale ID: {sale.id}, Amount: {sale.total_amount}, Date: {sale.created_at}")
        else:
            print("No sales found")

        print("\nDetailed Expense Data:")
        print("-"*50)
        result = await db.execute(select(Expense))
        expenses = result.scalars().all()
        if expenses:
            for expense in expenses:
                print(f"Expense ID: {expense.id}, Amount: {expense.amount}, Reason: {expense.reason}")
        else:
            print("No expenses found")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_all_data())
