# CLAUDE.md

Bu fayl Claude Code (claude.ai/code) uchun ushbu repozitoriydagi kod bilan ishlashda yo'riqnoma beradi.

## Loyiha Haqida Umumiy Ma'lumot

Bu Telegram bot funksiyasi bilan birlashtirilgan savdo do'koni uchun Kassa (POS) tizimi. Tizim quyidagilarni taqdim etadi:
- Xodimlar (adminlar, menejerlar, kassirlar) uchun veb-asosli kassa interfeysi
- Mijozlar uchun Telegram bot (balans tekshirish, qarz eslatmalari)
- Inventar va sklad boshqaruvi
- Mijozlar bilan munosabatlar boshqaruvi (CRM) kredit/qarz kuzatuvi bilan
- Savdo tahlillari va xarajatlarni kuzatish

**Texnologiyalar:**
- **Backend**: FastAPI (async)
- **ORM**: SQLAlchemy 2.0 (async rejim)
- **Ma'lumotlar bazasi**: SQLite (aiosqlite)
- **Bot Framework**: Aiogram 3.x
- **Shablonlar**: Jinja2
- **Autentifikatsiya**: JWT (python-jose bilan), passlib (parol xashlash uchun)

## Ilovani Ishga Tushirish

### Development Server (Ishlab Chiqish Serveri)

Virtual muhitni faollashtiring va FastAPI serverini ishga tushiring:

```bash
# Windows
venv\Scripts\activate

# Serverini auto-reload bilan ishga tushirish
python main.py
# YOKI
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Veb-interfeys `http://127.0.0.1:8000/` manzilida mavjud bo'ladi

### Standart Admin Ma'lumotlari

- Foydalanuvchi nomi: `admin`
- Parol: `admin123`

Admin foydalanuvchi birinchi ishga tushirilganda avtomatik ravishda yaratiladi (agar mavjud bo'lmasa).

### Telegram Bot

Telegram bot FastAPI ilovasi ishga tushganda avtomatik ravishda ishga tushadi (lifespan context manager orqali). Alohida jarayon kerak emas.

## Ma'lumotlar Bazasi Boshqaruvi

### Ma'lumotlar Bazasi Fayli

Asosiy ma'lumotlar bazasi `market.db` (SQLite, aiosqlite orqali async qo'llab-quvvatlash bilan).

### Sxema Migratsiyalari

Ma'lumotlar bazasi sxemasi quyidagilar orqali boshqariladi:
1. **Avtomatik migratsiyalar** `main.py` lifespan funksiyasida (99-138 qatorlar) - etishmayotgan ustunlarni qo'shishni boshqaradi
2. **SQLAlchemy metadata** - `Base.metadata.create_all()` etishmayotgan jadvallarni avtomatik yaratadi

### Yordamchi Skriptlar

```bash
# Bazadagi barcha xodimlarni tekshirish
python check_db_users.py

# Admin parolini '123' ga qayta o'rnatish
python reset_admin.py

# Xarajatlar jadvalini migratsiya qilish (created_by ustunini qo'shish)
python migrate_expenses.py
```

## Arxitektura

### Asosiy Fayllar

- **[main.py](main.py)** (1036 qator): Barcha API endpointlar bilan FastAPI ilovasi
  - Autentifikatsiya va JWT token boshqaruvi
  - Xodimlar/foydalanuvchilar boshqaruvi
  - Mahsulot va kategoriyalar CRUD
  - Savdo/kassa logikasi to'lov usullari bilan (naqd, terminal, karta, nasiya)
  - Mijozlarni boshqarish va qarzlarni kuzatish
  - Xarajatlarni kuzatish
  - Statistika va hisobotlar
  - Audit loglar
  - Telegram bot foydalanuvchilariga xabar yuborish

- **[bot.py](bot.py)** (174 qator): Aiogram yordamida Telegram bot
  - Mijozlarni ro'yxatdan o'tkazish jarayoni (telefon raqami + ism)
  - Balansni tekshirish
  - Qarz eslatmasi bildirişnomalari (har soatda ishlaydi, ertalab 9:00 da yuboradi)
  - FSM (Finite State Machine) bilan holat boshqaruvi

- **[database.py](database.py)** (127 qator): SQLAlchemy modellari va ma'lumotlar bazasi sozlamalari
  - Barcha ma'lumotlar bazasi jadvallari/modellari
  - Async sessiya boshqaruvi
  - Ma'lumotlar bazasini boshlash

### Ma'lumotlar Bazasi Modellari

Asosiy modellar ([database.py](database.py) ga qarang):

