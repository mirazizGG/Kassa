# Do'kon Kassa Tizimi (POS System)

Bu Telegram bot funksiyasi bilan birlashtirilgan savdo do'koni uchun professional Kassa (POS) tizimi.

## Asosiy Funksiyalar

### 🏪 Kassa (POS) Tizimi
- **Mahsulotlarni qidirish va sotish** - Shtrix kod yoki nom bo'yicha qidirish
- **Savat boshqaruvi** - Real-time savat yangilanishi
- **Ko'p to'lov usullari**:
  - 💵 Naqd pul (cash)
  - 💳 Plastik karta (card/plastic)
  - 🏦 Nasiya (kredit)
- **Kassir smena boshqaruvi** - Smena ochish/yopish, kassa balansi kuzatuvi

### 👥 Xodimlar Boshqaruvi
- **Uch darajali rol tizimi**:
  - **Admin** - To'liq kirish, barcha funksiyalar
  - **Menejer** - Mahsulotlar, savdolar, mijozlar boshqaruvi (xodimlarni faqat ko'rish)
  - **Kassir** - Faqat sotuv va cheklangan funksiyalar
- Xodim ma'lumotlari: ism, telefon, manzil, pasport, izohlar

### 📦 Mahsulotlar va Sklad
- Mahsulot kategoriyalari
- Shtrix kod qo'llab-quvvatlash
- Olish va sotish narxlari
- Sklad kuzatuvi
- Kam sklad ogohlantirishlari (Telegram orqali)
- Kirim tarixini saqlash

### 👤 Mijozlar (CRM)
- Mijozlarni ro'yxatdan o'tkazish
- Balans kuzatuvi (oldindan to'lov / qarz)
- Nasiya savdolar
- Qarz muddatini belgilash
- Qarz to'lovlari tarixi
- Telegram bot integratsiyasi

### 💰 Moliya
- **Savdolar tarixi** - To'liq savdolar ro'yxati
- **Xarajatlar kuzatuvi** - Biznes xarajatlari va kategoriyalari
- **Statistika va hisobotlar**:
  - Tushum (revenue)
  - Yalpi foyda (gross profit)
  - Sof foyda (net profit)
  - Top mahsulotlar
- **Audit loglar** - Barcha muhim harakatlar tarixi

### 📱 Telegram Bot
- Mijozlarni ro'yxatdan o'tkazish (telefon + ism)
- Balans tekshirish
- Avtomatlashtirilgan qarz eslatmalari:
  - Muddatdan 3, 2, 1 kun oldin
  - Muddat kuni
  - Muddatdan keyin (kechiktirilgan)

## Texnologiyalar

- **Backend**: FastAPI (async)
- **ORM**: SQLAlchemy 2.0 (async rejim)
- **Ma'lumotlar bazasi**: SQLite (aiosqlite)
- **Bot**: Aiogram 3.x
- **Frontend**: Bootstrap 5, JavaScript
- **Autentifikatsiya**: JWT tokens
- **Parol xavfsizligi**: passlib (pbkdf2_sha256)

## O'rnatish va Ishga Tushirish

### 1. Talablar

Python 3.10 yoki yuqori versiya kerak.

### 2. Virtual Muhitni Yaratish

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Kerakli Kutubxonalarni O'rnatish

```bash
pip install fastapi uvicorn sqlalchemy aiosqlite python-jose passlib aiogram httpx python-multipart jinja2
```

Yoki requirements.txt orqali:

```bash
pip install -r requirements.txt
```

### 4. Muhit O'zgaruvchilarini Sozlash (MUHIM!)

**XAVFSIZLIK:** Ishlab chiqarishdan oldin quyidagi maxfiy kalitlarni o'zgartiring!

`main.py` faylida:
```python
# 20-qator
SECRET_KEY = "o'zingizning_maxfiy_kalitingiz"  # JWT uchun

# 198-qator (send_low_stock_alert funksiyasida)
token = "SIZNING_TELEGRAM_BOT_TOKEN"
```

`bot.py` faylida:
```python
# 16-qator
TOKEN = "SIZNING_TELEGRAM_BOT_TOKEN"
```

### 5. Telegram Bot Yaratish

1. Telegram da [@BotFather](https://t.me/botfather) ga yuboring: `/newbot`
2. Bot nomini kiriting
3. Bot username kiriting (\_bot bilan tugashi kerak)
4. Token ni nusxalang va `bot.py` hamda `main.py` ga qo'ying

### 6. Serverni Ishga Tushirish

```bash
python main.py
```

Yoki:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Server ishga tushgach:
- Veb-interfeys: http://127.0.0.1:8000
- Telegram bot avtomatik ishga tushadi

### 7. Birinchi Kirish

**Standart admin ma'lumotlari:**
- Login: `admin`
- Parol: `admin123`

⚠️ **MUHIM**: Birinchi kirishdan keyin admin parolini o'zgartiring!

## Foydalanish

### Kassir Uchun

1. **Smena ochish**:
   - Tizimga kiring
   - "Smena ochish" tugmasini bosing
   - Boshlang'ich kassadagi pul miqdorini kiriting

2. **Savdo qilish**:
   - Mahsulotlarni qidiring yoki shtrix kod skanerlang
   - Savatga qo'shing
   - "To'lov Qilish" tugmasini bosing
   - To'lov usulini tanlang:
     - **Naqd**: Qabul qilingan pul miqdorini kiriting
     - **Karta**: Tasdiqlash
     - **Nasiya**: Mijozni tanlang va muddatni belgilang

3. **Smena yopish**:
   - Ish tugagach "Smena yopish" tugmasini bosing
   - Haqiqiy kassadagi pul miqdorini kiriting
   - Tizim kutilgan va haqiqiy miqdor farqini ko'rsatadi

### Menejer Uchun

- Mahsulotlar qo'shish/o'zgartirish
- Kirimlarni ro'yxatlash
- Mijozlarni boshqarish
- Savdolarni ko'rish va qaytarish
- Xarajatlarni kiritish
- Statistika ko'rish
- Xodimlarni faqat ko'rish (o'zgartira olmaydi)

### Admin Uchun

- Barcha menejer funksiyalari
- Xodimlar qo'shish/o'chirish
- Audit loglarni ko'rish
- Tizim sozlamalari
- Telegram orqali xabar yuborish

## Ma'lumotlar Bazasi

### Asosiy Jadvallar

- **employees** - Xodimlar (admin, menejer, kassir)
- **products** - Mahsulotlar
- **categories** - Mahsulot kategoriyalari
- **clients** - Mijozlar
- **sales** - Savdolar
- **sale_items** - Savdo elementlari
- **shifts** - Kassir smenalari
- **payments** - Qarz to'lovlari
- **expenses** - Xarajatlar
- **supplies** - Kirimlar
- **audit_logs** - Audit loglar

### Ma'lumotlar Bazasi Boshqaruvi

Ma'lumotlar bazasi `market.db` faylida saqlanadi. Avtomatik migratsiyalar mavjud.

**Yordamchi Skriptlar:**

```bash
# Barcha xodimlarni ko'rish
python check_db_users.py

# Admin parolini qayta o'rnatish
python reset_admin.py

# Barcha xodimlar va smenalarni ko'rish
python check_all.py

# Ochiq smenalarni tekshirish
python check_shifts.py

# Barcha ochiq smenalarni yopish (faqat muammo bo'lganda!)
python fix_shifts.py
```

## Xavfsizlik

### Ro'llar va Ruxsatlar

| Funksiya | Kassir | Menejer | Admin |
|----------|--------|---------|-------|
| Savdo qilish | ✅ | ✅ | ✅ |
| Smena ochish/yopish | ✅ | ✅ | ✅ |
| Mahsulot qo'shish | ❌ | ✅ | ✅ |
| Mijoz qo'shish | ✅ | ✅ | ✅ |
| Savdoni qaytarish | ❌ | ✅ | ✅ |
| Xarajat qo'shish | ✅ | ✅ | ✅ |
| Xarajatni o'chirish | ❌ | ✅ | ✅ |
| Statistika ko'rish | ✅ | ✅ | ✅ |
| Xodimlarni ko'rish | ❌ | ✅ (faqat ko'rish) | ✅ |
| Xodim qo'shish/o'chirish | ❌ | ❌ | ✅ |
| Audit loglar | ❌ | ✅ | ✅ |

### Himoya

- JWT token autentifikatsiyasi
- Parollar hash qilingan (pbkdf2_sha256)
- RBAC (Role-Based Access Control)
- Audit logging
- O'zini o'chirishdan himoya
- Asosiy adminni o'chirishdan himoya

## API Endpointlar

### Autentifikatsiya
- `POST /token` - Tizimga kirish
- `GET /login` - Login sahifasi
- `GET /logout` - Chiqish

### Mahsulotlar
- `GET /api/products` - Mahsulotlar ro'yxati
- `POST /api/products` - Mahsulot qo'shish (menejer/admin)
- `PUT /api/products/{id}` - Mahsulotni yangilash (menejer/admin)
- `DELETE /api/products/{id}` - Mahsulotni o'chirish (menejer/admin)

### Savdolar
- `POST /api/sell` - Savdo yaratish
- `GET /api/sales` - Savdolar tarixi
- `POST /api/sales/{id}/refund` - Savdoni qaytarish (menejer/admin)

### Smenalar
- `POST /api/shifts/open` - Smena ochish
- `GET /api/shifts/current` - Joriy smenani olish
- `POST /api/shifts/{id}/close` - Smena yopish
- `GET /api/shifts` - Barcha smenalar

### Mijozlar
- `GET /api/clients` - Mijozlar ro'yxati
- `POST /api/clients` - Mijoz qo'shish
- `PUT /api/clients/{id}` - Mijozni yangilash (menejer/admin)
- `DELETE /api/clients/{id}` - Mijozni o'chirish (admin)
- `POST /api/clients/{id}/payment` - Qarz to'lovi qabul qilish
- `GET /api/clients/{id}/payments` - To'lovlar tarixi

### Xarajatlar
- `GET /api/expenses` - Xarajatlar ro'yxati
- `POST /api/expenses` - Xarajat qo'shish
- `DELETE /api/expenses/{id}` - Xarajatni o'chirish (menejer/admin)

### Xodimlar
- `GET /api/employees` - Xodimlar ro'yxati
- `POST /api/employees` - Xodim qo'shish (admin)
- `PUT /api/employees/{id}` - Xodimni yangilash (admin)
- `DELETE /api/employees/{id}` - Xodimni o'chirish (admin)

### Boshqalar
- `GET /api/stats` - Statistika
- `GET /api/audits` - Audit loglar
- `GET /api/categories` - Kategoriyalar
- `POST /api/supplies` - Kirim qo'shish
- `POST /api/broadcast` - Telegram xabar yuborish

## Muammolarni Hal Qilish

### Server ishga tushmayapti

```bash
# Portni tekshiring
netstat -ano | findstr :8000

# Boshqa portda ishga tushiring
python main.py --port 8001
```

### Telegram bot ishlamayapti

1. Bot tokenni tekshiring
2. Internet aloqani tekshiring
3. BotFather da botni toping va tokeni qayta nusxalang

### Ma'lumotlar bazasi xatosi

```bash
# Bazani backup qiling
copy market.db market_backup.db

# Migratsiya skriptlarini ishga tushiring
python migrate_expenses.py
```

### Smena ochilmayapti

```bash
# Ochiq smenalarni tekshiring
python check_shifts.py

# Agar kerak bo'lsa, yoping
python fix_shifts.py
```

## Kelajakda Qo'shilishi Kerak

- [ ] Excel/PDF hisobotlar
- [ ] SMS bildirişnomalar
- [ ] Mahsulot rasmlari
- [ ] Barcode printer qo'llab-quvvatlash
- [ ] Multi-language (Rus, Ingliz)
- [ ] Cloud backup
- [ ] Dashboard grafiklari

## Muallif

Bu loyiha Claude AI yordamida yaratildi.

## Litsenziya

MIT License - Shaxsiy va tijoriy foydalanish uchun ochiq.

---

**Qo'llab-quvvatlash:** Muammolar yoki savollar bo'lsa, GitHub Issues bo'limiga yozing.
