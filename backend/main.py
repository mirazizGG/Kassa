from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import asyncio
from typing import Optional
import os
import logging

# .env ni eng boshida yuklaymiz — routerlar/util modullari import paytida
# os.getenv() ni ishlatadi, shuning uchun import tartibiga bog'liq bo'lmasin.
from dotenv import load_dotenv
load_dotenv()
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import init_db, engine, Base, SessionLocal, Employee
from core import (
    get_password_hash, limiter, APP_ENV,
    PRIMARY_ADMIN_USERNAME, PRIMARY_ADMIN_PASSWORD, DEV_ADMIN_PASSWORD,
)
from bot import bot, dp, check_debts
from routers import auth, inventory, pos, crm, finance, tasks, sales, audit, settings, suppliers, system
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError

# Configure Rate Limiting - MOVED TO core.py

# Fon vazifalari (rejalashtiruvchi, Telegram polling, ishga tushish nusxasi)
# YAGONA jarayonda ishlashi kerak.
#
# Ular lifespan ichida bo'lgani uchun `uvicorn --workers 4` ularni ham to'rt
# marta ishga tushirardi: to'rtta getUpdates polleri Telegram'dan uzluksiz
# 409 Conflict oladi va bot javob bermay qoladi; to'rtta rejalashtiruvchi har
# bir qarzdorga to'rttadan eslatma yuboradi; to'rtta nusxa vazifasi bitta
# papkaga bir vaqtda yozadi.
#
# Serverda: bitta systemd unit `RUN_BACKGROUND_JOBS=true` bilan (bitta jarayon),
# web unit esa ko'p worker bilan va bu flagsiz ishlaydi.
RUN_BACKGROUND_JOBS = os.getenv("RUN_BACKGROUND_JOBS", "true").strip().lower() in {
    "1", "true", "yes",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Startup: Initializing DB...")
    await init_db()

    scheduler = None
    backup_task = None
    bot_task = None

    if not RUN_BACKGROUND_JOBS:
        print("Startup: fon vazifalari o'chirilgan (RUN_BACKGROUND_JOBS=false) — "
              "faqat web so'rovlariga xizmat qilamiz.")

    if RUN_BACKGROUND_JOBS:
        # Start Scheduler for background tasks
        print("Startup: Starting scheduler...")
        scheduler = AsyncIOScheduler()
        # Har kuni ertalab soat 9:00 da qarzni tekshirish
        scheduler.add_job(check_debts, 'cron', hour=9, minute=0, args=[bot])

        # SQLite backup — kun davomida bir necha marta + har ishga tushganda.
        # run_daily_backup: lokal nusxa + BACKUP_MIRROR_DIR (bo'lsa) + Telegram (bo'lsa).
        if os.getenv("BACKUP_ENABLED", "true").lower() in {"1", "true", "yes"}:
            from utils.backup import run_daily_backup, run_startup_backup
            # Standart: har kuni soat 12:00 va 22:00 + har ishga tushganda.
            # BACKUP_HOURS="9,14,22" bilan .env dan o'zgartirish mumkin.
            raw_hours = os.getenv("BACKUP_HOURS", "12,22")
            backup_hours = sorted({
                int(h) for h in raw_hours.replace(" ", "").split(",")
                if h.strip().isdigit() and 0 <= int(h) <= 23
            }) or [12, 22]
            scheduler.add_job(
                run_daily_backup, 'cron', hour=",".join(str(h) for h in backup_hours), minute=0,
                id="daily_backup", replace_existing=True, kwargs={"bot": bot},
            )
            print(f"Startup: Backup rejalashtirildi - har kuni soat {backup_hours} + ishga tushganda.")
            # Har ishga tushganda darhol bitta nusxa (kechasi o'chirilgan kunlar uchun kafolat).
            backup_task = asyncio.create_task(run_startup_backup(bot))
        scheduler.start()
        # Start Telegram only when a token is configured.
        if bot:
            print("Startup: Starting bot polling...")

            async def _supervised_polling():
                """Polling uzilib qolsa QAYTA ishga tushiradi.

                Ilgari bu oddiy create_task edi: vazifa xato bilan tugasa hech
                kim bilmasdi — bot jim qolar, /health esa "ok" deb turaverardi.
                """
                delay = 5
                while True:
                    try:
                        await dp.start_polling(bot)
                        return                      # normal to'xtash (shutdown)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:        # noqa: BLE001
                        logging.error("Bot polling uzildi: %s. %s soniyadan keyin qayta.",
                                      exc, delay)
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 300)

            bot_task = asyncio.create_task(_supervised_polling())
        else:
            print("Startup: Telegram bot is disabled (no token).")

    # Create a default admin only if no admin account exists at all
    async with SessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Employee).where(Employee.role == "admin"))
        admin = result.scalars().first()
        if not admin:
            # Boshlang'ich parol: .env dagi PRIMARY_ADMIN_PASSWORD, aks holda
            # development'da qulaylik uchun DEV_ADMIN_PASSWORD. Production'da esa
            # zaif default ishlatmaymiz — aniq sozlama xatosi beramiz.
            bootstrap_password = PRIMARY_ADMIN_PASSWORD
            if not bootstrap_password:
                if APP_ENV == "production":
                    raise RuntimeError(
                        "PRIMARY_ADMIN_PASSWORD o'rnatilmagan va bazada admin hisobi yo'q. "
                        "backend/.env ga  PRIMARY_ADMIN_PASSWORD=<kuchli-parol>  qo'shing "
                        'yoki serverda  python reset_admin.py "<parol>"  ni ishlating.'
                    )
                bootstrap_password = DEV_ADMIN_PASSWORD
            print(f"Admin yaratilmoqda: {PRIMARY_ADMIN_USERNAME}")
            new_admin = Employee(
                username=PRIMARY_ADMIN_USERNAME,
                hashed_password=get_password_hash(bootstrap_password),
                role="admin",
                permissions="all"
            )
            db.add(new_admin)
            try:
                await db.commit()
            except IntegrityError:
                # Bir nechta worker bir vaqtda ishga tushsa, ikkinchisi shu
                # yerga yetib kelguncha birinchisi adminni yaratib bo'lgan
                # bo'ladi. Bu xato emas.
                await db.rollback()
                print("Admin allaqachon boshqa jarayon tomonidan yaratilgan.")
    
    print("Startup: Complete. Application running.")
    try:
        yield
    finally:
        print("Shutdown: Stopping scheduler and bot...")
        if scheduler is not None:
            scheduler.shutdown()
        if backup_task and not backup_task.done():
            try:
                await asyncio.wait_for(backup_task, timeout=10.0)
            except Exception as e:
                print(f"Startup backup cleanup: {e}")
        if bot_task:
            bot_task.cancel()
            try:
                await asyncio.wait([bot_task], timeout=2.0)
            except Exception as e:
                print(f"Cleanup error: {e}")
        if bot:
            await bot.session.close()
        
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

