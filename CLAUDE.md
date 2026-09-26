# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kassa (a.k.a. SmartKassa) is a self-hosted Point of Sale system for a retail shop in Uzbekistan. It covers sales, inventory, customer debt (CRM), supplier debt, employee shifts and attendance, finances, and audit logging.

**UI language is Uzbek.** All user-facing strings, error `detail` messages, and most code comments are Uzbek. Match that when adding anything a user or API client sees.

**Tech Stack:** PHP 8.1+ with no framework and PDO (MySQL on the cPanel host; PostgreSQL and SQLite also supported) on the backend; React 19 + Vite + React Router 7 + TanStack Query + Tailwind + Radix/shadcn on the frontend. Auth is JWT with passlib-compatible `pbkdf2_sha256` hashes.

**The backend used to be Python (FastAPI).** It was ported to PHP because Passenger on shared hosting held ~218 MB per process, and the Python code was removed from this repo on 2026-09-25 (an archive of it sits outside the repo). The port kept API paths, response shapes and all money logic identical, which is why the React app did not change. It dropped in-app self-update. The Telegram bot, which needs a long-lived process, came back as a separate CLI daemon (`php/bin/bot.php`, see "Telegram bot" below). [php/README.md](php/README.md) explains the port and its measurements.

## Common Commands

```bash
# Backend (from php/)
cp .env.example .env                 # local: APP_ENV=development, DATABASE_URL=sqlite:./market.db
php bin/setup.php                    # create/upgrade schema + first admin — idempotent, re-run after ANY schema change
php -S 127.0.0.1:8000 -t public public/index.php
php bin/reset_admin.php "new-password" [username]   # lockout recovery
php bin/backup.php                   # backup (cron on the server)

# Frontend (from frontend/)
npm install
npm run dev      # Vite on 0.0.0.0:5173, proxies /api -> 127.0.0.1:8000
npm run build    # emits frontend/dist; copy dist/* into php/public/ to serve it from PHP
npm run lint     # ESLint — CI runs this
```

PHP is not installed on the dev machine. A portable build from windows.php.net unzipped anywhere works; enable `pdo_sqlite`, `sqlite3`, `mbstring`, `curl`, `openssl` in its `php.ini`.

### Verification gate

CI ([.github/workflows/verify.yml](.github/workflows/verify.yml)) runs, and so should you before declaring work done:

```bash
cd frontend && npm ci && npm run lint && npm run build
cd php && find app bin public -name "*.php" -exec php -l {} \;
          php bin/setup.php            # against a scratch SQLite .env
```

There is no automated test suite for the PHP backend (the Python one was removed with the Python code). Verify money-path changes by exercising the API with `curl` against a local server and a throwaway SQLite database, then reset it.

## Architecture

### Request path and deployment shape

[php/public/index.php](php/public/index.php) is the single entry point. It serves the built React app (`php/public/index.html` + `assets/`, copied from `frontend/dist`, gitignored) and routes API calls. [Router.php](php/app/Router.php) loads only the route file matching the first path segment — `/sales/...` reads `app/routes/sales.php` and nothing else.

- API routes are at bare prefixes (`/auth`, `/sales`, `/pos`, …), **not** under `/api`. The `/api` prefix exists only in the Vite dev proxy, which strips it.
- `frontend/.env` is committed with `VITE_API_URL=/api` (dev, through the proxy); `frontend/.env.production` sets it empty (same-origin relative requests).
- Each request is a fresh PHP process. There is no in-memory state between requests; caches ([Cache.php](php/app/Cache.php)) and rate-limit counters live on disk under `php/logs/`.

### Backend layout

