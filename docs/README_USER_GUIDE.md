# SmartKassa: Menejer va Xavfsizlik Qo'llanmasi

Ushbu hujjat yangi qo'shilgan funksiyalar qanday ishlashi va muammo bo'lsa qanday to'g'irlash haqida.

---

## 1. Menejer Bo'limi (Manager Access)

**Qanday ishlaydi?**

- Menejer roli bilan kirgan xodim faqat o'z ishiga tegishli narsalarni ko'radi.
- **Yashirin:** Foyda (Profit), Tannarx (Cost) va Tizim sozlamalari menejerga ko'rinmaydi.
- **Ruxsat berilgan:** Kunlik savdo hajmi, xarajatlar va kassirlarning smenalarini tekshirish.

**Muammo bo'lsa:**

- Agar menejer kerakli bo'limni ko'rmasa, Admin profilidan "Xodimlar" bo'limiga kirib, uning rolini tekshiring.

---

## 2. Avtomatik Zahiralash (Auto-Backup)

**Qanday ishlaydi?**

- **Jadval bo'yicha:** `BACKUP_HOURS` da ko'rsatilgan soatlarda (sukut bo'yicha 12:00 va 22:00).
- **Har ishga tushganda:** dastur yoqilganda ham nusxa olinadi (oxirgisi bir soatdan yangi bo'lsa - o'tkazib yuboriladi).
- **Qo'lda:** Sozlamalar sahifasidagi "Zahira nusxa" tugmasi.
- Nusxa bir vaqtning o'zida bir necha manzilga boradi: `backend/backups/`, tashqi papka
  (`BACKUP_MIRROR_DIR`), maxfiy GitHub repozitoriysi va admin Telegrami - qaysi biri sozlangan bo'lsa.

> Ilgari bu yerda "har chek urilganda nusxa olinadi" deb yozilgan edi. Bu endi TO'G'RI EMAS
> va atayin olib tashlangan: har sotuvdan keyin nusxa olish eski nusxalarni siqib chiqarib,
> saqlash oynasini "oxirgi 30 ta sotuv" ga qisqartirib qo'yardi - ertalabki nusxa tushlikkacha
> o'chib ketardi.

### Ma'lumotni tiklash (Restore)

**DIQQAT.** SQLite bazasi bitta fayldan iborat EMAS. Yonida `market.db-wal` va
`market.db-shm` fayllari turadi va ularda hali asosiy faylga yozilmagan ma'lumot
bo'lishi mumkin. Agar faqat `market.db` ni almashtirsangiz, SQLite eski
`-wal` faylni YANGI baza ustiga yozib yuboradi va tiklangan nusxa buziladi.
Uchalasini HAR DOIM birga o'chiring.

**SQLite (do'kondagi kompyuter):**

1. Dasturni to'liq **to'xtating** (backend jarayoni ham).
2. `backend/` papkasidan uchala faylni birga o'chiring yoki boshqa joyga ko'chiring:
   `market.db`, `market.db-wal`, `market.db-shm`.
3. `backend/backups/` dan eng so'nggi `backup_*.db` faylni `backend/market.db` nomi bilan qo'ying.
4. Dasturni qayta ishga tushiring.
5. Bir nechta sotuvni va mijoz qarzini ochib, ma'lumot joyidaligini tekshiring.

**PostgreSQL (server):**

Serverdagi nusxalar `.dump` ko'rinishida bo'ladi va ular `pg_restore` bilan tiklanadi.
To'liq tartib: `deploy/DEPLOY.md` -> "Восстановление".

### Nusxa ishlashiga ishonch hosil qiling

Nusxa OLISH va nusxadan TIKLASH - ikki xil narsa. Oyda bir marta tekshiring:

    deploy/scripts/backup-verify.sh

Skript eng so'nggi nusxani vaqtinchalik bazaga tiklab, jadvallardagi satrlar
sonini ko'rsatadi va o'zidan keyin tozalab ketadi.

---

## 3. Audit va Nazorat (Audit Logs)

**Qanday ishlaydi?**

- Tizim quyidagilarni avtomatik yozib boradi:
  - Mahsulot o'chirilishi.
  - Xarajat qo'shilishi.
  - Xodim ma'lumotlari o'zgarishi.
- Admin profilida "Audit" sahifasida buni ko'rish mumkin.

---

## 4. Telegram Bot (Cloud Backup)

**Qanday ishlaydi?**

- Bot ishlashi uchun `.env` faylida `BOT_TOKEN` to'g'ri bo'lishi kerak.
- Admin o'zini botda ro'yxatdan o'tkazgan bo'lishi shart.

**Fayl kelmasa nima qilish kerak?**

1. Bot yoqilganini tekshiring (`python bot.py`).
2. Admin botga `/start` bosganini va telefon raqamini yuborganini tekshiring.
3. Internet borligiga ishonch hosil qiling.

---

> [!TIP]
> Har kuni kechqurun zahira nusxasini boshqa bir qurilmaga (fleshka yoki bulut) saqlab qo'yishni tavsiya qilamiz.