- **Employee**: Tizim foydalanuvchilari (admin/menejer/kassir) rol asosidagi ruxsatlar bilan
- **Product**: Inventar mahsulotlari shtrix kod, narxlar, sklad, o'lchov birligi, kategoriya bilan
- **Category**: Mahsulot kategoriyalari
- **Client**: Mijozlar balans kuzatuvi bilan (kredit/oldindan to'lovni qo'llab-quvvatlaydi), Telegram bilan bog'langan
- **Sale**: Savdo tranzaksiyalari to'lov usuli, umumiy summa, holati bilan
- **SaleItem**: Har bir savdo uchun qator elementlari (mahsulot, miqdori, narxi)
- **Expense**: Biznes xarajatlari sabab, summa, kategoriya bilan
- **Supply**: Inventar yetkazib berish/qayta to'ldirish tarixi
- **AuditLog**: Muhim harakatlarning audit iz
- **User**: Eski bot foydalanuvchilari jadvali (ishlatilmayotgan ko'rinadi, o'rniga Client ishlatiladi)

### Asosiy Munosabatlar

- **Sale** → **SaleItem** → **Product**: Savdolar mahsulotlarga havola qiluvchi bir nechta elementlarni o'z ichiga oladi
- **Sale** → **Employee** (kassir sifatida): Qaysi xodim savdoni amalga oshirganini kuzatadi
- **Sale** → **Client** (ixtiyoriy): Savdolarni aniq mijozlarga bog'laydi (nasiya/kredit uchun majburiy)
- **Client.balance**: Musbat = oldindan to'lov/depozit, Manfiy = qarz
- **Client.telegram_id**: CRM mijozni Telegram bot foydalanuvchisiga bog'laydi

## To'lov Jarayoni

### Nasiya (Kredit) Savdolari

Qachonki `payment_method == 'nasiya'`:
1. Mijoz tanlanishi shart (majburiy)
2. Savdo summasi mijoz balansidan **ayiriladi**
3. Agar natijada balans manfiy bo'lsa (qarz):
   - `debt_due_date` o'rnatiladi (so'rovdan yoki standart +30 kun)
   - Qarz eslatmasi bildirişnomalari yoqiladi
4. Agar balans musbat bo'lib qolsa (oldindan to'lov qoplaydi):
   - `debt_due_date` tozalanadi

### Sklad Boshqaruvi