- [bootstrap.php](php/app/bootstrap.php) — `.env` loading, constants (`PRIMARY_ADMIN_USERNAME`, `IS_PROD`), `fail()`, error handling.
- [Auth.php](php/app/Auth.php) — JWT, password hashing, `Auth::user()` / `Auth::require([...roles])`, approver verification.
- [Db.php](php/app/Db.php) — PDO wrapper: `one`/`all`/`val`/`run`/`insert`/`update`/`tx`, `ilike()`, driver differences.
- [Http.php](php/app/Http.php) — request body/query parsing **with validation** (`reqNum`, `reqStr`, `int`, `bool`, …) and `Http::json()`.
- [Shape.php](php/app/Shape.php) — response shapes. This is the API contract with the React app; field names and types must not drift.
- [Schema.php](php/app/Schema.php) — tables, unique/plain indexes, one-shot migrations.
- [Tz.php](php/app/Tz.php), [Audit.php](php/app/Audit.php), [Backup.php](php/app/Backup.php), [Xlsx.php](php/app/Xlsx.php).

**Routes** ([php/app/routes/](php/app/routes/)) — prefix equals filename:

| Route file | Owns |
|---|---|
| `auth` | login/logout, employee CRUD, `GET /auth/attendance` |
| `pos` | **shifts only** — open/close/active/history |
| `sales` | **sale creation, listing, refunds**, top products, cashier daily summary |
| `inventory` | products (incl. extra barcodes), categories, supplies, stock moves, barcode lookup, purchase list |
| `crm` | clients, debts, debt payments, per-client history |
| `finance` | stats, charts, expenses, Excel/CSV exports |
| `suppliers` | firms, receipts (with invoice image upload), supplier payments |
| `audit` | audit log listing + Excel export |
| `settings` | store settings, manual backup trigger |
| `system` | version; update endpoints answer that the feature is off |
| `tasks` | employee tasks (admin-only; surfaced inside the Employees page) |

Note `pos` vs `sales`: shift lifecycle is in `pos.php`, everything about a sale is in `sales.php`. New endpoints go in the matching route file.

**Products can have several barcodes.** `products.barcode` is the primary; `product_barcodes` holds extras (e.g. every flavour of one product sharing one name, price and stock). A code must be unique across *both* tables — `barcode_owner()` in `inventory.php` checks that. The product list attaches `extra_barcodes`; `Shape::product()` emits the key only when it was loaded, because the POS merges sale responses into its cached catalog and an empty list would wipe the codes. On the frontend use `productBarcodes()` from [lib/utils.js](frontend/src/lib/utils.js), never `product.barcode` alone.

**Restocking** goes through `POST /inventory/supplies` (adds to stock atomically, updates `buy_price`, writes supply history), surfaced by [SupplyDialog.jsx](frontend/src/components/SupplyDialog.jsx) with barcode scanning. Editing the product's stock field is an *adjustment*, not a supply. The warehouse role may create, edit, restock and delete products; once a product has sales or supply history only an admin may delete it (see "Admin can delete anything" below).

### Schema changes

There is no migration framework. `php bin/setup.php` → `Schema::createAll()` runs `CREATE TABLE IF NOT EXISTS`, then `ensureColumns()` (adds any column present in `Schema::tables()` but missing from the table) and `ensureIndexes()`. So:

- **To add a table or column:** add it to `Schema::tables()`. **To add an index:** add it to `uniques()` / `indexes()`. Then run `setup.php` — locally and **on the server after deploying**, or the new code will query a table that does not exist.
- **One-shot data migrations** rewrite rows and must be guarded by the `schema_migrations` ledger (`Schema::migrationApplied()` / `markMigration()`).
- Types go through `sqlType()` so the DDL is valid on MySQL, PostgreSQL and SQLite; don't write raw engine-specific DDL.

### Timestamps

**Everything in the database is naive UTC**, implemented in [Tz.php](php/app/Tz.php):

- Write "now" with `Tz::now()`.
- Turn a shop calendar day into a query range with `Tz::dayStartUtc()` / `dayEndUtc()` / `todayStartUtc()`.
- The shop timezone is `SHOP_TIMEZONE` (default `Asia/Tashkent`). The server's own clock is irrelevant.
- On the frontend, the mirror is [lib/datetime.js](frontend/src/lib/datetime.js): `formatDateTime()` / `parseServerDate()`. The API returns naive UTC with no zone suffix (`Tz::iso()`), which JS would otherwise read as local time. **Never call `new Date(apiValue)` directly.**

