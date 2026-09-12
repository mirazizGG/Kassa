"""SQLite (market.db) -> PostgreSQL ma'lumot ko'chirish.

Nima uchun alohida skript kerak
-------------------------------
`DATABASE_URL` ni PostgreSQL ga o'zgartirib qo'yish YETARLI EMAS: ilova bo'sh
bazada ishga tushadi, o'ziga yangi `miraziz` yaratadi va do'kon tovarsiz,
mijozsiz, qarzsiz va tarixsiz ochiladi. Haqiqiy ma'lumot market.db da qolib
ketadi.

Ishlatish
---------
    # 1. AVVAL nusxa oling
    cp backend/market.db backend/market.db.kochirishdan-oldin

    # 2. Quruq yurish (hech narsa yozilmaydi) - nima ko'chishini ko'rsatadi
    cd backend
    DATABASE_URL="postgresql://kassa:PAROL@localhost:5432/kassa" \
        python migrate_to_postgres.py --source market.db --dry-run

    # 3. Haqiqiy ko'chirish
    DATABASE_URL="postgresql://kassa:PAROL@localhost:5432/kassa" \
        python migrate_to_postgres.py --source market.db

Skript maqsadli bazaning BO'SH bo'lishini talab qiladi va oxirida har bir
jadval bo'yicha satrlar sonini solishtiradi.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, insert, inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from database import (  # noqa: E402
    Base,
    SHIFT_UTC_MIGRATION,
    ensure_employee_session_columns,
    ensure_expense_columns,
    ensure_indexes,
    ensure_product_columns,
    ensure_sale_idempotency_column,
    ensure_sale_item_columns,
    ensure_shift_total_columns,
)

BATCH = 500


def _normalise_pg(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _sqlite_url(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    if not p.exists():
        sys.exit(f"XATO: manba fayl topilmadi: {p}")
    return f"sqlite+aiosqlite:///{p.as_posix()}"


def _create_schema(sync_conn):
    """Maqsadli bazada sxemani yaratadi.

    DIQQAT: bu yerda `migrate_shift_times_to_utc` ATAYIN chaqirilmaydi. Manbadagi
    smena vaqtlari allaqachon UTC ga o'tkazilgan, va migratsiya belgisi
    `schema_migrations` jadvali bilan birga ko'chiriladi. Bu yerda ishlatsak,
    belgi ikki marta yozilib, birlamchi kalit buzilardi.
    """
    Base.metadata.create_all(sync_conn)
    ensure_employee_session_columns(sync_conn)
    ensure_sale_item_columns(sync_conn)
    ensure_product_columns(sync_conn)
    ensure_sale_idempotency_column(sync_conn)
    ensure_shift_total_columns(sync_conn)
    ensure_expense_columns(sync_conn)
    ensure_indexes(sync_conn)


def _reset_sequences(sync_conn):
    """Har bir jadvalning id ketma-ketligini eng katta id ga suradi.

    BU QADAM MAJBURIY. Satrlarni o'z id lari bilan ko'chirganda PostgreSQL ning
    ketma-ketliklari 1 da qolib ketadi, va birinchi yangi sotuv ham, mijoz ham
    "duplicate key" xatosi bilan yiqiladi.
    """
    moved = []
    for table in Base.metadata.sorted_tables:
        pk = list(table.primary_key.columns)
        if len(pk) != 1 or pk[0].name != "id":
            continue
        seq = sync_conn.execute(
            text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table.name}
        ).scalar()
        if not seq:
            continue
        new_val = sync_conn.execute(
            text(f"SELECT setval(:seq, COALESCE((SELECT MAX(id) FROM {table.name}), 1))"),
            {"seq": seq},
        ).scalar()
        moved.append((table.name, new_val))
    return moved


async def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite -> PostgreSQL ko'chirish")
    parser.add_argument("--source", default="market.db", help="SQLite fayli (default: market.db)")
    parser.add_argument("--dry-run", action="store_true", help="Hech narsa yozmaydi")
    args = parser.parse_args()

    dst_raw = os.getenv("DATABASE_URL", "").strip()
    if not dst_raw or "postgres" not in dst_raw:
        sys.exit(
            "XATO: DATABASE_URL PostgreSQL ga ishora qilishi kerak.\n"
            '  DATABASE_URL="postgresql://kassa:PAROL@localhost:5432/kassa" '
            "python migrate_to_postgres.py"
        )

    src_engine = create_async_engine(_sqlite_url(args.source))
    dst_engine = create_async_engine(_normalise_pg(dst_raw))

    print(f"Manba : {args.source}")
    print(f"Maqsad: {dst_raw.split('@')[-1]}")
    print()

    # --- 1. Manbada smena vaqtlari migratsiyasi bajarilganmi? ---------------
    async with src_engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        if "schema_migrations" not in tables:
            sys.exit(
                "XATO: manbada `schema_migrations` jadvali yo'q.\n"
                "Avval ilovani SQLite bilan BIR MARTA ishga tushiring - u sxemani\n"
                "yangilaydi va smena vaqtlarini UTC ga o'tkazadi. Shundan keyin ko'chiring."
            )
        applied = await conn.scalar(
            text("SELECT 1 FROM schema_migrations WHERE name = :n"),
            {"n": SHIFT_UTC_MIGRATION},
        )
        if not applied:
            sys.exit(
                f"XATO: manbada `{SHIFT_UTC_MIGRATION}` migratsiyasi bajarilmagan.\n"
                "Ilovani SQLite bilan bir marta ishga tushiring, keyin qayta urinib ko'ring.\n"
                "Aks holda smena vaqtlari mahalliy vaqtda qolib ketadi."
            )
        print(f"Manba tekshiruvi: `{SHIFT_UTC_MIGRATION}` bajarilgan.")

    # --- 2. Maqsadli bazada sxema ------------------------------------------
    if args.dry_run:
        print("Quruq yurish: sxema yaratilmaydi.\n")
    else:
        async with dst_engine.begin() as conn:
            await conn.run_sync(_create_schema)
        print("Maqsadli bazada sxema yaratildi.\n")

        # --- 3. Maqsad bo'shligini tekshiramiz -----------------------------
        async with dst_engine.connect() as conn:
            for table in Base.metadata.sorted_tables:
                count = await conn.scalar(select(func.count()).select_from(table))
                if count:
                    sys.exit(
                        f"XATO: maqsadli baza bo'sh emas - `{table.name}` da {count} ta satr bor.\n"
                        "Ko'chirish faqat toza bazaga bajariladi."
                    )

    # --- 4. Ko'chirish ------------------------------------------------------
    totals: list[tuple[str, int]] = []
    for table in Base.metadata.sorted_tables:      # FK tartibida: ota-onalar oldin
        async with src_engine.connect() as src:
            try:
                rows = (await src.execute(select(table))).mappings().all()
            except Exception as exc:               # noqa: BLE001
                print(f"  {table.name:24s} o'tkazib yuborildi (manbada yo'q): {exc}")
                continue

        if not rows:
            print(f"  {table.name:24s} 0")
            totals.append((table.name, 0))
            continue

        if not args.dry_run:
            payload = [dict(r) for r in rows]
            async with dst_engine.begin() as dst:
                for start in range(0, len(payload), BATCH):
                    await dst.execute(insert(table), payload[start:start + BATCH])

        print(f"  {table.name:24s} {len(rows)}")
        totals.append((table.name, len(rows)))

    if args.dry_run:
        print(f"\nQuruq yurish tugadi. Jami {sum(n for _, n in totals)} ta satr ko'chirilardi.")
        await src_engine.dispose()
        await dst_engine.dispose()
        return 0

    # --- 5. Ketma-ketliklarni surish ---------------------------------------
    print("\nid ketma-ketliklari surilmoqda...")
    async with dst_engine.begin() as conn:
        moved = await conn.run_sync(_reset_sequences)
    for name, val in moved:
        print(f"  {name:24s} -> {val}")

    # --- 6. Solishtirish ----------------------------------------------------
    print("\nTekshiruv (manba / maqsad):")
    ok = True
    async with dst_engine.connect() as conn:
        for name, expected in totals:
            table = Base.metadata.tables[name]
            actual = await conn.scalar(select(func.count()).select_from(table))
            if actual != expected:
                ok = False
            print(f"  {'OK ' if actual == expected else 'XATO'} {name:24s} {expected} / {actual}")

    await src_engine.dispose()
    await dst_engine.dispose()

    print()
    if ok:
        print("Ko'chirish muvaffaqiyatli tugadi.")
        print("Endi backend/.env dagi DATABASE_URL ni PostgreSQL ga o'zgartiring "
              "va ilovani qayta ishga tushiring.")
        return 0
    print("KO'CHIRISHDA FARQ BOR - maqsadli bazani ishlatmang, sababini aniqlang.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
