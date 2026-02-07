import asyncio
import os
from sqlalchemy import text
from database import engine, Base

async def update_db():
    print("Database yangilanmoqda...")
    async with engine.begin() as conn:
        # 1. Create new tables (StockMove, etc.)
        await conn.run_sync(Base.metadata.create_all)
        
        # 2. Add missing columns to existing tables (SQLite doesn't support ADD COLUMN if exists check easily in one go)
        # We'll try to add them and catch errors if they already exist
        
        new_columns = [
            ("clients", "bonus_balance", "FLOAT DEFAULT 0"),
            ("sales", "bonus_earned", "FLOAT DEFAULT 0"),
            ("sales", "bonus_spent", "FLOAT DEFAULT 0"),
            ("store_settings", "bonus_percentage", "FLOAT DEFAULT 1.0"),
            ("store_settings", "debt_reminder_days", "INTEGER DEFAULT 3")
        ]
        
        for table, col, col_type in new_columns:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                print(f"Qo'shildi: {table}.{col}")
            except Exception as e:
                # Column might already exist
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"Mavjud: {table}.{col}")
                else:
                    print(f"Xato ({table}.{col}): {e}")
                    
    print("Baza muvaffaqiyatli yangilandi.")

if __name__ == "__main__":
    asyncio.run(update_db())
