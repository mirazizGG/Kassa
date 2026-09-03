# SmartKassa — Deploy qo'llanmasi (tekin, do'kon kompyuterida)

Loyiha **do'kondagi bitta doim yoniq kompyuterda** ishlaydi. Kassir kompyuterlariga
hech narsa o'rnatilmaydi — ular faqat brauzer bilan kiradi.

- **Do'kon ichidan (LAN)** — `http://SERVER-IP:8000` (Caddy/Node kerak emas)
- **Uydan / tashqaridan** — `https://kassa.SIZNING-DOMEN` (ixtiyoriy, Cloudflare Tunnel)

```
Uyda:  kod o'zgartirish ──▶ publish.ps1 (build + push) ──▶ GitHub
                                                             │
Do'konda:  "Yangilash" tugmasi / update.ps1 ──git pull──────┘
                                    │
                     uvicorn :8000 ─┘   (backend API + frontend/dist + SPA)
                            ▲
        (ixtiyoriy)  Caddy :8080 ──▶ Cloudflare Tunnel ──▶ https://kassa.domen
```

Frontend **serverda build qilinmaydi** — u repodagi tayyor `frontend/dist` dan
olinadi (uyda `publish.ps1` build qiladi), backend uni o'zi beradi. Shu tufayli
serverga **Node.js va Caddy kerak emas** — faqat **Python + Git**. Windows 8.1 da ham ishlaydi.

---

## Eng oson yo'l — bir fayllik o'rnatuvchi (LAN)

Server kompyuterda oddiy PowerShell oynasida (Administrator shart emas — skript o'zi so'raydi).
Ikki yo'l, ikkalasi ham bir xil natija beradi:

**A) Loyihani o'zingiz yuklab olib (tavsiya etiladi)**

```powershell
git clone https://github.com/mirazizGG/Kassa.git C:\SmartKassa
cd C:\SmartKassa
.\deploy\install-smartkassa.ps1
```

Skript o'sha papkani (`C:\SmartKassa`) ishlatadi — boshqa joyga qayta klon qilmaydi.
(Git hali yo'q bo'lsa — 1-buyruq ishlamaydi; u holda B yo'lini ishlating, skript Git ni o'zi o'rnatadi.)

**B) Hech narsa yuklamasdan, bitta buyruq bilan**

```powershell
irm https://raw.githubusercontent.com/mirazizGG/Kassa/main/deploy/install-smartkassa.ps1 | iex
```

Bu holda loyiha `C:\SmartKassa` ga klon qilinadi.

O'rnatuvchi: Python + Git ni yuklaydi (yo'q bo'lsa) · kodni tayyorlaydi ·
`pip install` · `backend\.env` (+ tasodifiy `SECRET_KEY`) · `APP_ENV=production` +
`ALLOW_SELF_UPDATE=true` · ishga tushiradi · kompyuter yonganda avtomat ishlashini o'rnatadi.
Qayta ishga tushirish xavfsiz — faqat yangilaydi.

Tugagach: `http://SERVER-IP:8000`, login `miraziz` / `8434` (**darhol o'zgartiring**).

Internet orqali kirish (Cloudflare Tunnel) kerak bo'lsa — pastdagi to'liq qo'llanma.

### Uyda: o'zgarishni chiqarish

```powershell
.\deploy\publish.ps1 "nima o'zgardi"
```

Bu build qiladi, `dist` bilan birga commit qiladi va push qiladi. Keyin do'konda
ekrandagi **"Yangilash"** tugmasi (yoki `update.ps1`) o'sha versiyani tortadi.

---

## 0. Nima kerak (SERVER kompyuterda)

| Dastur      | Izoh                                                                           |
| ----------- | ------------------------------------------------------------------------------ |
| Git         | https://git-scm.com (Win 7+ ishlaydi) — o'rnatuvchi o'zi yuklaydi              |
| Python 3.9+ | https://python.org — o'rnatuvchi o'zi yuklaydi (Win 8.1 → 3.9, Win 10+ → 3.12) |
| cloudflared | _faqat_ internet orqali kirish uchun: `winget install Cloudflare.cloudflared`  |
| Caddy       | _faqat_ internet orqali kirish uchun: `winget install CaddyServer.Caddy`       |
| Domen       | _faqat_ internet uchun: Cloudflare'ga ulangan domen                            |

Node.js **kerak emas**.

---

## 1. Loyihani olish (qo'lda, o'rnatuvchisiz)

```powershell
cd C:\
git clone https://github.com/mirazizGG/Kassa.git SmartKassa
cd SmartKassa\deploy\scripts
```

## 2. Birinchi sozlash

```powershell
.\first-time-setup.ps1
```

Bu skript: Git/Python borligini tekshiradi · `backend\.env` yaratadi va
`SECRET_KEY` ni avtomatik to'ldiradi · `pip install` qiladi · `frontend\dist`
repodan kelganini tasdiqlaydi (Node bo'lsa — o'zi build qiladi).

**LAN uchun shu yetadi** — `.\start-all.ps1` ga o'ting (4-bo'lim).

