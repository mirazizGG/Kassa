"""PostgreSQL ga ko'chirish skriptining xavfli qismlari.

Haqiqiy PostgreSQL bu yerda yo'q, shuning uchun mantiqning eng xatarli ikki
joyini SQLite ustida tekshiramiz:

  1) jadvallar tashqi kalitlar tartibida ko'chirilishi (ota-onalar oldin) -
     aks holda PostgreSQL da (u FK ni majburlaydi) ko'chirish o'rtasida yiqiladi;
  2) `--source` va `DATABASE_URL` bo'yicha himoyalar.

Ketma-ketliklarni surish (`setval`) faqat PostgreSQL da bor, uni bu yerda
tekshirib bo'lmaydi - u serverda quruq yurishdan keyin qo'lda ko'riladi.
"""
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, event, func, insert, select, text

import database
from database import Base

BACKEND = Path(__file__).resolve().parent.parent


def _engine_with_fk(path):
    """FK majburlash yoqilgan SQLite engine - PostgreSQL xulqiga yaqin."""
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def test_tables_copy_in_foreign_key_order(tmp_path):
    """Ota-onalar bolalardan OLDIN ko'chirilishi shart."""
    src = _engine_with_fk(tmp_path / "src.db")
    with src.begin() as conn:
        Base.metadata.create_all(conn)
        conn.execute(text(
            "INSERT INTO employees (id, username, hashed_password, role, permissions, is_active) "
            "VALUES (1, 'kassir', 'x', 'cashier', '', 1)"
        ))
        conn.execute(text(
            "INSERT INTO clients (id, name, phone, balance, bonus_balance) "
            "VALUES (1, 'Mijoz', '+998901112233', -5000, 100)"
        ))
        conn.execute(text(
            "INSERT INTO categories (id, name) VALUES (1, 'Ichimlik')"
        ))
        conn.execute(text(
            "INSERT INTO products (id, name, barcode, buy_price, sell_price, stock, "
            "is_infinite, unit, category_id, is_favorite) "
            "VALUES (1, 'Suv', 'B1', 1000, 1500, 10, 0, 'dona', 1, 0)"
        ))
        conn.execute(text(
            "INSERT INTO shifts (id, cashier_id, opening_balance, status, opened_at) "
            "VALUES (1, 1, 0, 'open', '2026-09-07 08:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO sales (id, created_at, total_amount, payment_method, cashier_id, "
            "client_id, status, cash_amount, card_amount, transfer_amount, debt_amount, "
            "bonus_earned, bonus_spent) "
            "VALUES (1, '2026-09-07 09:00:00', 1500, 'cash', 1, 1, 'completed', "
            "1500, 0, 0, 0, 15, 0)"
        ))
        conn.execute(text(
            "INSERT INTO sale_items (id, sale_id, product_id, quantity, price, buy_price) "
            "VALUES (1, 1, 1, 1, 1500, 1000)"
        ))
        conn.execute(text(
            "INSERT INTO schema_migrations (name, applied_at) VALUES (:n, '2026-09-07 00:00:00')"
        ), {"n": database.SHIFT_UTC_MIGRATION})

    dst = _engine_with_fk(tmp_path / "dst.db")
    with dst.begin() as conn:
        Base.metadata.create_all(conn)

    # Skript bilan bir xil tartib va bir xil usul.
    copied = {}
    for table in Base.metadata.sorted_tables:
        with src.connect() as s:
            rows = [dict(r) for r in s.execute(select(table)).mappings().all()]
        if not rows:
            continue
        with dst.begin() as d:
            d.execute(insert(table), rows)   # FK yoqilgan: tartib xato bo'lsa yiqiladi
        copied[table.name] = len(rows)

    assert copied["employees"] == 1
    assert copied["sale_items"] == 1, "bolalar jadvali ko'chmadi"

    with dst.connect() as conn:
        for name, expected in copied.items():
            actual = conn.scalar(select(func.count()).select_from(Base.metadata.tables[name]))
            assert actual == expected, f"{name}: {expected} kutilgan, {actual} ko'chgan"

    src.dispose()
    dst.dispose()


def test_sorted_tables_puts_parents_first():
    """sorted_tables aynan FK bog'liqligi tartibini beradi."""
    order = [t.name for t in Base.metadata.sorted_tables]
    for parent, child in (
        ("employees", "shifts"),
        ("employees", "sales"),
        ("clients", "sales"),
        ("sales", "sale_items"),
        ("products", "sale_items"),
        ("categories", "products"),
        ("suppliers", "supply_receipts"),
        ("shifts", "payments"),
    ):
        assert order.index(parent) < order.index(child), (
            f"{parent} {child} dan keyin turibdi - PostgreSQL da FK xatosi bo'ladi"
        )


def _run(env_extra, *args):
    import os

    env = {**os.environ, **env_extra}
    return subprocess.run(
        [sys.executable, "migrate_to_postgres.py", *args],
        cwd=str(BACKEND), env=env, capture_output=True, text=True, timeout=120,
    )


def test_script_refuses_a_non_postgres_target():
    r = _run({"DATABASE_URL": "sqlite+aiosqlite:///x.db"})
    assert r.returncode != 0
    assert "PostgreSQL" in (r.stdout + r.stderr)


def test_script_refuses_a_missing_source():
    r = _run({"DATABASE_URL": "postgresql://u:p@h:5432/d"}, "--source", "yoq-bunday-fayl.db")
    assert r.returncode != 0
    assert "topilmadi" in (r.stdout + r.stderr)


def test_script_refuses_a_source_without_the_utc_migration(tmp_path):
    """Migratsiya bajarilmagan bazani ko'chirish smena vaqtlarini buzardi."""
    stale = tmp_path / "eski.db"
    engine = create_engine(f"sqlite:///{stale}")
    with engine.begin() as conn:
        Base.metadata.create_all(conn)      # jadval bor, lekin belgi yo'q
    engine.dispose()

    r = _run({"DATABASE_URL": "postgresql://u:p@h:5432/d"}, "--source", str(stale))
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    assert database.SHIFT_UTC_MIGRATION in combined or "migratsiya" in combined.lower()
