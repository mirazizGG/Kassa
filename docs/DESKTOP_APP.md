# SmartKassa Desktop (Electron) — qayta yasash qo'llanmasi

Bu hujjat `frontend/` ichidagi Electron o'ramini (desktop `.exe` dastur) qanday qayta build qilishni tushuntiradi. Backend (`backend/`) bunga kirmaydi — u alohida, oddiy Python server sifatida ishlaydi.

## Arxitektura, qisqacha

- **Backend** — bitta kompyuterda (yoki serverda) `python main.py` orqali ishlaydi, `0.0.0.0:8000`da tinglaydi.
- **Frontend (Electron)** — React ilovasini `frame:false` oynaga o'raydi, o'zining sarlavha panelini (`TitleBar.jsx`) chizadi va backendga HTTP orqali ulanadi.
- Ikkalasi orasidagi bog'lanish — oddiy REST so'rovlar (`VITE_API_URL`). Build vaqtida backend manzili frontend ichiga "qotib" yoziladi (runtime'da o'zgartirib bo'lmaydi — buni avval sinab ko'rib, o'chirib tashlagan edik, chunki keraksiz murakkablik edi).

## Talab qilinadigan narsalar

- Node.js va npm o'rnatilgan bo'lishi kerak
- `frontend/node_modules` o'rnatilgan (`npm install`)
- Windows'da build qilinadi (NSIS installer faqat Windows uchun)

## 1. Backend manzilini sozlash

`frontend/.env.electron` faylida backend qayerda ishlashini ko'rsating:

```
VITE_API_URL=http://<backend-kompyuterning-LAN-IP-manzili>:8000
```

Masalan: `VITE_API_URL=http://192.168.5.16:8000`

Bu kompyuterning joriy LAN IP manzilini bilish uchun:

```powershell
Get-NetIPConfiguration -InterfaceAlias "Ethernet" | Select-Object -ExpandProperty IPv4Address
```

**Muhim:** agar bu IP manzil o'zgarsa (router qayta ishga tushsa va h.k.), shu faylni yangilab, qaytadan build qilish kerak. Buning oldini olish uchun routerdan statik IP (DHCP reservation) berish tavsiya etiladi.

## 2. Build qilish

```bash
cd frontend
npm run electron:build
```

Bu buyruq:
1. `vite build --mode electron` — React ilovasini `.env.electron`dagi backend manzili bilan build qiladi (`frontend/dist/`).
2. `electron-builder` — Windows uchun `.exe` o'rnatuvchi yaratadi (`frontend/dist/SmartKassa Setup <versiya>.exe`).

Natija: `frontend/dist/SmartKassa Setup 1.0.0.exe` (~215 MB — shuning uchun bu fayl Git repo'ga qo'shilmagan, har safar mahalliy build qilinadi).

## 3. Backend uchun kerakli sozlamalar (build'dan mustaqil)

Desktop dastur ishlashi uchun backend tomonida:

- **`backend/.env`** faylida `ALLOWED_ORIGINS=*` bo'lishi kerak — Electron ilovasi tasodifiy portda ochiladi, shuning uchun aniq portlarni ro'yxatga kiritib bo'lmaydi.
- **Windows Firewall** — 8000-port boshqa kompyuterlardan kira olishi uchun ochiq bo'lishi kerak:
  ```powershell
  New-NetFirewallRule -DisplayName "SmartKassa Backend (8000)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Any
  ```
  (Administrator sifatida ishga tushirilishi kerak.)

## Fayllar tuzilishi

| Fayl | Vazifasi |
|---|---|
| `frontend/electron/main.cjs` | Electron asosiy jarayoni — oynani ochadi, production'da `dist/` papkasini mahalliy HTTP server orqali beradi (SPA routing to'g'ri ishlashi uchun) |
| `frontend/electron/preload.cjs` | Oynani yig'ish/kattalashtirish/yopish tugmalarini xavfsiz tarzda React'ga ulaydi (`window.electronAPI`) |
| `frontend/src/components/TitleBar.jsx` | Maxsus (native bo'lmagan) sarlavha paneli — faqat Electron ichida ko'rinadi (`window.electronAPI.isElectron` orqali aniqlanadi) |
| `frontend/build/icon.ico` / `icon.png` | Dastur ikonkasi. `frontend/build/gen_icon.py` (Python + Pillow) orqali qayta generatsiya qilinishi mumkin: `python build/gen_icon.py` |
| `frontend/build/installer.nsh` | NSIS o'rnatuvchisi uchun maxsus skript — agar dastur allaqachon o'rnatilgan bo'lsa, "Eski versiyani o'chirishni xohlaysizmi?" deb so'raydi |
| `frontend/package.json` → `"build"` bo'limi | electron-builder sozlamalari (appId, ikonka, NSIS parametrlari) |

## Muhim eslatmalar / o'tmishda uchragan muammolar

- **`min-h-screen` ishlatmang** sahifa darajasidagi komponentlarda (`Login.jsx`, `Layout.jsx` va h.k.) — Electron'da maxsus sarlavha paneli borligi sababli bu ortiqcha scroll paydo qiladi. O'rniga `min-h-full`/`h-full` ishlatiladi (`index.css`dagi `html, body, #root { height: 100% }` qoidasiga tayanadi).
- **Toast (sonner) mavzusi** — `frontend/src/components/ui/sonner.jsx` loyihaning o'z `theme-provider`idan foydalanadi, `next-themes`dan emas (bu kutubxona o'rnatilgan, lekin ishlatilmaydi — chalkashtirmang).
- **`oneClick: true`** — o'rnatuvchi hech qanday savol-javob oynasisiz o'rnatadi. Agar buni `false` qilsangiz, Windows "kim uchun o'rnatilsin" degan qo'shimcha savol beradi (kerak bo'lmasa, tegmang).

## Bitta kompyuterda ishga tushirish uchun (build qilmasdan, tez tekshirish)

```bash
cd frontend
npm run electron:dev
```

Bu `vite dev` serverini emas, to'g'ridan-to'g'ri `electron .` ni ishga tushiradi — oldindan `npm run dev` orqali Vite serverini alohida ishga tushirib qo'yish kerak (`electron/main.cjs` dev rejimida `http://localhost:5173`ni yuklaydi).
