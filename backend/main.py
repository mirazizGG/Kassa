from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from typing import Optional

from database import init_db, engine, Base, SessionLocal, Employee
from core import get_password_hash
from bot import bot, dp, check_debts
from routers import auth, inventory, pos, crm, finance

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start Bot Polling in Background
    asyncio.create_task(dp.start_polling(bot))
    # Start Debt Check Loop
    asyncio.create_task(check_debts(bot))

    # Admin creation if not exists
    async with SessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Employee).where(Employee.username == "admin"))
        admin = result.scalars().first()
        if not admin:
            print("Admin yaratilmoqda: admin / admin123")
            new_admin = Employee(
                username="admin",
                hashed_password=get_password_hash("123"),
                role="admin",
                permissions="all"
            )
            db.add(new_admin)
            await db.commit()
    yield

app = FastAPI(lifespan=lifespan, title="Kassa API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(pos.router)
app.include_router(crm.router)
app.include_router(finance.router)

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/")
async def root():
    return {"message": "Kassa API is running", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)