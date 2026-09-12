"""cPanel / Phusion Passenger uchun kirish nuqtasi.

Nima uchun bu fayl kerak
------------------------
cPanel ning "Setup Python App" ilovani Passenger orqali ishga tushiradi, u esa
WSGI kutadi. FastAPI — ASGI. Orada `a2wsgi` ko'prigi turadi.

MUHIM: `a2wsgi.ASGIMiddleware` lifespan hodisalarini ISHLATMAYDI. Ya'ni
`main.py` dagi startup bloki (init_db, rejalashtiruvchi, bot, birinchi admin)
bu yerda BAJARILMAYDI. Bazani tayyorlash alohida qadam:

    /opt/alt/python312/bin/python3 backend/setup_db.py

Shared hosting'da fon vazifalari yo'q:
  * RUN_BACKGROUND_JOBS=false — rejalashtiruvchi va Telegram bot ishga tushmaydi
    (Passenger bo'sh turgan jarayonlarni o'chiradi, long polling yashab qolmaydi).
  * Zahira nusxa cron orqali olinadi: deploy/cpanel/backup-cron.sh
  * ALLOW_SELF_UPDATE=false — ilova ichidan yangilash shared hosting'da ishlamaydi.
"""
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
BACKEND = APP_ROOT / "backend"

# backend/ ni import yo'liga qo'shamiz — main.py o'z yonidagi modullarni
# (database, core, routers) to'g'ridan-to'g'ri import qiladi.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Passenger ishchi katalogni kafolatlamaydi. backend/.env va nisbiy yo'llar
# to'g'ri topilishi uchun o'zimiz o'rnatamiz.
os.chdir(BACKEND)

# Shared hosting uchun majburiy sozlamalar — .env da boshqacha yozilgan bo'lsa ham.
os.environ["RUN_BACKGROUND_JOBS"] = "false"
os.environ["ALLOW_SELF_UPDATE"] = "false"

from a2wsgi import ASGIMiddleware  # noqa: E402
from main import app as _asgi_app  # noqa: E402

# Passenger aynan `application` nomini qidiradi.
application = ASGIMiddleware(_asgi_app)
