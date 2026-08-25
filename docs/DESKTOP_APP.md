# SmartKassa Desktop — brauzer-yorliq qo'llanmasi

Ilgari desktop ilova Electron orqali `.exe` sifatida o'ralgan edi. Bu yechimdan
voz kechildi, chunki Electron 23-versiyadan boshlab Windows 7/8/8.1'ni umuman
qo'llab-quvvatlamaydi (minimal talab — Windows 10), va mijozlarning bir qismi
hali eski Windows ishlatadi. Hozirgi yechim — kompyuterda allaqachon mavjud
bo'lgan brauzerni (Chrome yoki Edge) "app mode"da ochadigan oddiy Desktop
yorlig'i. Bu har qanday Windows versiyasida ishlaydi, chunki biz brauzerning
o'zini emas, faqat undan foydalanishni talab qilamiz.

## Arxitektura, qisqacha

- **Backend** — bitta serverda (yoki kompyuterda) `python main.py` orqali
  ishlaydi, `0.0.0.0:8000`da tinglaydi.
- **Frontend** — build qilingan React ilovasi (`frontend/dist/`) shu serverda
  `vite preview` orqali alohida portda (`4173`) statik tarzda beriladi.
- **Har bir kassir kompyuteri** — faqat Desktop'da bitta yorliqqa muhtoj: u
  brauzerni `--app=http://<server-ip>:4173` bilan ochadi (manzil satri va
  tablarsiz, oddiy dastur oynasiga o'xshab ko'rinadi).

Node.js faqat frontendni build qilish va uni serverda `vite preview` bilan
ishga tushirish uchun serverga kerak — kassir kompyuterlarida umuman kerak
emas, ularda faqat brauzer bo'lsa yetarli.

## 1. Backend manzilini sozlash

`frontend/.env.production` faylida backend qayerda ishlashini ko'rsating:

```
VITE_API_URL=http://<backend-kompyuterning-LAN-IP-manzili>:8000
```

LAN IP manzilni bilish uchun:

```powershell
Get-NetIPConfiguration -InterfaceAlias "Ethernet" | Select-Object -ExpandProperty IPv4Address
```

**Muhim:** agar bu IP o'zgarsa (router qayta ishga tushsa), shu faylni
yangilab qayta build qilish kerak. Buning oldini olish uchun routerdan
statik IP (DHCP reservation) berish tavsiya etiladi.

## 2. Frontendni build qilib, serverda ishga tushirish

Backend bilan bir xil kompyuterda (yoki alohida serverda):

```bash
cd frontend
npm install
npm run build      # frontend/dist/ ni yaratadi, .env.production dagi manzil bilan
npm run preview    # 0.0.0.0:4173 da statik serverni ishga tushiradi
```

`npm run preview` terminalni band qilib turadi — doimiy ishlashi uchun uni
Windows xizmat sifatida (masalan, NSSM yoki Task Scheduler orqali "log off
bo'lganda ham ishlasin" qilib) sozlang, aks holda terminal yopilganda
frontend ham to'xtaydi.

## 3. Backend uchun kerakli sozlamalar

- **`backend/.env`**da `ALLOWED_ORIGINS`ga frontend manzilini qo'shing
  (masalan `http://192.168.5.16:4173`), yoki oddiylik uchun `*` qoldiring.
- **Windows Firewall** — 8000 (backend) va 4173 (frontend) portlari boshqa
  kompyuterlardan kira olishi kerak:
  ```powershell
  New-NetFirewallRule -DisplayName "SmartKassa Backend (8000)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Any
  New-NetFirewallRule -DisplayName "SmartKassa Frontend (4173)" -Direction Inbound -LocalPort 4173 -Protocol TCP -Action Allow -Profile Any
  ```
  (Administrator sifatida ishga tushirilishi kerak.)

## 4. Har bir kassir kompyuterida o'rnatish

`frontend/build/` papkasidagi 3 ta faylni (`SmartKassa-ornatish.bat`,
`install.ps1`, `icon.ico`) shu kompyuterga (masalan, AnyDesk fayl uzatish
orqali) nusxalab, **`SmartKassa-ornatish.bat`ni ikki marta bosing.**

Bu skript avtomatik ravishda:
1. Kompyuterda Chrome yoki Edge borligini tekshiradi (yo'q bo'lsa, aniq
   xabar chiqarib to'xtaydi — birortasini qo'lda o'rnatishni so'raydi).
2. Serverga (`192.168.5.16:4173`) ulanish borligini tekshiradi va
   natijasini ko'rsatadi (ulanmasa ham davom etadi — server keyinroq
   yoqilishi mumkin).
3. Desktop'da SmartKassa ikonkasi bilan "SmartKassa" yorlig'ini yaratadi.

Yorliqni bosganda brauzer manzil satrisiz, alohida oyna sifatida ochiladi.

Boshqa server manzili yoki yorliq nomi bilan ishlatish uchun (masalan sinov
uchun) to'g'ridan-to'g'ri PowerShell orqali parametr berish mumkin:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -ServerUrl "http://192.168.5.16:4173" -ShortcutName "SmartKassa"
```

## Fayllar tuzilishi

| Fayl | Vazifasi |
|---|---|
| `frontend/build/SmartKassa-ornatish.bat` | Kassir kompyuterida ikki marta bosib ishga tushiriladigan o'rnatuvchi |
| `frontend/build/install.ps1` | Brauzerni tekshiradi, serverga ulanishni sinaydi, Desktop yorlig'ini yaratadi |
| `frontend/build/icon.ico` / `icon.png` | Yorliq ikonkasi (kassa apparati). `frontend/build/gen_icon.py` (Python + Pillow) orqali qayta generatsiya qilinishi mumkin |
| `frontend/.env.production` | Build vaqtida "qotib" yoziladigan backend manzili |

## Eski Electron yechimi haqida

Avvalgi versiyada `frontend/electron/`, NSIS installer va Electron-ga xos
`TitleBar.jsx` mavjud edi — bularning barchasi olib tashlandi. Sabab: bitta
mijoz kompyuteri Windows 8.1 ishlatgani va Electron 43 asosidagi `.exe`
"This app can't run on your PC" xatosi bilan umuman ochilmagan edi.
