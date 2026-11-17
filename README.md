# StockWise

[![CI](https://github.com/josephmarube/StockWise/actions/workflows/ci.yml/badge.svg)](https://github.com/josephmarube/StockWise/actions/workflows/ci.yml)

A web-based inventory management system for small retail businesses (scoped to Nairobi, Kenya). Built to the StockWise SRS.

**Many businesses, one platform.** Like Slack workspaces, each shop signs up and gets its own private space: products, stock, suppliers, staff and reports. The manager invites staff with a link. No business can see or change another's data. StockWise's own System Admins oversee the platform but see only business metadata, and everything they do is shown to the business.

**Stack:** React 18 (Vite) · FastAPI · SQLAlchemy 2 + Alembic · MySQL 8 · JWT + bcrypt

Stock can be recorded by typing, with a USB/Bluetooth barcode scanner, or with a phone or laptop camera. Every method goes through the same rules and audit log, and each movement records how it was entered.

```
stockwise/
├── backend/            FastAPI REST API
│   ├── app/
│   │   ├── main.py             app setup, CORS, error handling
│   │   ├── models.py           SQLAlchemy entities (SRS Appendix B.1 class diagram)
│   │   ├── schemas.py          request/response validation (NFR8)
│   │   ├── security.py         bcrypt hashing, JWT issue/verify (NFR1, FR4.1)
│   │   ├── deps.py             auth + role dependencies: Manager, Staff, System Admin (NFR2)
│   │   ├── services/stock_service.py   the only code that changes stock (B.3 sequence diagram)
│   │   └── routers/            one router per resource (NFR9)
│   ├── migrations/             Alembic database migrations
│   ├── scripts/seed.py         demo data
│   ├── scripts/load_test.py    NFR3 concurrency/latency check
│   └── tests/                  pytest suite, named by requirement ID
├── frontend/           React single-page app
│   └── src/
│       ├── pages/              Login, Signup, Join, Dashboard, RecordStock, Products, ProductDetail, Suppliers, Reports, Users
│       └── components/         shared UI, ProductPicker (search + scan), BarcodeScanner (camera)
├── docs/
│   ├── DEPLOY.md               Aiven + Render deployment guide
│   ├── USER_GUIDE.md           end-user guide (SRS 2.6)
│   └── TRACEABILITY.md         requirement → code → test map
├── Dockerfile                  production image (frontend build + API)
├── docker-compose.yml          production image + MySQL, for local runs
└── render.yaml                 Render Blueprint
```

## Quick start (local development)

Prerequisites: Python 3.11+, Node 20+, MySQL 8.

> **macOS:** the built-in `python3` is 3.9, which is too old. Use Homebrew's: `brew install python@3.12`, then create the venv with `/opt/homebrew/bin/python3.12 -m venv .venv`. Check with `python --version` once the venv is active.

**1. Database**

Choose a password for the database user, then run (with `mysql -uroot`):

```sql
CREATE DATABASE stockwise CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE stockwise_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;  -- for the test suite
CREATE USER 'stockwise'@'%' IDENTIFIED BY '<your-db-password>';
GRANT ALL ON stockwise.* TO 'stockwise'@'%';
GRANT ALL ON stockwise_test.* TO 'stockwise'@'%';
```

On macOS, install MySQL first: `brew install mysql && brew services start mysql`.

No passwords or secrets are written in this repository. Everything comes from `backend/.env` (git-ignored) locally, or from the host's environment settings in production.

**2. Backend**

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # put your database password in DATABASE_URL
python -m scripts.seed        # runs migrations + loads demo data
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

**3. Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000.

**Barcode scanning.** Every seeded product has a demo EAN-13 barcode, shown on its product page.
- *USB/Bluetooth scanner:* on **Record stock**, click the search box and scan. Scanners type like a keyboard, so there is no setup.
- *Camera:* tap **Scan**. Browsers allow the camera only on `https://` or `localhost`, so on a phone, test against the deployed (HTTPS) site rather than your laptop's network address.
- *No scanner?* Type a barcode into the search box and press Enter.

**Demo accounts** (from the seed script). There are two separate businesses, so you can see that each one sees only its own data:

| Business | Role | Email | Password |
|---|---|---|---|
| Mama Njeri Duka (shop) | Manager | admin@stockwise.co.ke | Admin@12345 |
| | Staff | grace@stockwise.co.ke | Staff@12345 |
| | Staff | brian@stockwise.co.ke | Staff@12345 |
| Kilimani Hardware | Manager | wanjiru@kilimanihardware.co.ke | Admin@12345 |
| | Staff | daniel@kilimanihardware.co.ke | Staff@12345 |
| StockWise (platform) | System Admin | support@stockwise.co.ke | System@12345 |

These are demo passwords for local use. For a public deployment, seed with `SEED_PASSWORD` set: every demo account then uses that password instead.

**Roles.** *Staff* record stock and view products. *Managers* also manage products, suppliers, reports, people and see the activity log. *System Admins* are StockWise staff: they see a list of businesses with counts, dates and when someone last logged in (never products, prices, stock or sales activity), can rename, deactivate or reactivate a business, and every such action appears in that business's activity log. There is no web signup for System Admins; create one from the server:

```bash
cd backend
python -m scripts.create_system_admin --email you@example.com --name "Your Name"   # asks for the password twice
```

**Or create your own business:** open http://localhost:5173/signup. To add staff, go to **Users → Invite people** and send them the link.

To start with an empty database, skip the seed step and just sign up. Alternatively, set `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` (and optionally `BOOTSTRAP_BUSINESS_NAME`) in `.env`, and the API creates that business and its manager on first start.

## Database migrations

The API applies migrations automatically when it starts (and the seed script does too), so normally there is nothing to run. A database created by StockWise v1.0, before migrations existed, is detected and upgraded in place without losing data.

```bash
alembic upgrade head                                  # apply migrations by hand
alembic revision --autogenerate -m "describe change"  # after changing models.py
python -m scripts.seed --reset                        # wipe everything and reload demo data
```

## Deployment and Docker

Production is a single Docker image (root `Dockerfile`): FastAPI serves the API and the built React app from one HTTPS address. The database is hosted MySQL (Aiven), connected over TLS.

- **Deploy to Render + Aiven:** follow [docs/DEPLOY.md](docs/DEPLOY.md). `render.yaml` is a ready-made Render Blueprint.
- **Run the production image locally** (needs Docker Desktop):
  ```bash
  cp .env.example .env               # fill in MYSQL_PASSWORD, MYSQL_ROOT_PASSWORD, JWT_SECRET
  docker compose up --build
  docker compose exec app python -m scripts.seed   # optional demo data
  ```
  Open http://localhost:8080.

## Tests

```bash
cd backend
pytest                                   # fast, in-memory SQLite (177 tests)

# Full suite against real MySQL (186 tests), adding the row-lock concurrency, migration and server-command tests:
TEST_DATABASE_URL='mysql+pymysql://stockwise:<your-db-password>@127.0.0.1/stockwise_test' pytest
```

GitHub Actions runs the full MySQL suite, a lint check and a frontend build on every pull request and every push to `main` (`.github/workflows/ci.yml`).

The MySQL run needs the empty `stockwise_test` database from step 1. Test accounts, passwords and keys are generated randomly on each run. Tests are named after the requirement they verify (`test_fr2_2_...`, `test_nfr1_...`). See `docs/TRACEABILITY.md`.

**Performance (NFR3).** Start the API against a seeded database, then run:

```bash
python -m scripts.load_test --users 10 --rounds 25
```

Measured during development: 10 concurrent users, 1,000 requests, p95 of 83–117 ms per operation, 0 errors (target is under 1,000 ms).

## Key design decisions

- **Stock changes go through one service.** `StockService.record_movement` locks the product row (`SELECT … FOR UPDATE`), applies the negative-stock rule, updates stock and inserts the movement in one transaction. Two cashiers selling the last units at the same moment cannot oversell. `tests/test_concurrency.py` proves this, and it fails if the lock is removed.
- **Movements are immutable and are the audit log** (FR7.1). Corrections are made with a new movement, never by editing history.
- **Multi-business (multi-tenant) with strict isolation.** Every table carries a `business_id`, and every query filters by the signed-in user's business, read from the database on each request. Another business's records behave exactly as if they did not exist (404 or empty lists), including barcode lookups, filters by ID, reports and CSV exports. SKUs, barcodes and category names are unique per business. `tests/test_tenancy.py` attacks every resource from a second business. Each test was also checked by deliberately removing a filter: the tests fail, which shows they would catch a leak.
- **One account belongs to one business.** Emails are unique across the platform. People join a business by signup (they become its manager) or by a manager's invite link. Invite tokens are random, single-use and expiring, and only their SHA-256 hash is stored.
- **Rate limits** on login (20 per 5 minutes), signup (5 per hour) and invite use (10 per hour), per IP address. They are held in memory, which suits a single-instance deployment; several instances would need a shared store such as Redis.
- **One core, many input channels.** Typed, scanner and camera entries all call the same `record_movement`, so the negative-stock rule, low-stock alerts and audit log behave identically. Each movement stores its `source` (manual, scanner or camera; import, till and API are reserved for later phases).
- **Barcodes are a separate table.** A product can have several (single unit and carton), and each barcode belongs to exactly one product.
- **Scanner detection is by typing speed.** USB scanners "type" a code in a few milliseconds; keystrokes averaging under 35 ms are recorded as `SCANNER`, slower typing as `MANUAL`.
- **Opening stock is a movement.** When a product is created with initial stock, that stock is recorded as a stock-in, so every unit can be traced.
- **Roles are checked against the database on every request**, not just read from the JWT. Demoting or disabling a user takes effect immediately.
- **Three roles with a hard boundary.** Managers and Staff belong to one business. System Admins belong to none (a database CHECK constraint enforces this), are rejected by every shop endpoint, and use `/api/platform` only, which returns counts, dates and last login, never a shop's products, prices, stock or sales activity. Only a System Admin can rename a business, so a shop can't rename itself to pose as another one.
- **Activity log with before/after values.** Every change to products, suppliers, categories, people, invites and the business is written to `activity_logs` in the same transaction as the change (who, role, what, `{field: [before, after]}`). Passwords are recorded only as "reset". Actions a System Admin takes on a business are logged against that business and highlighted in its log. Stock in/out keeps its own audit trail (FR7.1).
- **Timestamps are stored in UTC.** Report date ranges and CSV times use the business timezone (`BUSINESS_TIMEZONE`, default Africa/Nairobi).
- **CSV exports neutralise spreadsheet formulas.** A product named `=HYPERLINK(...)` cannot run in Excel.

## API overview

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/signup` | — | Create a business and its manager, get JWT |
| POST | `/api/auth/login` | — | Log in, get JWT |
| GET | `/api/auth/me` | any | Current user and their business (none for a System Admin) |
| GET | `/api/business` | shop | View your business |
| GET/POST/DELETE | `/api/invites…` | manager | Create, list and cancel invite links |
| GET | `/api/invites/preview/{token}` | — | What an invite link is for (join page) |
| POST | `/api/invites/accept` | — | Join a business with an invite, get JWT |
| GET | `/api/dashboard` | any | Totals, low-stock list, recent movements |
| GET | `/api/products` | any | Search/filter/sort catalogue (name, SKU or exact barcode) |
| GET | `/api/products/by-barcode/{code}` | any | Find the product for a scanned barcode |
| POST / PATCH | `/api/products[/{id}]` | manager | Create / edit |
| POST | `/api/products/{id}/archive` · `/restore` | manager | Archive / restore |
| DELETE | `/api/products/{id}` | manager | Delete (only if no history) |
| PUT | `/api/products/{id}/suppliers` | manager | Link suppliers |
| POST | `/api/stock/movements` | shop | Stock in/out with `source` (`override` manager-only) |
| GET | `/api/stock/movements` | any | Movement history (filter by product, type, source, dates) |
| GET/POST/PATCH/DELETE | `/api/suppliers…` | manager | Supplier CRUD; delete deactivates if linked |
| GET | `/api/reports/stock` · `/stock.csv` | manager | Stock report + CSV |
| GET | `/api/reports/audit` · `/movements.csv` | manager | Audit log + CSV |
| GET/POST/PATCH | `/api/users…` | manager | User management |
| GET/POST | `/api/categories` | shop / manager | Categories |
| GET | `/api/dashboard/trends` | shop | Daily in/out, fastest movers, value by category (managers) |
| GET | `/api/activity` | manager | Activity log with before/after values |
| GET | `/api/platform/summary` · `/businesses` | system admin | Business metadata (counts, dates) |
| PATCH | `/api/platform/businesses/{id}` | system admin | Rename, deactivate or reactivate (logged to the business) |
| GET | `/api/platform/activity` | system admin | Signups and System Admin actions |