### Business rules (ported verbatim from the Python version)

The sections below were written against the Python code and still describe the PHP behaviour — the port kept every rule. Read file references as: `backend/routers/X.py` → [php/app/routes/X.php](php/app/routes/), `core.py` → `Auth.php`/`bootstrap.php`, `database.py` / `ensure_*` → `Schema.php`, `utils/timezone.py` → `Tz.php`, `log_action()` → `Audit::log()`. Test names mentioned below refer to the removed Python suite.

### Roles

Five role strings exist, not three: `admin`, `manager`, `cashier`, `warehouse` (Omborchi), `sotuvchi` (Sotuvchi).

- `sotuvchi` is **rejected at login** with 403 — that role exists only to clock in/out via the Telegram bot.
- `warehouse` gets inventory and suppliers but no dashboard, POS, CRM, or finance (see the nav in [Layout.jsx](frontend/src/components/Layout.jsx) and `RoleProtectedRoute` in [App.jsx](frontend/src/App.jsx)).
- Enforcement is inline `if current_user.role not in [...]` at the top of each handler; there is no permission decorator. The `Employee.permissions` column is vestigial — it is stored and returned but nothing reads it for access decisions.

**Deliberate information-hiding — do not "fix" these:**

- `/finance/stats` zeroes `totalCost` and `netProfit` for `manager` and `cashier`. Only admins see margin.
- A `manager` cannot see sales, stats, performance, or employee rows belonging to an `admin` (filtered in `sales`, `finance`, `auth`).
- A `cashier` is silently scoped to their own `employee_id` in sales/stats queries.
- Audit logs are **admin-only** (both endpoints).

**Primary admin lock:** the account named `PRIMARY_ADMIN_USERNAME` in [core.py](backend/core.py) (`miraziz`, hardcoded on purpose — [Employees.jsx](frontend/src/pages/Employees.jsx) hardcodes it too) cannot be edited or deleted via the API. Its password changes only on the server via `python reset_admin.py`. Additionally, only `miraziz` may create an `admin`, edit/delete another `admin`, or promote anyone to `admin`.

### Auth session model

- `POST /auth/token` is rate-limited to 20/minute. The limiter key ([core.py](backend/core.py) `_real_client_ip`) uses the socket address unless `TRUST_PROXY_HEADERS=true`, which opts into `cf-connecting-ip` / `x-forwarded-for`. Turn it on **only** behind a proxy that rewrites those headers — they are client-supplied otherwise, and spoofing one gave every request a fresh rate-limit bucket.
- **One active session per user, strictly enforced.** The JWT carries a `sid` that must equal `Employee.session_token`; a missing or mismatched `sid` is a 401. Logging in while a session is live returns **409** — intended. The client retries with `force=true` (a form field), which writes a `FORCE_LOGOUT` audit entry.
- **Logout and password changes revoke live tokens.** Both null out `session_token`, and because the comparison is unconditional the outstanding JWT stops working immediately. The check used to be `if user.session_token and ...`, so a null token skipped it entirely: logging out revoked nothing and a stolen token outlived a password reset by up to 10 hours.
- Tokens last `ACCESS_TOKEN_EXPIRE_MINUTES` (600). The axios response interceptor ([api/axios.jsx](frontend/src/api/axios.jsx)) clears localStorage and redirects to `/login` on any 401 except the login call itself.

### Sales: what `POST /sales/` actually enforces

Read [sales.py](backend/routers/sales.py) before touching checkout. In order:

