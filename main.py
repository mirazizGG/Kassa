from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, Response, StreamingResponse
import io
import csv
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, case
from database import init_db, engine, Base, SessionLocal, Employee, Product, User, Expense, Supply, Client, Sale, SaleItem, Category, Payment, Shift
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager
import asyncio
from bot import bot, dp, check_debts

# --- SOZLAMALAR ---
SECRET_KEY = "bu_juda_maxfiy_kalit_uchun_ozgartiring"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 600

# Parol xavfsizligi
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- MODELLAR ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    permissions: str
    username: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "cashier" # admin, manager, cashier
    permissions: str = "pos"
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    passport: Optional[str] = None
    notes: Optional[str] = None

class CategoryCreate(BaseModel):
    name: str

class ProductCreate(BaseModel):
    name: str
    barcode: Optional[str] = None
    buy_price: float
    sell_price: float
    stock: int = 0
    unit: str = "dona"
    category_id: Optional[int] = None

class ExpenseCreate(BaseModel):
    reason: str
    amount: float
    category: str = "Boshqa"

class SupplyCreate(BaseModel):
    product_id: int
    quantity: int
    new_price: float # Yangi kelish narxi (optional logic: update product default)

class ClientCreate(BaseModel):
    name: str
    phone: str = None
    balance: float = 0

class PaymentCreate(BaseModel):
    amount: float
    payment_method: str = "cash" # cash, terminal, transfer
    note: Optional[str] = None

class ShiftOpen(BaseModel):
    opening_balance: float
    note: Optional[str] = None

class ShiftClose(BaseModel):
    closing_balance: float
    note: Optional[str] = None

# --- YORDAMCHI FUNKSIYALAR ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Baza jadvallarini yaratish
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # --- BOT STARTUP ---
    # Start Bot Polling in Background
    asyncio.create_task(dp.start_polling(bot))
    # Start Debt Check Loop
    asyncio.create_task(check_debts(bot))

    # --- MIGRATION LOGIC (Add missing columns for Products & Create Categories table if needed) ---
    async with SessionLocal() as db:
        try:
            # Check if 'unit' column exists in 'products'
            await db.execute(text("SELECT unit FROM products LIMIT 1"))
        except:
             print("Migratsiya: 'unit' ustuni qo'shilmoqda...")
             await db.execute(text("ALTER TABLE products ADD COLUMN unit VARCHAR DEFAULT 'dona'"))
             await db.commit()

        try:
            # Check if 'category_id' column exists in 'products'
            await db.execute(text("SELECT category_id FROM products LIMIT 1"))
        except:
             print("Migratsiya: 'category_id' ustuni qo'shilmoqda...")
             # SQLite doesn't strictly enforce FK in ALTER TABLE easily, so just adding integer column
             await db.execute(text("ALTER TABLE products ADD COLUMN category_id INTEGER")) 
             await db.commit()

        try:
            # Check if 'category' column exists in 'expenses'
            await db.execute(text("SELECT category FROM expenses LIMIT 1"))
        except:
             print("Migratsiya: 'category' ustuni expenses jadvaliga qo'shilmoqda...")
             await db.execute(text("ALTER TABLE expenses ADD COLUMN category VARCHAR DEFAULT 'Boshqa'"))
             await db.commit()

        try:
             # Check if 'expense_categories' table exists
             await db.execute(text("SELECT id FROM expense_categories LIMIT 1"))
        except:
             print("Migratsiya: 'expense_categories' jadvali yaratilmoqda...")
             # Create table manually or let metadata create it?
             # Metadata.create_all only creates missing tables, so main init_db call handles it usually.
             # But if connection is open, maybe force check?
             # Actually, init_db runs at start, so if we restart server, it should create new tables.
             # But let's be safe.
             async with engine.begin() as conn:
                 await conn.run_sync(Base.metadata.create_all)

        # Payments jadvaliga shift_id ustunini qo'shish
        try:
            await db.execute(text("SELECT shift_id FROM payments LIMIT 1"))
        except:
            print("Migratsiya: Payments jadvaliga shift_id ustuni qo'shilmoqda...")
            await db.execute(text("ALTER TABLE payments ADD COLUMN shift_id INTEGER"))
            await db.commit()

        # Xodimlar jadvali uchun qo'shimcha ustunlar
        try:
            await db.execute(text("SELECT full_name FROM employees LIMIT 1"))
        except:
            print("Migratsiya: Employee jadvaliga qo'shimcha ustunlar qo'shilmoqda...")
            await db.execute(text("ALTER TABLE employees ADD COLUMN full_name VARCHAR"))
            await db.execute(text("ALTER TABLE employees ADD COLUMN phone VARCHAR"))
            await db.execute(text("ALTER TABLE employees ADD COLUMN address VARCHAR"))
            await db.execute(text("ALTER TABLE employees ADD COLUMN passport VARCHAR"))
            await db.execute(text("ALTER TABLE employees ADD COLUMN notes VARCHAR"))
            await db.commit()

        # Xodimlar jadvaliga telegram_id ustunini qo'shish (admin hisobotlari uchun)
        try:
            await db.execute(text("SELECT telegram_id FROM employees LIMIT 1"))
        except:
            print("Migratsiya: Employee jadvaliga telegram_id ustuni qo'shilmoqda...")
            await db.execute(text("ALTER TABLE employees ADD COLUMN telegram_id INTEGER"))
            await db.commit()

        # Mahsulotlar jadvaliga is_favorite ustunini qo'shish
        try:
            await db.execute(text("SELECT is_favorite FROM products LIMIT 1"))
        except:
            print("Migratsiya: Products jadvaliga is_favorite ustuni qo'shilmoqda...")
            await db.execute(text("ALTER TABLE products ADD COLUMN is_favorite BOOLEAN DEFAULT 0"))
            await db.commit()

    # Adminni yaratish (agar yo'q bo'lsa)
    async with SessionLocal() as db:
        result = await db.execute(select(Employee).where(Employee.username == "admin"))
        admin = result.scalars().first()
        if not admin:
            print("Admin yaratilmoqda: admin / admin123")
            new_admin = Employee(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                role="admin",
                permissions="all"
            )
            db.add(new_admin)
            await db.commit()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

# --- ASYNC TASKS ---
TELEGRAM_TOKEN = "8301998756:AAEBjeXT-eURJ4olXG2jvhlhI-s8MyMeYug"

async def send_telegram_notification(telegram_id: int, message: str):
    """Mijozga Telegram orqali xabar yuborish"""
    try:
        import httpx
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={
                "chat_id": telegram_id,
                "text": message,
                "parse_mode": "HTML"
            })
    except Exception as e:
        print(f"Telegram xabar yuborishda xatolik: {e}")

async def send_low_stock_alert(items):
    try:
        from sqlalchemy import select
        from database import User
        async with SessionLocal() as db:
             result = await db.execute(select(User).limit(1)) # Send to any bot user (admin)
             admin = result.scalars().first()
             if admin and admin.telegram_id:
                msg = "⚠️ <b>Diqqat! Mahsulotlar kam qolmoqda:</b>\n\n" + "\n".join(items)
                await send_telegram_notification(admin.telegram_id, msg)
    except Exception as e:
        print(f"Alert failed: {e}")

async def get_db():
    async with SessionLocal() as session:
        yield session

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login qilish kerak",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(Employee).where(Employee.username == username))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

