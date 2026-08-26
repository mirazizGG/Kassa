
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os

DATABASE_URL = "sqlite+aiosqlite:///c:/Users/u0068/Desktop/Kassa/backend/market.db"

async def test_db():
    print("Connecting to DB...")
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            print("Executing query...")
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            print(f"Result: {result.scalar()}")
            
            # Try to query employees
            print("Querying employees...")
            from database import Employee
            result = await session.execute(select(Employee).limit(1))
            user = result.scalars().first()
            print(f"Employee found: {user.username if user else 'None'}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db())
