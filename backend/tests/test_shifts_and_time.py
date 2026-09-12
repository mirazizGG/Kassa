"""Smena vaqtlari va UTC migratsiyasi bo'yicha testlar.

Bu joy hostingga ko'chishda eng xavfli edi: smena vaqtlari server LOKAL
soatida, sotuvlar esa UTC da yozilardi.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

import database
from utils.timezone import utc_now, day_start_utc, day_end_utc


def test_shift_is_stored_in_utc(client, auth):
    """Smena UTC da ochilishi kerak, server lokal soatida emas."""
    client.post("/pos/shifts/close", headers=auth, json={"closing_balance": 0, "note": "test"})
    r = client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    assert r.status_code == 200, r.text

    opened = datetime.fromisoformat(r.json()["opened_at"].replace("Z", ""))
    if opened.tzinfo is not None:
        opened = opened.astimezone(timezone.utc).replace(tzinfo=None)

    drift = abs((opened - utc_now()).total_seconds())
    assert drift < 120, (
        f"smena vaqti UTC dan {drift / 3600:.1f} soatga farq qiladi — "
        "server lokal vaqtida yozilayotgan bo'lishi mumkin"
    )


def test_shift_utc_migration_converts_once(tmp_path):
    """Ma'lumot migratsiyasi bir marta ishlashi va ikkinchi safar tegmasligi shart."""
    engine = create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with engine.begin() as conn:
        database.Base.metadata.create_all(conn)
        conn.execute(text(
            "INSERT INTO shifts (id, cashier_id, opening_balance, opened_at, closed_at, status) "
            "VALUES (1, 1, 0, '2026-09-07 13:00:00', '2026-09-07 21:00:00', 'closed')"
        ))

        database.migrate_shift_times_to_utc(conn)
        after = conn.execute(text("SELECT opened_at, closed_at FROM shifts WHERE id = 1")).first()
        assert str(after[0]).startswith("2026-09-07 08:00"), f"noto'g'ri o'tkazish: {after[0]}"
        assert str(after[1]).startswith("2026-09-07 16:00"), f"noto'g'ri o'tkazish: {after[1]}"

        # Takroriy ishga tushirish ma'lumotni yana surib yubormasligi kerak.
        database.migrate_shift_times_to_utc(conn)
        again = conn.execute(text("SELECT opened_at, closed_at FROM shifts WHERE id = 1")).first()
        assert again == after, "migratsiya ikkinchi marta ham ma'lumotni o'zgartirdi"

        marks = conn.execute(text(
            "SELECT count(*) FROM schema_migrations WHERE name = :n"
        ), {"n": database.SHIFT_UTC_MIGRATION}).scalar()
        assert marks == 1
    engine.dispose()


def test_shop_day_boundaries_are_converted_to_utc():
    """Do'kon kuni UTC oynasiga to'g'ri o'girilishi kerak (Toshkent = UTC+5)."""
    from datetime import date

    day = date(2026, 9, 7)
    start, end = day_start_utc(day), day_end_utc(day)

    assert start == datetime(2026, 9, 6, 19, 0, 0)
    assert end.replace(microsecond=0) == datetime(2026, 9, 7, 18, 59, 59)
    assert (end - start) < timedelta(days=1)


def test_expected_cash_counts_only_this_shift(client, auth):
    """Smena kassasi faqat SHU smenadagi sotuvlarni hisoblashi kerak."""
    client.post("/pos/shifts/close", headers=auth, json={"closing_balance": 0, "note": "reset"})

    p = client.post("/inventory/products", headers=auth, json={
        "name": "Smena tovari", "barcode": "TEST-SHIFT-1", "buy_price": 100.0,
        "sell_price": 500.0, "stock": 50.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }).json()

    assert client.post("/pos/shifts/open", headers=auth,
                       json={"opening_balance": 1000}).status_code == 200

    sale = client.post("/sales/", headers=auth, json={
        "total_amount": 1500.0, "payment_method": "cash",
        "items": [{"product_id": p["id"], "quantity": 3, "price": 500.0}],
        "cash_amount": 1500.0, "card_amount": 0, "transfer_amount": 0,
        "debt_amount": 0, "bonus_spent": 0,
    })
    assert sale.status_code == 200, sale.text

    active = client.get("/pos/shifts/active", headers=auth).json()
    assert active is not None, "ochiq smena topilmadi"
    assert active["total_cash"] == 1500.0, f"naqd noto'g'ri: {active['total_cash']}"
    assert active["expected_cash"] == 2500.0, (
        f"kutilgan kassa noto'g'ri: {active['expected_cash']} "
        "(1000 boshlang'ich + 1500 naqd sotuv)"
    )