# --- AUTH ROUTES ---

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Employee).where(Employee.username == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol xato",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )

    # Audit log: Login
    await log_audit(db, user.id, "Login", f"User: {user.username} ({user.role})")

    # Return user info along with token for frontend
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "permissions": user.permissions,
        "username": user.username
    }

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/logout")
async def logout(current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Audit log: Logout
    await log_audit(db, current_user.id, "Logout", f"User: {current_user.username} ({current_user.role})")

    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

# --- USER MANAGEMENT (Admin Only) ---
@app.post("/api/employees")
async def create_employee(user: UserCreate, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Faqat Admin xodim qo'shishi mumkin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Huquqingiz yetmaydi")
        
    hashed_pw = get_password_hash(user.password)
    new_user = Employee(
        username=user.username,
        hashed_password=hashed_pw,
        role=user.role,
        permissions=user.permissions,
        full_name=user.full_name,
        phone=user.phone,
        address=user.address,
        passport=user.passport,
        notes=user.notes
    )
    db.add(new_user)
    try:
        await db.commit()

        # Audit log: Xodim yaratish
        await log_audit(db, current_user.id, "Xodim yaratdi",
                       f"Username: {new_user.username}, Rol: {new_user.role}, Ism: {new_user.full_name}")
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Bu foydalanuvchi nomi (login) allaqachon mavjud!")
    return {"status": "ok", "username": new_user.username}

@app.get("/api/employees")
async def get_employees(current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Admin va Menejer ko'rishi mumkin (Menejer faqat read-only)
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Huquqingiz yetmaydi")
    
    stmt = select(Employee)
    
    # Manager, Adminlarni ko'rmasligi kerak
    if current_user.role == "manager":
        stmt = stmt.where(Employee.role != "admin")
        
    result = await db.execute(stmt)
    return result.scalars().all()

class EmployeeUpdate(BaseModel):
    username: str
    password: str = None
    role: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    passport: Optional[str] = None
    notes: Optional[str] = None

@app.put("/api/employees/{id}")
async def update_employee(id: int, employee: EmployeeUpdate, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Faqat Admin xodimlarni o'zgartirishi mumkin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Huquqingiz yetmaydi")
    
    db_emp = await db.get(Employee, id)
    if not db_emp:
         raise HTTPException(status_code=404, detail="Xodim topilmadi")
         
    db_emp.username = employee.username
    db_emp.role = employee.role
    db_emp.full_name = employee.full_name
    db_emp.phone = employee.phone
    db_emp.address = employee.address
    db_emp.passport = employee.passport
    db_emp.notes = employee.notes
    if employee.password and employee.password.strip():
        db_emp.hashed_password = get_password_hash(employee.password)

    try:
        await db.commit()

        # Audit log: Xodim yangilash
        await log_audit(db, current_user.id, "Xodim yangiladi",
                       f"ID: {id}, Username: {db_emp.username}, Rol: {db_emp.role}")
    except:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Xatolik")
    return {"status": "updated"}

@app.delete("/api/employees/{id}")
async def delete_employee(id: int, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Faqat Admin xodimlarni o'chirishi mumkin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Huquqingiz yetmaydi")

    emp = await db.get(Employee, id)
    if not emp:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")

    # 1. Self deletion check
    if emp.id == current_user.id:
        raise HTTPException(status_code=400, detail="O'z profilingizni o'chira olmaysiz")

    # 2. Main Admin protection
    if emp.username == "admin":
        raise HTTPException(status_code=400, detail="Asosiy adminni o'chirib bo'lmaydi")

    emp_username = emp.username
    emp_role = emp.role

    await db.delete(emp)
    await db.commit()

    # Audit log: Xodim o'chirish
    await log_audit(db, current_user.id, "Xodim o'chirdi",
                   f"ID: {id}, Username: {emp_username}, Rol: {emp_role}")

    return {"status": "deleted"}

# --- MAIN PAGES ---

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- PRODUCTS API ---

# --- CATEGORY API ---

@app.get("/api/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category))
    return result.scalars().all()

@app.post("/api/categories")
async def create_category(category: CategoryCreate, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    new_cat = Category(name=category.name)
    try:
        db.add(new_cat)
        await db.commit()
        await db.refresh(new_cat)

        # Audit log: Kategoriya yaratish
        await log_audit(db, current_user.id, "Kategoriya yaratdi", f"Nomi: {new_cat.name}")
    except:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Kategoriya mavjud bo'lishi mumkin")
    return new_cat

@app.delete("/api/categories/{id}")
async def delete_category(id: int, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    cat = await db.get(Category, id)
    if cat:
        cat_name = cat.name
        await db.delete(cat)
        await db.commit()

        # Audit log: Kategoriya o'chirish
        await log_audit(db, current_user.id, "Kategoriya o'chirdi", f"ID: {id}, Nomi: {cat_name}")

    return {"status": "deleted"}

# --- PRODUCTS API ---

@app.get("/api/products")
async def get_products(search: str = "", category_id: int = None, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Product)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if search:
        query = query.where(Product.name.ilike(f"{search}%") | Product.barcode.ilike(f"{search}%"))
    result = await db.execute(query)
    return result.scalars().all()

# --- KAM QOLGAN MAHSULOTLAR (OMBOR OGOHLANTIRISH) ---
@app.get("/api/low-stock-products")
async def get_low_stock_products(threshold: int = 5, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Kam qolgan mahsulotlar ro'yxati (standart: 5 dan kam)"""
    query = select(Product).where(Product.stock <= threshold).order_by(Product.stock.asc())
    result = await db.execute(query)
    products = result.scalars().all()

    return [{
        "id": p.id,
        "name": p.name,
        "barcode": p.barcode,
        "stock": p.stock,
        "unit": p.unit,
        "sell_price": p.sell_price,
        "category_id": p.category_id
    } for p in products]

@app.post("/api/products")
async def create_product(product: ProductCreate, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Faqat Admin va Manager qo'shishi mumkin
    if current_user.role not in ["admin", "manager"]:
         raise HTTPException(status_code=403, detail="Huquqingiz yetmaydi")
         
    # Agar shtrix kod bo'sh bo'lsa, None qilamiz (Unique constraint buzilmasligi uchun)
    final_barcode = product.barcode
    if final_barcode and final_barcode.strip() == "":
        final_barcode = None

    new_product = Product(
        name=product.name,
        barcode=final_barcode,
        buy_price=product.buy_price,
        sell_price=product.sell_price,
        stock=product.stock,
        unit=product.unit,
        category_id=product.category_id
    )
    try:
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)

        # Audit log: Mahsulot yaratish
        await log_audit(db, current_user.id, "Mahsulot yaratdi",
                       f"Nomi: {new_product.name}, Sotish narxi: {new_product.sell_price}, Sklad: {new_product.stock}")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Xatolik! Tafsilot: {str(e)}")

    return {"status": "ok", "product": new_product.name}

@app.put("/api/products/{product_id}")
async def update_product(product_id: int, product: ProductCreate, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
         raise HTTPException(status_code=403, detail="Huquqingiz yetmaydi")
    
    db_product = await db.get(Product, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
        
    db_product.name = product.name
    
    final_barcode = product.barcode
    if final_barcode and final_barcode.strip() == "":
        final_barcode = None
    db_product.barcode = final_barcode
    
    db_product.buy_price = product.buy_price
    db_product.sell_price = product.sell_price
    db_product.stock = product.stock
    db_product.unit = product.unit
    db_product.category_id = product.category_id
    
    try:
        await db.commit()

        # Audit log: Mahsulot yangilash
        await log_audit(db, current_user.id, "Mahsulot yangiladi",
                       f"ID: {product_id}, Nomi: {db_product.name}, Yangi narx: {db_product.sell_price}")
    except:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Xatolik")

    return {"status": "updated"}

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
         raise HTTPException(status_code=403, detail="Huquqingiz yetmaydi")

    db_product = await db.get(Product, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    await db.delete(db_product)
    await db.commit()

    # Audit Log
    await log_audit(db, current_user.id, "Deleted Product", f"Product ID: {product_id}, Name: {db_product.name}")

    return {"status": "deleted"}

@app.post("/api/products/{product_id}/favorite")
async def toggle_favorite(product_id: int, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Mahsulotni sevimli qilish/olib tashlash"""
    db_product = await db.get(Product, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    db_product.is_favorite = not db_product.is_favorite
    await db.commit()

    return {"status": "success", "is_favorite": db_product.is_favorite}

@app.get("/api/products/favorites")
async def get_favorite_products(current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Sevimli mahsulotlar ro'yxati"""
    result = await db.execute(
        select(Product).where(Product.is_favorite == True).order_by(Product.name)
    )
    products = result.scalars().all()
    return [{
        "id": p.id,
        "name": p.name,
        "barcode": p.barcode,
        "price": p.sell_price,
        "buy_price": p.buy_price,
        "stock": p.stock,
        "unit": p.unit,
        "is_favorite": p.is_favorite
    } for p in products]

from sqlalchemy import func
from database import Sale, SaleItem

# --- SOZLAMALAR --- (Yuqorida bor)

# Chek Qolipi
class SaleItemModel(BaseModel):
    product_id: int
    quantity: int
    price: float

class SaleCreate(BaseModel):
    items: list[SaleItemModel]
    payment_method: str # cash, terminal, card
    client_id: int | None = None
    due_date: str | None = None # YYYY-MM-DD

@app.post("/api/sell")
async def create_sale(data: SaleCreate, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        # 0. MUHIM: Kassir uchun ochiq smena tekshiruvi
        if current_user.role == "cashier":
            shift_result = await db.execute(
                select(Shift).where(
                    Shift.cashier_id == current_user.id,
                    Shift.status == "open"
                )
            )
            current_shift = shift_result.scalars().first()
            if not current_shift:
                raise HTTPException(
                    status_code=400,
                    detail="Savdo qilish uchun avval smenani ochishingiz kerak!"
                )

        # 1. Umumiy chek summani hisoblash
        total_amount = sum(item.quantity * item.price for item in data.items)

        # 2. Mahsulotlarni tekshirish va xaritaga olish
        product_ids = [item.product_id for item in data.items]
        products_result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
        products = products_result.scalars().all()
        products_map = {p.id: p for p in products}

        if len(products) != len(product_ids):
            raise HTTPException(status_code=400, detail="Mahsulotlardan biri topilmadi")

        # 3. Savdo (chek) yaratish
        new_sale = Sale(
            total_amount=total_amount,
            payment_method=data.payment_method,
            cashier_id=current_user.id,
            client_id=data.client_id,
            created_at=datetime.utcnow()
        )

        # 4. Nasiya (kredit) savdolarni boshqarish
        if data.payment_method == 'nasiya':
             if not data.client_id:
                  raise HTTPException(status_code=400, detail="Nasiya savdo uchun mijoz tanlanishi shart!")

             client = await db.get(Client, data.client_id)
             if not client:
                  raise HTTPException(status_code=404, detail="Mijoz topilmadi")

             # Mijoz balansidan savdo summasini ayirish
             # Misol: Balans +50 (oldindan to'lov), Xarid 20 -> Yangi balans +30
             # Yoki: Balans 0, Xarid 20 -> Yangi balans -20 (qarz)
             client.balance -= total_amount

             # Agar balans manfiy bo'lsa (qarz), muddatni o'rnatish
             if client.balance < 0:
                 if data.due_date:
                     try:
                         client.debt_due_date = datetime.strptime(data.due_date, '%Y-%m-%d')
                     except:
                         raise HTTPException(status_code=400, detail="Sana formati noto'g'ri (YYYY-MM-DD)")
                 else:
                     # Standart 30 kun muddat
                     client.debt_due_date = datetime.utcnow() + timedelta(days=30)
             else:
                # Qarz yo'q bo'lsa, muddatni tozalash
                client.debt_due_date = None
             
        db.add(new_sale)
        await db.commit()
        await db.refresh(new_sale)

        # 5. Savdo elementlarini saqlash va skladni kamaytirish
        low_stock_items = []
        for item in data.items:
            product = products_map.get(item.product_id)
            if not product:
                raise HTTPException(status_code=400, detail=f"Mahsulot ID {item.product_id} topilmadi")

            # Sklad yetarliligini tekshirish
            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"{product.name} mahsulotidan yetarli miqdorda yo'q. Qolgan: {product.stock} {product.unit}"
                )

            # Kam sklad ogohlantirishi
            if product.stock < 5:
                 low_stock_items.append(f"{product.name} ({product.stock} ta qoldi)")

            # Savdo elementini yaratish
            sale_item = SaleItem(
                sale_id=new_sale.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.price
            )
            db.add(sale_item)

            # Skladni kamaytirish
            product.stock -= item.quantity

        await db.commit()

        # Audit log: Savdo yaratish
        product_names = ", ".join([f"{products_map[item.product_id].name} x{item.quantity}" for item in data.items])
        client_info = ""
        if data.client_id:
            client_result = await db.get(Client, data.client_id)
            if client_result:
                client_info = f", Mijoz: {client_result.name}"
        await log_audit(db, current_user.id, "Savdo yaratdi",
                       f"Summa: {total_amount}, To'lov: {data.payment_method}, Mahsulotlar: {product_names}{client_info}")

        # Kam sklad haqida Telegram orqali ogohlantirish
        if low_stock_items:
            import asyncio
            asyncio.create_task(send_low_stock_alert(low_stock_items))

        # Nasiya savdo bo'lganda mijozga Telegram xabar yuborish
        if data.payment_method == 'nasiya' and data.client_id:
            client_for_notify = await db.get(Client, data.client_id)
            if client_for_notify and client_for_notify.telegram_id:
                import asyncio
                balance_text = f"{client_for_notify.balance:,.0f} so'm"
                if client_for_notify.balance < 0:
                    balance_text += " (qarz)"

                due_text = ""
                if client_for_notify.debt_due_date:
                    due_text = f"\n📅 To'lov muddati: {client_for_notify.debt_due_date.strftime('%d.%m.%Y')}"

                msg = (
                    f"🛒 <b>Nasiya xarid amalga oshirildi!</b>\n\n"
                    f"💰 Xarid summasi: {total_amount:,.0f} so'm\n"
                    f"📊 Yangi balans: {balance_text}{due_text}\n\n"
                    f"Xaridingiz uchun rahmat! 🙏"
                )
                asyncio.create_task(send_telegram_notification(client_for_notify.telegram_id, msg))

        return {"message": "Sotuv muvaffaqiyatli amalga oshirildi", "sale_id": new_sale.id}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server ichki xatosi: {str(e)}")

@app.get("/api/sales")
async def get_sales(start_date: str = None, end_date: str = None, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
        
    stmt = select(Sale).options(
        selectinload(Sale.items).selectinload(SaleItem.product), 
        selectinload(Sale.cashier), 
        selectinload(Sale.client)
    ).order_by(Sale.created_at.desc())

    # Date Filters
    if start_date:
        try:
            s_dt = datetime.strptime(start_date, '%Y-%m-%d')
            stmt = stmt.where(Sale.created_at >= s_dt)
        except ValueError:
            pass # Ignore invalid
            
    if end_date:
        try:
            e_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            stmt = stmt.where(Sale.created_at < e_dt)
        except ValueError:
            pass
            
    # If no date, limit to 100
    if not start_date and not end_date:
        stmt = stmt.limit(100)

    result = await db.execute(stmt)
    sales = result.scalars().all()
    
    # Format response
    data = []
    for s in sales:
        data.append({
            "id": s.id,
            "created_at": s.created_at.strftime('%Y-%m-%d %H:%M'),
            "total_amount": s.total_amount,
            "payment_method": s.payment_method,
            "status": s.status,
            "cashier": s.cashier.username if s.cashier else "Noma'lum",
            "client": s.client.name if s.client else "-",
            "items": [{"name": i.product.name, "qty": i.quantity, "price": i.price} for i in s.items if i.product]
        })
    return data

@app.get("/api/sales/{sale_id}")
async def get_sale_details(sale_id: int, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Bitta savdoning batafsil ma'lumotlarini olish"""
    if current_user.role not in ["admin", "manager", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    stmt = select(Sale).options(
        selectinload(Sale.items).selectinload(SaleItem.product),
        selectinload(Sale.cashier),
        selectinload(Sale.client)
    ).where(Sale.id == sale_id)

    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()

    if not sale:
        raise HTTPException(status_code=404, detail="Savdo topilmadi")

    return {
        "id": sale.id,
        "created_at": sale.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        "total_amount": sale.total_amount,
        "payment_method": sale.payment_method,
        "status": sale.status,
        "cashier": sale.cashier.username if sale.cashier else "Noma'lum",
        "client": sale.client.name if sale.client else None,
        "items": [
            {
                "product_name": item.product.name if item.product else "Noma'lum",
                "quantity": item.quantity,
                "price": item.price,
                "subtotal": item.quantity * item.price
            }
            for item in sale.items
        ]
    }

@app.post("/api/sales/{id}/refund")
async def refund_sale(id: int, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager", "cashier"]:
         raise HTTPException(status_code=403, detail="Ruxsat yo'q")
         
    sale = await db.get(Sale, id)
    if not sale:
        raise HTTPException(status_code=404, detail="Chek topilmadi")
        
    if sale.status == "refunded":
        raise HTTPException(status_code=400, detail="Bu chek allaqachon qaytarilgan")
        
    # Restore Stock
    result_items = await db.execute(select(SaleItem).where(SaleItem.sale_id == sale.id))
    items = result_items.scalars().all()
    
    for item in items:
        prod = await db.get(Product, item.product_id)
        if prod:
            prod.stock += item.quantity
            
    sale.status = "refunded"
    await db.commit()
    
    
    # Audit
    await log_audit(db, current_user.id, "Refunded Sale", f"Sale ID: {id}, Amount: {sale.total_amount}")
    
    return {"status": "refunded"}

async def log_audit(db: AsyncSession, user_id: int, action: str, details: str):
    from database import AuditLog
    log = AuditLog(user_id=user_id, action=action, details=details)
    db.add(log)
    await db.commit()





@app.get("/api/expenses")
async def get_expenses(start_date: str = None, end_date: str = None, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Expense).order_by(Expense.created_at.desc())
    
    if start_date:
        try:
            s_dt = datetime.strptime(start_date, '%Y-%m-%d')
            stmt = stmt.where(Expense.created_at >= s_dt)
        except:
            pass
        
    if end_date:
        try:
            e_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            stmt = stmt.where(Expense.created_at < e_dt)
        except:
            pass

    if not start_date and not end_date:
        stmt = stmt.limit(50)

    result = await db.execute(stmt)
    return result.scalars().all()

@app.post("/api/expenses")
async def create_expense(data: ExpenseCreate, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Create
    exp = Expense(
        reason=data.reason,
        amount=data.amount,
        category=data.category,
        created_by=current_user.id
    )
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    await log_audit(db, current_user.id, "Created Expense", f"{data.reason} - {data.amount}")
    return {"status": "success"}

@app.delete("/api/expenses/{id}")
async def delete_expense(id: int, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
        
    exp = await db.get(Expense, id)
    if not exp:
        raise HTTPException(status_code=404, detail="Topilmadi")
        
    await db.delete(exp)
    await db.commit()
    return {"status": "deleted"}

@app.get("/api/stats")
async def get_stats(start_date: str = None, end_date: str = None, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # 1. Determine Date Range
    try:
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        else:
            end_dt = start_dt + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Sana formati noto'g'ri (YYYY-MM-DD)")

    # 2. Fetch Sales
    # Get all completed sales in period
    stmt_sales = select(Sale).options(selectinload(Sale.items).selectinload(SaleItem.product))\
                 .where(Sale.created_at >= start_dt)\
                 .where(Sale.created_at < end_dt)\
                 .where(Sale.status != "refunded")
    
    res_sales = await db.execute(stmt_sales)
    sales = res_sales.scalars().all()
    
    total_revenue = 0
    total_cost = 0
    product_counts = {}
    
    for s in sales:
        total_revenue += s.total_amount
        for item in s.items:
            # Calculate Cost (Buy Price * Qty)
            # Note: We use current buy_price of product. ideally we should snapshot it, but for simple POS this is acceptable.
            bp = item.product.buy_price if item.product else 0
            total_cost += (bp * item.quantity)
            
            # Top Products Logic
            p_name = item.product.name if item.product else "Noma'lum"
            product_counts[p_name] = product_counts.get(p_name, 0) + item.quantity

    gross_profit = total_revenue - total_cost

    # 3. Fetch Expenses
    stmt_exp = select(func.sum(Expense.amount)).where(Expense.created_at >= start_dt).where(Expense.created_at < end_dt)
    res_exp = await db.execute(stmt_exp)
    total_expenses = res_exp.scalar() or 0

    # 3.5. Fetch Debt Payments (Qarz to'lovlari)
    stmt_payments = select(func.sum(Payment.amount)).where(
        Payment.created_at >= start_dt,
        Payment.created_at < end_dt,
        Payment.amount > 0  # Faqat to'lovlar, qarz qo'shilganlarni emas
    )
    res_payments = await db.execute(stmt_payments)
    total_debt_payments = res_payments.scalar() or 0

    # Qarz to'lovlari sonini hisoblash
    stmt_payments_count = select(func.count(Payment.id)).where(
        Payment.created_at >= start_dt,
        Payment.created_at < end_dt,
        Payment.amount > 0
    )
    res_payments_count = await db.execute(stmt_payments_count)
    debt_payments_count = res_payments_count.scalar() or 0

    net_profit = gross_profit - total_expenses

    # 4. Top Products (Sort)
    top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_products_list = [{"name": k, "qty": v} for k, v in top_products]

    return {
        "revenue": total_revenue,
        "gross_profit": gross_profit,
        "expenses": total_expenses,
        "net_profit": net_profit,
        "sales_count": len(sales),
        "debt_payments": total_debt_payments,  # Qarz to'lovlari summasi
        "debt_payments_count": debt_payments_count,  # Qarz to'lovlari soni
        "top_products": top_products_list
    }

# --- HISOBOTLAR (Kunlik/Haftalik/Oylik) ---
@app.get("/api/reports/summary")
async def get_reports_summary(current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Kunlik, haftalik, oylik hisobotlar va solishtirishlar"""

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())  # Dushanba
    last_week_start = week_start - timedelta(days=7)
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    async def get_period_stats(start_dt, end_dt):
        """Ma'lum davr uchun statistika"""
        # Savdolar
        sales_stmt = select(func.sum(Sale.total_amount), func.count(Sale.id)).where(
            Sale.created_at >= start_dt,
            Sale.created_at < end_dt,
            Sale.status == 'completed'
        )
        sales_res = await db.execute(sales_stmt)
        sales_data = sales_res.one()
        revenue = sales_data[0] or 0
        sales_count = sales_data[1] or 0

        # Xarajatlar
        exp_stmt = select(func.sum(Expense.amount)).where(
            Expense.created_at >= start_dt,
            Expense.created_at < end_dt
        )
        exp_res = await db.execute(exp_stmt)
        expenses = exp_res.scalar() or 0

        # Qarz to'lovlari
        pay_stmt = select(func.sum(Payment.amount)).where(
            Payment.created_at >= start_dt,
            Payment.created_at < end_dt,
            Payment.amount > 0
        )
        pay_res = await db.execute(pay_stmt)
        payments = pay_res.scalar() or 0

        return {
            "revenue": revenue,
            "sales_count": sales_count,
            "expenses": expenses,
            "payments": payments,
            "profit": revenue - expenses
        }

    # Bugungi va kechagi
    today_stats = await get_period_stats(today, today + timedelta(days=1))
    yesterday_stats = await get_period_stats(yesterday, today)

    # Shu hafta va o'tgan hafta
    this_week_stats = await get_period_stats(week_start, today + timedelta(days=1))
    last_week_stats = await get_period_stats(last_week_start, week_start)

    # Shu oy va o'tgan oy
    this_month_stats = await get_period_stats(month_start, today + timedelta(days=1))
    last_month_stats = await get_period_stats(last_month_start, month_start)

    def calc_change(current, previous):
        """O'zgarish foizini hisoblash"""
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    return {
        "today": {
            **today_stats,
            "change": calc_change(today_stats["revenue"], yesterday_stats["revenue"])
        },
        "yesterday": yesterday_stats,
        "this_week": {
            **this_week_stats,
            "change": calc_change(this_week_stats["revenue"], last_week_stats["revenue"])
        },
        "last_week": last_week_stats,
        "this_month": {
            **this_month_stats,
            "change": calc_change(this_month_stats["revenue"], last_month_stats["revenue"])
        },
        "last_month": last_month_stats
    }

@app.get("/api/audits")
async def get_audits(start_date: str = None, end_date: str = None, employee_id: int = None, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    from database import AuditLog # Deferred import to avoid circular issues if any

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())

    # Filter bo'yicha xodim
    if employee_id:
        stmt = stmt.where(AuditLog.user_id == employee_id)

    if start_date:
        try:
            s_dt = datetime.strptime(start_date, '%Y-%m-%d')
            stmt = stmt.where(AuditLog.created_at >= s_dt)
        except: pass

    if end_date:
        try:
            e_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            stmt = stmt.where(AuditLog.created_at < e_dt)
        except: pass

    if not start_date and not end_date and not employee_id:
        stmt = stmt.limit(100)
    # Ideally should join with Employee
    
    res = await db.execute(stmt)
    logs = res.scalars().all()
    
    # For username, let's fetch employees map
    res_emp = await db.execute(select(Employee))
    emps = {e.id: e.username for e in res_emp.scalars().all()}
    
    return [{
        "id": l.id,
        "action": l.action,
        "details": l.details,
        "user": emps.get(l.user_id, "Noma'lum"), # Fixed: user_id
        "created_at": l.created_at.strftime('%Y-%m-%d %H:%M')
    } for l in logs]

# --- XODIMLAR FAOLIYATI STATISTIKASI ---
@app.get("/api/employee-activity")
async def get_employee_activity(employee_id: int = None, date: str = None, current_user: Employee = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Xodimlarning faoliyatini ko'rsatadi - necha savdo qilgan, qancha pul yig'gan
    Admin va Menejerlar uchun
    """
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    # Sana filtri (standart - bugun)
    if date:
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d')
        except:
            raise HTTPException(status_code=400, detail="Sana formati noto'g'ri (YYYY-MM-DD)")
    else:
        target_date = datetime.utcnow().date()
        target_date = datetime.combine(target_date, datetime.min.time())

    end_date = target_date + timedelta(days=1)

    # Barcha xodimlar yoki aniq bir xodim
    emp_filter = select(Employee)
    if employee_id:
        emp_filter = emp_filter.where(Employee.id == employee_id)

    employees_result = await db.execute(emp_filter)
    employees = employees_result.scalars().all()

    activity_data = []

    for emp in employees:
        # Savdolar soni va summasi
        sales_stmt = select(Sale).where(
            Sale.cashier_id == emp.id,
            Sale.created_at >= target_date,
            Sale.created_at < end_date,
            Sale.status != "refunded"
        )
        sales_result = await db.execute(sales_stmt)
        sales = sales_result.scalars().all()

        sales_count = len(sales)
        total_revenue = sum(s.total_amount for s in sales)

        # To'lov usullari bo'yicha ajratish
        cash_sales = sum(s.total_amount for s in sales if s.payment_method == 'cash')
        card_sales = sum(s.total_amount for s in sales if s.payment_method in ['card', 'plastic', 'terminal'])
        credit_sales = sum(s.total_amount for s in sales if s.payment_method == 'nasiya')

        # Oxirgi faoliyat vaqti (login/logout)
        from database import AuditLog
        last_activity_stmt = select(AuditLog).where(
            AuditLog.user_id == emp.id,
            AuditLog.created_at >= target_date,
            AuditLog.created_at < end_date
        ).order_by(AuditLog.created_at.desc()).limit(1)
        last_activity_result = await db.execute(last_activity_stmt)
        last_activity = last_activity_result.scalars().first()

        activity_data.append({
            "employee_id": emp.id,
            "username": emp.username,
            "full_name": emp.full_name or emp.username,
            "role": emp.role,
            "sales_count": sales_count,
            "total_revenue": total_revenue,
            "cash_sales": cash_sales,
            "card_sales": card_sales,
            "credit_sales": credit_sales,
            "last_activity": last_activity.created_at.strftime('%Y-%m-%d %H:%M') if last_activity else None,
            "last_action": last_activity.action if last_activity else None
        })

    return activity_data


# Duplicate functions removed - kept original versions above (lines 701-727, 663-691)




# --- TOVAR KIRIMI (SUPPLY) ---

@app.post("/api/supplies")
async def add_supply(supply: SupplyCreate, db: AsyncSession = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """Mahsulot kirimini qo'shish (faqat admin/menejer)"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    # 1. Mahsulotni topish
    result = await db.execute(select(Product).where(Product.id == supply.product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    # 2. Kirimni tarixga yozish
    new_supply = Supply(
        product_id=product.id,
        quantity=supply.quantity,
        buy_price=supply.new_price
    )
    db.add(new_supply)

    # 3. Mahsulot narxi va skladini yangilash
    product.buy_price = supply.new_price
    product.stock += supply.quantity

    await db.commit()
    await log_audit(db, current_user.id, "Supply Added", f"Product: {product.name}, Quantity: {supply.quantity}, Price: {supply.new_price}")

    return {"message": "Kirim muvaffaqiyatli qo'shildi", "new_stock": product.stock}

# --- DEBT MANAGEMENT ---
class DebtRequest(BaseModel):
    amount: float
    due_date: str = None  # YYYY-MM-DD, ixtiyoriy
    reason: str = None  # Sabab/izoh, ixtiyoriy

@app.post("/api/clients/{id}/debt")
async def add_debt(
    id: int, 
    request: DebtRequest, 
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    
    result = await db.execute(select(Client).where(Client.id == id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    
    # Update balance (Debt is negative balance usually, or positive depending on sys. User said "Qarz". 
    # Usually: Positive Balance = Client has money. Negative = Client owes money.
    # User Request: "summa va qachon qaytarib berishini". 
    # If I give 100 debt -> Balance becomes -100.
    
    client.balance -= request.amount  # Decrease balance (increase debt)

    if request.due_date:
        from datetime import datetime
        try:
             client.debt_due_date = datetime.strptime(request.due_date, "%Y-%m-%d")
        except:
             pass

    # Qarz qo'shilganda ham to'lovlar tarixiga yozuv qo'shish (manfiy summa bilan)
    reason_text = f" - {request.reason}" if hasattr(request, 'reason') and request.reason else ""
    new_payment = Payment(
        client_id=id,
        amount=-request.amount,  # Manfiy summa = qarz qo'shildi
        payment_method="qarz",
        note=f"Qarz qo'shildi{reason_text}",
        created_by=current_user.id,
        shift_id=None  # Qarz qo'shish smena bilan bog'liq emas
    )
    db.add(new_payment)

    await db.commit()

    # Audit Log
    reason_text_audit = f", Sabab: {request.reason}" if hasattr(request, 'reason') and request.reason else ""
    await log_audit(db, current_user.id, "Qarz qo'shdi", f"Summa: {request.amount}, Mijoz: {client.name}{reason_text_audit}")

    return {"message": "Qarz yozildi va muddat belgilandi", "new_balance": client.balance}

# --- BROADCASTING ---

class BroadcastRequest(BaseModel):
    message: str

@app.post("/api/broadcast")
async def broadcast_message(
    request: BroadcastRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: Employee = Depends(get_current_user)
):
    if "admin" not in current_user.role and "manager" not in current_user.role:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    
    # Get all clients with telegram_id
    result = await db.execute(select(Client).where(Client.telegram_id.isnot(None)))
    clients = result.scalars().all()
    
    import httpx
    token = "8301998756:AAEBjeXT-eURJ4olXG2jvhlhI-s8MyMeYug"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    success_count = 0
    async with httpx.AsyncClient() as client:
        for c in clients:
            try:
                payload = {"chat_id": c.telegram_id, "text": request.message, "parse_mode": "HTML"}
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    success_count += 1
            except Exception:
                pass
                
    return {"message": f"Xabar yuborildi: {success_count} ta mijozga"}

@app.get("/api/supplies")
async def get_supplies(db: AsyncSession = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """Kirimlar tarixini ko'rish"""
    query = select(Supply, Product.name).join(Product, Supply.product_id == Product.id).order_by(Supply.created_at.desc()).limit(50)
    result = await db.execute(query)

    supplies = []
    for s, name in result:
        supplies.append({
            "id": s.id,
            "product_name": name,
            "quantity": s.quantity,
            "buy_price": s.buy_price,
            "date": s.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return supplies

# --- MIJOZLAR (CLIENTS) ---

@app.get("/api/clients")
async def get_clients(db: AsyncSession = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    result = await db.execute(select(Client).order_by(Client.name))
    return result.scalars().all()

@app.post("/api/clients")
async def create_client(client: ClientCreate, db: AsyncSession = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    new_client = Client(name=client.name, phone=client.phone, balance=client.balance)
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)

    # Audit log: Mijoz yaratish
    await log_audit(db, current_user.id, "Mijoz yaratdi",
                   f"Nomi: {new_client.name}, Telefon: {new_client.phone}, Balans: {new_client.balance}")

    return {"message": "Mijoz qo'shildi", "client": new_client}

@app.put("/api/clients/{id}")
async def update_client(id: int, client: ClientCreate, db: AsyncSession = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    
    result = await db.execute(select(Client).where(Client.id == id))
    db_client = result.scalars().first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    
    db_client.name = client.name
    db_client.phone = client.phone
    db_client.balance = client.balance

    await db.commit()

    # Audit log: Mijoz yangilash
    await log_audit(db, current_user.id, "Mijoz yangiladi",
                   f"ID: {id}, Nomi: {db_client.name}, Yangi balans: {db_client.balance}")

    return {"message": "Mijoz yangilandi"}

@app.delete("/api/clients/{id}")
async def delete_client(id: int, db: AsyncSession = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    result = await db.execute(select(Client).where(Client.id == id))
    db_client = result.scalars().first()
    if db_client:
        client_name = db_client.name
        await db.delete(db_client)
        await db.commit()

        # Audit log: Mijoz o'chirish
        await log_audit(db, current_user.id, "Mijoz o'chirdi", f"ID: {id}, Nomi: {client_name}")

    return {"message": "Mijoz o'chirildi"}

# --- QARZ TO'LOVLARI ---
@app.post("/api/clients/{id}/payment")
async def add_payment(
    id: int,
    payment: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Mijoz qarzini to'lash"""
    # Mijozni topish
    result = await db.execute(select(Client).where(Client.id == id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")

    # Ochiq smenani tekshirish (kassir, admin, menejer uchun)
    shift_id = None
    shift_result = await db.execute(
        select(Shift).where(
            Shift.cashier_id == current_user.id,
            Shift.status == "open"
        )
    )
    current_shift = shift_result.scalars().first()
    if current_shift:
        shift_id = current_shift.id

    # To'lovni saqlash
    new_payment = Payment(
        client_id=id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        note=payment.note,
        created_by=current_user.id,
        shift_id=shift_id
    )
    db.add(new_payment)

    # Balansni yangilash (to'lov qarz balansiga qo'shiladi, ya'ni manfiy bo'lsa kamayadi)
    client.balance += payment.amount

    # Agar qarz to'liq to'langan bo'lsa, debt_due_date ni tozalash
    if client.balance >= 0:
        client.debt_due_date = None

    await db.commit()
    await db.refresh(new_payment)

    # Audit log
    await log_audit(db, current_user.id, "Client Payment", f"Client: {client.name}, Amount: {payment.amount}, New Balance: {client.balance}")

    # Telegram bildirishnoma
    if client.telegram_id:
        import asyncio
        balance_text = f"{client.balance:,.0f} so'm"
        status_emoji = "✅"
        status_text = ""

        if client.balance < 0:
            balance_text += " (qarz qoldi)"
            status_emoji = "💳"
            status_text = "\n\n⏰ Qolgan qarzni o'z vaqtida to'lashni unutmang!"
        elif client.balance > 0:
            balance_text += " (oldindan to'lov)"
            status_text = "\n\n🎉 Sizda ortiqcha mablag' bor!"
        else:
            status_text = "\n\n🎉 Qarzingiz to'liq to'landi!"

        msg = (
            f"{status_emoji} <b>To'lov qabul qilindi!</b>\n\n"
            f"💰 To'langan summa: <b>{payment.amount:,.0f} so'm</b>\n"
            f"📊 Yangi balans: <b>{balance_text}</b>"
            f"{status_text}\n\n"
            f"Rahmat, {client.name}! 🙏"
        )
        asyncio.create_task(send_telegram_notification(client.telegram_id, msg))

    return {"message": "To'lov muvaffaqiyatli qabul qilindi", "new_balance": client.balance, "payment_id": new_payment.id}

@app.get("/api/clients/{id}/payments")
async def get_client_payments(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Mijozning to'lovlar tarixini olish"""
    stmt = select(Payment).where(Payment.client_id == id).order_by(Payment.created_at.desc())
    result = await db.execute(stmt)
    payments = result.scalars().all()

    # Xodimlar nomlarini olish
    emp_ids = [p.created_by for p in payments if p.created_by]
    if emp_ids:
        emp_result = await db.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        employees = {e.id: e.username for e in emp_result.scalars().all()}
    else:
        employees = {}

    return [{
        "id": p.id,
        "amount": p.amount,
        "payment_method": p.payment_method,
        "note": p.note,
        "created_at": p.created_at.strftime('%Y-%m-%d %H:%M'),
        "created_by": employees.get(p.created_by, "Noma'lum")
    } for p in payments]

@app.get("/api/payments")
async def get_all_payments(
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Barcha qarz to'lovlarini olish (admin, menejer, kassir)"""
    stmt = select(Payment).options(
        selectinload(Payment.client),
        selectinload(Payment.employee)
    ).order_by(Payment.created_at.desc())

    # Kassir faqat o'zining to'lovlarini ko'radi
    if current_user.role == "cashier":
        stmt = stmt.where(Payment.created_by == current_user.id)

    # Sana filtri
    if start_date:
        try:
            s_dt = datetime.strptime(start_date, '%Y-%m-%d')
            stmt = stmt.where(Payment.created_at >= s_dt)
        except: pass

    if end_date:
        try:
            e_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            stmt = stmt.where(Payment.created_at < e_dt)
        except: pass

    # Agar sana berilmagan bo'lsa, faqat bugungilarni ko'rsat
    if not start_date and not end_date:
        today = datetime.utcnow().date()
        today_dt = datetime.combine(today, datetime.min.time())
        tomorrow_dt = today_dt + timedelta(days=1)
        stmt = stmt.where(Payment.created_at >= today_dt, Payment.created_at < tomorrow_dt)

    result = await db.execute(stmt)
    payments = result.scalars().all()

    return [{
        "id": p.id,
        "client_name": p.client.name if p.client else "Noma'lum",
        "amount": p.amount,
        "payment_method": p.payment_method,
        "note": p.note,
        "created_at": p.created_at.strftime('%Y-%m-%d %H:%M'),
        "created_by": p.employee.username if p.employee else "Noma'lum",
        "shift_id": p.shift_id
    } for p in payments]

# --- KASSIR SMENASI (SHIFTS) ---
@app.post("/api/shifts/open")
async def open_shift(
    shift_data: ShiftOpen,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Yangi smena ochish"""
    # Kassir va menejerlar uchun ruxsat
    if current_user.role not in ["cashier", "manager", "admin"]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    # Avval ochiq smena borligini tekshirish
    result = await db.execute(
        select(Shift).where(
            Shift.cashier_id == current_user.id,
            Shift.status == "open"
        )
    )
    existing_shift = result.scalars().first()
    if existing_shift:
        raise HTTPException(status_code=400, detail="Sizda ochiq smena mavjud. Avval uni yoping.")

    # Yangi smena ochish
    new_shift = Shift(
        cashier_id=current_user.id,
        opening_balance=shift_data.opening_balance,
        note=shift_data.note
    )
    db.add(new_shift)
    await db.commit()
    await db.refresh(new_shift)

    await log_audit(db, current_user.id, "Shift Opened", f"Opening Balance: {shift_data.opening_balance}")

    return {
        "message": "Smena muvaffaqiyatli ochildi",
        "shift_id": new_shift.id,
        "opening_balance": new_shift.opening_balance
    }

@app.get("/api/shifts/current")
async def get_current_shift(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Joriy ochiq smenani olish"""
    print(f"DEBUG: Checking shift for user ID: {current_user.id}, username: {current_user.username}")
    
    result = await db.execute(
        select(Shift).where(
            Shift.cashier_id == current_user.id,
            Shift.status == "open"
        )
    )
    shift = result.scalars().first()

    if not shift:
        print(f"DEBUG: No open shift found for user {current_user.id}")
        return {"shift": None}

    print(f"DEBUG: Found open shift ID: {shift.id}")
    
    # Smena davomida qilingan savdolarni hisoblash
    sales_result = await db.execute(
        select(func.sum(Sale.total_amount)).where(
            Sale.cashier_id == current_user.id,
            Sale.created_at >= shift.opened_at,
            Sale.status == "completed"
        )
    )
    total_sales = sales_result.scalar() or 0
    
    # Savdolarni to'lov usullari bo'yicha
    sales_cash = await db.execute(
        select(func.sum(Sale.total_amount)).where(
            Sale.cashier_id == current_user.id,
            Sale.created_at >= shift.opened_at,
            Sale.status == "completed",
            Sale.payment_method == "cash"
        )
    )
    sales_cash_amount = sales_cash.scalar() or 0
    
    sales_card = await db.execute(
        select(func.sum(Sale.total_amount)).where(
            Sale.cashier_id == current_user.id,
            Sale.created_at >= shift.opened_at,
            Sale.status == "completed",
            Sale.payment_method.in_(["plastic", "card"])
        )
    )
    sales_card_amount = sales_card.scalar() or 0
    
    # Qarz to'lovlarini hisoblash (created_by va vaqt bo'yicha)
    payments_result = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == current_user.id,
            Payment.created_at >= shift.opened_at
        )
    )
    total_payments = payments_result.scalar() or 0
    
    # Qarz to'lovlarini to'lov usullari bo'yicha
    payments_cash = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == current_user.id,
            Payment.created_at >= shift.opened_at,
            Payment.payment_method == "cash"
        )
    )
    payments_cash_amount = payments_cash.scalar() or 0
    
    payments_terminal = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == current_user.id,
            Payment.created_at >= shift.opened_at,
            Payment.payment_method == "terminal"
        )
    )
    payments_terminal_amount = payments_terminal.scalar() or 0
    
    payments_transfer = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == current_user.id,
            Payment.created_at >= shift.opened_at,
            Payment.payment_method == "transfer"
        )
    )
    payments_transfer_amount = payments_transfer.scalar() or 0

    # Smena davomida qilingan xarajatlarni hisoblash
    expenses_result = await db.execute(
        select(func.sum(Expense.amount)).where(
            Expense.created_by == current_user.id,
            Expense.created_at >= shift.opened_at
        )
    )
    total_expenses = expenses_result.scalar() or 0

    # Vozvrat qilingan savdolar (soni va summasi)
    refunds_result = await db.execute(
        select(
            func.count(Sale.id).label('count'),
            func.coalesce(func.sum(Sale.total_amount), 0).label('total')
        ).where(
            Sale.cashier_id == current_user.id,
            Sale.created_at >= shift.opened_at,
            Sale.status == 'refunded'
        )
    )
    refunds_data = refunds_result.first()
    refunds_count = refunds_data.count if refunds_data else 0
    refunds_total = refunds_data.total if refunds_data else 0

    # Kutilayotgan kassa balansi
    expected_balance = shift.opening_balance + total_sales + total_payments - total_expenses

    return {
        "shift": {
            "id": shift.id,
            "opening_balance": shift.opening_balance,
            "opened_at": shift.opened_at.strftime('%Y-%m-%d %H:%M'),
            "total_sales": total_sales,
            "sales_cash": sales_cash_amount,
            "sales_card": sales_card_amount,
            "total_payments": total_payments,
            "payments_cash": payments_cash_amount,
            "payments_terminal": payments_terminal_amount,
            "payments_transfer": payments_transfer_amount,
            "total_expenses": total_expenses,
            "refunds_count": refunds_count,
            "refunds_total": refunds_total,
            "expected_balance": expected_balance,
            "note": shift.note
        }
    }

@app.post("/api/shifts/{id}/close")
async def close_shift(
    id: int,
    shift_close: ShiftClose,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Smenani yopish"""
    # Smenani topish
    result = await db.execute(select(Shift).where(Shift.id == id))
    shift = result.scalars().first()

    if not shift:
        raise HTTPException(status_code=404, detail="Smena topilmadi")

    # Faqat o'z smenasini yopishi mumkin (yoki admin)
    if shift.cashier_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    if shift.status == "closed":
        raise HTTPException(status_code=400, detail="Smena allaqachon yopilgan")

    # Smenani yopish
    shift.closing_balance = shift_close.closing_balance
    shift.closed_at = datetime.utcnow()
    shift.status = "closed"
    if shift_close.note:
        shift.note = shift.note + "; " + shift_close.note if shift.note else shift_close.note

    await db.commit()

    # Hisobot uchun ma'lumotlar
    sales_result = await db.execute(
        select(func.sum(Sale.total_amount)).where(
            Sale.cashier_id == shift.cashier_id,
            Sale.created_at >= shift.opened_at,
            Sale.created_at <= shift.closed_at,
            Sale.status == "completed"
        )
    )
    total_sales = sales_result.scalar() or 0
    
    # Savdolarni to'lov usullari bo'yicha
    sales_cash = await db.execute(
        select(func.sum(Sale.total_amount)).where(
            Sale.cashier_id == shift.cashier_id,
            Sale.created_at >= shift.opened_at,
            Sale.created_at <= shift.closed_at,
            Sale.status == "completed",
            Sale.payment_method == "cash"
        )
    )
    sales_cash_amount = sales_cash.scalar() or 0
    
    sales_card = await db.execute(
        select(func.sum(Sale.total_amount)).where(
            Sale.cashier_id == shift.cashier_id,
            Sale.created_at >= shift.opened_at,
            Sale.created_at <= shift.closed_at,
            Sale.status == "completed",
            Sale.payment_method.in_(["plastic", "card"])
        )
    )
    sales_card_amount = sales_card.scalar() or 0
    
    # Qarz to'lovlarini hisoblash (created_by va vaqt bo'yicha)
    payments_result = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == shift.cashier_id,
            Payment.created_at >= shift.opened_at,
            Payment.created_at <= shift.closed_at
        )
    )
    total_payments = payments_result.scalar() or 0
    
    # Qarz to'lovlarini to'lov usullari bo'yicha
    payments_cash = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == shift.cashier_id,
            Payment.created_at >= shift.opened_at,
            Payment.created_at <= shift.closed_at,
            Payment.payment_method == "cash"
        )
    )
    payments_cash_amount = payments_cash.scalar() or 0
    
    payments_terminal = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == shift.cashier_id,
            Payment.created_at >= shift.opened_at,
            Payment.created_at <= shift.closed_at,
            Payment.payment_method == "terminal"
        )
    )
    payments_terminal_amount = payments_terminal.scalar() or 0
    
    payments_transfer = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.created_by == shift.cashier_id,
            Payment.created_at >= shift.opened_at,
            Payment.created_at <= shift.closed_at,
            Payment.payment_method == "transfer"
        )
    )
    payments_transfer_amount = payments_transfer.scalar() or 0

    expenses_result = await db.execute(
        select(func.sum(Expense.amount)).where(
            Expense.created_by == shift.cashier_id,
            Expense.created_at >= shift.opened_at,
            Expense.created_at <= shift.closed_at
        )
    )
    total_expenses = expenses_result.scalar() or 0

    # Vozvrat qilingan savdolar (soni va summasi)
    refunds_result = await db.execute(
        select(
            func.count(Sale.id).label('count'),
            func.coalesce(func.sum(Sale.total_amount), 0).label('total')
        ).where(
            Sale.cashier_id == shift.cashier_id,
            Sale.created_at >= shift.opened_at,
            Sale.created_at <= shift.closed_at,
            Sale.status == 'refunded'
        )
    )
    refunds_data = refunds_result.first()
    refunds_count = refunds_data.count if refunds_data else 0
    refunds_total = refunds_data.total if refunds_data else 0

    expected_balance = shift.opening_balance + total_sales + total_payments - total_expenses
    difference = shift_close.closing_balance - expected_balance

    await log_audit(db, current_user.id, "Shift Closed", f"Closing Balance: {shift_close.closing_balance}, Expected: {expected_balance}, Difference: {difference}")

    return {
        "message": "Smena yopildi",
        "opening_balance": shift.opening_balance,
        "closing_balance": shift_close.closing_balance,
        "total_sales": total_sales,
        "sales_cash": sales_cash_amount,
        "sales_card": sales_card_amount,
        "total_payments": total_payments,
        "payments_cash": payments_cash_amount,
        "payments_terminal": payments_terminal_amount,
        "payments_transfer": payments_transfer_amount,
        "total_expenses": total_expenses,
        "refunds_count": refunds_count,
        "refunds_total": refunds_total,
        "expected_balance": expected_balance,
        "difference": difference
    }

@app.get("/api/shifts")
async def get_all_shifts(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Barcha smenalarni ko'rish (admin/manager uchun)"""
    # Kassir faqat o'z smenalarini ko'radi
    if current_user.role == "cashier":
        stmt = select(Shift).where(Shift.cashier_id == current_user.id).order_by(Shift.opened_at.desc())
    else:
        stmt = select(Shift).order_by(Shift.opened_at.desc())

    result = await db.execute(stmt)
    shifts = result.scalars().all()

    # Kassirlar nomlarini olish
    cashier_ids = [s.cashier_id for s in shifts]
    if cashier_ids:
        cashier_result = await db.execute(select(Employee).where(Employee.id.in_(cashier_ids)))
        cashiers = {c.id: c.username for c in cashier_result.scalars().all()}
    else:
        cashiers = {}

    response_data = []
    for s in shifts:
        # Savdolar
        sales_result = await db.execute(
            select(func.sum(Sale.total_amount)).where(
                Sale.cashier_id == s.cashier_id,
                Sale.created_at >= s.opened_at,
                Sale.created_at <= (s.closed_at if s.closed_at else datetime.utcnow()),
                Sale.status == "completed"
            )
        )
        total_sales = sales_result.scalar() or 0

        # Savdolar to'lov usuli bo'yicha
        sales_cash = await db.execute(
            select(func.sum(Sale.total_amount)).where(
                Sale.cashier_id == s.cashier_id,
                Sale.created_at >= s.opened_at,
                Sale.created_at <= (s.closed_at if s.closed_at else datetime.utcnow()),
                Sale.status == "completed",
                Sale.payment_method == "cash"
            )
        )
        sales_cash_amount = sales_cash.scalar() or 0

        sales_card = await db.execute(
            select(func.sum(Sale.total_amount)).where(
                Sale.cashier_id == s.cashier_id,
                Sale.created_at >= s.opened_at,
                Sale.created_at <= (s.closed_at if s.closed_at else datetime.utcnow()),
                Sale.status == "completed",
                Sale.payment_method.in_(["plastic", "card"])
            )
        )
        sales_card_amount = sales_card.scalar() or 0

        # Qarz to'lovlari
        payments_result = await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.created_by == s.cashier_id,
                Payment.created_at >= s.opened_at,
                Payment.created_at <= (s.closed_at if s.closed_at else datetime.utcnow())
            )
        )
        total_payments = payments_result.scalar() or 0

        # Qarz to'lovlari usuli bo'yicha
        payments_cash = await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.created_by == s.cashier_id,
                Payment.created_at >= s.opened_at,
                Payment.created_at <= (s.closed_at if s.closed_at else datetime.utcnow()),
                Payment.payment_method == "cash"
            )
        )
        payments_cash_amount = payments_cash.scalar() or 0

        payments_terminal = await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.created_by == s.cashier_id,
                Payment.created_at >= s.opened_at,
                Payment.created_at <= (s.closed_at if s.closed_at else datetime.utcnow()),
                Payment.payment_method == "terminal"
            )
        )
        payments_terminal_amount = payments_terminal.scalar() or 0

        payments_transfer = await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.created_by == s.cashier_id,
                Payment.created_at >= s.opened_at,
                Payment.created_at <= (s.closed_at if s.closed_at else datetime.utcnow()),
                Payment.payment_method == "transfer"
            )
        )
        payments_transfer_amount = payments_transfer.scalar() or 0

        # Xarajatlar
        expenses_result = await db.execute(
            select(func.sum(Expense.amount)).where(
                Expense.created_by == s.cashier_id,
                Expense.created_at >= s.opened_at,
                Expense.created_at <= (s.closed_at if s.closed_at else datetime.utcnow())
            )
        )
        total_expenses = expenses_result.scalar() or 0
        
        expected_balance = s.opening_balance + total_sales + total_payments - total_expenses
        difference = (s.closing_balance - expected_balance) if s.closing_balance is not None else 0

        response_data.append({
            "id": s.id,
            "cashier": cashiers.get(s.cashier_id, "Noma'lum"),
            "opening_balance": s.opening_balance,
            "closing_balance": s.closing_balance,
            "opened_at": s.opened_at.strftime('%Y-%m-%d %H:%M'),
            "closed_at": s.closed_at.strftime('%Y-%m-%d %H:%M') if s.closed_at else None,
            "status": s.status,
            "total_sales": total_sales,
            "sales_cash": sales_cash_amount,
            "sales_card": sales_card_amount,
            "total_payments": total_payments,
            "payments_cash": payments_cash_amount,
            "payments_terminal": payments_terminal_amount,
            "payments_transfer": payments_transfer_amount,
            "total_expenses": total_expenses,
            "expected_balance": expected_balance,
            "difference": difference,
            "note": s.note
        })

    return response_data

# =====================================================
# EXCEL EKSPORT ENDPOINTLARI
# =====================================================

@app.get("/api/export/products")
async def export_products(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Mahsulotlarni CSV formatda eksport qilish"""
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    result = await db.execute(
        select(Product, Category.name.label('category_name'))
        .outerjoin(Category, Product.category_id == Category.id)
        .order_by(Product.name)
    )
    products = result.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['ID', 'Nomi', 'Shtrix kod', 'Sotish narxi', 'Olish narxi', 'Sklad', "O'lchov", 'Kategoriya'])

    # Data
    for p, cat_name in products:
        writer.writerow([
            p.id, p.name, p.barcode or '', p.sell_price or 0, p.buy_price or 0,
            p.stock, p.unit, cat_name or ''
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mahsulotlar_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

@app.get("/api/export/sales")
async def export_sales(
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Savdolarni CSV formatda eksport qilish"""
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    stmt = select(Sale).options(
        selectinload(Sale.items).selectinload(SaleItem.product),
        selectinload(Sale.client)
    ).order_by(Sale.created_at.desc())

    if start_date:
        stmt = stmt.where(Sale.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        stmt = stmt.where(Sale.created_at < end_dt)

    result = await db.execute(stmt)
    sales = result.scalars().all()

    # Kassirlar ismlarini olish
    cashier_ids = list(set(s.cashier_id for s in sales if s.cashier_id))
    cashiers = {}
    if cashier_ids:
        emp_result = await db.execute(select(Employee).where(Employee.id.in_(cashier_ids)))
        for emp in emp_result.scalars().all():
            cashiers[emp.id] = emp.full_name or emp.username

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['ID', 'Sana', 'Vaqt', 'Kassir', 'Mijoz', "To'lov usuli", 'Summa', 'Mahsulotlar', 'Holat'])

    # Data
    for s in sales:
        products_str = "; ".join([f"{item.product.name} x{item.quantity}" for item in s.items if item.product])
        writer.writerow([
            s.id,
            s.created_at.strftime('%Y-%m-%d'),
            s.created_at.strftime('%H:%M'),
            cashiers.get(s.cashier_id, ''),
            s.client.name if s.client else '',
            s.payment_method,
            s.total_amount,
            products_str,
            s.status
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=savdolar_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

@app.get("/api/export/clients")
async def export_clients(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Mijozlarni CSV formatda eksport qilish"""
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    result = await db.execute(select(Client).order_by(Client.name))
    clients = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['ID', 'Ism', 'Telefon', 'Balans', 'Qarz muddati', 'Telegram'])

    # Data
    for c in clients:
        writer.writerow([
            c.id, c.name, c.phone or '',
            c.balance,
            c.debt_due_date.strftime('%Y-%m-%d') if c.debt_due_date else '',
            'Ha' if c.telegram_id else 'Yo\'q'
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mijozlar_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

# =====================================================
# KASSIRLAR HISOBOTI
# =====================================================

@app.get("/api/cashier-report")
async def get_cashier_report(
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Kassirlar bo'yicha hisobot"""
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    # Sana filtri
    start_dt = datetime.strptime(start_date, '%Y-%m-%d') if start_date else datetime.now().replace(day=1, hour=0, minute=0, second=0)
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) if end_date else datetime.now() + timedelta(days=1)

    # Barcha kassirlarni olish
    emp_result = await db.execute(
        select(Employee).where(Employee.role.in_(['cashier', 'manager', 'admin']), Employee.is_active == True)
    )
    employees = emp_result.scalars().all()

    report = []

    for emp in employees:
        # Savdolar soni va summasi
        sales_result = await db.execute(
            select(
                func.count(Sale.id).label('count'),
                func.coalesce(func.sum(Sale.total_amount), 0).label('total')
            ).where(
                Sale.cashier_id == emp.id,
                Sale.created_at >= start_dt,
                Sale.created_at < end_dt,
                Sale.status == 'completed'
            )
        )
        sales_data = sales_result.first()

        # To'lov usullari bo'yicha
        cash_result = await db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                Sale.cashier_id == emp.id,
                Sale.created_at >= start_dt,
                Sale.created_at < end_dt,
                Sale.status == 'completed',
                Sale.payment_method == 'cash'
            )
        )
        cash_sales = cash_result.scalar() or 0

        card_result = await db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                Sale.cashier_id == emp.id,
                Sale.created_at >= start_dt,
                Sale.created_at < end_dt,
                Sale.status == 'completed',
                Sale.payment_method.in_(['card', 'terminal', 'plastic'])
            )
        )
        card_sales = card_result.scalar() or 0

        nasiya_result = await db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                Sale.cashier_id == emp.id,
                Sale.created_at >= start_dt,
                Sale.created_at < end_dt,
                Sale.status == 'completed',
                Sale.payment_method == 'nasiya'
            )
        )
        nasiya_sales = nasiya_result.scalar() or 0

        # Qarz to'lovlari
        payments_result = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.created_by == emp.id,
                Payment.created_at >= start_dt,
                Payment.created_at < end_dt,
                Payment.amount > 0
            )
        )
        total_payments = payments_result.scalar() or 0

        # Qaytarilgan savdolar (soni va summasi)
        refunds_result = await db.execute(
            select(
                func.count(Sale.id).label('count'),
                func.coalesce(func.sum(Sale.total_amount), 0).label('total')
            ).where(
                Sale.cashier_id == emp.id,
                Sale.created_at >= start_dt,
                Sale.created_at < end_dt,
                Sale.status == 'refunded'
            )
        )
        refunds_data = refunds_result.first()
        refunds_count = refunds_data.count if refunds_data else 0
        refunds_total = refunds_data.total if refunds_data else 0

        report.append({
            "id": emp.id,
            "name": emp.full_name or emp.username,
            "role": emp.role,
            "sales_count": sales_data.count if sales_data else 0,
            "sales_total": sales_data.total if sales_data else 0,
            "cash_sales": cash_sales,
            "card_sales": card_sales,
            "nasiya_sales": nasiya_sales,
            "payments_collected": total_payments,
            "refunds_count": refunds_count,
            "refunds_total": refunds_total,
            "avg_sale": round(sales_data.total / sales_data.count, 0) if sales_data and sales_data.count > 0 else 0
        })

    # Eng ko'p savdo qilgani bo'yicha tartiblash
    report.sort(key=lambda x: x['sales_total'], reverse=True)

    return report

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)