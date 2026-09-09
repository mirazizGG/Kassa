# Kassa — Point-of-Sale System

> 🇺🇿 Batafsil o'zbekcha hujjat: [`docs/README.md`](docs/README.md)

A full-stack POS system for a retail shop, with an integrated Telegram bot.
Covers the whole shop workflow: selling at the register, inventory, customer
credit (CRM), cashier shifts, finance/reporting, employee management and audit
logging — with role-based access control.

## Features

- **Register (POS)** — barcode / name search, real-time cart, cash / card /
  credit payments, per-cashier shift open & close with cash-discrepancy check
- **Inventory** — categories, barcodes, buy/sell prices, stock tracking,
  low-stock Telegram alerts, supply history; barcode name lookup falls back to
  the Open Food Facts API
- **CRM** — customers with balance (prepayment / debt), credit sales, debt due
  dates, payment history, Telegram self-service
- **Finance** — sales history & refunds, expense tracking, revenue / gross /
  net profit stats, top products
- **Roles** — admin, manager, cashier, each with a distinct permission set;
  a locked "primary admin" account that can only be changed from the server
- **Telegram bot** — customer registration, balance checks, automated debt
  reminders (3/2/1 days before, on due date, overdue)
- **Audit log** — every significant action recorded
- **Single active session per user**, JWT auth, hashed passwords, daily SQLite
  backup (optionally mirrored / sent to Telegram)

## Stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI (async), SQLAlchemy 2.0 async, SQLite (aiosqlite) / Postgres (asyncpg) |
| Bot | Aiogram 3.x |
| Auth | JWT (python-jose), passlib pbkdf2_sha256 |
| Scheduling | APScheduler (debt checks, backups), SlowAPI rate limiting |
| Frontend | React 19, Vite, React Router, TanStack Query, Tailwind CSS, Radix UI / shadcn/ui, Recharts |

## Architecture

```
frontend/  React SPA (Vite dev server, proxies /api → backend)
                    │  JWT in Authorization header
                    ▼
backend/   FastAPI app (main.py lifespan: init DB, seed admin,
           start bot polling + debt/backup schedulers)
  routers/  auth · pos · inventory · crm · finance · suppliers · audit · tasks · settings · system
  core.py   JWT, hashing, get_current_user, config from .env
  database.py  async SQLAlchemy 2.0 models, auto schema sync on startup
  bot.py    Aiogram bot (shares the same DB via telegram_id)
```

Schema changes are applied automatically on startup — there are no migration
scripts.

## Run it

Requirements: Python 3.10+, Node 18+.

```bash
# backend
cd backend
python -m venv venv && venv\Scripts\activate      # Linux/Mac: python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                             # then fill it in (see below)
python main.py                                     # http://127.0.0.1:8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev                                        # http://127.0.0.1:5173
```

### Configuration (`backend/.env`)

All secrets come from `backend/.env` — nothing sensitive is committed.

| Key | Notes |
|---|---|
| `APP_ENV` | `development` (default) or `production` |
| `SECRET_KEY` | JWT signing key — **required** in production |
| `PRIMARY_ADMIN_PASSWORD` | password for the seeded `miraziz` admin — **required** in production |
| `DATABASE_URL` | defaults to local SQLite; `postgres://` URLs auto-rewritten to asyncpg |
| `ALLOWED_ORIGINS` | comma-separated CORS allowlist (defaults to `*` if unset) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID` | bot credentials / backup delivery chat |
| `BACKUP_ENABLED`, `BACKUP_HOUR`, `BACKUP_RETENTION`, `BACKUP_MIRROR_DIR` | daily SQLite snapshot settings |

In `production`, the app refuses to start if `SECRET_KEY` or
`PRIMARY_ADMIN_PASSWORD` is missing or still the sample value.

To reset the primary admin password on the server:

```bash
cd backend && python reset_admin.py "new-strong-password"
```

## License

MIT — free for personal and commercial use.