def test_ensure_columns_upgrade_a_populated_old_table(tmp_path):
    """Jonli do'kon bazasida ustun qo'shish ma'lumotni yo'qotmasligi shart.

    Bu yerda ATAYIN eski sxema yaratamiz (yangi ustunlarsiz), unga satr
    yozamiz va migratsiyani ishlatamiz — xuddi serverdagi bazadek.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        # Eski sxema: yopilish hisobi ustunlari yo'q.
        conn.execute(text("""
            CREATE TABLE shifts (
                id INTEGER PRIMARY KEY,
                cashier_id INTEGER,
                opening_balance FLOAT,
                closing_balance FLOAT,
                opened_at DATETIME,
                closed_at DATETIME,
                status VARCHAR,
                note VARCHAR
            )
        """))
        conn.execute(text("""
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY,
                reason VARCHAR,
                category VARCHAR,
                amount FLOAT,
                created_at DATETIME,
                created_by INTEGER
            )
        """))
        conn.execute(text(
            "INSERT INTO shifts (id, cashier_id, opening_balance, closing_balance, "
            "opened_at, status, note) "
            "VALUES (7, 3, 50000, 61000, '2026-09-07 08:00:00', 'closed', 'eski smena')"
        ))
        conn.execute(text(
            "INSERT INTO expenses (id, reason, category, amount, created_at, created_by) "
            "VALUES (4, 'eski xarajat', 'Boshqa', 12000, '2026-09-07 09:00:00', 3)"
        ))

        database.ensure_shift_total_columns(conn)
        database.ensure_expense_columns(conn)
        # Ikkinchi marta ham xavfsiz bo'lishi kerak.
        database.ensure_shift_total_columns(conn)
        database.ensure_expense_columns(conn)

        shift_cols = {c["name"] for c in __import__("sqlalchemy").inspect(conn).get_columns("shifts")}
        for col in ("total_cash", "total_expenses", "expected_cash", "cash_difference", "closed_by"):
            assert col in shift_cols, f"ustun qo'shilmadi: {col}"

        row = conn.execute(text(
            "SELECT opening_balance, closing_balance, note FROM shifts WHERE id = 7"
        )).first()
        assert row[0] == 50000 and row[1] == 61000 and row[2] == "eski smena", (
            "migratsiya mavjud ma'lumotni buzdi"
        )

        exp = conn.execute(text(
            "SELECT amount, payment_method FROM expenses WHERE id = 4"
        )).first()
        assert exp[0] == 12000
        assert exp[1] == "cash", "eski xarajat naqd deb belgilanmadi"
    engine.dispose()


def test_alter_table_types_are_portable():
    """ALTER TABLE tiplarini dialektga moslash.

    `DATETIME` va `BOOLEAN DEFAULT 0` - SQLite yozuvi. PostgreSQL da bunday tip
    yo'q, shuning uchun keyingi ustun qo'shilganda serverda ilova ishga tushmay
    qolardi. Toza bazada bu ALTER lar ishlamaydi (create_all hamma ustunni
    yaratib bo'lgan), ya'ni xato darhol emas, keyinroq chiqadi - shuning uchun
    test kerak.
    """
    class _FakeDialect:
        def __init__(self, name):
            self.name = name

    class _FakeConn:
        def __init__(self, name):
            self.dialect = _FakeDialect(name)

    sqlite_conn = _FakeConn("sqlite")
    pg_conn = _FakeConn("postgresql")

    assert database._sql_type(sqlite_conn, "timestamp") == "DATETIME"
    assert database._sql_type(pg_conn, "timestamp") == "TIMESTAMP", (
        "PostgreSQL da DATETIME tipi yo'q"
    )

    assert database._sql_type(sqlite_conn, "bool_false") == "BOOLEAN DEFAULT 0"
    assert database._sql_type(pg_conn, "bool_false") == "BOOLEAN DEFAULT FALSE", (
        "PostgreSQL da 0 mantiqiy qiymat emas"
    )

    # Noma'lum dialekt ham SQLite emas, standart SQL olishi kerak.
    assert database._sql_type(_FakeConn("mysql"), "timestamp") == "TIMESTAMP"

    for kind in database._PORTABLE_TYPES:
        for conn in (sqlite_conn, pg_conn):
            assert database._sql_type(conn, kind), f"{kind} uchun tip yo'q"


def test_only_one_alter_table_statement_exists():
    """Barcha ustun qo'shishlar _add_column_if_missing orqali o'tsin."""
    import io
    from pathlib import Path

    src = io.open(Path(__file__).resolve().parent.parent / "database.py", encoding="utf-8").read()
    assert src.count("ADD COLUMN") == 1, (
        "ALTER TABLE to'g'ridan-to'g'ri yozilgan - dialekt tekshiruvini chetlab o'tadi"
    )


def test_timezone_is_configured_in_one_place():
    """Mintaqa faqat utils/timezone.py da bo'lishi kerak.

    Ilgari "Asia/Tashkent" finance.py, audit.py, pos.py va sales.py da qat'iy
    yozilgan edi: SHOP_TIMEZONE sozlamasi ularga ta'sir qilmasdi va "bugun"
    turli sahifalarda turli oraliqni bildirardi.
    """
    import io
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    offenders = []
    for path in backend.rglob("*.py"):
        if "utils/timezone.py" in path.as_posix() or "tests/" in path.as_posix():
            continue
        # Izohlarni hisobga olmaymiz - faqat KOD tekshiriladi.
        code = "\n".join(
            line for line in io.open(path, encoding="utf-8").read().split("\n")
            if not line.lstrip().startswith("#")
        )
        if 'ZoneInfo("Asia/Tashkent")' in code:
            offenders.append(path.relative_to(backend).as_posix())
    assert not offenders, f"mintaqa qat'iy yozilgan: {offenders}"


def test_filter_dates_use_the_shop_day():
    """Foydalanuvchi bergan sana DO'KON kuni chegaralariga o'girilsin."""
    from utils.timezone import parse_filter_date, day_start_utc, day_end_utc
    from datetime import date

    day = date(2026, 9, 7)
    assert parse_filter_date("2026-09-07") == day_start_utc(day)
    assert parse_filter_date("2026-09-07", end_of_day=True) == day_end_utc(day)
    assert parse_filter_date(None) is None
    assert parse_filter_date("axlat") is None
