# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kassa (a.k.a. SmartKassa) is a self-hosted Point of Sale system for a retail shop in Uzbekistan, with a Telegram bot attached. It covers sales, inventory, customer debt (CRM), supplier debt, employee shifts and attendance, finances, and audit logging.

**UI language is Uzbek.** All user-facing strings, error `detail` messages, and most code comments are Uzbek. Match that when adding anything a user or API client sees.

**Tech Stack:** FastAPI (async) + SQLAlchemy 2.0 async + SQLite/aiosqlite + Aiogram 3.x on the backend; React 19 + Vite + React Router 7 + TanStack Query + Tailwind + Radix/shadcn on the frontend. Auth is JWT (python-jose) with passlib `pbkdf2_sha256`.

## Common Commands

```bash
# Backend
pip install -r backend/requirements.txt
cd backend && python main.py          # or: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
python reset_admin.py "new-password"  # from backend/ — reset the primary admin (lockout recovery)

# Frontend
cd frontend && npm install
npm run dev      # Vite on 0.0.0.0:5173, proxies /api -> 127.0.0.1:8000
npm run build    # emits frontend/dist, which the backend then serves itself
npm run lint     # ESLint — CI runs this
npm run preview  # 0.0.0.0:4173
```

`./run_project.ps1` starts both, but it first force-kills **every** `python`/`node`/`uvicorn` process on the machine. Only use it when that is acceptable.

### Verification gate

CI ([.github/workflows/verify.yml](.github/workflows/verify.yml)) runs, and so should you before declaring work done:

```bash
cd frontend && npm ci && npm run lint && npm run build
cd backend  && pip install -r requirements.txt -r requirements-dev.txt
              python -m compileall -q .
              python -m pytest
```

`backend/tests/` covers the money paths — sale, refund, shift cash, debt, bonus,
payment splits, delete guards, the shift-time UTC migration, and backup
behaviour. They run against a temporary SQLite file (never `market.db`) through
FastAPI's `TestClient`; `tests/conftest.py` sets the environment before
`database`/`core` are imported, which matters because those read `os.getenv` at
module level. **Add a test for any money-path change** — these are regression
tests for real defects, and each one has a comment naming the defect it guards.

The root-level `test_*.py` scripts predate this and are stale: `test_features.py`
needs a running API plus `requests` (not in requirements), and `check_db_lock.py`
has a hardcoded path from another machine. Ignore them.

## Architecture

### Request path and deployment shape

The backend serves the frontend. [main.py](backend/main.py) mounts `frontend/dist` at `/` through an `SPAStaticFiles` subclass that falls back to `index.html` so React Router deep links work. In production there is one origin and one port — no Node, no separate web server. Consequences:

- API routes are mounted at bare prefixes (`/auth`, `/sales`, `/pos`, …), **not** under `/api`. The `/api` prefix exists only in the Vite dev proxy, which strips it.
- `frontend/.env` is committed with `VITE_API_URL=/api` (dev, through the proxy); `frontend/.env.production` sets it empty (same-origin relative requests).
- If `frontend/dist/index.html` is missing, `/` returns a JSON banner instead and the UI is unavailable.

### Backend layout

- [main.py](backend/main.py) — lifespan: `init_db()`, APScheduler (debt check at 09:00, backups), bot polling task, bootstrap admin creation. Also the global exception handler (returns a generic Uzbek 500 message, logs the real error) and CORS.
- [core.py](backend/core.py) — JWT, password hashing, `get_current_user`, the slowapi `limiter`, `PRIMARY_ADMIN_USERNAME`, env validation.
- [database.py](backend/database.py) — engine, models, `init_db`, `get_db`.
- [schemas.py](backend/schemas.py) — Pydantic DTOs (some routers, e.g. [suppliers.py](backend/routers/suppliers.py), define their own inline instead).
- [bot.py](backend/bot.py) — Aiogram handlers plus `check_debts`.
- [utils/backup.py](backend/utils/backup.py), [utils/telegram.py](backend/utils/telegram.py).

**Routers** ([backend/routers/](backend/routers/)) — prefix equals filename:

| Router | Owns |
|---|---|
| `auth` | login/logout, employee CRUD, `GET /auth/attendance` |
| `pos` | **shifts only** — open/close/active/history |
| `sales` | **sale creation, listing, refunds**, top products, cashier daily summary |
| `inventory` | products, categories, supplies, stock moves, barcode lookup, purchase list |
| `crm` | clients, debts, debt payments, per-client history |
| `finance` | stats, charts, expenses, Excel/CSV exports |
| `suppliers` | firms, receipts (with invoice image upload), supplier payments |
| `audit` | audit log listing + Excel export; `log_action()` helper used everywhere |
| `settings` | store settings, manual backup trigger |
| `system` | version, self-update check/start/status |
| `tasks` | employee tasks (admin-only; surfaced inside the Employees page) |

