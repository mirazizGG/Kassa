"""Database backup helpers for the local SQLite deployment."""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


async def send_backup_to_telegram(bot, admin_id: int) -> None:
    """Create and send a backup to an administrator's Telegram account."""
    from aiogram.types import FSInputFile

    backup_path = create_backup()
    if not backup_path:
        raise RuntimeError("Backup could not be created")

    document = FSInputFile(backup_path)
    await bot.send_document(
        admin_id,
        document,
        caption=f"Avtomatik zahira nusxasi\nVaqt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
    )


async def run_daily_backup(bot=None) -> None:
    """Scheduler job: lokal + (sozlangan bo'lsa) tashqi papka + Telegram nusxa.

    Hech qachon xato ko'tarmaydi — scheduler ishini to'xtatib qo'ymasligi uchun.
    """
    admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    if bot and admin_chat_id:
        try:
            await send_backup_to_telegram(bot, int(admin_chat_id))
            return
        except Exception as exc:  # noqa: BLE001 - job hech qachon yiqilmasin
            print(f"Telegram backup error: {exc}")
    # Telegram sozlanmagan yoki xato bo'lsa — kamida lokal (+ mirror) nusxa qoladi.
    try:
        create_backup()
    except Exception as exc:  # noqa: BLE001
        print(f"Daily backup error: {exc}")