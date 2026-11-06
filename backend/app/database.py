"""SQLAlchemy engine and session management."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    s = get_settings()
    kwargs: dict = {"pool_pre_ping": True}
    if s.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # pool_recycle below typical hosted-MySQL idle timeouts.
        kwargs.update(pool_size=5, max_overflow=5, pool_recycle=280, connect_args=s.db_connect_args())
    return create_engine(s.database_url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
