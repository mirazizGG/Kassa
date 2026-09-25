# Kassa — Point-of-Sale System

> 🇺🇿 Batafsil o'zbekcha hujjat: [`docs/README.md`](docs/README.md)

A full-stack POS system for a retail shop.
Covers the whole shop workflow: selling at the register, inventory, customer
credit (CRM), cashier shifts, finance/reporting, employee management and audit
logging — with role-based access control.

## Features

- **Register (POS)** — barcode / name search, real-time cart, cash / card /
  credit payments, per-cashier shift open & close with cash-discrepancy check
- **Inventory** — categories, barcodes, buy/sell prices, stock tracking,
  low-stock list, supply history; barcode name lookup falls back to
  the Open Food Facts API
- **CRM** — customers with balance (prepayment / debt), credit sales, debt due
  dates, payment history
- **Finance** — sales history & refunds, expense tracking, revenue / gross /
  net profit stats, top products
- **Roles** — admin, manager, cashier, each with a distinct permission set;
  a locked "primary admin" account that can only be changed from the server
- **Audit log** — every significant action recorded
- **Single active session per user**, JWT auth, hashed passwords, backups

## Stack

| Layer | Tech |
|---|---|
| Backend | PHP 8.1+, no framework, PDO (MySQL / PostgreSQL / SQLite) |
| Auth | JWT, pbkdf2_sha256 password hashes (passlib-compatible) |
| Frontend | React 19, Vite, React Router, TanStack Query, Tailwind CSS, Radix UI / shadcn/ui, Recharts |

The backend used to be Python (FastAPI). It was ported to PHP for cPanel
shared hosting and the Python code has been removed. The PHP port has no
Telegram bot and no in-app self-update.

## Architecture

```
frontend/  React SPA (Vite dev server, proxies /api → 127.0.0.1:8000)
                    │  JWT in Authorization header
                    ▼
php/       PHP backend — same API paths and response shapes
  public/index.php   single entry point; also serves the built React app
  app/routes/        auth · pos · sales · inventory · crm · finance · suppliers · audit · tasks · settings · system
  app/Schema.php     tables, indexes, one-shot migrations
  bin/setup.php      creates/updates the schema and the first admin (idempotent)
```

After any schema change, run `php bin/setup.php` on the server.

## Run it

Requirements: PHP 8.1+ (pdo_sqlite, mbstring, curl), Node 18+.

```bash
# backend
cd php
cp .env.example .env            # for local work: DATABASE_URL=sqlite:./market.db
php bin/setup.php
php -S 127.0.0.1:8000 -t public public/index.php

# frontend — either the dev server (separate terminal)...
cd frontend && npm install && npm run dev          # http://127.0.0.1:5173
# ...or build it into php/public and use http://127.0.0.1:8000
cd frontend && npm run build && cp -r dist/* ../php/public/
```

Configuration lives in `php/.env` — see [php/.env.example](php/.env.example).
Deployment: [php/DEPLOY.md](php/DEPLOY.md). Reset the primary admin password
on the server with `php bin/reset_admin.php`.

## License

MIT — free for personal and commercial use.
