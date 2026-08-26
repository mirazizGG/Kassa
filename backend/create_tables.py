import asyncio
from database import engine, Base
import routers.settings # Force import to register models if they were in routers (not the case here)
import database

async def create_tables():
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Done.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_tables())
