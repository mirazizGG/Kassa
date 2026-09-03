from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address


def _real_client_ip(request: Request) -> str:
    """Rate-limit key that works behind a reverse proxy (Caddy) and Cloudflare.

    Without this every request looks like it comes from 127.0.0.1 and the whole
    shop shares one rate-limit bucket.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_real_client_ip)

from database import get_db, Employee

import os
from dotenv import load_dotenv

load_dotenv()

# Security configurations
# APP_ENV=production bo'lsa, zaif/yo'q SECRET_KEY bilan dastur ishga tushmaydi.
_DEV_SECRET_KEY = "dev_secret_key_change_in_production_12345"
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

if APP_ENV == "production" and SECRET_KEY == _DEV_SECRET_KEY:
    raise RuntimeError(
        "Production'da namunaviy (default) SECRET_KEY ishlatib bo'lmaydi. "
        "backend/.env da o'zingizning tasodifiy kalitingizni qo'ying."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 600

# Bosh administrator — bu hisobni API orqali o'zgartirib yoki o'chirib bo'lmaydi.
# Parolni faqat serverda `python reset_admin.py` bilan tiklash mumkin.
PRIMARY_ADMIN_USERNAME = "miraziz"

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

    session_id = payload.get("sid")
    if user.session_token and session_id != user.session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessiya boshqa qurilmada yakunlangan. Qaytadan kiring.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user
