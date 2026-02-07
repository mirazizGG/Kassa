# database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from datetime import datetime, timezone

import os
from dotenv import load_dotenv

load_dotenv()

# Baza fayli nomi (sqlite)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'market.db')}")

from sqlalchemy import event

engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
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
    telegram_id = Column(Integer, unique=True, nullable=True, index=True) # Telegram bot uchun

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
    unit = Column(String, default="dona") # dona, kg, litr
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_favorite = Column(Boolean, default=False) # Sevimli mahsulot (kassada yuqorida)

# 2. Mijozlar (Bot uchun)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    full_name = Column(String)
    phone = Column(String)
    bonus_balance = Column(Float, default=0) # Keshbek

# 7. Mijozlar (CRM) - Moved up for FK reference
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, nullable=True)
    telegram_id = Column(Integer, unique=True, nullable=True, index=True)
    balance = Column(Float, default=0) # Nasiya yoki oldindan to'lov
    bonus_balance = Column(Float, default=0) # Keshbek ballari
    debt_due_date = Column(DateTime, nullable=True) # Qarz qaytarish muddati
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# 3. Savdo Cheklari (Tarix)
class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    creator = relationship("Employee")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("employees.id"))
    action = Column(String) # e.g., "Deleted Product", "Refunded Sale"
    details = Column(String) # JSON or description
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class StockMove(Base):
    __tablename__ = "stock_moves"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Float) # Musbat (kirim) yoki manfiy (chiqim)
    type = Column(String) # sale, restock, refund, adjustment, audit
    reason = Column(String, nullable=True) # Izoh
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
    opened_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime, nullable=True)
    status = Column(String, default="open") # open, closed
    note = Column(String, nullable=True) # Izoh

    # Relationships
    cashier = relationship("Employee")

# 9. Vazifalar (Tasks for Employees)
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String, nullable=True)
    status = Column(String, default="pending") # pending, in_progress, completed
    assigned_to = Column(Integer, ForeignKey("employees.id"))
    created_by = Column(Integer, ForeignKey("employees.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SupplyReceipt(Base):
    __tablename__ = "supply_receipts"
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    total_amount = Column(Float) # Jami kelgan mol summasi
    invoice_image = Column(String, nullable=True) # Nakladnoy rasmi yo'li
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    note = Column(String, nullable=True)
    
    supplier = relationship("Supplier")

class SupplierPayment(Base):
    __tablename__ = "supplier_payments"
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    amount = Column(Float) # To'langan summa
    payment_method = Column(String, default="cash") # cash, card, transfer
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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

# Bazani yaratish funksiyasi
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with SessionLocal() as db:
        yield db