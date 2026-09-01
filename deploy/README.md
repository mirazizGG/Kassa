# SmartKassa — Deploy qo'llanmasi (tekin, do'kon kompyuterida)

Bu qo'llanma loyihani **do'kondagi bitta doim yoniq kompyuterda** ishga tushiradi va
uni **Cloudflare Tunnel** orqali internetga chiqaradi. Natijada:

- **Do'kon ichidan** — `http://SERVER-IP:8080` (tez, LAN)
- **Uydan / boshqa shahardan** — `https://kassa.SIZNING-DOMEN` (tunnel orqali)
- Bitta baza, bitta tizim. Kassir kompyuterlariga hech narsa o'rnatilmaydi — ular faqat brauzer.

```
Uydagi komp ──git push──▶ GitHub ──update.ps1──▶ SERVER komp ──▶ kassirlar (brauzer)
                                                     │
                                     Caddy :8080 ◀───┤ (frontend + /api)
                                     uvicorn :8000 ◀─┘ (backend)
                                          ▲
                                   Cloudflare Tunnel ──▶ https://kassa.domen
```

---

## Eng oson yo'l — bir tugmali o'rnatuvchi (faqat LAN)

Do'kon ichidan kirish yetarli bo'lsa (tashqi domen shart emas), quyidagi
**bitta fayl** hamma ishni qiladi: Git/Python/Node/Caddy o'rnatadi, loyihani
yuklaydi, sozlaydi, ishga tushiradi va avtomatik ishga tushirishni o'rnatadi.

Server kompyuterda PowerShell'da (Administrator shart emas — skript o'zi so'raydi):

```powershell
irm https://raw.githubusercontent.com/mirazizGG/Kassa/main/deploy/install-smartkassa.ps1 -OutFile "$env:USERPROFILE\Desktop\install-smartkassa.ps1"
& "$env:USERPROFILE\Desktop\install-smartkassa.ps1"
```

Tugagach: `http://SERVER-IP:8080`, login `admin` / `123` (darhol o'zgartiring).
Yangilash — ekrandagi **"Yangilash"** tugmasi (`ALLOW_SELF_UPDATE=true` avtomat qo'yiladi).

Internet orqali kirish (Cloudflare Tunnel) kerak bo'lsa — pastdagi to'liq qo'llanma.

---

## 0. Nima kerak (SERVER kompyuterda)

| Dastur       | O'rnatish                                                                |
| ------------ | ------------------------------------------------------------------------ |
| Git          | https://git-scm.com                                                      |
| Python 3.11+ | https://python.org (PATH ga qo'shing)                                    |
| Node.js 20+  | https://nodejs.org                                                       |
| Caddy        | `winget install CaddyServer.Caddy`                                       |
| cloudflared  | `winget install Cloudflare.cloudflared`                                  |
| Domen        | Cloudflare'ga ulangan domen (`.com` ~ $10/yil, arzonroq TLD'lar ham bor) |

---

## 1. Loyihani olish

```powershell
cd C:\
git clone https://github.com/mirazizGG/Kassa.git SmartKassa
cd SmartKassa\deploy\scripts
```

## 2. Birinchi sozlash

```powershell
.\first-time-setup.ps1
```

Bu skript:

- dasturlarni tekshiradi
- `backend\.env` yaratadi va `SECRET_KEY` ni avtomatik to'ldiradi
- `frontend\.env.production` yaratadi
- kutubxonalarni o'rnatadi (`pip install`, `npm ci`)
- frontendni build qiladi

Keyin **`backend\.env`** ni oching va shu qatorni to'g'rilang:

```
ALLOWED_ORIGINS=https://kassa.SIZNING-DOMEN
```

## 3. Cloudflare Tunnel sozlash

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
    service: http://localhost:8080
  - service: http_status:404
```

## 4. Ishga tushirish

```powershell
.\start-all.ps1
```

Tekshirish:

- Do'kon ichidan: `http://SERVER-IP:8080`
- Tashqaridan: `https://kassa.SIZNING-DOMEN`

Login: `admin` / `123` — **darhol parolni o'zgartiring** (Xodimlar bo'limida).

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
`git pull` → kerak bo'lsa `pip install` / `npm build` → backendni qayta ishga
tushiradi (5-10 soniya). Yangilik bo'lmasa hech narsa qilmaydi.

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
- [ ] `admin` / `123` paroli o'zgartirilgan
- [ ] Windows Firewall: faqat 8080 port LAN uchun ochiq (internetdan kirish faqat tunnel orqali)
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

| Belgi                         | Yechim                                                                      |
| ----------------------------- | --------------------------------------------------------------------------- |
| `https://kassa...` ochilmaydi | `.\status.ps1` — cloudflared ishlayaptimi? `deploy\run\cloudflared.err.log` |
| Do'kon ichidan ochilmaydi     | Firewall'da 8080 portni oching; `http://SERVER-IP:8080` to'g'rimi?          |
| Login "boshqa qurilmada..."   | Normal — dialogdan "Chiqarib, shu yerdan kirish" bosing                     |
| `update.ps1` konflikt beradi  | SERVER'da kod o'zgartirilgan. `git checkout -- .` keyin qayta               |
| Frontend eski ko'rinadi       | Brauzerda `Ctrl+Shift+R` (kesh tozalash)                                    |
