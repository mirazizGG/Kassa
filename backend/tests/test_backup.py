"""Zahira nusxa mexanizmi bo'yicha testlar.

Audit ikkita jiddiy kamchilik topgan edi:
  1) nusxa har sotuvdan keyin olinib, retention oynasini "oxirgi 30 ta sotuv"
     ga qisqartirardi va kunlik nusxalarni o'chirib yuborardi;
  2) baza yo'li qat'iy `backend/market.db` edi va DATABASE_URL o'qilmasdi —
     boshqa bazada ishlayotgan tizim bo'sh fayldan nusxa olib, "muvaffaqiyatli"
     deb javob berardi.
"""
import io
import sqlite3

import pytest

from utils import backup as bk


def test_sale_does_not_trigger_a_backup():
    """create_backup() sotuv yo'lidan olib tashlanganini qat'iy tekshiramiz."""
    src = io.open("routers/sales.py", encoding="utf-8").read()
    assert "create_backup" not in src, (
        "sotuv yo'lida yana zahira nusxa paydo bo'ldi — retention oynasi "
        "'oxirgi 30 ta sotuv' ga qisqaradi"
    )


def test_sqlite_path_follows_database_url(monkeypatch, tmp_path):
    target = tmp_path / "boshqa.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{target.as_posix()}")
    assert bk._sqlite_path() == target, "DATABASE_URL e'tiborga olinmadi"


def test_postgres_url_is_detected_and_normalised(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://kassa:pw@localhost:5432/kassa")
    assert bk.is_postgres() is True
    assert bk._libpq_url() == "postgresql://kassa:pw@localhost:5432/kassa", (
        "pg_dump drayver qo'shimchasi bilan URL ni tushunmaydi"
    )

    monkeypatch.setenv("DATABASE_URL", "postgres://kassa:pw@localhost/kassa")
    assert bk.is_postgres() is True
    assert bk._libpq_url().startswith("postgresql://")


def test_sqlite_backup_is_a_real_readable_copy(monkeypatch, tmp_path):
    db = tmp_path / "src.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.execute("INSERT INTO t (v) VALUES ('muhim ma''lumot')")
    con.commit()
    con.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db.as_posix()}")
    monkeypatch.setattr(bk, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setenv("BACKUP_MIRROR_DIR", "")
    monkeypatch.setattr(bk, "BACKUP_MIRROR_DIR", "")

    path = bk.create_backup()
    assert path, "nusxa olinmadi"

    restored = sqlite3.connect(path)
    assert restored.execute("SELECT v FROM t").fetchone()[0] == "muhim ma'lumot"
    restored.close()


def test_retention_keeps_newest_and_covers_both_formats(monkeypatch, tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    monkeypatch.setattr(bk, "BACKUP_DIR", d)

    made = []
    for i in range(6):
        suffix = ".db" if i % 2 == 0 else ".dump"
        f = d / f"backup_2026090{i}_000000{suffix}"
        f.write_bytes(b"x")
        import os as _os
        _os.utime(f, (1_700_000_000 + i * 60, 1_700_000_000 + i * 60))
        made.append(f)

    bk.clean_old_backups(limit=2)
    left = sorted(p.name for p in d.glob(bk.BACKUP_GLOB))
    assert len(left) == 2, f"retention ishlamadi: {left}"
    assert left == sorted(p.name for p in made[-2:]), (
        f"eng yangilari emas, boshqalari qoldi: {left} "
        "(.dump fayllari glob'ga tushmayotgan bo'lishi mumkin)"
    )


def test_upload_dir_is_anchored_not_cwd_relative():
    """Yo'l modul joylashuviga bog'langan bo'lishi kerak.

    Ilgari `"uploads"` deb yozilgani uchun ilovani repo ildizidan ishga
    tushirish yetardi: yangi bo'sh papka yaratilib, oldin yuklangan hamma
    nakladnoy 404 bo'lib qolardi.
    """
    from pathlib import Path

    assert bk.UPLOAD_DIR.is_absolute(), "UPLOAD_DIR nisbiy yo'l"
    assert bk.UPLOAD_DIR.name == "uploads"
    assert bk.UPLOAD_DIR.parent == Path(bk.BASE_DIR)

    src = io.open("routers/suppliers.py", encoding="utf-8").read()
    assert 'os.path.join("uploads"' not in src, "suppliers.py yana nisbiy yo'lga qaytdi"
    main_src = io.open("main.py", encoding="utf-8").read()
    assert 'StaticFiles(directory="uploads")' not in main_src, "main.py nisbiy yo'lda qoldi"


def test_uploads_are_archived_for_backup(monkeypatch, tmp_path):
    """Nakladnoy fayllari baza dumpiga kirmaydi - alohida arxiv bo'lishi shart."""
    import tarfile

    uploads = tmp_path / "uploads" / "invoices"
    uploads.mkdir(parents=True)
    (uploads / "nakladnoy.png").write_bytes(b"\x89PNG rasm")

    monkeypatch.setattr(bk, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(bk, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(bk, "BACKUP_MIRROR_DIR", "")

    path = bk.create_uploads_archive()
    assert path, "arxiv yaratilmadi"

    with tarfile.open(path, "r:gz") as tar:
        names = tar.getnames()
    assert any(n.endswith("nakladnoy.png") for n in names), f"fayl arxivga kirmadi: {names}"


def test_no_uploads_means_no_archive(monkeypatch, tmp_path):
    empty = tmp_path / "uploads"
    empty.mkdir()
    monkeypatch.setattr(bk, "UPLOAD_DIR", empty)
    monkeypatch.setattr(bk, "BACKUP_DIR", tmp_path / "backups")
    assert bk.create_uploads_archive() is None


def test_database_and_upload_retention_do_not_delete_each_other(monkeypatch, tmp_path):
    """Ikki xil glob bir-birining fayllarini o'chirib yubormasin."""
    import os as _os

    d = tmp_path / "backups"
    d.mkdir()
    monkeypatch.setattr(bk, "BACKUP_DIR", d)

    for i in range(4):
        for name in (f"backup_2026090{i}_000000.db", f"uploads_2026090{i}_000000.tar.gz"):
            f = d / name
            f.write_bytes(b"x")
            _os.utime(f, (1_700_000_000 + i * 60, 1_700_000_000 + i * 60))

    bk.clean_old_backups(limit=2)
    bk._clean_old_uploads_archives(limit=2)

    assert len(list(d.glob(bk.BACKUP_GLOB))) == 2
    assert len(list(d.glob(bk.UPLOAD_ARCHIVE_GLOB))) == 2, (
        "baza retention'i nakladnoy arxivlarini o'chirib yubordi"
    )
