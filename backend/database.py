# database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, Text, BigInteger, inspect, text
from datetime import datetime, timezone

import os
from dotenv import load_dotenv

from utils.timezone import utc_now

load_dotenv()

# Baza fayli nomi (sqlite)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# .env da `DATABASE_URL=` bo'sh qoldirilsa, os.getenv default emas, bo'sh satr
# qaytaradi va create_async_engine("") import paytida yiqiladi. Bo'shni
# "berilmagan" deb hisoblaymiz.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or (
    f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'market.db')}"
)

# Drayversiz "sqlite:///..." yozilsa, async engine uni ko'tara olmaydi va ilova
# import paytida yiqiladi. Sukut bo'yicha aiosqlite ni qo'shib qo'yamiz.
if DATABASE_URL.startswith("sqlite://") and "+aiosqlite" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)

# Render/Heroku postgres:// URLs require +asyncpg for SQLAlchemy async engine
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

from sqlalchemy import event

# SQLite setup differs from PostgreSQL
is_sqlite = DATABASE_URL.startswith("sqlite")

engine_args = {
    "echo": False,
    "pool_pre_ping": True
}

if is_sqlite:
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(DATABASE_URL, **engine_args)

if is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        # synchronous=FULL: pul bilan ishlaydigan tizimda tezlikdan ko'ra
        # ishonchlilik muhim. NORMAL da elektr o'chganda oxirgi tasdiqlangan
        # tranzaksiyalar (ya'ni allaqachon bo'lib bo'lingan sotuvlar) qaytib
        # ketishi mumkin edi: mijoz tovarni olib ketgan, pul kassada, lekin
        # bazada sotuv ham, qoldiq kamayishi ham yo'q.
        cursor.execute("PRAGMA synchronous=FULL")
        # SQLite tashqi kalitlarni SUKUT BO'YICHA majburlamaydi. Uni yoqmasak,
        # ishlab chiqish PostgreSQL dan boshqacha ishlaydi: bu yerda "o'tadigan"
        # o'chirish serverda IntegrityError bo'lib chiqardi.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# --- JADVALLAR (MODELS) ---

# 0. Xodimlar (Admin, Manager, Kassir)
class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String) # admin, manager, cashier
    permissions = Column(String) # "pos,stock,dashboard"
    is_active = Column(Boolean, default=True)
    # Qo'shimcha ma'lumotlar
    full_name = Column(String, nullable=True) # To'liq ism
    phone = Column(String, nullable=True) # Telefon raqami
    address = Column(String, nullable=True) # Manzil
    passport = Column(String, nullable=True) # Pasport seriyasi
    notes = Column(String, nullable=True) # Qo'shimcha izohlar
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True) # Telegram bot uchun
    session_token = Column(String, nullable=True)
    session_expires_at = Column(DateTime, nullable=True)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

# 1. Mahsulotlar (Sklad)
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) # Nomi
    barcode = Column(String, unique=True, index=True) # Shtrix kod
    buy_price = Column(Float) # Kelish narxi
    sell_price = Column(Float) # Sotish narxi
    stock = Column(Float, default=0) # Qoldiq
    is_infinite = Column(Boolean, default=False) # Cheksiz qoldiq (sotuvda kamaymaydi)
    unit = Column(String, default="dona") # dona, kg, litr
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_favorite = Column(Boolean, default=False) # Sevimli mahsulot (kassada yuqorida)

# 2. Mijozlar (Bot uchun)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    full_name = Column(String)
    phone = Column(String)
    bonus_balance = Column(Float, default=0) # Keshbek

# 7. Mijozlar (CRM) - Moved up for FK reference
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, nullable=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    balance = Column(Float, default=0) # Nasiya yoki oldindan to'lov
    bonus_balance = Column(Float, default=0) # Keshbek ballari
    debt_due_date = Column(DateTime, nullable=True) # Qarz qaytarish muddati
    created_at = Column(DateTime, default=utc_now)