- Sklad savdo yaratilganda **kamaytiriladi** ([main.py:553](main.py#L553))
- Sklad savdo qaytarilganda **oshiriladi** ([main.py:637](main.py#L637))
- Kam sklad ogohlantirishlari (<5 birlik) Telegram bildirişnomalarini ishga tushiradi ([main.py:541-559](main.py#L541-L559))

## API Endpointlar

Barcha endpointlar JWT autentifikatsiyasini talab qiladi (`/login` va `/token` dan tashqari).

### Autentifikatsiya
- `POST /token` - Tizimga kirish, JWT access token qaytaradi
- `GET /login` - Login sahifasi
- `GET /logout` - Tizimdan chiqish va tokenni tozalash

### Mahsulotlar va Kategoriyalar
- `GET /api/products?search=&category_id=` - Mahsulotlarni ro'yxatlash/qidirish
- `POST /api/products` - Mahsulot yaratish (faqat admin/menejer)
- `PUT /api/products/{id}` - Mahsulotni yangilash (faqat admin/menejer)
- `DELETE /api/products/{id}` - Mahsulotni o'chirish (faqat admin/menejer)
- `GET /api/categories` - Kategoriyalarni ro'yxatlash
- `POST /api/categories` - Kategoriya yaratish (faqat admin/menejer)
- `DELETE /api/categories/{id}` - Kategoriyani o'chirish (faqat admin/menejer)

### Savdolar
- `POST /api/sell` - Savdo yaratish/kassa
- `GET /api/sales?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` - Savdolarni ro'yxatlash
- `POST /api/sales/{id}/refund` - Savdoni qaytarish, skladni tiklash (faqat admin/menejer)

### Mijozlar
- `GET /api/clients` - Barcha mijozlarni ro'yxatlash
- `POST /api/clients` - Mijoz yaratish
- `PUT /api/clients/{id}` - Mijozni yangilash (faqat admin/menejer)
- `DELETE /api/clients/{id}` - Mijozni o'chirish (faqat admin)
- `POST /api/clients/{id}/debt` - Mijozga qarz qo'shish (faqat admin/menejer)

### Xarajatlar
- `GET /api/expenses?start_date=&end_date=` - Xarajatlarni ro'yxatlash
- `POST /api/expenses` - Xarajat yaratish
- `DELETE /api/expenses/{id}` - Xarajatni o'chirish (faqat admin/menejer)

### Yetkazib Berish
- `POST /api/supplies` - Yetkazib berish/qayta to'ldirish qo'shish (mahsulot skladi va buy_price ni yangilaydi)
- `GET /api/supplies` - Yetkazib berish tarixini ro'yxatlash

### Statistika
- `GET /api/stats?start_date=&end_date=` - Daromad, foyda, xarajatlar, eng ko'p sotiladigan mahsulotlarni olish

### Administrator
- `GET /api/employees` - Xodimlarni ro'yxatlash (admin - barcha xodimlar, menejer - faqat ko'rish, adminlar ko'rinmaydi)
- `POST /api/employees` - Xodim yaratish (faqat admin)
- `PUT /api/employees/{id}` - Xodimni yangilash (faqat admin)
- `DELETE /api/employees/{id}` - Xodimni o'chirish (faqat admin)
- `GET /api/audits?start_date=&end_date=` - Audit logni ko'rish (faqat admin/menejer)
- `POST /api/broadcast` - Telegram foydalanuvchilariga xabar yuborish (faqat admin/menejer)

## Xavfsizlik Masalalari

### MUHIM: Qattiq Kodlangan Maxfiy Kalitlar

**KRITIK**: Quyidagi maxfiy kalitlar qattiq kodlangan va ishlab chiqarishdan oldin o'zgartirilishi kerak:

1. **JWT Maxfiy Kaliti** [main.py:20](main.py#L20) da:
   ```python
   SECRET_KEY = "bu_juda_maxfiy_kalit_uchun_ozgartiring"
   ```

2. **Telegram Bot Tokeni** [bot.py:16](bot.py#L16) va [main.py:167](main.py#L167) da:
   ```python
   TOKEN = "8301998756:AAEBjeXT-eURJ4olXG2jvhlhI-s8MyMeYug"
   ```

**TALAB QILINADIGAN HARAKAT**: Bularni joylashtirshdan oldin muhit o'zgaruvchilariga o'tkazing.

### Rol Asosidagi Kirish Nazorati

- **Admin**: Barcha funksiyalarga to'liq kirish
- **Menejer**: Xodimlar bo'limini faqat ko'rishi mumkin (read-only, adminlar ko'rinmaydi). Boshqa bo'limlarda to'liq kirish.
- **Kassir**: Xodimlar bo'limiga umuman kirolmaydi. Faqat POS operatsiyalari va cheklangan boshqaruv kirishlari.

O'zini o'chirish bloklangan ([main.py:312](main.py#L312)). Asosiy admin foydalanuvchini o'chirish mumkin emas ([main.py:316](main.py#L316)).

## Umumiy Ish Jarayonlari

### Yangi Mahsulot Qo'shish

1. Kerak bo'lsa kategoriya yarating: `POST /api/categories`
2. Mahsulot yarating: `POST /api/products` category_id bilan
3. Boshlang'ich skladni qo'shing: `POST /api/supplies`

### Savdoni Amalga Oshirish

1. Mahsulotlarni skanerlash/tanlash
2. Agar kredit savdo bo'lsa: mijozni tanlang, due_date ni o'rnating
3. Yuborish: `POST /api/sell` items massivi, payment_method, ixtiyoriy client_id bilan
4. Sklad avtomatik ravishda kamayadi
5. Nasiya uchun: mijoz balansi yangilanadi, due_date o'rnatiladi

### Savdoni Qaytarish

1. Admin/Menejer: `POST /api/sales/{id}/refund`
2. Sklad avtomatik ravishda tiklanadi
3. Holat "refunded" ga o'zgartiriladi
4. Audit log yaratiladi

## Telegram Bot Ish Jarayoni

1. Mijoz: `/start` buyrug'i
2. Bot telefon raqamini so'raydi (kontakt tugmasi)
3. Bot to'liq ismni so'raydi
4. Mijoz yozuvi telegram_id bilan yaratiladi/yangilanadi
5. Mijoz balansni tekshirishi mumkin: "💰 Balansim" tugmasi
6. Avtomatlashtirilgan qarz eslatmalari har soatda ishlaydi (faqat ertalab 9:00 da yuboradi):
   - Muddatdan 3 kun oldin
   - Muddatdan 2 kun oldin
   - Muddatdan 1 kun oldin
   - Muddat kuni
   - Muddatdan keyin (kechiktirilgan)

## Kod Konvensiyalari

- **Til**: Izohlar va UI matni o'zbek tilida (lotin yozuvi)
- **Async/Await**: Barcha ma'lumotlar bazasi operatsiyalari async
- **DateTime**: Vaqt belgilari uchun `datetime.utcnow()` ishlatiladi
- **Valyuta**: Summalar so'm (O'zbekiston valyutasi) da
- **Exception Handling**: API xatolari uchun HTTPException, bot operatsiyalari uchun try/except
