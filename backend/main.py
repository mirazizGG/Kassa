from fastapi import FastAPI, Response  
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from typing import Optional
import os

from database import init_db, engine, Base, SessionLocal, Employee
from core import get_password_hash
from bot import bot, dp, check_debts
from routers import auth, inventory, pos, crm, finance, tasks, sales, audit, settings, suppliers
from fastapi.staticfiles import StaticFiles

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Startup: Initializing DB...")
    await init_db()
    
    # Start Bot tasks and track them
    print("Startup: Starting background tasks...")
    bot_task = asyncio.create_task(dp.start_polling(bot))
    debt_task = asyncio.create_task(check_debts(bot))

    # Create admin if not exists
    async with SessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Employee).where(Employee.username == "admin"))
        admin = result.scalars().first()
        if not admin:
            print("Admin yaratilmoqda: admin / 123")
            new_admin = Employee(
                username="admin",
                hashed_password=get_password_hash("123"),
                role="admin",
                permissions="all"
            )
            db.add(new_admin)
            await db.commit()
    
    print("Startup: Complete. Application running.")
    try:
        yield
    finally:
        print("Shutdown: Stopping background tasks...")
        # Stop polling explicitly if possible, or just cancel tasks
        bot_task.cancel()
        debt_task.cancel()
        
        # Close bot session for clean exit
        await bot.session.close()
        
        try:
            # Wait for tasks to finish with a short timeout
            await asyncio.wait([bot_task, debt_task], timeout=2.0)
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        print("Shutdown: Complete.")
    print("Shutdown: Application stopping...")

app = FastAPI(lifespan=lifespan, title="Kassa API", version="2.0.0")

from fastapi import Request
from fastapi.responses import JSONResponse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Ichki server xatoligi yuz berdi. Iltimos, administratorga murojaat qiling."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","), # Change to specific origins in production
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
app.include_router(tasks.router)
app.include_router(sales.router)
app.include_router(audit.router)
app.include_router(settings.router)
app.include_router(suppliers.router)

# Static files for invoices
if not os.path.exists("uploads"):
    os.makedirs("uploads")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/")
async def root():
    return {"message": "Kassa API is running", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)