# 3. Savdo Cheklari (Tarix)
class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=utc_now)
    total_amount = Column(Float) # Chek summasi
    payment_method = Column(String) # cash, plastic, card
    cashier_id = Column(Integer, ForeignKey("employees.id")) # Fix: Point to employees
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True) # Mijoz (optional)
    status = Column(String, default="completed") # completed, refunded
    
    # Split Payment Columns
    cash_amount = Column(Float, default=0)
    card_amount = Column(Float, default=0)
    transfer_amount = Column(Float, default=0)
    debt_amount = Column(Float, default=0)
    
    # Bonus Fields
    bonus_earned = Column(Float, default=0) # Ushbu savdodan to'plangan bonus
    bonus_spent = Column(Float, default=0) # Ushbu savdoda ishlatilgan bonus

    # Takroriy chekni oldini olish uchun kalit. Kassir "To'lash" tugmasini ikki
    # marta bossa yoki so'rov timeout bo'lib qayta yuborilsa, ilgari IKKITA chek
    # yozilardi: ombordan tovar ikki marta yechilib, kassaga ikki marta pul
    # tushgandek ko'rinardi. Endi bir xil kalitli ikkinchi so'rov yangi chek
    # yaratmaydi, birinchisini qaytaradi.
    idempotency_key = Column(String, unique=True, nullable=True, index=True)

    # Vozvrat QAYSI smenada qilingani. Pul jismonan o'sha smenaning kassasidan
    # chiqadi, shuning uchun smena hisobi buni bilishi kerak.
    #
    # Ilgari vozvrat na vaqtni, na smenani yozmasdi. compute_shift_totals faqat
    # smena oynasidagi sotuvlarni sanaydi, shuning uchun KECHAGI naqd sotuvni
    # bugun qaytarganda pul bugungi ящикdan chiqar, lekin bugungi smena bu
    # haqda bilmasdi: kassir aynan shu summaga kamomadda qolib, tizim o'zi
    # bilgan pul uchun tushuntirish xati yozardi.
    refunded_at = Column(DateTime, nullable=True)
    refund_shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True)
    
    # Relationships
    items = relationship("SaleItem", back_populates="sale")
    cashier = relationship("Employee")
    client = relationship("Client")

class SaleItem(Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Float) # Nechta?
    price = Column(Float) # Qanchadan sotildi?
    buy_price = Column(Float, nullable=True) # Sotuv paytidagi tannarx (foyda hisobi uchun snapshot)
    
    # Relationships
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")

# 5. Xarajatlar (Expenses)
class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    reason = Column(String) # Nomi
    category = Column(String, default="Boshqa") # Kategoriya: Ovqat, Firma...
    amount = Column(Float) # Summa
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    # Xarajat kassadan naqd chiqqanmi yoki bank orqali ketganmi. Faqat naqd
    # xarajat smena kassasidan ayiriladi.
    payment_method = Column(String, default="cash")  # cash, card, transfer
    # Qaysi smenada yozilgan (Payment kabi). Smena kassasini hisoblash uchun.
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True)
    creator = relationship("Employee")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("employees.id"))
    action = Column(String) # e.g., "Deleted Product", "Refunded Sale"
    details = Column(String) # JSON or description
    created_at = Column(DateTime, default=utc_now)

    user = relationship("Employee")

class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

# 6. Kirim (Supply History)
class Supply(Base):
    __tablename__ = "supplies"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Float)
    buy_price = Column(Float) # O'sha paytdagi kirim narxi
    created_at = Column(DateTime, default=utc_now)

class StockMove(Base):
    __tablename__ = "stock_moves"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Float) # Musbat (kirim) yoki manfiy (chiqim)
    type = Column(String) # sale, restock, refund, adjustment, audit
    reason = Column(String, nullable=True) # Izoh
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    product = relationship("Product")
    user = relationship("Employee")

# 7. Qarz To'lovlari (Payment History)
class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    amount = Column(Float) # To'langan summa
    payment_method = Column(String, default="cash") # cash, terminal, transfer
    note = Column(String, nullable=True) # Izoh
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=True) # Qaysi smenada qabul qilingan

    # Relationships
    client = relationship("Client")
    employee = relationship("Employee")

# 8. Kassir Smenasi (Cashier Shifts)
class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, index=True)
    cashier_id = Column(Integer, ForeignKey("employees.id"))
    opening_balance = Column(Float, default=0) # Boshlanish kassadagi pul
    closing_balance = Column(Float, nullable=True) # Yopilgandagi kassadagi pul
    opened_at = Column(DateTime, default=utc_now)
    closed_at = Column(DateTime, nullable=True)
    status = Column(String, default="open") # open, closed
    note = Column(String, nullable=True) # Izoh

    # --- Yopilish paytida MUZLATILGAN hisob-kitob ---
    # Ilgari smena hisobi har so'rovda jonli sotuvlardan qayta hisoblanardi.
    # Ya'ni yopilgandan keyin qilingan vozvrat o'tgan smenaning kamomadini
    # o'zgartirib yuborardi: kassir imzolagan raqam bilan hisobotdagi raqam
    # bir xil bo'lmay qolardi. Endi yopilishda hisob shu ustunlarga yoziladi
    # va boshqa hech qachon o'zgarmaydi.
    total_cash = Column(Float, nullable=True)
    total_card = Column(Float, nullable=True)
    total_transfer = Column(Float, nullable=True)
    total_debt = Column(Float, nullable=True)
    total_expenses = Column(Float, nullable=True)   # smenada kassadan chiqqan naqd
    total_refunds = Column(Float, nullable=True)    # smenada kassadan berilgan naqd vozvrat
    expected_cash = Column(Float, nullable=True)
    cash_difference = Column(Float, nullable=True)  # haqiqiy - kutilgan
    closed_by = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Relationships
    cashier = relationship("Employee", foreign_keys=[cashier_id])
    closer = relationship("Employee", foreign_keys=[closed_by])

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    status = Column(String) # "in", "out"
    created_at = Column(DateTime, default=utc_now)
    note = Column(String, nullable=True)

    employee = relationship("Employee")

