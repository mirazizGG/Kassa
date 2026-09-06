"""Database backup helpers for the local SQLite deployment."""
from __future__ import annotations

import asyncio
import base64
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "market.db"
BACKUP_DIR = BASE_DIR / "backups"
DEFAULT_RETENTION = int(os.getenv("BACKUP_RETENTION", "30"))
# Ixtiyoriy: har zahira nusxa shu papkaga ham ko'chiriladi (tashqi disk yoki
# Google Drive/OneDrive kabi sinxronlanadigan papka). Bo'sh bo'lsa — o'tkazib yuboriladi.
BACKUP_MIRROR_DIR = os.getenv("BACKUP_MIRROR_DIR", "").strip()


def create_backup() -> str | None:
    """Create a consistent SQLite snapshot, including data in WAL mode."""
    if not DB_PATH.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"backup_{timestamp}.db"

    try:
        with sqlite3.connect(DB_PATH) as source, sqlite3.connect(backup_path) as destination:
            source.backup(destination)
        clean_old_backups()
        _mirror_backup(backup_path)
        return str(backup_path)
    except sqlite3.Error as exc:
        if backup_path.exists():
            backup_path.unlink()
        print(f"Backup error: {exc}")
        return None


def _mirror_backup(backup_path: Path) -> None:
    """Copy a fresh backup into BACKUP_MIRROR_DIR. Never fails the primary backup."""
    if not BACKUP_MIRROR_DIR:
        return
    try:
        mirror_dir = Path(BACKUP_MIRROR_DIR)
        mirror_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, mirror_dir / backup_path.name)
        mirrors = sorted(
            mirror_dir.glob("backup_*.db"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for old in mirrors[DEFAULT_RETENTION:]:
            old.unlink(missing_ok=True)
    except OSError as exc:
        print(f"Backup mirror error: {exc}")


def clean_old_backups(limit: int = DEFAULT_RETENTION) -> None:
    """Keep only the newest valid backup files."""
    backups = sorted(BACKUP_DIR.glob("backup_*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
    for backup in backups[limit:]:
        backup.unlink(missing_ok=True)


def list_backups() -> list[dict[str, Any]]:
    """Return backup metadata without exposing filesystem paths."""
    if not BACKUP_DIR.exists():
        return []

    return [
        {
            "filename": backup.name,
            "size": backup.stat().st_size,
            "created_at": datetime.fromtimestamp(backup.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for backup in sorted(BACKUP_DIR.glob("backup_*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
    ]


def github_upload(backup_path: Path) -> bool | None:
    """Zahira nusxani alohida (maxfiy) GitHub repozitoriysiga yuklaydi.

    Har safar bitta faylni (BACKUP_GITHUB_PATH, default `market.db`) eskisi ustiga
    yozadi — repozitoriyda doim eng oxirgi nusxa turadi (git tarixida esa oldingilari).

    Sozlanmagan bo'lsa None, muvaffaqiyatli bo'lsa True, xato bo'lsa False.
    """
    token = os.getenv("BACKUP_GITHUB_TOKEN", "").strip()
    repo = os.getenv("BACKUP_GITHUB_REPO", "").strip()  # "egasi/repo-nomi"
    if not token or not repo:
        return None
    path_in_repo = (os.getenv("BACKUP_GITHUB_PATH", "").strip() or "market.db").lstrip("/")
    branch = os.getenv("BACKUP_GITHUB_BRANCH", "").strip() or "main"

    api = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "SmartKassa-Backup",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        content_b64 = base64.b64encode(backup_path.read_bytes()).decode()
        with httpx.Client(timeout=30.0) as client:
            # Yangilash uchun mavjud faylning `sha` si kerak (birinchi marta bo'lmasa).
            sha = None
            r = client.get(api, headers=headers, params={"ref": branch})
            if r.status_code == 200:
                sha = r.json().get("sha")
            payload: dict[str, Any] = {
                "message": f"backup {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                "content": content_b64,
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha
            r = client.put(api, headers=headers, json=payload)
        if r.status_code in (200, 201):
            return True
        print(f"GitHub backup xatosi: {r.status_code} {r.text[:300]}")
        return False
    except (httpx.HTTPError, OSError, ValueError) as exc:
        print(f"GitHub backup xatosi: {exc}")
        return False


async def send_backup_to_telegram(bot, admin_id: int, backup_path: str | None = None) -> None:
    """Tayyor zahira nusxani admin Telegramiga fayl bo'lib yuboradi."""
    from aiogram.types import FSInputFile

    if not backup_path:
        backup_path = create_backup()
    if not backup_path:
        raise RuntimeError("Backup could not be created")

    document = FSInputFile(backup_path)
    await bot.send_document(
        admin_id,
        document,
        caption=f"Zahira nusxasi\nVaqt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
    )


async def run_full_backup(bot=None) -> dict:
    """Bitta amalda: lokal + bulut papka (mirror) + GitHub + Telegram.

    Har bir manzil mustaqil — biri ishlamasa qolganlari baribir bajariladi.
    Natija: qaysi manzilga borgani haqida lug'at.
    """
    result: dict[str, Any] = {"local": None, "mirror": None, "github": None, "telegram": None}

    backup_path = await asyncio.to_thread(create_backup)
    if not backup_path:
        raise RuntimeError("Zahira nusxasi yaratilmadi")
    result["local"] = backup_path

    if BACKUP_MIRROR_DIR:
        result["mirror"] = (Path(BACKUP_MIRROR_DIR) / Path(backup_path).name).exists()

    result["github"] = await asyncio.to_thread(github_upload, Path(backup_path))

    admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    if bot and admin_chat_id:
        try:
            await send_backup_to_telegram(bot, int(admin_chat_id), backup_path)
            result["telegram"] = True
        except Exception as exc:  # noqa: BLE001 - Telegram xatosi backupni buzmasin
            print(f"Telegram backup xatosi: {exc}")
            result["telegram"] = False

    return result


def _latest_backup_age_seconds() -> float | None:
    """Eng yangi zaxira nusxa necha soniya oldin olingan (yo'q bo'lsa None)."""
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(
        BACKUP_DIR.glob("backup_*.db"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        return None
    return datetime.now(timezone.utc).timestamp() - backups[0].stat().st_mtime


async def run_startup_backup(bot=None, min_gap_seconds: int = 3600) -> None:
    """Ishga tushganda nusxa — lekin oxirgi nusxa juda yaqin bo'lsa o'tkazib yuboradi
    (tez-tez qayta ishga tushirishda zaxira papkasi to'lib ketmasligi uchun)."""
    age = _latest_backup_age_seconds()
    if age is not None and age < min_gap_seconds:
        print(f"Startup backup: o'tkazib yuborildi (oxirgi nusxa {int(age // 60)} daqiqa oldin).")
        return
    await run_daily_backup(bot)


async def run_daily_backup(bot=None) -> None:
    """Scheduler job: lokal + tashqi papka + GitHub + Telegram nusxa.

    Hech qachon xato ko'tarmaydi — scheduler ishini to'xtatib qo'ymasligi uchun.
    """
    try:
        await run_full_backup(bot)
    except Exception as exc:  # noqa: BLE001 - job hech qachon yiqilmasin
        print(f"Daily backup error: {exc}")