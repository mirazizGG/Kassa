from fastapi import FastAPI, Response  
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from typing import Optional
import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import init_db, engine, Base, SessionLocal, Employee
from core import get_password_hash, limiter
from bot import bot, dp, check_debts
from routers import auth, inventory, pos, crm, finance, tasks, sales, audit, settings, suppliers
from fastapi.staticfiles import StaticFiles

# Configure Rate Limiting - MOVED TO core.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Startup: Initializing DB...")
    await init_db()
    
    # Start Scheduler for background tasks
    print("Startup: Starting scheduler...")
    scheduler = AsyncIOScheduler()
    # Har kuni ertalab soat 9:00 da qarzni tekshirish
    scheduler.add_job(check_debts, 'cron', hour=9, minute=0, args=[bot])
    # Har soatda bazani backup qilish (ixtiyoriy)
    # scheduler.add_job(create_backup, 'interval', hours=1)
    scheduler.start()
    
    # Start Bot tasks
    print("Startup: Starting bot polling...")
    bot_task = asyncio.create_task(dp.start_polling(bot))

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
        print("Shutdown: Stopping scheduler and bot...")
        scheduler.shutdown()
        bot_task.cancel()
        
        await bot.session.close()
        
        try:
            await asyncio.wait([bot_task], timeout=2.0)
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        print("Shutdown: Complete.")

app = FastAPI(lifespan=lifespan, title="Kassa API", version="2.0.0")

# Add Rate Limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

# Configure CORS
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex="https://.*\.vercel\.app", # Allow all Vercel subdomains
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