# 9. Vazifalar (Tasks for Employees)
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String, nullable=True)
    status = Column(String, default="pending") # pending, in_progress, completed
    assigned_to = Column(Integer, ForeignKey("employees.id"))
    created_by = Column(Integer, ForeignKey("employees.id"))
    created_at = Column(DateTime, default=utc_now)
    due_date = Column(DateTime, nullable=True)

    # Relationships
    assignee = relationship("Employee", foreign_keys=[assigned_to])
    creator = relationship("Employee", foreign_keys=[created_by])

# 11. Firmalar (Suppliers)
class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    balance = Column(Float, default=0) # Qancha qarzimiz bor (musbat bo'lsa qarzmiz, manfiy bo'lsa haqimiz)
    created_at = Column(DateTime, default=utc_now)

class SupplyReceipt(Base):
    __tablename__ = "supply_receipts"
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    total_amount = Column(Float) # Jami kelgan mol summasi
    invoice_image = Column(String, nullable=True) # Nakladnoy rasmi yo'li
    date = Column(DateTime, default=utc_now)
    note = Column(String, nullable=True)
    
    supplier = relationship("Supplier")

class SupplierPayment(Base):
    __tablename__ = "supplier_payments"
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    amount = Column(Float) # To'langan summa
    payment_method = Column(String, default="cash") # cash, card, transfer
    date = Column(DateTime, default=utc_now)
    note = Column(String, nullable=True)
    
    supplier = relationship("Supplier")

# Do'kon Sozlamalari (Store Settings)
class StoreSetting(Base):
    __tablename__ = "store_settings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Mening Do'konim")
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    header_text = Column(String, nullable=True) # Check tepasidagi yozuv
    footer_text = Column(String, nullable=True) # Check pastidagi yozuv
    logo_url = Column(String, nullable=True)
    low_stock_threshold = Column(Integer, default=5)
    
    # New V2 Settings
    bonus_percentage = Column(Float, default=1.0) # Har bir xarid uchun necha % bonus (1% default)
    debt_reminder_days = Column(Integer, default=3) # To'lov muddatidan necha kun oldin eslatish

class SchemaMigration(Base):
    """Bir marta bajarilishi kerak bo'lgan ma'lumot migratsiyalari ro'yxati.

    Ustun qo'shish (ensure_* funksiyalari) idempotent — ularni har safar
    ishlatish xavfsiz. Ammo MA'LUMOTNI o'zgartiradigan migratsiya (masalan
    vaqtlarni UTC ga ko'chirish) ikki marta ishlasa ma'lumotni buzadi.
    Shuning uchun bajarilganlari shu jadvalda belgilanadi.
    """
    __tablename__ = "schema_migrations"
    name = Column(String, primary_key=True)
    applied_at = Column(DateTime, default=utc_now)


def _migration_applied(sync_connection, name: str) -> bool:
    row = sync_connection.execute(
        text("SELECT 1 FROM schema_migrations WHERE name = :name"), {"name": name}
    ).first()
    return row is not None


def _mark_migration(sync_connection, name: str) -> None:
    sync_connection.execute(
        text("INSERT INTO schema_migrations (name, applied_at) VALUES (:name, :ts)"),
        {"name": name, "ts": utc_now()},
    )


# Do'kon Toshkentda: UTC+5, yozgi/qishki o'tish yo'q.
TASHKENT_UTC_OFFSET_HOURS = 5
SHIFT_UTC_MIGRATION = "2026_09_shift_times_to_utc"


