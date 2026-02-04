from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

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
    phone: Optional[str] = None
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
    barcode: Optional[str] = None
    buy_price: float
    sell_price: float
    stock: float = 0
    unit: str = "dona"
    category_id: Optional[int] = None
    is_favorite: bool = False

class ProductCreate(ProductBase):
    pass

class ProductOut(ProductBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class SupplyBase(BaseModel):
    product_id: int
    quantity: float
    buy_price: float

class SupplyCreate(SupplyBase):
    pass

class SupplyOut(SupplyBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- CRM SCHEMAS ---
class ClientBase(BaseModel):
    name: str
    phone: Optional[str] = None
    telegram_id: Optional[int] = None
    balance: float = 0
    debt_due_date: Optional[datetime] = None

class ClientCreate(ClientBase):
    pass

class ClientOut(ClientBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- POS SCHEMAS ---
class SaleItemBase(BaseModel):
    product_id: int
    quantity: float
    price: float

class SaleItemOut(SaleItemBase):
    id: int
    product: Optional[ProductOut] = None
    model_config = ConfigDict(from_attributes=True)

class SaleCreate(BaseModel):
    total_amount: float
    payment_method: str
    client_id: Optional[int] = None
    items: List[SaleItemBase]
    
    # Optional split payment amounts
    cash_amount: Optional[float] = 0
    card_amount: Optional[float] = 0
    transfer_amount: Optional[float] = 0
    debt_amount: Optional[float] = 0

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
    items: List[SaleItemOut] = []
    model_config = ConfigDict(from_attributes=True)

class ShiftOpen(BaseModel):
    opening_balance: float
    note: Optional[str] = None

class ShiftClose(BaseModel):
    closing_balance: float
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
    total_debt: Optional[float] = 0
    model_config = ConfigDict(from_attributes=True)

# --- FINANCE SCHEMAS ---
class ExpenseBase(BaseModel):
    reason: str
    category: str = "Boshqa"
    amount: float

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseOut(ExpenseBase):
    id: int
    created_at: datetime
    created_by: Optional[int] = None
    creator: Optional[EmployeeOut] = None
    model_config = ConfigDict(from_attributes=True)

class PaymentCreate(BaseModel):
    amount: float
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

class StoreSettingOut(StoreSettingBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