Internet orqali kirish kerak bo'lsa, **`backend\.env`** da:

```
ALLOWED_ORIGINS=https://kassa.SIZNING-DOMEN
```

va Caddy + cloudflared o'rnating (`winget install CaddyServer.Caddy Cloudflare.cloudflared`).

## 3. Cloudflare Tunnel sozlash (faqat internet kerak bo'lsa)

```powershell
# 3.1 Cloudflare'ga kirish (brauzer ochiladi, domeningizni tanlaysiz)
cloudflared tunnel login

# 3.2 Tunnel yaratish
cloudflared tunnel create kassa
#  -> "kassa" tunnel yaratildi, ID: xxxxxxxx-xxxx-...
#  -> credentials fayl:  C:\Users\<siz>\.cloudflared\xxxxxxxx-....json

# 3.3 Domenni tunnelga bog'lash
cloudflared tunnel route dns kassa kassa.SIZNING-DOMEN
```

3.4 `C:\Users\<siz>\.cloudflared\config.yml` fayl yarating.
Namuna: `deploy\cloudflared-config.example.yml` — undan nusxa oling va `<...>` larni to'ldiring:

```yaml
tunnel: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
credentials-file: C:\Users\<siz>\.cloudflared\xxxxxxxx-....json

ingress:
  - hostname: kassa.SIZNING-DOMEN
    service: http://localhost:8000 # to'g'ridan-to'g'ri backendga, Caddysiz
  - service: http_status:404
```

## 4. Ishga tushirish

```powershell
.\start-all.ps1
```

Tekshirish:

- Do'kon ichidan: `http://SERVER-IP:8000` (Caddy ishlasa `:8080` ham)
- Tashqaridan: `https://kassa.SIZNING-DOMEN`

Login: `miraziz` / `8434` — **darhol parolni o'zgartiring** (Xodimlar bo'limida).

Xodim parolini unutsa: Xodimlar bo'limi → xodimni tahrirlash → "Yangi Parol" ga yangi parol yozing → ko'z belgisi bilan ko'rib, xodimga aytasiz. Eski parolni tizim ko'rsata olmaydi (u shifrlangan), faqat yangisini qo'yish mumkin.

## 5. Avtomatik ishga tushirish (kompyuter yonganda)

**Administrator** PowerShell'da:

```powershell
.\install-autostart.ps1
```

> Kompyuter yonganda hech kim login qilmasa ham ishlashi uchun Windows'da
> **avtomatik login** yoqilgani ma'qul (yoki bu PC doim login holatida tursin).

---

## Yangilanish kiritish (kundalik ish)

**Uyda / boshqa kompyuterda:**

```powershell
git add .
git commit -m "..."
git push
```

**Yangilashning 2 usuli:**

**A) Ilova ichidan (oson) —** `backend\.env` da `ALLOW_SELF_UPDATE=true` bo'lsa.
Ekranning chap-pastida **"Yangilash"** tugmasi chiqadi (GitHub'da yangi versiya
bo'lsa — sariq "Yangilanish bor"). Istalgan xodim bosadi → ogohlantirish →
"kuting" oynasi → tugagach barcha kompyuterlar o'zi yangilanadi. Serverga
qo'l tekkizish shart emas.

**B) Qo'lda (server kompyuterda):**

```powershell
cd C:\SmartKassa\deploy\scripts
.\update.ps1
```

Ikkalasi ham bir xil ishni qiladi: **bazadan zahira nusxa oladi** →
`git pull` (tayyor `dist` ham keladi) → kerak bo'lsa `pip install` → backendni
qayta ishga tushiradi (5-10 soniya). Yangilik bo'lmasa hech narsa qilmaydi.
Serverda `npm`/build ishlamaydi — frontend uyda `publish.ps1` da tayyorlanadi.

### Ma'lumotlar xavfsizmi?

Ha. Yangilanish **faqat kodni** almashtiradi:

