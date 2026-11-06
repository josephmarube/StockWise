"""Multi-business isolation: one business can never see or change another's data.

Every test uses two real businesses: "Test Shop" (admin_h/staff_h, owns `product`)
and "Other Shop" (other_h). Other Shop's admin tries to reach Test Shop's data by ID,
by search, by barcode and through reports. Each attempt must behave as if the data
did not exist.
"""
import pytest

from tests.conftest import OTHER_CATEGORY_ID


def move(client, h, pid, type_="IN", qty=1, **extra):
    return client.post("/api/stock/movements", headers=h, json={"product_id": pid, "type": type_, "quantity": qty, **extra})


@pytest.fixture()
def supplier(client, admin_h):
    return client.post("/api/suppliers", headers=admin_h, json={"name": "Shop Supplier Ltd"}).json()


@pytest.fixture()
def barcoded(client, admin_h):
    return client.post("/api/products", headers=admin_h, json={
        "sku": "SCAN-1", "name": "Scannable", "category_id": 1, "unit_price": 10,
        "reorder_threshold": 1, "initial_stock": 5, "barcodes": ["6160000010011"],
    }).json()


class TestCannotSeeOtherBusiness:
    def test_product_list_and_search(self, client, other_h, product):
        assert client.get("/api/products", headers=other_h).json()["total"] == 0
        assert client.get("/api/products?q=Mineral", headers=other_h).json()["total"] == 0
        assert client.get("/api/products?include_archived=true", headers=other_h).json()["total"] == 0

    def test_product_by_id(self, client, other_h, product):
        assert client.get(f"/api/products/{product['id']}", headers=other_h).status_code == 404

    def test_barcode_lookup_and_search(self, client, other_h, barcoded):
        assert client.get("/api/products/by-barcode/6160000010011", headers=other_h).status_code == 404
        assert client.get("/api/products?q=6160000010011", headers=other_h).json()["total"] == 0

    def test_categories(self, client, admin_h, other_h):
        mine = {c["id"] for c in client.get("/api/categories", headers=admin_h).json()}
        theirs = {c["id"] for c in client.get("/api/categories", headers=other_h).json()}
        assert mine == {1, 2} and theirs == {OTHER_CATEGORY_ID}

    def test_suppliers(self, client, other_h, supplier):
        assert client.get("/api/suppliers", headers=other_h).json() == []
        assert client.get(f"/api/suppliers/{supplier['id']}", headers=other_h).status_code == 404

    def test_users(self, client, other_h):
        emails = [u["email"] for u in client.get("/api/users", headers=other_h).json()]
        assert emails == ["boss@othershop.co.ke"]

    def test_stock_history(self, client, other_h, product):
        assert client.get("/api/stock/movements", headers=other_h).json()["total"] == 0
        assert client.get(f"/api/stock/movements?product_id={product['id']}", headers=other_h).json()["total"] == 0

    def test_dashboard(self, client, other_h, product):
        d = client.get("/api/dashboard", headers=other_h).json()
        assert d["active_products"] == 0 and d["total_units"] == 0 and d["recent_movements"] == [] and d["low_stock"] == []

    def test_reports_audit_and_csv(self, client, other_h, admin_h, product):
        assert client.get("/api/reports/stock", headers=other_h).json()["rows"] == []
        assert client.get("/api/reports/audit", headers=other_h).json()["total"] == 0
        assert "BEV-001" not in client.get("/api/reports/stock.csv", headers=other_h).text
        assert "Mineral" not in client.get("/api/reports/movements.csv", headers=other_h).text
        # filtering by the other business's user id must not reveal anything either
        staff_id = [u for u in client.get("/api/users", headers=admin_h).json() if u["role"] == "STAFF"][0]["id"]
        assert client.get(f"/api/reports/audit?user_id={staff_id}", headers=other_h).json()["total"] == 0


