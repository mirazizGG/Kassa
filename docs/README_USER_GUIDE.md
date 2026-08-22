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

- **Sotuvda:** Har safar chek urilganda, `backend/backups/` papkasiga bazaning nusxasi olinadi.
- **Smena yopilganda:** Dastur eng so'nggi bazani Adminning **Telegramiga** yuboradi.

**Ma'lumotni tiklash (Restore):**
Agar baza buzilsa yoki kompyuter almashtirilsa:

1. `backend/backups/` papkasidan yoki Telegramdan eng so'nggi `.db` faylni toping.
2. `backend/market.db` faylini o'chirib yuboring (yoki nomini o'zgartiring).
3. Zahira faylini nomini shunchaki `market.db` ga o'zgartiring va o'rniga qo'ying.
4. Dasturni qayta ishga tushiring.

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
