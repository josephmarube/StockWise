import os

# Must be set before the app (and its engine) is imported.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-at-least-32-bytes"
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
from app.models import Category, Role, User
from app.security import hash_password

ADMIN = {"email": "admin@shop.co.ke", "password": "AdminPass123"}
STAFF = {"email": "staff@shop.co.ke", "password": "StaffPass123"}


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")  # e.g. mysql+pymysql://u:p@127.0.0.1/stockwise_test


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
    s.add_all(
        [
            User(name="Amina Admin", email=ADMIN["email"], password_hash=hash_password(ADMIN["password"]), role=Role.ADMIN),
            User(name="Sam Staff", email=STAFF["email"], password_hash=hash_password(STAFF["password"]), role=Role.STAFF),
            Category(name="Beverages"),
            Category(name="Household"),
        ]
    )
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