def migrate_shift_times_to_utc(sync_connection):
    """Smena vaqtlarini SERVER LOKAL vaqtidan UTC ga ko'chiradi.

    Ilgari Shift.opened_at/closed_at `datetime.now()` bilan, ya'ni serverning
    lokal vaqtida yozilardi, qolgan hamma jadval esa UTC da. pos.py ikkalasini
    "Asia/Tashkent" deb qat'iy belgilangan ko'prik orqali solishtirardi. Bu
    faqat server soati Toshkentda bo'lgandagina to'g'ri ishlaydi — hostingga
    ko'chganda (odatda UTC) smena oynasi 5 soatga surilib, kassa hisobiga
    boshqa smenaning sotuvlari qo'shilib ketardi.

    Endi smena vaqtlari ham UTC da yoziladi va ko'prik olib tashlandi. Bazadagi
    ESKI satrlar hali lokal vaqtda — ularni shu yerda bir marta ko'chiramiz.
    """
    if _migration_applied(sync_connection, SHIFT_UTC_MIGRATION):
        return

    hours = TASHKENT_UTC_OFFSET_HOURS
    if sync_connection.dialect.name == "sqlite":
        sync_connection.exec_driver_sql(
            f"UPDATE shifts SET opened_at = datetime(opened_at, '-{hours} hours') "
            "WHERE opened_at IS NOT NULL"
        )
        sync_connection.exec_driver_sql(
            f"UPDATE shifts SET closed_at = datetime(closed_at, '-{hours} hours') "
            "WHERE closed_at IS NOT NULL"
        )
    else:
        sync_connection.exec_driver_sql(
            f"UPDATE shifts SET opened_at = opened_at - INTERVAL '{hours} hours' "
            "WHERE opened_at IS NOT NULL"
        )
        sync_connection.exec_driver_sql(
            f"UPDATE shifts SET closed_at = closed_at - INTERVAL '{hours} hours' "
            "WHERE closed_at IS NOT NULL"
        )

    _mark_migration(sync_connection, SHIFT_UTC_MIGRATION)


# Bazani yaratish funksiyasi
def ensure_employee_session_columns(sync_connection):
    _add_column_if_missing(sync_connection, "employees", "session_token", "text")
    _add_column_if_missing(sync_connection, "employees", "session_expires_at", "timestamp")


def ensure_sale_item_columns(sync_connection):
    columns = {column["name"] for column in inspect(sync_connection).get_columns("sale_items")}
    if "buy_price" not in columns:
        _add_column_if_missing(sync_connection, "sale_items", "buy_price", "float")
        # Eski satrlar uchun hozirgi tannarxni boshlang'ich qiymat sifatida yozamiz.
        sync_connection.exec_driver_sql(
            "UPDATE sale_items SET buy_price = ("
            "SELECT products.buy_price FROM products WHERE products.id = sale_items.product_id"
            ") WHERE buy_price IS NULL"
        )


# ALTER TABLE uchun ko'chma tiplar.
#
# `DATETIME` va `BOOLEAN DEFAULT 0` - SQLite yozuvi; PostgreSQL da bunday tip yo'q
# va `0` mantiqiy qiymat emas. Toza bazada bu `ALTER` lar umuman ishlamaydi
# (create_all hamma ustunni yaratib bo'lgan), shuning uchun bugun sezilmaydi -
# lekin KEYINGI ustun qo'shilganda serverda ilova ishga tushmay qoladi.
_PORTABLE_TYPES = {
    "text":       {"sqlite": "VARCHAR",            "default": "TEXT"},
    "int":        {"sqlite": "INTEGER",            "default": "INTEGER"},
    "float":      {"sqlite": "FLOAT",              "default": "DOUBLE PRECISION"},
    "timestamp":  {"sqlite": "DATETIME",           "default": "TIMESTAMP"},
    "bool_false": {"sqlite": "BOOLEAN DEFAULT 0",  "default": "BOOLEAN DEFAULT FALSE"},
}


def _sql_type(sync_connection, kind: str) -> str:
    """Mantiqiy tip nomini joriy dialektning DDL tipiga o'giradi."""
    variants = _PORTABLE_TYPES[kind]
    return variants.get(sync_connection.dialect.name, variants["default"])


def _add_column_if_missing(sync_connection, table: str, column: str, kind: str) -> None:
    """Ustun bo'lmasa qo'shadi. `kind` - _PORTABLE_TYPES dagi mantiqiy nom."""
    columns = {c["name"] for c in inspect(sync_connection).get_columns(table)}
    if column not in columns:
        ddl_type = _sql_type(sync_connection, kind)
        sync_connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def ensure_sale_idempotency_column(sync_connection):
    _add_column_if_missing(sync_connection, "sales", "idempotency_key", "text")
    # Unique indeks NULL larni cheklamaydi (ham SQLite, ham PostgreSQL) —
    # kalitsiz eski cheklar bemalol yashayveradi.
    sync_connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_idempotency_key "
        "ON sales (idempotency_key)"
    )