Note `pos` vs `sales`: shift lifecycle is in `pos.py`, everything about a sale is in `sales.py`. New endpoints go in the matching domain router, never in `main.py`.

### Schema migrations

There is no Alembic. `init_db()` runs `Base.metadata.create_all`, then the
`ensure_*` functions via `run_sync`. Two distinct kinds, and the difference matters:

- **Idempotent structure changes** — `ensure_employee_session_columns`, `ensure_sale_item_columns`, `ensure_product_columns`, `ensure_indexes`. Safe to re-run every startup. To add a column, add the model attribute **and** an `ensure_…` function that inspects the table and issues `ALTER TABLE … ADD COLUMN` (backfilling if needed), then register it in `init_db`. See `ensure_sale_item_columns` for the backfill pattern.
- **One-shot data migrations** — these rewrite existing rows and would corrupt data if they ran twice. They must be guarded by the `schema_migrations` ledger: check `_migration_applied(conn, NAME)`, do the work, call `_mark_migration(conn, NAME)`. `migrate_shift_times_to_utc` is the worked example, and it branches on `conn.dialect.name` so the SQL is valid on both SQLite and PostgreSQL.

`ensure_indexes` creates 21 indexes with `CREATE INDEX IF NOT EXISTS` (portable
across both engines) on the columns actually filtered — sale/shift/payment dates
and every foreign key. Note that adding `index=True` to a model column does
**not** create the index on an existing table; `create_all` only creates missing
tables. Add it to `_INDEXES` instead.

### Timestamps

**Everything in the database is naive UTC.** There is exactly one rule and one
place that implements it: [utils/timezone.py](backend/utils/timezone.py).

- Write "now" with `utc_now()`.
- Turn a user-supplied shop calendar day into a query range with `day_start_utc()` / `day_end_utc()` / `today_start_utc()`.
- The shop timezone is `SHOP_TIMEZONE` (default `Asia/Tashkent`), not hardcoded. The server's own clock is irrelevant — a UTC host is fine and expected.
- On the frontend, the mirror of this is [lib/datetime.js](frontend/src/lib/datetime.js): `formatDateTime()` / `parseServerDate()`. The API returns naive UTC with no zone suffix, which JS would otherwise read as local time. **Never call `new Date(apiValue)` directly.**

This used to be the worst trap in the codebase: `Shift.opened_at`/`closed_at`
were written with bare `datetime.now()` (server local) while everything else was
UTC, and `pos.py` bridged the two through a hardcoded Asia/Tashkent conversion
that only worked while the server sat in Uzbekistan. Shift times are now UTC like
everything else and the bridge is gone. Existing rows are converted once by
`migrate_shift_times_to_utc` (see below). `tzdata` is a dependency because
Windows lacks the IANA database.

[audit.py](backend/routers/audit.py) and [finance.py](backend/routers/finance.py)
still carry their own older day-boundary helpers (`local_day_boundary`,
`local_today_start`). They are correct but duplicated — fold them into
`utils/timezone.py` when you next touch those files.

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

**Deletes are guarded.** `delete_product`, `delete_client` and `delete_employee`
refuse with 409 when history references the row, listing the count. SQLite now
runs with `PRAGMA foreign_keys=ON` so development matches PostgreSQL, where an
unguarded delete would surface as an `IntegrityError` 500. For employees the
answer is to block the account (`is_active = False`), not delete it.

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

[utils/backup.py](backend/utils/backup.py) `run_full_backup()` fans out to four
independent destinations — local `backend/backups/`, `BACKUP_MIRROR_DIR`, a
**separate private GitHub repo** (via the Contents API, overwriting one file so
history holds the versions), and Telegram. Each is independent; one failing never
blocks the others, and the scheduler job never raises.

The engine decides the format: SQLite uses `sqlite3.Connection.backup()` (WAL data
included) producing `backup_*.db`; PostgreSQL shells out to `pg_dump --format=custom`
producing `backup_*.dump`, restored with `pg_restore`. The source path comes from
`DATABASE_URL`, not a hardcoded filename. `PG_DUMP_PATH` overrides the binary
location. Anything globbing the backup directory must use `BACKUP_GLOB`, which
matches both extensions.