- Baza (`market.db`) git'ga kirmaydi — `git pull` unga hech qachon tegmaydi
- Yangilanish boshida avtomatik **zahira nusxa** olinadi (`backups/`)
- Migratsiyalar faqat yangi ustun qo'shadi, hech narsa o'chirmaydi
- Kassir yangilanish paytida savdo qilayotgan bo'lsa, savati saqlanib,
  sahifa qayta yuklangach tiklanadi

Yo'qolishi mumkin bo'lgan yagona narsa — brauzerdagi ochilmagan to'lov oynasi
summasi (savatning o'zi emas).

> **Savdo gavjum vaqtida yangilamang** — o'sha 5-10 soniyada chek yopib bo'lmaydi.

> SERVER kompyuterda **hech qachon kod o'zgartirmang** — faqat `update.ps1`.
> Aks holda `git pull` konflikt beradi.

---

## Kundalik buyruqlar

| Buyruq            | Vazifa                         |
| ----------------- | ------------------------------ |
| `.\status.ps1`    | xizmatlar holati + LAN manzili |
| `.\start-all.ps1` | hammasini yoqish               |
| `.\stop-all.ps1`  | hammasini o'chirish            |
| `.\update.ps1`    | GitHub'dan yangilash           |

Loglar: `deploy\run\*.log`

---

## Xavfsizlik ro'yxati (internetga chiqishdan oldin)

- [ ] `backend\.env` da `SECRET_KEY` — tasodifiy (setup avtomatik qildi)
- [ ] `backend\.env` da `ALLOWED_ORIGINS` — faqat o'z domeningiz, `*` emas
- [ ] `miraziz` / `8434` paroli o'zgartirilgan
- [ ] `backend\.env` da `APP_ENV=production` (zaif `SECRET_KEY` bilan ishga tushmaydi)
- [ ] Windows Firewall: LAN uchun 8000 port ochiq (internetdan kirish faqat tunnel orqali)
- [ ] Cloudflare dashboard'da domenga **proxy (to'q sariq bulut)** yoniq
- [ ] Muntazam backup tekshirilyapti (`backend\backups\`)
- [ ] `BACKUP_MIRROR_DIR` — tashqi disk yoki sinxron papkaga ikkinchi nusxa yoqilgan
- [ ] `TELEGRAM_ADMIN_CHAT_ID` to'ldirilgan — kunlik backup Telegram'ga ham tushadi

---

## Baza: SQLite → PostgreSQL (keyinroq)

Boshida SQLite yetadi. Agar `database is locked` xatolari chiqsa (10+ kishi bir vaqtda):

```powershell
# PostgreSQL o'rnatish (Docker bilan eng oson)
docker run -d --name kassa-db --restart always `
  -e POSTGRES_USER=kassa -e POSTGRES_PASSWORD=KUCHLI_PAROL -e POSTGRES_DB=kassa `
  -p 5432:5432 -v kassa-pgdata:/var/lib/postgresql/data postgres:16
```

`backend\.env`:

```
DATABASE_URL=postgresql://kassa:KUCHLI_PAROL@localhost:5432/kassa
```

Kod avtomatik `asyncpg` ga o'tadi. Eski SQLite ma'lumotini ko'chirish kerak bo'lsa — alohida yordam beramiz.

---

## Muammolar

| Belgi                                        | Yechim                                                                          |
| -------------------------------------------- | ------------------------------------------------------------------------------- |
| `https://kassa...` ochilmaydi                | `.\status.ps1` — cloudflared ishlayaptimi? `deploy\run\cloudflared.err.log`     |
| Do'kon ichidan ochilmaydi                    | Firewall'da 8000 portni oching; `http://SERVER-IP:8000` to'g'rimi?              |
| Frontend bo'sh / oq ekran                    | `frontend\dist` bo'sh — uyda `deploy\publish.ps1` bilan build qilib push qiling |
| `SECRET_KEY` xatosi, backend ishga tushmaydi | `backend\.env` da `SECRET_KEY` bo'sh — `first-time-setup.ps1` qayta             |
| Login "boshqa qurilmada..."                  | Normal — dialogdan "Chiqarib, shu yerdan kirish" bosing                         |
| `update.ps1` konflikt beradi                 | SERVER'da kod o'zgartirilgan. `git checkout -- .` keyin qayta                   |
| Frontend eski ko'rinadi                      | Brauzerda `Ctrl+Shift+R` (kesh tozalash)                                        |
