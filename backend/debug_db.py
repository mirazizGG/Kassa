import asyncio
from sqlalchemy import select
from database import engine, StoreSetting, SessionLocal

async def check():
    print("Connecting to DB...")
    try:
        async with SessionLocal() as db:
            print("Executing select...")
            result = await db.execute(select(StoreSetting))
            settings = result.scalars().first()
            print(f"Result: {settings}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
