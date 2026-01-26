import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "sqlite+aiosqlite:///./market.db"

async def migrate():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        print("Migrating Expenses table...")
        try:
            # 1. Check if created_by column exists
            # SQLite doesn't have partial alter table well supported in older versions but let's try add column
            await conn.execute(text("ALTER TABLE expenses ADD COLUMN created_by INTEGER REFERENCES employees(id)"))
            print("Added 'created_by' column to 'expenses'.")
        except Exception as e:
            if "duplicate column name" in str(e):
                print("Column 'created_by' already exists.")
            elif "no such table" in str(e):
                print("Table 'expenses' does not exist yet. It will be created by main app.")
            else:
                print(f"Error adding column: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