0. **Idempotency.** If the body carries `idempotency_key`, an existing sale with that key is returned instead of creating a second one; a concurrent duplicate is caught by the unique index and resolved the same way on `IntegrityError`. The POS generates one key per cart and rotates it after a completed sale. Without this, a double-click or a retried timeout wrote two receipts and decremented stock twice.
1. **An open shift is required** — the check lives here, not in `pos.py`.
2. **Selling below `sell_price` requires manager approval inline**: the request body carries `manager_username`/`manager_password`, verified against an active `admin`/`manager`. Approval is per-request, checked once, then reused for the rest of the cart.
3. Stock is decremented unless `Product.is_infinite` — via an **atomic conditional `UPDATE ... WHERE stock >= qty`**, not a read-modify-write. `rowcount == 0` means someone else sold it first, and the request 409s. The plain `product.stock < qty` check just above it exists only for the friendly message.
4. `SaleItem.buy_price` snapshots the product's cost at sale time so historical margin doesn't drift when purchase prices change. Profit queries `coalesce(SaleItem.buy_price, Product.buy_price)` for pre-snapshot rows.
5. The cart total must match the sum of items within 1 so'm; non-cash payments must not exceed the total; and cash must cover `total − non_cash`. That last check was once gated behind `if sale.cash_amount and ...`, so a cash-less underpaid sale sailed through and the shortfall was booked as cash received — see `test_underpaid_sale_is_rejected`.
6. **`Sale.cash_amount` is recomputed, not trusted.** The client sends the cash the buyer handed over (which may include change); the server stores `total − card − transfer − debt − bonus` so the drawer figure is net. Shift cash math depends on this.
7. Debt reduces `Client.balance`; bonus is earned at `StoreSetting.bonus_percentage` on the non-debt portion. All three balance moves are **atomic `UPDATE`s**, and spending bonus is conditional (`WHERE bonus_balance >= spent`). The ORM object is `refresh`ed afterwards because the sessionmaker sets `expire_on_commit=False` and would otherwise return a stale balance.

**Refunds** are *not* role-gated — any authenticated user can call `POST /sales/{id}/refund`, but the body must carry valid `admin`/`manager` credentials (`RefundApproval`). The refund restores stock (skipping `is_infinite` products, which never decremented), logs a `StockMove`, and reverses debt and bonus in one atomic `UPDATE`. The same credential-in-body pattern appears in [suppliers.py](backend/routers/suppliers.py) via `verify_confirming_employee`.

**Concurrency.** Every balance and stock mutation in the codebase is an atomic
SQL `UPDATE` — there are no `x.stock += n` / `x.balance -= n` read-modify-writes
left, and there should not be. SQLite's single-writer lock used to hide these
races; PostgreSQL writes in parallel and will not.

**Numeric input is constrained at the schema.** Money and quantity fields carry
`allow_inf_nan=False` plus `gt=0`/`ge=0`. `NaN` used to pass validation, land in a
`REAL` column as `NULL`, and then 500 every list endpoint that read it back.
[main.py](backend/main.py) also installs a `RequestValidationError` handler that
scrubs non-finite floats from the error body — FastAPI echoes the rejected input,
and standard JSON has no `NaN`, so the 422 itself used to crash while rendering.

**Product edits use optimistic locking.** `ProductUpdate.expected_stock` carries
the stock the edit form loaded; the server 409s if it no longer matches. The form
previously wrote its stale value back, silently undoing every sale made while the
dialog was open and logging a fake "adjustment" against the manager.

**Online/offline.** `Auth::user()` stamps `employees.last_seen_at` (at most once a
minute), and `Layout.jsx` calls `POST /auth/ping` every 60 s while the site is open.
`GET /auth/employees` adds `is_online` (live session and seen within 5 min),
`last_seen_at` and `on_shift` for **admins only**; the Employees page refetches
every 30 s.

