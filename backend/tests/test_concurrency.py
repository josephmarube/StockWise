"""Row-lock behaviour (SELECT ... FOR UPDATE) and NFR3 concurrency.

Requires a real MySQL database; skipped on SQLite:
    TEST_DATABASE_URL=mysql+pymysql://stockwise:stockwise@127.0.0.1/stockwise_test pytest
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import MovementType, User
from app.services.stock_service import InsufficientStock, record_movement
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not (TEST_DATABASE_URL or "").startswith("mysql"), reason="needs MySQL (TEST_DATABASE_URL)"
)


def test_simultaneous_stock_outs_never_oversell(engine, client, admin_h, product, db):
    """20 units, 12 concurrent requests for 3 units each: exactly 6 succeed, stock ends at 2."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    staff_id = db.query(User).filter_by(role="STAFF").one().id

    def attempt(_):
        with Session() as s:
            user = s.get(User, staff_id)
            try:
                record_movement(s, user=user, product_id=product["id"], type_=MovementType.OUT, quantity=3)
                return "ok"
            except InsufficientStock:
                return "rejected"

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(12)))

    assert results.count("ok") == 6 and results.count("rejected") == 6
    final = client.get(f"/api/products/{product['id']}", headers=admin_h).json()
    assert final["current_stock"] == 2
    hist = client.get(f"/api/stock/movements?product_id={product['id']}&limit=100", headers=admin_h).json()
    assert hist["total"] == 7  # initial + 6 successful outs
    assert sorted(m["stock_after"] for m in hist["items"] if m["type"] == "OUT") == [2, 5, 8, 11, 14, 17]
