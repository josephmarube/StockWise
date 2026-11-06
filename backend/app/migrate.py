"""Run Alembic migrations from code (API startup, seed script).

Databases created by StockWise v1.0 (before migrations existed) have the tables
but no alembic_version row. Those are stamped at the baseline revision first,
so upgrading them applies only the newer migrations and keeps existing data.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from .database import Base, engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
BASELINE = "0001"


def _config(connection) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["connection"] = connection
    return cfg


def upgrade_to_head() -> None:
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        cfg = _config(conn)
        if "alembic_version" not in tables and "users" in tables:
            command.stamp(cfg, BASELINE)
        command.upgrade(cfg, "head")


def reset_database() -> None:
    """Drop everything (including the migration record) and rebuild from migrations."""
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    upgrade_to_head()


if __name__ == "__main__":
    # `python -m app.migrate`: run once before starting the API workers.
    import logging

    logging.basicConfig(level=logging.INFO)
    upgrade_to_head()
    print("Database is up to date.")
