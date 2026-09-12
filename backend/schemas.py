from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Annotated
from datetime import datetime
import re

# Lenient Regex for phone numbers to support any legacy data
PHONE_REGEX = r"^(\+)?\d{3,20}$"
# Barcode: lenient to support manual entries and various formats
BARCODE_REGEX = r"^[a-zA-Z0-9-]{1,30}$"

# --- AUTH SCHEMAS ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    permissions: str
    username: str
    user_id: Optional[int] = None

class TokenData(BaseModel):
    username: Optional[str] = None

# --- EMPLOYEE SCHEMAS ---
class EmployeeBase(BaseModel):
    username: str
    role: str
    permissions: str = "pos"
    full_name: Optional[str] = None
    phone: Optional[str] = Field(None, pattern=PHONE_REGEX, description="Phone format: +998901234567")
    address: Optional[str] = None
    passport: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True

class EmployeeCreate(EmployeeBase):
    password: str

class EmployeeUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    passport: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class EmployeeOut(EmployeeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- INVENTORY SCHEMAS ---
class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ProductBase(BaseModel):
    name: str
    barcode: Optional[str] = Field(None, description="Standard barcode 8-14 digits")
    buy_price: float = Field(ge=0, allow_inf_nan=False)
    sell_price: float = Field(ge=0, allow_inf_nan=False)
    stock: float = Field(default=0, allow_inf_nan=False)
    is_infinite: bool = False
    unit: str = "dona"
    category_id: Optional[int] = None
    is_favorite: bool = False

class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    """Tahrirlashda qoldiq uchun optimistik qulf.

    Tahrirlash oynasi ochilganda qoldiq nechta bo'lgani `expected_stock` da
    yuboriladi. Oyna ochiq turganda tovar sotilgan bo'lsa, saqlash 409 bilan
    rad etiladi. Ilgari forma yuklangan paytdagi eski qoldiqni QAYTA yozib,
    oradagi sotuvlarni bekor qilardi va omborga "adjustment" deb yolg'on
    tuzatish yozardi.
    """
    expected_stock: Optional[float] = Field(default=None, allow_inf_nan=False)

class ProductOut(ProductBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class StockMoveBase(BaseModel):
    product_id: Optional[int] = None
    quantity: float
    type: str
    reason: Optional[str] = None

class StockMoveOut(StockMoveBase):
    id: int
    created_at: datetime
    created_by: Optional[int] = None
    product: Optional[ProductOut] = None
    model_config = ConfigDict(from_attributes=True)

class SupplyBase(BaseModel):
    product_id: int
    # Manfiy/NaN kirim qoldiqni ham, tannarxni ham buzardi: tannarx
    # SaleItem.buy_price ga muzlatilgani uchun keyin tuzatish eski cheklarni
    # tiklamaydi.
    quantity: float = Field(gt=0, allow_inf_nan=False)
    buy_price: float = Field(ge=0, allow_inf_nan=False)

class SupplyCreate(SupplyBase):
    pass

class SupplyOut(SupplyBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- CRM SCHEMAS ---
class ClientBase(BaseModel):
    name: str
    phone: Optional[str] = Field(None, pattern=PHONE_REGEX)
    telegram_id: Optional[int] = None
    balance: float = 0
    bonus_balance: float = 0
    debt_due_date: Optional[datetime] = None

class ClientCreate(BaseModel):
    # DIQQAT: balance va bonus_balance ATAYIN yo'q. Ular ClientBase'da bor va
    # avval ClientCreate ularni meros qilib olardi — natijada istalgan xodim
    # POST /crm/clients bilan o'ziga bonus "chizib" olib, kassada pul o'rnida
    # sarflay olardi. Balans faqat sotuv/to'lov orqali o'zgaradi.
    name: str
    phone: Optional[str] = Field(None, pattern=PHONE_REGEX)
    telegram_id: Optional[int] = None
    debt_due_date: Optional[datetime] = None

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = Field(None, pattern=PHONE_REGEX)
    telegram_id: Optional[int] = None
    debt_due_date: Optional[datetime] = None

class ClientOut(ClientBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- POS SCHEMAS ---
class SaleItemBase(BaseModel):
    product_id: int
    # allow_inf_nan=False: NaN/inf REAL ustunni NULL ga aylantirib, keyin butun
    # ro'yxat endpointini 500 ga olib borardi.
    quantity: float = Field(gt=0, allow_inf_nan=False)
    price: float = Field(gt=0, allow_inf_nan=False)

class SaleItemOut(SaleItemBase):
    id: int
    product: Optional[ProductOut] = None
    model_config = ConfigDict(from_attributes=True)

class SaleCreate(BaseModel):
    total_amount: float = Field(gt=0, allow_inf_nan=False)
    payment_method: str
    client_id: Optional[int] = None
    items: List[SaleItemBase] = Field(min_length=1)

    # Optional split payment amounts
    cash_amount: float = Field(default=0, ge=0, allow_inf_nan=False)
    card_amount: float = Field(default=0, ge=0, allow_inf_nan=False)
    transfer_amount: float = Field(default=0, ge=0, allow_inf_nan=False)
    debt_amount: float = Field(default=0, ge=0, allow_inf_nan=False)
    bonus_spent: float = Field(default=0, ge=0, allow_inf_nan=False)
    manager_username: Optional[str] = None
    manager_password: Optional[str] = None
    # Takroriy yuborishdan himoya (yuqoridagi Sale.idempotency_key ga qarang).
    idempotency_key: Optional[str] = Field(default=None, max_length=64)

class RefundApproval(BaseModel):
    manager_username: str
    manager_password: str


class StockReturn(BaseModel):
    quantity: float = Field(gt=0)
    reason: str = Field(min_length=3, max_length=300)

class SaleOut(BaseModel):
    id: int
    created_at: datetime
    total_amount: float
    payment_method: str
    cashier_id: int
    cashier: Optional[EmployeeOut] = None
    client_id: Optional[int] = None
    client: Optional[ClientOut] = None
    status: str
    cash_amount: float = 0
    card_amount: float = 0
    transfer_amount: float = 0
    debt_amount: float = 0
    bonus_earned: float = 0
    bonus_spent: float = 0
    items: List[SaleItemOut] = []
    model_config = ConfigDict(from_attributes=True)

class ShiftOpen(BaseModel):
    opening_balance: float = Field(ge=0, allow_inf_nan=False)
    note: Optional[str] = None

class ShiftClose(BaseModel):
    closing_balance: float = Field(ge=0, allow_inf_nan=False)
    note: Optional[str] = None

class ShiftOut(BaseModel):
    id: int
    cashier_id: int
    cashier: Optional[EmployeeOut] = None
    opening_balance: float
    closing_balance: Optional[float] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    status: str
    note: Optional[str] = None
    total_cash: Optional[float] = 0
    total_card: Optional[float] = 0
    total_transfer: Optional[float] = 0
    total_debt: Optional[float] = 0
    total_expenses: Optional[float] = 0
    total_refunds: Optional[float] = 0
    expected_cash: Optional[float] = 0
    cash_difference: Optional[float] = None
    closed_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

# --- FINANCE SCHEMAS ---
class ExpenseBase(BaseModel):
    reason: str
    category: str = "Boshqa"
    amount: float = Field(gt=0, allow_inf_nan=False, description="Xarajat summasi musbat bo'lishi kerak")
    # Faqat naqd xarajat smena kassasidan ayiriladi.
    payment_method: str = "cash"

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseUpdate(BaseModel):
    """Xato yozilgan xarajatni tuzatish. Berilgan maydonlargina o'zgaradi."""
    reason: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    payment_method: Optional[str] = None


class ExpenseOut(ExpenseBase):
    id: int
    created_at: datetime
    created_by: Optional[int] = None
    creator: Optional[EmployeeOut] = None
    model_config = ConfigDict(from_attributes=True)

class PaymentCreate(BaseModel):
    amount: float = Field(gt=0, allow_inf_nan=False, description="To'lov summasi musbat bo'lishi kerak")
    payment_method: str = "cash"
    note: Optional[str] = None
    client_id: int

# --- TASK SCHEMAS ---
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "pending"
    assigned_to: int
    due_date: Optional[datetime] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None

class TaskOut(TaskBase):
    id: int
    created_at: datetime
    created_by: int
    model_config = ConfigDict(from_attributes=True)

# --- SETTINGS SCHEMAS ---
class StoreSettingBase(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    logo_url: Optional[str] = None
    low_stock_threshold: Optional[int] = 5
    bonus_percentage: Optional[float] = 1.0
    debt_reminder_days: Optional[int] = 3

class StoreSettingOut(StoreSettingBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