**Admin can delete anything; history is detached, never deleted.** The owner
wants the admin to have full power, so deleting a client, product or employee
with history is allowed for `admin`. Before the row goes, every referencing
column is set to `NULL` explicitly (old SQLite databases have `NO ACTION`
foreign keys with `foreign_keys=ON`, so relying on `ON DELETE SET NULL` is not
enough). Sales, payments, shifts and audit rows stay, so money totals don't move.
A deleted product's name and cost are first copied into
`sale_items.product_name`/`buy_price`, and `Shape::saleItem()` shows the name with
"(o'chirilgan)" so old receipts and margin survive. Non-admins still get 409 on a
product with history. The one remaining guard: an employee with an **open shift**
cannot be deleted until it is force-closed, since nobody could close it afterwards.

### Shifts

```
expected_cash = opening_balance
              + net cash sales in the shift window
              + cash debt payments stamped with this shift_id
              - cash expenses stamped with this shift_id
              - cash refunds paid out during this shift
```

That last term needs care. A refund stamps `Sale.refunded_at` and
`Sale.refund_shift_id`, and `shift_cash_refunds_total()` subtracts
`Sale.cash_amount` **only for sales that were not already counted in this
shift's completed sum**. A sale rung and refunded inside the same shift flips to
`status = "refunded"` and therefore drops out of that sum on its own —
subtracting it again would show the drawer as short by twice the amount.
Refunding an *earlier* shift's sale is the case that matters: the money leaves
today's drawer while today's window never contained the sale.

`compute_shift_totals()` in [pos.py](backend/routers/pos.py) is the **only** place
this is calculated. It used to be copy-pasted into the history handler, the
active-shift handler and `close_shift`, and the copies drifted — the POS
close-shift dialog showed the cashier one number while the server checked
another. The frontend now renders `expected_cash` straight from the API and
computes nothing itself.

The expense term is why [finance.py](backend/routers/finance.py) stamps
`Expense.shift_id` and why `Expense.payment_method` exists — only cash expenses
leave the drawer. Without it, every shift where the cashier paid for something
out of the till closed short, so the discrepancy note became a daily formality
and stopped meaning anything.

**A closed shift's reconciliation is frozen.** `close_shift` writes
`total_cash`/`total_card`/`total_transfer`/`total_debt`/`total_expenses`/
`expected_cash`/`cash_difference`/`closed_by` onto the row, and
`totals_for_display()` returns those stored values instead of recomputing.
Previously a refund processed after closing silently rewrote a past shift's
discrepancy, so the number the cashier signed off on no longer matched the
report. Closing with a discrepancy over 0.01 **requires a note**.

`POST /pos/shifts/{id}/force-close` lets an admin or manager close someone
else's stranded shift (a note is mandatory). Only the owner could close a shift
before, so a cashier who left without closing stranded the till permanently and
could never open a new shift. One open shift per cashier.

### Correcting a mistake

Money records used to be write-once: a mistyped expense, a payment credited to
the wrong customer, or a supply with a wrong cost price were permanent and
poisoned every report from then on. Each now has a reversal path, all
admin/manager-gated, all requiring a `reason` query parameter, and all writing an
audit entry:

- `PATCH /finance/expenses/{id}` and `DELETE /finance/expenses/{id}` — a deleted cash expense returns to the shift's `expected_cash` automatically, because that is computed from the rows.
- `DELETE /crm/payments/{id}` (admin only) — reverses `Client.balance` atomically.
- `DELETE /inventory/supplies/{id}` — reverses stock (409 if the goods were already sold, since stock must not go negative) and restores `Product.buy_price` from the *previous* supply row.

When the record belongs to an already-closed shift, the response carries a
`warning` and the audit entry says so. The shift's own reconciliation stays
frozen — that is the historical record of what the cashier signed off on — but
the finance reports do change, and the operator needs to know that.

**The audit log paginates for real.** `GET /audit/logs` returns `X-Total-Count`
and clamps `limit` to 500. The page previously never sent `limit`/`offset` at
all, took the default 100 rows, and displayed that as the total — so during the
one investigation the log exists for, it silently truncated while claiming
nothing was omitted.

### Money model

