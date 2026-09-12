import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address


# Proksi orqasidamizmi? Faqat shu yoqilganda X-Forwarded-For / CF-Connecting-IP
# ga ishonamiz. Aks holda istalgan mijoz shu sarlavhani O'ZI yasab, har so'rovda
# boshqa "IP" ko'rsatib, login urinishlari chegarasini butunlay chetlab o'tardi.
# VPS da Caddy/nginx orqasida ishlatganda backend/.env ga TRUST_PROXY_HEADERS=true
# qo'ying — lekin faqat proksi bu sarlavhalarni O'ZI qayta yozadigan bo'lsa.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").strip().lower() in {
    "1", "true", "yes",
}


def _real_client_ip(request: Request) -> str:
    """Rate-limit kaliti: proksi orqasida ham to'g'ri IP ni topadi."""
    if TRUST_PROXY_HEADERS:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_real_client_ip)

from database import get_db, Employee

# Security configurations
# APP_ENV=production bo'lsa, zaif/yo'q SECRET_KEY bilan dastur ishga tushmaydi.
_DEV_SECRET_KEY = "dev_secret_key_change_in_production_12345"
# .env.example bilan keladigan namunaviy qiymatlar. Bulardan biri production'da
# qolib ketsa, JWT imzo kaliti ochiq repozitoriyda turadi — ya'ni istalgan odam
# o'ziga admin token yasay oladi. Shuning uchun ro'yxat bo'yicha tekshiramiz.
_PLACEHOLDER_SECRET_KEYS = {
    _DEV_SECRET_KEY,
    "change_me_generate_with_secrets_token_hex_32",
}
_MIN_SECRET_KEY_LEN = 32
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

if not SECRET_KEY:
    if APP_ENV == "production":
        raise RuntimeError(
            "SECRET_KEY o'rnatilmagan. Production'da bu majburiy. "
            "backend/.env ga qo'shing. Yangi kalit: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    SECRET_KEY = _DEV_SECRET_KEY

if APP_ENV == "production" and (
    SECRET_KEY in _PLACEHOLDER_SECRET_KEYS or len(SECRET_KEY) < _MIN_SECRET_KEY_LEN
):
    raise RuntimeError(
        "Production'da namunaviy yoki juda qisqa SECRET_KEY ishlatib bo'lmaydi "
        f"(kamida {_MIN_SECRET_KEY_LEN} belgi). backend/.env da o'zingizning "
        "tasodifiy kalitingizni qo'ying. Yangi kalit: "
        'python -c "import secrets; print(secrets.token_hex(32))"'
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 600

# Bosh administrator — bu hisobni API orqali o'zgartirib yoki o'chirib bo'lmaydi.
# Parolni faqat serverda `python reset_admin.py` bilan tiklash mumkin.
# Bu nom atayin .env'dan sozlanmaydi: frontend (Employees.jsx) ham aynan shu
# nomga bog'langan, ikkisini bir joyda o'zgartirmasdan ajratib bo'lmaydi.
PRIMARY_ADMIN_USERNAME = "miraziz"

# Bosh admin BOSHLANG'ICH paroli — faqat bazada hech qanday admin bo'lmaganda
# (birinchi ishga tushirish yoki bazani yo'qotib qayta tiklashda) ishlatiladi.
# Qo'yilmasa: development'da qulaylik uchun DEV_ADMIN_PASSWORD, production'da esa
# admin yaratish kerak bo'lgan payt main.py aniq xato beradi (zaif default yo'q).
DEV_ADMIN_PASSWORD = "8038434"
PRIMARY_ADMIN_PASSWORD = os.getenv("PRIMARY_ADMIN_PASSWORD", "").strip()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Tasdiqlash urinishlarini cheklash: bir foydalanuvchi bir daqiqada nechta
# menejer paroli taxmin qila oladi.
_APPROVAL_ATTEMPTS: dict[int, list[float]] = {}
APPROVAL_LIMIT_PER_MINUTE = 5


async def verify_approver(db, requester, username: str, password: str, roles=("admin", "manager")):
    """Menejer/admin tasdig'ini tekshiradi — CHEKLOV va JURNAL bilan.

    Ilgari bu tekshiruv uch joyda takrorlangan, cheklovsiz va muvaffaqiyatsiz
    urinishlar jurnalga YOZILMASDAN turardi. Kassir kassadan turib menejer
    parolini xohlaganicha tez taxmin qila olardi, hech qanday iz qoldirmasdan;
    topilgan parol esa /auth/token uchun ham yaraydi, ya'ni to'liq eskalatsiya.
    Bundan tashqari verify_password — sinxron pbkdf2, ya'ni uzoq davom etgan
    hujum serverni ham sekinlashtiradi.
    """
    import time as _time
    from routers.audit import log_action

    now = _time.monotonic()
    window = [t for t in _APPROVAL_ATTEMPTS.get(requester.id, []) if now - t < 60]
    if len(window) >= APPROVAL_LIMIT_PER_MINUTE:
        _APPROVAL_ATTEMPTS[requester.id] = window
        raise HTTPException(
            status_code=429,
            detail="Juda ko'p urinish. Bir daqiqadan keyin qayta urinib ko'ring.",
        )
    window.append(now)
    _APPROVAL_ATTEMPTS[requester.id] = window

    result = await db.execute(
        select(Employee).where(Employee.username == username, Employee.is_active == True)
    )
    approver = result.scalars().first()

    if not approver or approver.role not in roles or not verify_password(password, approver.hashed_password):
        await log_action(
            db, requester.id, "TASDIQ_XATO",
            f"Menejer tasdig'i muvaffaqiyatsiz. Kiritilgan login: {username!r}",
        )
        await db.commit()
        raise HTTPException(status_code=403, detail="Menejer tasdig'i noto'g'ri")

    # Muvaffaqiyatli urinishdan keyin hisoblagichni tozalaymiz.
    _APPROVAL_ATTEMPTS.pop(requester.id, None)
    return approver


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    result = await db.execute(select(Employee).where(Employee.username == username))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foydalanuvchi faol emas (bloklangan)"
        )

    # Sessiya kalitini HAR DOIM solishtiramiz.
    #
    # Ilgari shart `if user.session_token and ...` edi. Chiqishda (logout)
    # session_token NULL ga o'rnatiladi va NULL "yolg'on" bo'lgani uchun butun
    # tekshiruv o'tkazib yuborilardi: chiqib ketilgan token o'zining 600
    # daqiqasi tugagunicha ishlayverardi. Ya'ni "Chiqish" tugmasi hech narsani
    # bekor qilmasdi va "bitta qurilma" himoyasi ham yo'qolardi.
    session_id = payload.get("sid")
    if not session_id or session_id != user.session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessiya yakunlangan. Qaytadan tizimga kiring.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user
