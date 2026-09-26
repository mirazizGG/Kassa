KASSA BOT — DO'KON KOMPYUTERIGA O'RNATISH
==========================================

Kassa sayti serverda ishlaydi. Bu papka do'kondagi kompyuterda Telegram botni
ishlatadi: bot Telegramdan xabarni oladi, serverga (sayt API'si orqali,
HTTPS) uzatadi va javobni Telegramga yetkazadi. Barcha hisob-kitob serverda.
Baza paroli bu kompyuterda YO'Q — faqat sayt manzili va maxfiy kalit.

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


O'RNATISHDAN OLDIN — SERVERDA (bir marta)
------------------------------------------
1. Serverdagi kassa kodi yangi bo'lishi kerak (unda /bot API bo'lsin).
2. Serverdagi .env ga BOT_API_KEY qatorini qo'shing — QIYMATI shu papkadagi
   .env dagi BOT_API_KEY bilan BIR XIL bo'lishi shart. Shuningdek
   TELEGRAM_ADMIN_CHAT_ID ham serverda bo'lsin (hisobot kimga borishi uchun).


O'RNATISH — DO'KON KOMPYUTERIDA
-------------------------------
1. .env faylida KASSA_API_URL to'g'ri ekanini tekshiring (sayt manzili,
   masalan https://smart-kassa.uz).
2. ORNATISH.bat ni ikki marta bosing va "Ha" (Administrator) ni tanlang.
   Skript o'zi: PHP ni yuklaydi, server va Telegram bilan aloqani tekshiradi,
   botni ishga tushiradi va kompyuter har safar yoqilganda avtomatik ishga
   tushadigan qilib qo'yadi.
3. Telegramda botga /start yozing.


XODIMLARNI BOTGA ULASH
----------------------
Saytdagi Xodimlar sahifasida xodimning TELEFON raqami to'ldirilgan bo'lishi
kerak. Xodim botga /start yozib, o'sha raqamni yuborsa — xodim sifatida tanib
olinadi. Raqami mos kelmasa, mijoz sifatida ro'yxatdan o'tadi.

Admin menyusi: saytda admin bo'lgan xodim botga ulansa, yoki serverdagi
TELEGRAM_ADMIN_CHAT_ID ga teng chatda chiqadi. Hisobot va ogohlantirishlar
ikkalasiga ham boradi.


VAQTLARNI O'ZGARTIRISH — SERVERDAGI .env da
-------------------------------------------
  BOT_REPORT_TIME=22:00        kunlik hisobot
  BACKUP_TIME=22:00            zahira nusxa
  DEBT_REMINDER_TIME=09:00     qarz eslatmalari
  BOT_NOTIFY_ATTENDANCE=true   xodim kelib-ketganda adminga xabar (false — o'chirish)


BOSHQA REJIM (kassa shu kompyuterning o'zida bo'lsa)
----------------------------------------------------
KASSA_API_URL ni o'chirib, DATABASE_URL ni yozsangiz — bot bazaga o'zi ulanadi
va hammasini o'zi hisoblaydi. Bunda vaqtlar shu .env dan olinadi.


MUAMMO BO'LSA
-------------
  logs\bot.log            — bot nima qilayotgani
  logs\bot-console.log    — xatolar
  OCHIRISH.bat            — botni to'xtatish va avtomatik ishga tushishni olib tashlash
