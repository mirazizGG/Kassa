"""Zahira nusxa olish — cron uchun.

Nima uchun kerak
----------------
Odatda nusxani ilova ichidagi rejalashtiruvchi (APScheduler) oladi. Ammo
cPanel/shared hosting'da fon vazifalari yo'q: Passenger bo'sh turgan
jarayonni o'chiradi va rejalashtiruvchi bilan birga nusxa olish ham to'xtaydi.
Shuning uchun u yerda nusxani cron chaqiradi.

cron misoli (kuniga ikki marta, 12:00 va 22:00):

    0 12,22 * * * cd /home/erkatoyu/smart-kassa/backend && \
        /home/erkatoyu/smart-kassa/venv/bin/python run_backup.py >> ~/kassa-backup.log 2>&1

Skript hech qachon xato bilan yiqilmaydi — cron jurnalini to'ldirmaslik uchun
natijani matn bilan yozadi va chiqish kodi bilan bildiradi.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# load_dotenv() SHART. Bu skript cron'dan ishga tushadi va main.py ni import
# qilmaydi — ya'ni .env ni hech kim o'qimaydi. Usiz DATABASE_URL bo'sh bo'lib
# qoladi va utils/backup.py PostgreSQL o'rniga SQLite faylini qidiradi.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent / ".env")

from utils.backup import run_full_backup  # noqa: E402


async def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        # bot=None: shared hosting'da Telegram jo'natish yo'q, qolgan manzillar ishlaydi.
        result = await run_full_backup(bot=None)
    except Exception as exc:  # noqa: BLE001 - cron hech qachon "yiqildi" demasin
        print(f"[{stamp}] XATO: {exc}")
        return 1

    parts = [f"lokal={Path(result['local']).name}"]
    if result.get("uploads"):
        parts.append(f"nakladnoylar={Path(result['uploads']).name}")
    if result.get("mirror") is not None:
        parts.append(f"bulut={'ha' if result['mirror'] else 'yo^q'}")
    if result.get("github") is not None:
        parts.append(f"github={'ha' if result['github'] else 'yo^q'}")

    print(f"[{stamp}] OK: " + ", ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
