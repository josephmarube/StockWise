"""StockWise API entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text

from .config import get_settings
from .database import SessionLocal, engine
from .migrate import upgrade_to_head
from .models import Business, Role, User
from .routers import (
    auth,
    business,
    categories,
    dashboard,
    invites,
    products,
    reports,
    stock,
    suppliers,
    users,
)
from .security import hash_password

log = logging.getLogger("stockwise")


def init_db() -> None:
    s = get_settings()
    if s.migrate_on_startup:
        upgrade_to_head()
    if not (s.bootstrap_admin_email and s.bootstrap_admin_password):
        return
    with SessionLocal() as db:
        has_users = db.scalar(select(func.count()).select_from(User))
        if not has_users:
            db.add(
                User(
                    business=Business(name=s.bootstrap_business_name),
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


for r in (auth, business, invites, users, categories, products, suppliers, stock, dashboard, reports):
    app.include_router(r.router)


@app.get("/api/health", tags=["meta"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


# ---------- Production: serve the built React app from the same origin ----------
# In development Vite serves the frontend; in the Docker image STATIC_DIR points at its build.
_static = get_settings().static_dir
STATIC_DIR = Path(_static).resolve() if _static else None

if STATIC_DIR and (STATIC_DIR / "index.html").is_file():
    INDEX = STATIC_DIR / "index.html"
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.middleware("http")
    async def static_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/assets/"):
            # File names contain a content hash, so they never change.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "Not found")
        file = (STATIC_DIR / path).resolve()
        if path and file.is_file() and STATIC_DIR in file.parents:
            return FileResponse(file)
        # Client-side routes (/products/3, /record, ...) all load the app shell.
        return FileResponse(INDEX, headers={"Cache-Control": "no-cache"})