class TestCannotChangeOtherBusiness:
    def test_edit_archive_restore_delete_product(self, client, other_h, admin_h, product):
        pid = product["id"]
        assert client.patch(f"/api/products/{pid}", headers=other_h, json={"name": "Hacked"}).status_code == 404
        assert client.post(f"/api/products/{pid}/archive", headers=other_h).status_code == 404
        assert client.post(f"/api/products/{pid}/restore", headers=other_h).status_code == 404
        assert client.delete(f"/api/products/{pid}", headers=other_h).status_code == 404
        p = client.get(f"/api/products/{pid}", headers=admin_h).json()
        assert p["name"] == "Mineral Water 500ml" and p["archived"] is False

    def test_record_stock_on_other_business_product(self, client, other_h, admin_h, product):
        assert move(client, other_h, product["id"], "OUT", 5).status_code == 404
        assert client.get(f"/api/products/{product['id']}", headers=admin_h).json()["current_stock"] == 20

    def test_create_product_in_other_business_category(self, client, other_h):
        r = client.post("/api/products", headers=other_h, json={
            "sku": "X1", "name": "x", "category_id": 1, "unit_price": 1, "reorder_threshold": 0})
        assert r.status_code == 422  # category 1 belongs to Test Shop

    def test_link_other_business_supplier(self, client, other_h, supplier):
        mine = client.post("/api/products", headers=other_h, json={
            "sku": "MINE", "name": "Mine", "category_id": OTHER_CATEGORY_ID, "unit_price": 1, "reorder_threshold": 0}).json()
        r = client.put(f"/api/products/{mine['id']}/suppliers", headers=other_h, json={"supplier_ids": [supplier["id"]]})
        assert r.status_code == 422
        r = client.post("/api/products", headers=other_h, json={
            "sku": "MINE2", "name": "x", "category_id": OTHER_CATEGORY_ID, "unit_price": 1,
            "reorder_threshold": 0, "supplier_ids": [supplier["id"]]})
        assert r.status_code == 422

    def test_link_suppliers_to_other_business_product(self, client, other_h, product):
        r = client.put(f"/api/products/{product['id']}/suppliers", headers=other_h, json={"supplier_ids": []})
        assert r.status_code == 404

    def test_edit_or_delete_other_business_supplier(self, client, other_h, admin_h, supplier):
        sid = supplier["id"]
        assert client.patch(f"/api/suppliers/{sid}", headers=other_h, json={"name": "Hacked"}).status_code == 404
        assert client.post(f"/api/suppliers/{sid}/deactivate", headers=other_h).status_code == 404
        assert client.delete(f"/api/suppliers/{sid}", headers=other_h).status_code == 404
        assert client.get(f"/api/suppliers/{sid}", headers=admin_h).json()["name"] == "Shop Supplier Ltd"

    def test_edit_or_disable_other_business_user(self, client, other_h, admin_h):
        staff = [u for u in client.get("/api/users", headers=admin_h).json() if u["role"] == "STAFF"][0]
        for body in ({"is_active": False}, {"role": "ADMIN"}, {"password": "takeover123"}):
            assert client.patch(f"/api/users/{staff['id']}", headers=other_h, json=body).status_code == 404
        assert client.post("/api/auth/login", json={"email": "staff@shop.co.ke", "password": "StaffPass123"}).status_code == 200


class TestPerBusinessUniqueness:
    def test_same_sku_category_and_barcode_allowed_in_different_businesses(self, client, other_h, barcoded, product):
        r = client.post("/api/products", headers=other_h, json={
            "sku": "BEV-001", "name": "Their water", "category_id": OTHER_CATEGORY_ID, "unit_price": 50,
            "reorder_threshold": 1, "barcodes": ["6160000010011"]})
        assert r.status_code == 201, r.text
        assert client.post("/api/categories", headers=other_h, json={"name": "Household"}).status_code == 201
        # each business's scan resolves to its own product
        assert client.get("/api/products/by-barcode/6160000010011", headers=other_h).json()["name"] == "Their water"

    def test_still_unique_within_a_business(self, client, admin_h, barcoded, product):
        dup = {"sku": "BEV-001", "name": "d", "category_id": 1, "unit_price": 1, "reorder_threshold": 0}
        assert client.post("/api/products", headers=admin_h, json=dup).status_code == 409
        dup2 = {**dup, "sku": "NEW", "barcodes": ["6160000010011"]}
        assert client.post("/api/products", headers=admin_h, json=dup2).status_code == 409
        assert client.post("/api/categories", headers=admin_h, json={"name": "beverages"}).status_code == 409

    def test_last_admin_rule_is_per_business(self, client, other_h):
        me = client.get("/api/auth/me", headers=other_h).json()
        assert client.patch(f"/api/users/{me['id']}", headers=other_h, json={"role": "STAFF"}).status_code == 409


class TestWritesLandInOwnBusiness:
    def test_new_rows_belong_to_creator_business(self, client, other_h, admin_h):
        client.post("/api/suppliers", headers=other_h, json={"name": "Their Supplier"})
        client.post("/api/users", headers=other_h, json={"name": "New", "email": "new@othershop.co.ke", "password": "Password1"})
        p = client.post("/api/products", headers=other_h, json={
            "sku": "T1", "name": "Theirs", "category_id": OTHER_CATEGORY_ID, "unit_price": 1,
            "reorder_threshold": 0, "initial_stock": 3}).json()
        assert move(client, other_h, p["id"], "OUT", 1).status_code == 201
        assert [s["name"] for s in client.get("/api/suppliers", headers=admin_h).json()] == []
        assert "new@othershop.co.ke" not in [u["email"] for u in client.get("/api/users", headers=admin_h).json()]
        assert client.get("/api/stock/movements", headers=admin_h).json()["total"] == 0
        assert client.get("/api/stock/movements", headers=other_h).json()["total"] == 2

    def test_me_shows_business(self, client, admin_h, other_h):
        assert client.get("/api/auth/me", headers=admin_h).json()["business"]["name"] == "Test Shop"
        assert client.get("/api/auth/me", headers=other_h).json()["business"]["name"] == "Other Shop"


def test_deactivated_business_locks_out_its_users(client, other_h, admin_h, db):
    from app.models import Business

    b = db.query(Business).filter_by(name="Other Shop").one()
    b.is_active = False
    db.commit()
    assert client.get("/api/products", headers=other_h).status_code == 401
    assert client.post("/api/auth/login", json={"email": "boss@othershop.co.ke", "password": "OtherPass123"}).status_code == 401
    assert client.get("/api/products", headers=admin_h).status_code == 200