- `Client.balance`: negative = owes the shop, positive = prepaid. Debt payments *increase* it.
- `Supplier.balance`: positive = the shop owes the supplier.
- Sales carry a four-way split (`cash_amount`, `card_amount`, `transfer_amount`, `debt_amount`) plus `bonus_earned`/`bonus_spent`; `payment_method` is a label alongside it, not the source of truth.
- **All stored datetimes are naive.** Model defaults use `utc_now`, not `datetime.now(timezone.utc)`. This is not cosmetic: no column declares `timezone=True`, so on PostgreSQL they are `timestamp without time zone`, and asyncpg rejects a tz-aware value for those. Passing an aware datetime would fail on the server while working fine on SQLite.

### Backups

[Backup.php](php/app/Backup.php) writes a portable SQL dump through PDO (no `mysqldump`/`pg_dump`, which shared hosting rarely allows) into `php/backups/` (`BACKUP_DIR` overrides), plus an archive of `public/uploads/` so invoice photos survive a restore. Triggered by cron (`php bin/backup.php`, see its header), by the bot at `BACKUP_TIME`, and manually via `POST /settings/backup` — **never after every sale**, because each run also prunes to `BACKUP_RETENTION`. `bin/backup.php` and the bot both send the dump to `TELEGRAM_ADMIN_CHAT_ID`; that is the only copy that lives off the machine holding the database.

### Telegram bot

[bin/bot.php](php/bin/bot.php) is a long-polling daemon meant to run on the **shop PC**, connecting to the server's MySQL remotely (cPanel Remote MySQL must allow the PC's IP). [php/bot-windows/](php/bot-windows/) installs it: `ORNATISH.bat` → `install.ps1` downloads portable PHP into `runtime/`, runs `bin/bot-check.php`, and registers the "Kassa bot" scheduled task (at startup as SYSTEM when elevated) that runs `start-bot.ps1`, which restarts the bot if it exits. The shipped zip (`kassa-bot-*.zip`, gitignored because it contains `.env`) is `app/` + `bin/` + those scripts at the root.

