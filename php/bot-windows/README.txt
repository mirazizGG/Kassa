KASSA BOT — DO'KON KOMPYUTERIGA O'RNATISH
==========================================

Bu papka do'kondagi kompyuterda Telegram botni ishlatadi. Kassa dasturining
o'zi serverda ishlaydi; bot shu kompyuterdan server bazasiga ulanadi.

Bot nima qiladi:
  • Har kuni 22:00 — adminga kunlik hisobot (savdo, foyda, kassirlar, top mahsulotlar)
  • Har kuni 22:00 — bazaning zahira nusxasi Telegramga
  • Har kuni 09:00 — qarzdor mijozlarga eslatma, adminga muddati o'tganlar ro'yxati
  • Darhol — vozvrat, kamomadli smena, narxdan arzon sotuv, tugayotgan mahsulot
  • Xodimlar botda "Ishga kelish / Ishdan ketish" bosadi, admin "Kim ishda?" ni ko'radi
  • Mijozlar botda o'z balansi va bonusini ko'radi
  • Admin menyusi: Bugungi hisobot, Kim ishda?, Ma'lumotlar (Excel), Reklama yuborish

Kompyuter o'chiq bo'lsa, 22:00 dagi hisobot va zahira kompyuter keyingi safar
yoqilganda (shu kunning o'zida) yuboriladi.


O'RNATISH
---------
1. Hostingda (cPanel → Remote MySQL) shu kompyuterning IP manzilini ruxsat
   etilganlar ro'yxatiga qo'shing. Busiz bot bazaga ulana olmaydi.

2. .env faylini Bloknot bilan oching va DATABASE_URL qatorini to'ldiring:
       DATABASE_URL=mysql://FOYDALANUVCHI:PAROL@SERVER_MANZILI:3306/BAZA_NOMI
   Parolda @ : / ? # bo'lsa foizli kodlang (@ -> %40).

3. ORNATISH.bat ni ikki marta bosing va "Ha" (Administrator) ni tanlang.
   Skript o'zi: PHP ni yuklaydi, aloqani tekshiradi, botni ishga tushiradi va
   kompyuter har safar yoqilganda avtomatik ishga tushadigan qilib qo'yadi.

4. Telegramda botga /start yozing.


XODIMLARNI BOTGA ULASH
----------------------
Saytdagi Xodimlar sahifasida xodimning TELEFON raqami to'ldirilgan bo'lishi
kerak. Xodim botga /start yozib, o'sha raqamni yuborsa — xodim sifatida tanib
olinadi. Raqami mos kelmasa, mijoz sifatida ro'yxatdan o'tadi.

Admin menyusi: saytda admin bo'lgan xodim botga ulansa, yoki .env dagi
TELEGRAM_ADMIN_CHAT_ID ga teng chatda chiqadi. Hisobot va ogohlantirishlar
ikkalasiga ham boradi.


VAQTLARNI O'ZGARTIRISH (.env)
-----------------------------
  BOT_REPORT_TIME=22:00        kunlik hisobot
  BACKUP_TIME=22:00            zahira nusxa
  DEBT_REMINDER_TIME=09:00     qarz eslatmalari
  BOT_NOTIFY_ATTENDANCE=true   xodim kelib-ketganda adminga xabar (false — o'chirish)
O'zgartirgandan keyin kompyuterni qayta yoqing yoki ORNATISH.bat ni qayta bosing.


MUAMMO BO'LSA
-------------
  logs\bot.log            — bot nima qilayotgani
  logs\bot-console.log    — xatolar
  OCHIRISH.bat            — botni to'xtatish va avtomatik ishga tushishni olib tashlash
