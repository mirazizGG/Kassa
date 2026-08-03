"""Database backup helpers for the local SQLite deployment."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "market.db"
BACKUP_DIR = BASE_DIR / "backups"
DEFAULT_RETENTION = int(os.getenv("BACKUP_RETENTION", "30"))


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
        return str(backup_path)
    except sqlite3.Error as exc:
        if backup_path.exists():
            backup_path.unlink()
        print(f"Backup error: {exc}")
        return None


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