Invoice photos are **not** in the database dump. `create_uploads_archive()`
tars `backend/uploads/` into `uploads_*.tar.gz` beside the dump, with its own
retention and its own glob (`UPLOAD_ARCHIVE_GLOB`) so the two retentions do not
delete each other's files. Without this a restore brought back every
`SupplyReceipt` row pointing at files that no longer existed — the supplier
balance survived, the evidence for it did not. `UPLOAD_DIR` is anchored to the
module location, not the working directory; it used to be the bare string
`"uploads"`, so starting the app from the repo root silently stranded every
previously uploaded invoice behind a 404.

Triggers: scheduled at `BACKUP_HOURS`, on startup (skipped if a backup is under an
hour old), and manually via `POST /settings/backup`. **Not after every sale** —
that used to be the case, and because `create_backup()` calls `clean_old_backups()`,
it collapsed `BACKUP_RETENTION` from "30 snapshots" to "the last 30 sales",
deleting the morning's backup by lunchtime. `test_sale_does_not_trigger_a_backup`
guards against it coming back.

### Deployment (VPS + PostgreSQL)

[deploy/](deploy/) holds everything for a server install and
[deploy/DEPLOY.md](deploy/DEPLOY.md) is the step-by-step runbook. The pieces that
matter architecturally:

- **Two systemd units, not one.** `kassa-web` runs uvicorn with several workers and `RUN_BACKGROUND_JOBS=false`; `kassa-worker` runs a single process with it `true`. The scheduler, Telegram polling and the startup backup live in the lifespan, so with N workers you get N pollers (Telegram answers `409 Conflict` in a loop), N schedulers (every debtor gets N reminders) and N backup jobs writing the same directory. `/health` reports which role the process is playing.
- **[migrate_to_postgres.py](backend/migrate_to_postgres.py)** moves the shop's live SQLite data across. Pointing `DATABASE_URL` at PostgreSQL is *not* enough — the app would bootstrap a fresh `miraziz` and open an empty shop. The script refuses unless `schema_migrations` on the source shows `migrate_shift_times_to_utc` applied (otherwise shift times would land 5 hours off), refuses a non-empty target, copies in `Base.metadata.sorted_tables` order so foreign keys hold, and — critically — runs `setval` on every `id` sequence afterwards. Without that last step PostgreSQL's sequences stay at 1 and the first new sale dies on a duplicate key. `--dry-run` reports row counts without writing.
- **`ALLOW_SELF_UPDATE=false` on the server.** `POST /system/update` is now admin-only, and `Login.jsx` no longer fires it automatically — it used to, so any cashier logging in mid-trading silently triggered a `git pull`, frontend rebuild and restart. Updates run through [deploy/scripts/update.sh](deploy/scripts/update.sh) after closing.
- `pg_dump` gets the password via `PGPASSWORD`, never argv, so it does not show up in `ps`.
- Searches use `.icontains()`, which compiles to `ILIKE` on PostgreSQL and `lower() LIKE lower()` on SQLite. Plain `.contains()` is `LIKE`, which is case-insensitive only on SQLite — product and audit search would have gone quiet on the server.

### Self-update

[system.py](backend/routers/system.py) spawns `deploy/scripts/update.ps1` detached to `git pull`, rebuild, and restart, tracking progress in `deploy/run/update-status.json` polled by [UpdateOverlay.jsx](frontend/src/components/UpdateOverlay.jsx). Gated on `ALLOW_SELF_UPDATE`. **`deploy/` is not present in this checkout** (and `deploy/run/` is gitignored), so these endpoints will 500 here — that is expected outside the production server.

### Telegram bot

Runs in-process via `asyncio.create_task(dp.start_polling(bot))`, sharing the database and the `SessionLocal` factory. If `TELEGRAM_BOT_TOKEN` is unset, `bot` is `None` and the app starts anyway — guard any new bot usage with a truthiness check. The menu branches on whether the `telegram_id` belongs to a `Client` (balance, bonuses) or an `Employee` (clock in/out; admins additionally get broadcast, "who's working", and a data dump). Employee attendance is bot-only — there is no web clock-in. `check_debts` runs daily at 09:00 and reminds at 3/2/1 days before the due date, on the day, and after.

### Frontend patterns

