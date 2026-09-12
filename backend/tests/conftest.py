"""Test uchun umumiy sozlamalar.

Har bir test moduli o'zining vaqtinchalik SQLite bazasida ishlaydi — hech qachon
haqiqiy market.db ga tegmaydi. Muhit o'zgaruvchilari `database`/`core` import
qilinishidan OLDIN o'rnatilishi shart, chunki ular modul darajasida o'qiladi.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP_DB = Path(tempfile.gettempdir()) / f"kassa_test_{uuid.uuid4().hex}.db"

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB.as_posix()}"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_ADMIN_CHAT_ID"] = ""
os.environ["BACKUP_ENABLED"] = "false"
os.environ["ALLOW_SELF_UPDATE"] = "false"
os.environ["PRIMARY_ADMIN_PASSWORD"] = "test-admin-password-123"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    import main

    with TestClient(main.app) as c:
        yield c

    try:
        _TMP_DB.unlink(missing_ok=True)
    except OSError:
        pass


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post(
        "/auth/token",
        data={"username": "miraziz", "password": "test-admin-password-123", "force": "true"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def temp_user_factory(client, auth):
    """Berilgan roldagi vaqtinchalik xodim yaratib, uning tokenini qaytaradi."""
    import uuid

    def _make(role: str = "cashier"):
        username = f"rol_{role}_{uuid.uuid4().hex[:6]}"
        password = "Vaqtincha-Parol-123"
        created = client.post("/auth/employees", headers=auth, json={
            "username": username, "password": password, "role": role,
            "permissions": "", "full_name": f"Test {role}",
        })
        assert created.status_code == 200, created.text
        token = client.post("/auth/token", data={
            "username": username, "password": password, "force": "true",
        })
        assert token.status_code == 200, token.text
        return {"Authorization": f"Bearer {token.json()['access_token']}"}

    return _make
