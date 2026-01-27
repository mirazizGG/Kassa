"""
Database Clearing Script
Drops all tables and recreates them for a fresh start
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from database import Base, DATABASE_URL

async def clear_database():
    """Drop all tables and recreate them"""
    print("Starting database clearing process...")

    # Create engine
    engine = create_async_engine(DATABASE_URL, echo=True)

    # Drop all tables
    print("\nDropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("All tables dropped successfully")

    # Recreate all tables
    print("\nRecreating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables recreated successfully")

    # Close engine
    await engine.dispose()

    print("\nDatabase cleared successfully!")
    print("Default admin user will be created when you start the backend server")
    print("   Username: admin")
    print("   Password: 123")

if __name__ == "__main__":
    asyncio.run(clear_database())
