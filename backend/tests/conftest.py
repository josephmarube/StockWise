# ruff: noqa: E402  -- environment must be set before the app is imported
import os
import secrets

# Must be set before the app (and its engine) is imported.
# Secrets and passwords are generated per run, so none are written in the repository.
TEST_JWT_SECRET = secrets.token_urlsafe(48)
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ.pop("BOOTSTRAP_ADMIN_EMAIL", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base, get_db
from app.main import app
from app import ratelimit
from app.models import Business, Category, Role, User
from app.security import hash_password

def new_password() -> str:
    """A random, valid password for test accounts."""
    return secrets.token_urlsafe(12)


ADMIN = {"email": "admin@shop.co.ke", "password": new_password()}
STAFF = {"email": "staff@shop.co.ke", "password": new_password()}
# A second, unrelated business used to prove isolation.
OTHER_ADMIN = {"email": "boss@othershop.co.ke", "password": new_password()}
OTHER_CATEGORY_ID = 3  # "Beverages" in the other business (same name is allowed per business)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")  # a MySQL URL for an empty test database (see README)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture()
def engine():
    if TEST_DATABASE_URL:
        eng = create_engine(TEST_DATABASE_URL, pool_size=20, max_overflow=0)
        Base.metadata.drop_all(eng)
    else:
        eng = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(eng)
    yield eng
    if TEST_DATABASE_URL:
        Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = Session()
    shop = Business(name="Test Shop")
    other = Business(name="Other Shop")
    s.add_all([shop, other])
    s.flush()
    s.add_all(
        [
            User(business_id=shop.id, name="Amina Admin", email=ADMIN["email"], password_hash=hash_password(ADMIN["password"]), role=Role.ADMIN),
            User(business_id=shop.id, name="Sam Staff", email=STAFF["email"], password_hash=hash_password(STAFF["password"]), role=Role.STAFF),
            User(business_id=other.id, name="Olive Other", email=OTHER_ADMIN["email"], password_hash=hash_password(OTHER_ADMIN["password"]), role=Role.ADMIN),
        ]
    )
    s.add_all([Category(business_id=shop.id, name="Beverages"), Category(business_id=shop.id, name="Household")])
    s.flush()
    s.add(Category(business_id=other.id, name="Beverages"))
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def client(engine, db, monkeypatch):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "engine", engine)
    monkeypatch.setattr(main_mod, "SessionLocal", Session)
    # Tables come from create_all above; migrations are tested in test_migrations.py.
    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client, creds) -> dict:
    r = client.post("/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin_h(client):
    return _login(client, ADMIN)


@pytest.fixture()
def staff_h(client):
    return _login(client, STAFF)


@pytest.fixture()
def other_h(client):
    """Admin of the other business."""
    return _login(client, OTHER_ADMIN)


@pytest.fixture()
def product(client, admin_h):
    """A product with 20 units and reorder threshold 5."""
    r = client.post(
        "/api/products",
        headers=admin_h,
        json={
            "sku": "bev-001",
            "name": "Mineral Water 500ml",
            "category_id": 1,
            "unit_price": "45.00",
            "reorder_threshold": 5,
            "initial_stock": 20,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