import math
from fastapi.exceptions import RequestValidationError


def _json_safe(value):
    """NaN/Infinity ni matnga aylantiradi.

    Pydantic NaN ni to'g'ri rad etadi (422), ammo FastAPI xato javobida
    kiritilgan qiymatni QAYTA JSON ga o'giradi — va standart JSON da NaN yo'q.
    Natijada validatsiya xatosi javob yozilayotganda 500 ga aylanardi, ya'ni
    noto'g'ri son yuborgan mijoz baribir serverni yiqitardi.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": _json_safe(exc.errors())})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Ichki server xatoligi yuz berdi. Iltimos, administratorga murojaat qiling."},
    )

# Configure CORS
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
if APP_ENV == "production" and (not allowed_origins or "*" in allowed_origins):
    # Ilgari bu shunchaki ogohlantirish edi va server ochiq CORS bilan
    # ishlayverardi. Production'da bu sozlama xatosi — ishga tushirmaymiz.
    raise RuntimeError(
        "Production'da ALLOWED_ORIGINS='*' bo'lishi mumkin emas. "
        "backend/.env da o'z domeningizni ko'rsating, masalan: "
        "ALLOWED_ORIGINS=https://kassa.sizning-domen"
    )

# Ro'yxat javoblari (mahsulotlar, savdolar, audit) siqilmasdan ketardi.
# Do'kon Wi-Fi'sida bu sezilarli — JSON juda yaxshi siqiladi.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
app.include_router(system.router)

# Static files for invoices
# Yo'l modul joylashuviga bog'langan: ilovani qaysi katalogdan ishga
# tushirishdan qat'i nazar, fayllar doim backend/uploads/ da bo'ladi.
from utils.backup import UPLOAD_DIR  # noqa: E402

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "invoices").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/health")
async def health():
    """Monitoring uchun. Bu jarayon nima bilan shug'ullanayotganini ham ko'rsatadi."""
    return {
        "status": "ok",
        "background_jobs": RUN_BACKGROUND_JOBS,
        "bot": bool(bot) and RUN_BACKGROUND_JOBS,
    }


# --- Frontend (yig'ilgan statik fayllar) ---
# Caddy/Node kerak emas: backend'ning o'zi frontendni ham beradi.
# frontend/dist repo bilan birga keladi (uyda `deploy/publish.ps1` build qiladi).
_FRONTEND_DIST = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
)


class SPAStaticFiles(StaticFiles):
    """Noma'lum yo'llar (React Router sahifalari) uchun index.html qaytaradi."""

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


if os.path.isfile(os.path.join(_FRONTEND_DIST, "index.html")):
    app.mount("/", SPAStaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"message": "Kassa API is running", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)