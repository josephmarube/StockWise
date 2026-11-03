# StockWise

A web-based inventory management system for small, single-location retail businesses (scoped to Nairobi, Kenya). Built to the StockWise SRS v1.1.

**Stack:** React 18 (Vite) · FastAPI · SQLAlchemy 2 · MySQL 8 · JWT + bcrypt

```
stockwise/
├── backend/            FastAPI REST API
│   ├── app/
│   │   ├── main.py             app setup, CORS, error handling
│   │   ├── models.py           SQLAlchemy entities (SRS Appendix B.1 class diagram)
│   │   ├── schemas.py          request/response validation (NFR8)
│   │   ├── security.py         bcrypt hashing, JWT issue/verify (NFR1, FR4.1)
│   │   ├── deps.py             auth + admin-role dependencies (NFR2)
│   │   ├── services/stock_service.py   the only code that changes stock (B.3 sequence diagram)
│   │   └── routers/            one router per resource (NFR9)
│   ├── scripts/seed.py         demo data
│   ├── scripts/load_test.py    NFR3 concurrency/latency check
│   └── tests/                  pytest suite, named by requirement ID
├── frontend/           React single-page app
│   └── src/pages/      Login, Dashboard, RecordStock, Products, ProductDetail, Suppliers, Reports, Users
├── docs/
│   ├── USER_GUIDE.md           end-user guide (SRS 2.6)
│   └── TRACEABILITY.md         requirement → code → test map
└── docker-compose.yml
```

## Quick start (local development)

Prerequisites: Python 3.11+, Node 20+, MySQL 8.

**1. Database**

```sql
CREATE DATABASE stockwise CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'stockwise'@'localhost' IDENTIFIED BY 'stockwise';
GRANT ALL ON stockwise.* TO 'stockwise'@'localhost';
```

On macOS: `brew install mysql && brew services start mysql`, then run the SQL above with `mysql -uroot`.

**2. Backend**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # edit JWT_SECRET
python -m scripts.seed        # creates tables + demo data
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

**Demo accounts** (from the seed script):

| Role  | Email                   | Password    |
|-------|-------------------------|-------------|
| Admin | admin@stockwise.co.ke   | Admin@12345 |
| Staff | grace@stockwise.co.ke   | Staff@12345 |
| Staff | brian@stockwise.co.ke   | Staff@12345 |

To start with an empty database instead, skip the seed step and set `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` in `.env`. The API creates that admin on first start if there are no users.

## Docker

```bash
docker compose up --build
docker compose exec backend python -m scripts.seed   # optional demo data
```

Open http://localhost:8080. Set `JWT_SECRET` and `MYSQL_PASSWORD` in a root `.env` file before deploying anywhere real, and put the stack behind a TLS-terminating proxy so all traffic is HTTPS (SRS 3.4).

## Tests

```bash
cd backend
pytest                                   # fast, in-memory SQLite (70 tests)

# Full suite against real MySQL, including the row-lock concurrency test:
TEST_DATABASE_URL=mysql+pymysql://stockwise:stockwise@127.0.0.1/stockwise_test pytest
```

The MySQL run needs an empty `stockwise_test` database the `stockwise` user can access. Tests are named after the requirement they verify (`test_fr2_2_...`, `test_nfr1_...`). See `docs/TRACEABILITY.md`.

**Performance (NFR3).** Start the API against a seeded database, then run:

```bash
python -m scripts.load_test --users 10 --rounds 25
```

Measured during development: 10 concurrent users, 1,000 requests, p95 of 83–117 ms per operation, 0 errors (target is under 1,000 ms).

## Key design decisions

- **Stock changes go through one service.** `StockService.record_movement` locks the product row (`SELECT … FOR UPDATE`), applies the negative-stock rule, updates stock and inserts the movement in one transaction. Two cashiers selling the last units at the same moment cannot oversell. `tests/test_concurrency.py` proves this, and it fails if the lock is removed.
- **Movements are immutable and are the audit log** (FR7.1). Corrections are made with a new movement, never by editing history.
- **Opening stock is a movement.** When a product is created with initial stock, that stock is recorded as a stock-in, so every unit can be traced.
- **Roles are checked against the database on every request**, not just read from the JWT. Demoting or disabling a user takes effect immediately.
- **Timestamps are stored in UTC.** Report date ranges and CSV times use the business timezone (`BUSINESS_TIMEZONE`, default Africa/Nairobi).
- **CSV exports neutralise spreadsheet formulas.** A product named `=HYPERLINK(...)` cannot run in Excel.

## API overview

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/login` | — | Log in, get JWT |
| GET | `/api/auth/me` | any | Current user |
| GET | `/api/dashboard` | any | Totals, low-stock list, recent movements |
| GET | `/api/products` | any | Search/filter/sort catalogue |
| POST / PATCH | `/api/products[/{id}]` | admin | Create / edit |
| POST | `/api/products/{id}/archive` · `/restore` | admin | Archive / restore |
| DELETE | `/api/products/{id}` | admin | Delete (only if no history) |
| PUT | `/api/products/{id}/suppliers` | admin | Link suppliers |
| POST | `/api/stock/movements` | any | Stock in/out (`override` admin-only) |
| GET | `/api/stock/movements` | any | Movement history |
| GET/POST/PATCH/DELETE | `/api/suppliers…` | admin | Supplier CRUD; delete deactivates if linked |
| GET | `/api/reports/stock` · `/stock.csv` | admin | Stock report + CSV |
| GET | `/api/reports/audit` · `/movements.csv` | admin | Audit log + CSV |
| GET/POST/PATCH | `/api/users…` | admin | User management |
| GET/POST | `/api/categories` | any / admin | Categories |
