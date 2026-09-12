"""Vaqt bilan ishlashning YAGONA joyi.

Qoida (butun loyiha bo'ylab bitta):
  * BAZADA hamma vaqt UTC va "naive" (tzinfo siz) saqlanadi.
  * FOYDALANUVCHI do'kon vaqtida o'ylaydi (sukut bo'yicha Asia/Tashkent).
  * Bu ikkisi orasidagi har qanday o'tkazish faqat shu modul orqali bo'ladi.

Ilgari bu mantiq uch joyda uch xil edi: finance.py o'zining `local_today_start`
funksiyasiga, audit.py `local_day_boundary` ga, pos.py esa smena vaqtlarini
SERVER LOKAL vaqtida yozib, keyin ularni qayta hisoblaydigan ko'prikka
tayanardi. Server soati Toshkentda bo'lmasa (masalan hostingda — u yerda odatda
UTC) hisoblar bir-biriga mos kelmay qolardi.

Do'kon vaqt mintaqasini `SHOP_TIMEZONE` muhit o'zgaruvchisi bilan almashtirish
mumkin — kod ichida qat'iy yozilmagan.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

SHOP_TIMEZONE = os.getenv("SHOP_TIMEZONE", "Asia/Tashkent").strip() or "Asia/Tashkent"

try:
    SHOP_TZ = ZoneInfo(SHOP_TIMEZONE)
except Exception:  # noqa: BLE001 - noto'g'ri sozlama dasturni yiqitmasin
    print(f"Ogohlantirish: SHOP_TIMEZONE='{SHOP_TIMEZONE}' topilmadi, Asia/Tashkent ishlatiladi.")
    SHOP_TZ = ZoneInfo("Asia/Tashkent")


def utc_now() -> datetime:
    """Bazaga yoziladigan "hozir": UTC, naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_shop_time(value: datetime) -> datetime:
    """Bazadagi naive-UTC qiymatni do'kon vaqtiga o'giradi (ko'rsatish uchun)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SHOP_TZ)


def _shop_moment_to_utc(value: datetime) -> datetime:
    """Do'kon vaqtidagi naive qiymatni naive-UTC ga o'giradi."""
    return value.replace(tzinfo=SHOP_TZ).astimezone(timezone.utc).replace(tzinfo=None)


def day_start_utc(day: date) -> datetime:
    """Do'kon kunining boshlanishi -> bazada solishtirish uchun naive-UTC."""
    return _shop_moment_to_utc(datetime.combine(day, time.min))


def day_end_utc(day: date) -> datetime:
    """Do'kon kunining oxiri -> bazada solishtirish uchun naive-UTC."""
    return _shop_moment_to_utc(datetime.combine(day, time.max))


def shop_today() -> date:
    """Do'kon bo'yicha bugungi KALENDAR sana."""
    return datetime.now(SHOP_TZ).date()


def shop_date(value: datetime) -> date:
    """Bazadagi naive-UTC qiymatning do'kon bo'yicha kalendar sanasi."""
    return to_shop_time(value).date()


def days_until(value: datetime) -> int:
    """Bugundan `value` sanasigacha necha KUN qolgani (do'kon vaqti bo'yicha).

    Muhim: bu KALENDAR kunlari farqi, timedelta emas. Ilgari qarz eslatmalari
    `(due - now).days` bilan hisoblanardi: manfiy timedelta pastga
    yaxlitlangani uchun muddat KUNIning o'zida ham natija -1 chiqib, mijozga
    "muddati o'tgan" deb yozilardi.
    """
    return (shop_date(value) - shop_today()).days


def day_bounds_utc(day: date) -> "tuple[datetime, datetime]":
    """Do'kon kuni uchun [boshi, keyingi kun boshi) oralig'i, naive-UTC."""
    from datetime import timedelta

    return day_start_utc(day), day_start_utc(day + timedelta(days=1))


def parse_filter_date(value, end_of_day: bool = False):
    """Foydalanuvchi bergan sanani bazada solishtirish uchun naive-UTC ga o'giradi.

    "YYYY-MM-DD" - DO'KON kalendar kuni, shuning uchun uning chegaralari
    day_start_utc/day_end_utc orqali olinadi. Ilgari finance.py va sales.py da
    bir xil `parse_date` nusxalari bor edi va ular kunni UTC bo'yicha kesardi:
    "bugungi" hisobot smenalar va audit ko'rsatadigan kundan boshqa oraliqni
    qamrab olardi.
    """
    if not value:
        return None
    text = str(value)
    try:
        if len(text) <= 10:
            day = datetime.strptime(text, "%Y-%m-%d").date()
            return day_end_utc(day) if end_of_day else day_start_utc(day)

        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if moment.tzinfo:
            return moment.astimezone(timezone.utc).replace(tzinfo=None)
        return moment
    except ValueError:
        return None


def today_start_utc() -> datetime:
    """Do'kon bo'yicha BUGUN boshlangan payt, naive-UTC."""
    return day_start_utc(datetime.now(SHOP_TZ).date())
