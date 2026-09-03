# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kassa is a full-stack Point of Sale (POS) system with Telegram bot integration. It manages sales, inventory, customers (CRM), employee shifts, finances, and tasks. The system supports role-based access control with three roles: admin, manager (menejer), and cashier (kassir).

**Tech Stack:**

- Backend: FastAPI (async), SQLAlchemy 2.0 (async mode), SQLite (aiosqlite), Aiogram 3.x (Telegram bot)
- Frontend: React 19, Vite, React Router, TanStack Query, Tailwind CSS, Radix UI, shadcn/ui components
- Authentication: JWT tokens with passlib (pbkdf2_sha256)

## Common Commands

### Backend

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run backend server (development)
cd backend
python main.py
# OR
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Database utilities (run from backend/)
python reset_admin.py         # Reset admin password (lockout recovery)
```

Schema changes (new tables/columns) are applied automatically on `main.py` startup — there are no separate migration scripts.

### Frontend

```bash
cd frontend
npm install
npm run dev        # Development server (Vite, binds 0.0.0.0:5173 — LAN-accessible by default)
npm run build       # Production bundle
npm run lint         # ESLint — run before submitting frontend changes
npm run preview     # Preview production build
```

### Running both at once

`./run_project.ps1` starts backend and frontend together, but it first force-kills any running `python`/`node`/`uvicorn` processes — only use it when that's acceptable.

### Testing

There is no unified test runner or coverage tooling. Ad hoc scripts exist at the repo root (`test_features.py`, `test_async_db.py`, `check_db_lock.py`) — some require a running API or configured database. For new behavior, prefer adding a focused script and manually verifying the affected API routes and UI flows.

## Architecture

### Backend Structure

The backend follows a **modular router pattern**:

- **[main.py](backend/main.py)** - Application entry point with lifespan management. Initializes database, creates default admin user, starts Telegram bot polling and debt checking tasks in background
- **[database.py](backend/database.py)** - SQLAlchemy 2.0 async models and database setup. All database operations are async using `AsyncSession`
- **[core.py](backend/core.py)** - Authentication utilities (JWT, password hashing, `get_current_user` dependency)
- **[schemas.py](backend/schemas.py)** - Pydantic models for request/response validation
- **[bot.py](backend/bot.py)** - Telegram bot implementation with debt reminders
- **[routers/](backend/routers/)** - FastAPI routers organized by domain:
  - **auth.py** - Login, employee CRUD (admin/manager only)
  - **pos.py** - POS sales, shift management (open/close)
  - **inventory.py** - Products, categories, stock management
  - **crm.py** - Clients, debt tracking, payment history
  - **finance.py** - Sales history, expenses, statistics
  - **tasks.py** - Employee task management

### Frontend Structure

The frontend uses **React Router for navigation** with a protected route pattern:

- **[App.jsx](frontend/src/App.jsx)** - Root component with React Router setup, protected routes, TanStack Query provider, theme provider
- **[pages/](frontend/src/pages/)** - Route components (Dashboard, POS, Inventory, CRM, Finance, Employees, Login)
- **[components/](frontend/src/components/)** - Shared UI components:
  - **Layout.jsx** - Main layout with navigation sidebar
  - **ui/** - shadcn/ui components (buttons, dialogs, forms, etc.)
  - **theme-provider.jsx** - Dark/light theme management
- **[api/](frontend/src/api/)** - API client setup with axios and TanStack Query hooks
- **[lib/](frontend/src/lib/)** - Utilities (e.g., `cn()` for className merging)

### Database Schema

Key relationships and patterns:

1. **Employee** - Central user model for authentication. Referenced by shifts, sales, expenses, tasks, audit logs
2. **Client** - Customer CRM with balance tracking (positive = prepayment, negative = debt) and debt due dates
3. **Sale** - Has many **SaleItems** (one-to-many). References Employee (cashier) and Client (optional, for credit sales)
4. **Shift** - Cashier shift with opening/closing balance. One shift per cashier at a time (enforced in business logic)
5. **Product** - Referenced by SaleItems and Supplies. Has category relationship
6. **Payment** - Client debt payments, linked to Client, Employee (who processed), and Shift (when processed)
7. **Task** - Employee task assignments with status tracking (pending, in_progress, completed)

All timestamps use `datetime.utcnow()` and are stored as DateTime columns.

### Authentication & Authorization

**Flow:**

1. Login via `POST /auth/token` returns JWT with role/permissions
2. Frontend stores token in localStorage
3. All protected routes use `get_current_user` dependency which validates JWT
4. Role checks are done in route handlers (e.g., `if current_user.role not in ["admin", "manager"]`)

**Roles & Permissions:**

- **admin** - Full access, can manage employees, view audit logs
- **manager** (menejer) - Can manage products, sales, clients, expenses, view employees (read-only)
- **cashier** (kassir) - Can make sales, open/close shifts, add clients, add expenses (limited delete rights)

**Default Credentials:**

- Username: `miraziz`
- Password: `8038434` (created in [main.py](backend/main.py) on startup only if no admin account exists at all)

An admin/manager resets a forgotten employee password from the Employees page — edit the employee, type a new password in "Yangi Parol", the eye icon reveals it. Backend: `PATCH /auth/employees/{id}` with a `password` field. Stored passwords are hashed and cannot be read back — only replaced.

**Primary admin lock:** the account named `PRIMARY_ADMIN_USERNAME` ([core.py](backend/core.py), `miraziz`) cannot be edited or deleted through the API — `PATCH`/`DELETE /auth/employees/{id}` refuse it (403/400) and the frontend hides those actions for that row. Change its password only on the server with `python reset_admin.py "new-password"` (prompts if no arg; never writes the password to disk).

**Only the primary admin manages the admin tier:** creating an `admin`-role account, editing or deleting another `admin`-role account, and promoting anyone to `admin` are all restricted to `miraziz` (403 otherwise, in [routers/auth.py](backend/routers/auth.py)). A regular admin still manages managers/cashiers/warehouse and can edit their own account. The frontend hides the "Admin" role option and the row actions on admin rows unless the logged-in user is `miraziz`.

**Single active session per user:** logging in while a previous session token hasn't expired returns `409 Conflict` ("boshqa qurilmada tizimga kirgan"). This is enforced via `Employee.session_token`/`session_expires_at` in [routers/auth.py](backend/routers/auth.py) — not a bug. Sessions expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (600 min) or clear on logout.

### Telegram Bot Integration

The bot runs in the background via `asyncio.create_task()` in the app lifespan:

- **Client registration** - Clients can register via Telegram using phone number
- **Balance checking** - Clients can check their debt balance
- **Automated debt reminders** - Sent at 3, 2, 1 days before due date, on due date, and after overdue
- **Low stock alerts** - Notifications when product stock is low (implementation varies)

The bot and API share the same database, linking via `telegram_id` on Client and Employee models.

### Async Patterns

All database operations are async:

- Use `await db.execute()` for queries with SQLAlchemy 2.0 style
- Use `await db.commit()` to persist changes
- Use `await db.refresh(obj)` to reload object after commit
- Get single result: `result.scalars().first()`
- Get all results: `result.scalars().all()`

Example:

```python
from sqlalchemy import select
result = await db.execute(select(Employee).where(Employee.username == username))
user = result.scalars().first()
```

### Frontend API Integration

Uses TanStack Query (React Query) for data fetching:

- Query hooks for GET requests with automatic caching/refetching
- Mutation hooks for POST/PUT/DELETE with optimistic updates
- API base URL should be configurable (currently likely hardcoded in api client)
- All authenticated requests include JWT token in Authorization header

## Important Configuration

**Backend** — configured via `backend/.env` (loaded with `python-dotenv`):

- `APP_ENV` - `development` (default) or `production`. When `production`, [core.py](backend/core.py) raises on startup if `SECRET_KEY` is unset or still the sample dev key.
- `SECRET_KEY` - JWT signing key ([core.py](backend/core.py)); in `development` falls back to an insecure shared default
- `DATABASE_URL` - defaults to local SQLite (`backend/market.db`); `postgres://`/`postgresql://` URLs are rewritten to use `asyncpg` automatically ([database.py](backend/database.py))
- `ALLOWED_ORIGINS` - comma-separated CORS allowlist ([main.py](backend/main.py)); defaults to `*` if unset, but if you set it, every frontend origin you test from (including LAN IPs) must be listed explicitly or requests are blocked by CORS with no error detail beyond a browser console message
- `BACKUP_ENABLED`/`BACKUP_HOUR`/`BACKUP_RETENTION` - daily SQLite snapshot into `backend/backups/` ([utils/backup.py](backend/utils/backup.py)); the scheduler job is `run_daily_backup` in [main.py](backend/main.py)
- `BACKUP_MIRROR_DIR` - optional second location every backup is copied to (external disk / synced folder); empty = local only
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID` - bot credentials; when `TELEGRAM_ADMIN_CHAT_ID` is set the daily backup file is also sent to that chat

**Frontend:**

- **[vite.config.js](frontend/vite.config.js)** - Path alias `@` points to `src/`; dev server binds `0.0.0.0:5173` and proxies `/api` to `http://127.0.0.1:8000`
- **[api/axios.jsx](frontend/src/api/axios.jsx)** - `VITE_API_URL` env var sets the API base URL (defaults to `http://localhost:8000`, which only works for same-machine access — set it to the backend host's LAN IP when testing from another device)

## Development Workflow

1. **Start backend first**: The backend must be running for the frontend to function
2. **Database auto-creates**: Tables are created automatically via SQLAlchemy on first run
3. **Default admin**: Created on startup if doesn't exist
4. **Telegram bot**: Starts automatically with backend (ensure token is configured)
5. **Frontend proxy**: Vite dev server should proxy API requests to backend (verify proxy config if needed)

## Key Business Logic

**Shift Management:**

- Cashiers must open shift before making sales
- Only one open shift per cashier allowed
- Opening balance tracks cash at start, closing balance at end
- Discrepancy calculated on shift close

**Sales & Inventory:**

- Sales automatically decrement product stock
- Refunds (admin/manager only) restore stock and mark sale as "refunded"
- Supply/incoming stock tracked separately in Supply table

**Client Debt:**

- Negative balance = client owes money
- Positive balance = client has prepaid
- Debt due dates trigger Telegram reminders
- Payment history tracked in Payment table

**Audit Logging:**

- Important actions logged to audit_logs table
- Includes user_id (employee), action, details, timestamp

## Coding Conventions

- Python: four-space indentation, `snake_case` functions/modules, `PascalCase` for models/Pydantic schemas, type annotations, async DB access throughout. Add new endpoints to the appropriate domain router in `routers/`, not `main.py`.
- React: `PascalCase.jsx` for components/pages, camelCase variables/functions, Tailwind utility classes. Resolve ESLint errors rather than disabling rules.
- Do not commit local databases (`*.db`, `*.db-shm`, `*.db-wal`), `.env` files, or generated build output.
