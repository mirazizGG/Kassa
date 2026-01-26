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
    stock: int = 0
    unit: str = "dona"
    category_id: Optional[int] = None
    is_favorite: bool = False

class ProductCreate(ProductBase):
    pass

class ProductOut(ProductBase):
    id: int
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
    quantity: int
    price: float

class SaleCreate(BaseModel):
    total_amount: float
    payment_method: str
    client_id: Optional[int] = None
    items: List[SaleItemBase]

class SaleOut(BaseModel):
    id: int
    created_at: datetime
    total_amount: float
    payment_method: str
    cashier_id: int
    client_id: Optional[int] = None
    status: str
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
    opening_balance: float
    closing_balance: Optional[float] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    status: str
    note: Optional[str] = None
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
    model_config = ConfigDict(from_attributes=True)

class PaymentCreate(BaseModel):
    amount: float
    payment_method: str = "cash"
    note: Optional[str] = None
    client_id: int
