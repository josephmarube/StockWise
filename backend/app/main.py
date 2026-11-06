"""StockWise API entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from .config import get_settings
from .database import SessionLocal, engine
from .migrate import upgrade_to_head
from .models import Role, User
from .routers import auth, categories, dashboard, products, reports, stock, suppliers, users
from .security import hash_password

log = logging.getLogger("stockwise")


def init_db() -> None:
    upgrade_to_head()
    s = get_settings()
    if not (s.bootstrap_admin_email and s.bootstrap_admin_password):
        return
    with SessionLocal() as db:
        has_users = db.scalar(select(func.count()).select_from(User))
        if not has_users:
            db.add(
                User(
                    name="Administrator",
                    email=s.bootstrap_admin_email.lower(),
                    password_hash=hash_password(s.bootstrap_admin_password),
                    role=Role.ADMIN,
                )
            )
            db.commit()
            log.warning("Created bootstrap admin %s; change its password after first login.",
                        s.bootstrap_admin_email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="StockWise API",
    version="1.0.0",
    description="Inventory management for small retail businesses.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Readable validation errors (NFR8) with a per-field map for the UI."""
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        key = ".".join(loc) or "request"
        msg = err.get("msg", "Invalid value").removeprefix("Value error, ")
        fields.setdefault(key, msg)
    summary = "; ".join(f"{k}: {v}" for k, v in fields.items())
    return JSONResponse(
        status_code=422,
        content={"detail": f"Invalid input - {summary}", "fields": fields},
    )


for r in (auth, users, categories, products, suppliers, stock, dashboard, reports):
    app.include_router(r.router)


@app.get("/api/health", tags=["meta"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