- Menus follow the old Python bot: client (balance, bonus), staff (clock in/out → `attendance`), admin (daily report, who's working, Excel data, broadcast via `copyMessage`). Registration matches the phone's last 9 digits against `employees.phone` first, then `clients.phone`; a contact is only accepted if `contact.user_id` equals the sender.
- Daily jobs (`BOT_REPORT_TIME`, `BACKUP_TIME`, `DEBT_REMINDER_TIME`) run once per shop day, catching up the same day if the PC was off. Alerts (below-price sale, refund, shift closed with a discrepancy, low stock) are found by polling cursors, not audit text.
- All state (update offset, last-run dates, alert cursors) is in `logs/bot-state.json`; on first run cursors start at "now" so history is not replayed. `logs/bot.lock` keeps one instance — two pollers on one token get Telegram 409.
- `BOT_DRY_RUN=true` logs messages instead of sending them; `define('BOT_NO_LOOP', true)` before requiring `bot.php` loads its functions without the loop, for testing.
- On the CLI, `Db::pdo()` throws on a failed connection instead of `Http::fail`, which printed JSON and exited 0; `Db::reset()` drops a stale connection.

### Deployment

The shop runs on cPanel shared hosting with MySQL. [php/DEPLOY.md](php/DEPLOY.md) is the runbook; `php/deploy/01-check.sh` and `02-switch.sh` performed the one-time switch from the old Python app on the server (they archive it, they don't delete it). [php/bin/migrate.php](php/bin/migrate.php) copies an old SQLite database into the configured one. After every deploy that touches `Schema.php`, run `php bin/setup.php` on the server.

### Frontend patterns

- Pages are `React.lazy`-loaded in [App.jsx](frontend/src/App.jsx); `ProtectedRoute` checks the token, `RoleProtectedRoute` checks `localStorage.role`. This is UX gating only — the backend re-checks everything.
- No shared API-hook layer: each page calls `api` from [api/axios.jsx](frontend/src/api/axios.jsx) directly inside `useQuery`/`useMutation`. Query keys are ad hoc strings (`["products"]`, `["dashboard-stats", filters]`) invalidated by name after mutations. Defaults ([api/queryClient.jsx](frontend/src/api/queryClient.jsx)): `staleTime` 5 min, no refetch on focus, 1 retry.
- Auth state lives in `localStorage` (`token`, `role`, `username`, `userId`) — there is no auth context.
- [POS.jsx](frontend/src/pages/POS.jsx) is ~1700 lines and holds the register: cart drafts and held carts persisted to `localStorage`, `react-hotkeys-hook` shortcuts (F2 focuses search, etc.), split-payment and manager-approval dialogs.
- ESLint's `no-unused-vars` is an **error** with `varsIgnorePattern: '^[A-Z_]'`. Fix violations rather than disabling the rule.

## Configuration

Backend config is `php/.env` (see [php/.env.example](php/.env.example), the authoritative annotated list):

- `APP_ENV` — `development` or `production`. In production the app refuses to start without a strong `SECRET_KEY`, and errors are not shown.
- `SECRET_KEY` — JWT signing key, at least 32 random characters.
- `DATABASE_URL` — `mysql://…`, `postgresql://…` or `sqlite:/path/market.db`. URL-encode special characters in the password. `DB_PERSISTENT` toggles persistent PDO connections.
- `PRIMARY_ADMIN_PASSWORD` — bootstrap password used by `setup.php` **only when no admin exists**. Unset in development falls back to `DEV_ADMIN_PASSWORD` (`8038434`); unset in production aborts. The username `miraziz` is hardcoded.
- `SHOP_TIMEZONE` — default `Asia/Tashkent`.
- `ALLOWED_ORIGINS` — CORS allowlist. `TRUST_PROXY_HEADERS` — only behind a proxy that rewrites `X-Forwarded-For`.
- `BACKUP_ENABLED`, `BACKUP_RETENTION`, `BACKUP_DIR`.
- `ALLOW_SELF_UPDATE` — keep `false`; the PHP port has no self-update.

Frontend: `VITE_API_URL` in [api/axios.jsx](frontend/src/api/axios.jsx), with `??` (not `||`) so an explicit empty string means same-origin. `@` aliases `src/` ([vite.config.js](frontend/vite.config.js)).

## Coding Conventions

- **PHP:** `declare(strict_types=1)`, four-space indent, static methods on `final` classes, route handlers as closures passed to `Router::get/post/put/delete`. Read input only through `Http::` helpers (they validate and 422 with an Uzbek message). Guard each handler with `Auth::require([...roles], ...)`. Wrap multi-statement writes in `Db::tx()` and call `Audit::log()` inside it. Mutate money and stock with an atomic `UPDATE … SET x = x + ?` (conditional `WHERE stock >= ?` when decrementing), never read-modify-write. Compare booleans with bound `true`/`false`, not `1`/`0` — PostgreSQL columns are real `BOOLEAN`. Use `Db::ilike()` for case-insensitive search. Return shapes through `Shape::`.
- **React:** `PascalCase.jsx` for components and pages, camelCase for variables, Tailwind utilities, `cn()` from [lib/utils.js](frontend/src/lib/utils.js) for conditional classes. Render server timestamps with `formatDateTime()` from [lib/datetime.js](frontend/src/lib/datetime.js) — never bare `new Date(apiValue)`. The `react-hooks` lint rules are on, including `set-state-in-effect`; to reset a dialog on open, remount it with a `key` instead of setting state in an effect.
- Never commit `*.db`, `.env` (except `.example` files and the deliberately tracked `frontend/.env*`), `php/public/assets/`, `php/public/index.html`, uploads, backups, or build output — `.gitignore` covers these.

## Documentation caveat

Everything under [docs/](docs/) and [OPTIMIZATION_TASKS.md](OPTIMIZATION_TASKS.md) was written for the Python backend. The business findings still apply; the file paths, commands and test names do not.