- Pages are `React.lazy`-loaded in [App.jsx](frontend/src/App.jsx); `ProtectedRoute` checks the token, `RoleProtectedRoute` checks `localStorage.role`. This is UX gating only — the backend re-checks everything.
- No shared API-hook layer: each page calls `api` from [api/axios.jsx](frontend/src/api/axios.jsx) directly inside `useQuery`/`useMutation`. Query keys are ad hoc strings (`["products"]`, `["dashboard-stats", filters]`) invalidated by name after mutations. Defaults ([api/queryClient.jsx](frontend/src/api/queryClient.jsx)): `staleTime` 5 min, no refetch on focus, 1 retry.
- Auth state lives in `localStorage` (`token`, `role`, `username`, `userId`) — there is no auth context.
- [POS.jsx](frontend/src/pages/POS.jsx) is ~1700 lines and holds the register: cart drafts and held carts persisted to `localStorage`, `react-hotkeys-hook` shortcuts (F2 focuses search, etc.), split-payment and manager-approval dialogs.
- ESLint's `no-unused-vars` is an **error** with `varsIgnorePattern: '^[A-Z_]'`. Fix violations rather than disabling the rule.

## Configuration

Backend config is `backend/.env` (see [backend/.env.example](backend/.env.example), which is the authoritative annotated list):

- `APP_ENV` — `development` (default) or `production`. In production, [core.py](backend/core.py) refuses to start without a non-sample `SECRET_KEY`.
- `SECRET_KEY` — JWT signing key; falls back to a shared insecure dev key in development.
- `PRIMARY_ADMIN_PASSWORD` — bootstrap password, used **only when no admin row exists at all**. Unset in development falls back to `DEV_ADMIN_PASSWORD` (`8038434`); unset in production raises rather than creating a weak account. The username `miraziz` is hardcoded and not configurable.
- `DATABASE_URL` — defaults to `backend/market.db`. `postgres://`/`postgresql://` are rewritten to `+asyncpg`. SQLite connections get `journal_mode=WAL`, `synchronous=FULL` (durability over speed — this is a till) and `foreign_keys=ON`. **PostgreSQL is the right choice on a server**: SQLite allows one writer at a time, so two registers trading concurrently hit `database is locked`.
- `SHOP_TIMEZONE` — default `Asia/Tashkent`. Drives every "day" boundary and all displayed times. The host clock is irrelevant.
- `TRUST_PROXY_HEADERS` — default `false`. Enable only behind a reverse proxy that rewrites `X-Forwarded-For`.
- `PG_DUMP_PATH` — override the `pg_dump` binary location for backups.
- `ALLOWED_ORIGINS` — comma-separated CORS allowlist; defaults to `*` (warned about in production). If you set it, every origin you test from must be listed or requests fail with only a browser console error.
- `BACKUP_ENABLED`, `BACKUP_HOURS` (comma-separated hours, default `12,22` — note the plural), `BACKUP_RETENTION`, `BACKUP_MIRROR_DIR`, `BACKUP_GITHUB_TOKEN`/`_REPO`/`_PATH`/`_BRANCH`.
- `ALLOW_SELF_UPDATE` — enables the in-app update button.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`.

Frontend: `VITE_API_URL` in [api/axios.jsx](frontend/src/api/axios.jsx), with `??` (not `||`) so an explicit empty string means same-origin. `@` aliases `src/` ([vite.config.js](frontend/vite.config.js)).

Pinned for an old Windows server: `numpy<2.1`, `pandas<2.3` (Python 3.9 compatibility). Don't bump these casually.

## Coding Conventions

- **Python:** four-space indent, `snake_case`, `PascalCase` models/schemas, type annotations, async DB access throughout (`await db.execute(select(...))`, `.scalars().first()` / `.all()`, `.unique()` when `joinedload` touches a collection). Log meaningful mutations with `await log_action(db, user_id, "UPPER_SNAKE_UZBEK", details)` before the commit that persists them — `log_action` only flushes. Mutate money and stock with an atomic `UPDATE`, never `+=` on an ORM attribute. Write timestamps with `utc_now()` from [utils/timezone.py](backend/utils/timezone.py).
- **React:** `PascalCase.jsx` for components and pages, camelCase for variables, Tailwind utilities, `cn()` from [lib/utils.js](frontend/src/lib/utils.js) for conditional classes. Render server timestamps with `formatDateTime()` from [lib/datetime.js](frontend/src/lib/datetime.js) — never bare `new Date(apiValue)`.
- Never commit `*.db`/`*.db-shm`/`*.db-wal`, `.env` (except the `.example` files and the deliberately tracked `frontend/.env*`), `backend/uploads/`, or build output.

## Documentation caveat

[docs/README.md](docs/README.md) and [docs/README_USER_GUIDE.md](docs/README_USER_GUIDE.md) predate the React rewrite: they describe a Bootstrap/Jinja UI, `/api/*` endpoint paths, and hardcoded tokens in `main.py`, none of which exist any more. Treat them as historical. [docs/AGENTS.md](docs/AGENTS.md) is broadly accurate but references a `test_render_400.py` that is no longer in the tree.
