"""Dasturni ilova ichidan yangilash (self-update).

Admin/menejer/kassir — istalgan xodim "Yangilash" tugmasini bosishi mumkin.
Tugma serverda `deploy/scripts/update.ps1` ni alohida (detached) jarayonda
ishga tushiradi; u `git pull` qilib, kerak bo'lsa frontendni qayta yig'adi va
backendni qayta ishga tushiradi. Frontend `/system/update-status` ni so'rab
turib "kuting" oynasini ko'rsatadi.

Faqat server `.env` da `ALLOW_SELF_UPDATE=true` bo'lsagina ishlaydi.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core import get_current_user
from database import Employee, get_db
from routers.audit import log_action

router = APIRouter(prefix="/system", tags=["system"])

REPO_ROOT = Path(__file__).resolve().parents[2]
UPDATE_SCRIPT = REPO_ROOT / "deploy" / "scripts" / "update.ps1"
RUN_DIR = REPO_ROOT / "deploy" / "run"
STATUS_FILE = RUN_DIR / "update-status.json"

ALLOW_SELF_UPDATE = os.getenv("ALLOW_SELF_UPDATE", "false").strip().lower() in {"1", "true", "yes"}
# Yangilanish shu vaqtdan uzoq "running" holatда qolsa, qotib qolgan deb hisoblaymiz.
STALE_SECONDS = 15 * 60


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=20,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def _read_status() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _current_commit() -> str:
    return _git("rev-parse", "--short", "HEAD") or "?"


@router.get("/version")
async def get_version(current_user: Employee = Depends(get_current_user)):
    status = _read_status()
    running = bool(status.get("running"))
    if running and time.time() - status.get("updated_at", 0) > STALE_SECONDS:
        running = False
    return {
        "commit": _current_commit(),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "updating": running,
        "self_update_enabled": ALLOW_SELF_UPDATE,
    }


@router.get("/update-check")
async def check_for_update(current_user: Employee = Depends(get_current_user)):
    """GitHub'da yangi versiya bor-yo'qligini tekshiradi (git fetch)."""
    if not ALLOW_SELF_UPDATE:
        return {"enabled": False, "update_available": False}
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "main"
    _git("fetch", "origin", branch)
    local = _git("rev-parse", "HEAD")
    remote = _git("rev-parse", f"origin/{branch}")
    behind = _git("rev-list", "--count", f"HEAD..origin/{branch}")
    try:
        behind_n = int(behind)
    except ValueError:
        behind_n = 0
    return {
        "enabled": True,
        "update_available": bool(local and remote and local != remote and behind_n > 0),
        "behind_count": behind_n,
        "current_commit": local[:7],
        "latest_commit": remote[:7],
    }


@router.get("/update-status")
async def update_status(current_user: Employee = Depends(get_current_user)):
    status = _read_status()
    if status.get("running") and time.time() - status.get("updated_at", 0) > STALE_SECONDS:
        status = {**status, "running": False, "ok": False,
                  "message": "Yangilanish javob bermay qoldi. Serverni tekshiring."}
    status.setdefault("running", False)
    status.setdefault("phase", "idle")
    return status


@router.post("/update")
async def start_update(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not ALLOW_SELF_UPDATE:
        raise HTTPException(status_code=403, detail="Bu serverda ilova ichidan yangilash o'chirilgan")
    if not UPDATE_SCRIPT.exists():
        raise HTTPException(status_code=500, detail=f"update.ps1 topilmadi: {UPDATE_SCRIPT}")

    status = _read_status()
    if status.get("running") and time.time() - status.get("updated_at", 0) <= STALE_SECONDS:
        raise HTTPException(status_code=409, detail="Yangilanish allaqachon boshlangan")

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps({
        "running": True,
        "ok": None,
        "phase": "boshlanmoqda",
        "message": "Yangilanish boshlandi...",
        "started_by": current_user.username,
        "started_at": time.time(),
        "updated_at": time.time(),
        "from_commit": _current_commit(),
    }), encoding="utf-8")

    await log_action(db, current_user.id, "TIZIM_YANGILASH", f"Dastur yangilanishi boshlandi: @{current_user.username}")
    await db.commit()

    # update.ps1 ni ALOHIDA jarayonda ishga tushiramiz — backend qayta ishga
    # tushganda ham u to'xtamasligi kerak.
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(UPDATE_SCRIPT), "-FromApp"],
            cwd=str(REPO_ROOT),
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            ["pwsh", "-NoProfile", "-File", str(UPDATE_SCRIPT), "-FromApp"],
            cwd=str(REPO_ROOT), start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    return {"started": True}