def ensure_sale_refund_columns(sync_connection):
    """Vozvrat qaysi smenada bo'lganini saqlash uchun ustunlar."""
    _add_column_if_missing(sync_connection, "sales", "refunded_at", "timestamp")
    _add_column_if_missing(sync_connection, "sales", "refund_shift_id", "int")


def ensure_shift_total_columns(sync_connection):
    """Smena yopilganda muzlatiladigan hisob ustunlari."""
    for column in ("total_cash", "total_card", "total_transfer", "total_debt",
                   "total_expenses", "total_refunds", "expected_cash", "cash_difference"):
        _add_column_if_missing(sync_connection, "shifts", column, "float")
    _add_column_if_missing(sync_connection, "shifts", "closed_by", "int")


def ensure_expense_columns(sync_connection):
    """Xarajatni smenaga va to'lov usuliga bog'lash."""
    _add_column_if_missing(sync_connection, "expenses", "payment_method", "text")
    _add_column_if_missing(sync_connection, "expenses", "shift_id", "int")
    # Eski satrlar naqd deb hisoblanadi — do'konda xarajat odatda kassadan olinadi.
    sync_connection.exec_driver_sql(
        "UPDATE expenses SET payment_method = 'cash' WHERE payment_method IS NULL"
    )


def ensure_product_columns(sync_connection):
    _add_column_if_missing(sync_connection, "products", "is_infinite", "bool_false")


# Hisobot va smena so'rovlari aynan shu ustunlar bo'yicha filtrlaydi. Ular
# indekssiz bo'lgani uchun har bir dashboard/hisobot butun jadvalni skanerlardi.
# "CREATE INDEX IF NOT EXISTS" ham SQLite'da, ham PostgreSQL'da ishlaydi.
_INDEXES = (
    ("ix_sales_created_at", "sales (created_at)"),
    ("ix_sales_cashier_created", "sales (cashier_id, created_at)"),
    ("ix_sales_status_created", "sales (status, created_at)"),
    ("ix_sales_client_id", "sales (client_id)"),
    ("ix_sales_refund_shift", "sales (refund_shift_id)"),
    ("ix_sale_items_sale_id", "sale_items (sale_id)"),
    ("ix_sale_items_product_id", "sale_items (product_id)"),
    ("ix_shifts_cashier_status", "shifts (cashier_id, status)"),
    ("ix_shifts_opened_at", "shifts (opened_at)"),
    ("ix_payments_client_id", "payments (client_id)"),
    ("ix_payments_shift_id", "payments (shift_id)"),
    ("ix_stock_moves_product_id", "stock_moves (product_id)"),
    ("ix_stock_moves_created_at", "stock_moves (created_at)"),
    ("ix_audit_logs_created_at", "audit_logs (created_at)"),
    ("ix_audit_logs_user_id", "audit_logs (user_id)"),
    ("ix_expenses_created_at", "expenses (created_at)"),
    ("ix_expenses_created_by", "expenses (created_by)"),
    ("ix_expenses_shift_id", "expenses (shift_id)"),
    ("ix_attendance_employee_id", "attendance (employee_id)"),
    ("ix_attendance_created_at", "attendance (created_at)"),
    ("ix_supply_receipts_supplier_id", "supply_receipts (supplier_id)"),
    ("ix_supplier_payments_supplier_id", "supplier_payments (supplier_id)"),
    ("ix_supplies_product_id", "supplies (product_id)"),
    # Dashboard'dagi "kam qolgan" va katalog tartibi uchun.
    ("ix_products_stock", "products (stock)"),
    ("ix_products_category_id", "products (category_id)"),
    ("ix_clients_balance", "clients (balance)"),
)


def ensure_indexes(sync_connection):
    for name, target in _INDEXES:
        sync_connection.exec_driver_sql(
            f"CREATE INDEX IF NOT EXISTS {name} ON {target}"
        )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_employee_session_columns)
        await conn.run_sync(ensure_sale_item_columns)
        await conn.run_sync(ensure_product_columns)
        await conn.run_sync(ensure_sale_idempotency_column)
        await conn.run_sync(ensure_sale_refund_columns)
        await conn.run_sync(ensure_shift_total_columns)
        await conn.run_sync(ensure_expense_columns)
        await conn.run_sync(ensure_indexes)
        await conn.run_sync(migrate_shift_times_to_utc)

async def get_db():
    async with SessionLocal() as db:
        yield db