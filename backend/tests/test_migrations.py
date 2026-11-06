"""Alembic migrations: fresh install, and upgrading a v1.0 database without losing data.

Requires MySQL (skipped on SQLite):
    TEST_DATABASE_URL=mysql+pymysql://stockwise:stockwise@127.0.0.1/stockwise_test pytest
"""
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app import migrate
from app.database import Base
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not (TEST_DATABASE_URL or "").startswith("mysql"), reason="needs MySQL (TEST_DATABASE_URL)"
)


@pytest.fixture()
def eng(monkeypatch):
    e = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(e)
    with e.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS alembic_version"))
    monkeypatch.setattr(migrate, "engine", e)
    yield e
    Base.metadata.drop_all(e)
    with e.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS alembic_version"))
    e.dispose()


def _schema_diff(e):
    with e.connect() as c:
        return compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata)


def test_fresh_database_matches_models(eng):
    migrate.upgrade_to_head()
    assert _schema_diff(eng) == []
    with eng.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0003"


def test_v1_database_upgrades_and_keeps_data(eng):
    # Build the v1.0 schema exactly as v1.0 shipped it (migration 0001), then forget Alembic,
    # which is the state of a database created by v1.0's create_all.
    with eng.begin() as c:
        command.upgrade(migrate._config(c), "0001")
        c.execute(text("DROP TABLE alembic_version"))
        c.execute(text("INSERT INTO users (id,name,email,password_hash,role,is_active,created_at) "
                       "VALUES (1,'A','a@x.co','h','ADMIN',1,NOW())"))
        c.execute(text("INSERT INTO categories (id,name) VALUES (1,'C')"))
        c.execute(text("INSERT INTO products (id,sku,name,category_id,unit_price,reorder_threshold,"
                       "current_stock,archived,created_at,updated_at) VALUES (1,'S','P',1,10,1,5,0,NOW(),NOW())"))
        c.execute(text("INSERT INTO stock_movements (product_id,user_id,type,quantity,stock_after,override,created_at) "
                       "VALUES (1,1,'IN',5,5,0,NOW())"))

    migrate.upgrade_to_head()

    assert _schema_diff(eng) == []
    with eng.connect() as c:
        assert c.execute(text("SELECT source FROM stock_movements")).scalar() == "MANUAL"
        assert c.execute(text("SELECT current_stock FROM products WHERE id=1")).scalar() == 5
        # single-shop data moved into one business (migration 0003)
        assert c.execute(text("SELECT name FROM businesses")).scalars().all() == ["My Business"]
        for table in ("users", "categories", "products", "stock_movements"):
            assert c.execute(text(f"SELECT COUNT(*) FROM {table} WHERE business_id IS NULL")).scalar() == 0
    assert "product_barcodes" in inspect(eng).get_table_names()


def test_fresh_install_creates_no_placeholder_business(eng):
    migrate.upgrade_to_head()
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM businesses")).scalar() == 0


def test_v1_1_database_with_barcodes_moves_into_one_business(eng):
    """A database at 0002 (barcodes, single shop) upgrades with barcodes kept and scoped."""
    with eng.begin() as c:
        command.upgrade(migrate._config(c), "0002")
        c.execute(text("INSERT INTO users (id,name,email,password_hash,role,is_active,created_at) "
                       "VALUES (1,'A','a@x.co','h','ADMIN',1,NOW())"))
        c.execute(text("INSERT INTO categories (id,name) VALUES (1,'C')"))
        c.execute(text("INSERT INTO products (id,sku,name,category_id,unit_price,reorder_threshold,"
                       "current_stock,archived,created_at,updated_at) VALUES (1,'S','P',1,10,1,5,0,NOW(),NOW())"))
        c.execute(text("INSERT INTO product_barcodes (product_id, code) VALUES (1, '6160000010011')"))
    migrate.upgrade_to_head()
    assert _schema_diff(eng) == []
    with eng.connect() as c:
        bid = c.execute(text("SELECT id FROM businesses")).scalar()
        assert c.execute(text("SELECT business_id FROM product_barcodes")).scalar() == bid
        assert c.execute(text("SELECT business_id FROM users")).scalar() == bid


def test_upgrade_is_idempotent(eng):
    migrate.upgrade_to_head()
    migrate.upgrade_to_head()
    assert _schema_diff(eng) == []


def test_reset_rebuilds_empty_schema(eng):
    migrate.upgrade_to_head()
    with eng.begin() as c:
        c.execute(text("INSERT INTO businesses (id, name, is_active, created_at) VALUES (1, 'B', 1, NOW())"))
        c.execute(text("INSERT INTO categories (business_id, name) VALUES (1, 'X')"))
    migrate.reset_database()
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM categories")).scalar() == 0
    assert _schema_diff(eng) == []
