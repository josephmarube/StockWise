"""Tests named after the SRS requirement they verify."""
import csv
import io

import jwt
import pytest

from app.models import StockMovement
from tests.conftest import ADMIN, STAFF


def move(client, h, pid, type_, qty, **extra):
    return client.post(
        "/api/stock/movements",
        headers=h,
        json={"product_id": pid, "type": type_, "quantity": qty, **extra},
    )


# ---------------- FR4 Authentication & access control ----------------
class TestFR4Auth:
    def test_fr4_1_login_issues_signed_jwt(self, client):
        r = client.post("/api/auth/login", json=ADMIN)
        assert r.status_code == 200
        body = r.json()
        claims = jwt.decode(body["access_token"], "test-secret-key-that-is-at-least-32-bytes", algorithms=["HS256"])
        assert claims["role"] == "ADMIN" and "exp" in claims
        assert body["user"]["email"] == ADMIN["email"]

    @pytest.mark.parametrize(
        "creds",
        [
            {"email": ADMIN["email"], "password": "wrong"},
            {"email": "nobody@shop.co.ke", "password": "whatever"},
        ],
    )
    def test_fr4_1_invalid_credentials_generic_error(self, client, creds):
        r = client.post("/api/auth/login", json=creds)
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid email or password"

    def test_login_is_case_insensitive_on_email(self, client):
        r = client.post("/api/auth/login", json={**ADMIN, "email": ADMIN["email"].upper()})
        assert r.status_code == 200

    def test_nfr1_protected_endpoints_require_jwt(self, client):
        for path in ["/api/products", "/api/dashboard", "/api/stock/movements", "/api/auth/me"]:
            assert client.get(path).status_code == 401
        assert client.get("/api/products", headers={"Authorization": "Bearer garbage"}).status_code == 401

    def test_nfr1_expired_token_rejected(self, client):
        import datetime as dt

        tok = jwt.encode(
            {"sub": "1", "role": "ADMIN", "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)},
            "test-secret-key-that-is-at-least-32-bytes",
            algorithm="HS256",
        )
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401

    def test_nfr1_passwords_stored_as_bcrypt(self, db):
        from app.models import User

        u = db.query(User).first()
        assert u.password_hash.startswith("$2b$") and ADMIN["password"] not in u.password_hash

    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("get", "/api/suppliers", None),
            ("post", "/api/suppliers", {"name": "X"}),
            ("get", "/api/users", None),
            ("post", "/api/users", {"name": "x", "email": "x@x.co", "password": "longenough"}),
            ("get", "/api/reports/stock", None),
            ("get", "/api/reports/stock.csv", None),
            ("get", "/api/reports/audit", None),
            ("post", "/api/products", {"sku": "A", "name": "a", "category_id": 1, "unit_price": 1, "reorder_threshold": 1}),
            ("post", "/api/categories", {"name": "New"}),
        ],
    )
    def test_fr4_2_nfr2_admin_only_enforced_at_api(self, client, staff_h, method, path, body):
        r = getattr(client, method)(path, headers=staff_h, **({"json": body} if body else {}))
        assert r.status_code == 403

    def test_fr4_2_staff_can_view_products_and_record_stock(self, client, staff_h, product):
        assert client.get("/api/products", headers=staff_h).status_code == 200
        assert move(client, staff_h, product["id"], "IN", 1).status_code == 201

    def test_demoted_admin_loses_access_immediately(self, client, admin_h):
        # create a second admin, log in as them, demote them, old token no longer admin
        client.post("/api/users", headers=admin_h, json={"name": "B", "email": "b@shop.co.ke", "password": "Password1", "role": "ADMIN"})
        bh = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"email": "b@shop.co.ke", "password": "Password1"}).json()["access_token"]}
        assert client.get("/api/users", headers=bh).status_code == 200
        uid = [u for u in client.get("/api/users", headers=admin_h).json() if u["email"] == "b@shop.co.ke"][0]["id"]
        client.patch(f"/api/users/{uid}", headers=admin_h, json={"role": "STAFF"})
        assert client.get("/api/users", headers=bh).status_code == 403

    def test_deactivated_user_cannot_use_token_or_login(self, client, admin_h, staff_h):
        sid = [u for u in client.get("/api/users", headers=admin_h).json() if u["role"] == "STAFF"][0]["id"]
        client.patch(f"/api/users/{sid}", headers=admin_h, json={"is_active": False})
        assert client.get("/api/products", headers=staff_h).status_code == 401
        assert client.post("/api/auth/login", json=STAFF).status_code == 401

    def test_last_admin_cannot_be_demoted(self, client, admin_h):
        me = client.get("/api/auth/me", headers=admin_h).json()
        r = client.patch(f"/api/users/{me['id']}", headers=admin_h, json={"role": "STAFF"})
        assert r.status_code == 409


# ---------------- FR1 Product management ----------------
class TestFR1Products:
    def test_fr1_1_create_product(self, product):
        assert product["sku"] == "BEV-001"
        assert product["current_stock"] == 20
        assert product["category"]["name"] == "Beverages"

    def test_fr1_1_duplicate_sku_rejected(self, client, admin_h, product):
        r = client.post(
            "/api/products",
            headers=admin_h,
            json={"sku": "Bev-001", "name": "Dup", "category_id": 1, "unit_price": 1, "reorder_threshold": 1},
        )
        assert r.status_code == 409

    @pytest.mark.parametrize(
        "patch",
        [
            {"sku": ""},
            {"sku": "has space"},
            {"name": ""},
            {"unit_price": -1},
            {"reorder_threshold": -2},
            {"initial_stock": -5},
            {"category_id": 999},
            {"unit_price": "abc"},
        ],
    )
    def test_fr1_1_invalid_fields_rejected(self, client, admin_h, patch):
        body = {"sku": "OK-1", "name": "Ok", "category_id": 1, "unit_price": "10", "reorder_threshold": 1, **patch}
        r = client.post("/api/products", headers=admin_h, json=body)
        assert r.status_code == 422, r.text

    def test_fr1_1_initial_stock_is_audited(self, client, admin_h, product):
        r = client.get(f"/api/stock/movements?product_id={product['id']}", headers=admin_h).json()
        assert r["total"] == 1 and r["items"][0]["note"] == "Initial stock"

    def test_fr1_2_edit_product(self, client, admin_h, product):
        r = client.patch(f"/api/products/{product['id']}", headers=admin_h, json={"name": "Water 1L", "reorder_threshold": 8})
        assert r.status_code == 200 and r.json()["name"] == "Water 1L" and r.json()["reorder_threshold"] == 8

    def test_fr1_2_stock_not_editable_directly(self, client, admin_h, product):
        client.patch(f"/api/products/{product['id']}", headers=admin_h, json={"current_stock": 999})
        assert client.get(f"/api/products/{product['id']}", headers=admin_h).json()["current_stock"] == 20

    def test_fr1_2_product_with_history_cannot_be_deleted(self, client, admin_h, product):
        r = client.delete(f"/api/products/{product['id']}", headers=admin_h)
        assert r.status_code == 409
        assert client.post(f"/api/products/{product['id']}/archive", headers=admin_h).json()["archived"] is True

    def test_fr1_2_product_without_history_can_be_deleted(self, client, admin_h):
        p = client.post("/api/products", headers=admin_h, json={"sku": "NEW", "name": "n", "category_id": 2, "unit_price": 1, "reorder_threshold": 0}).json()
        assert client.delete(f"/api/products/{p['id']}", headers=admin_h).status_code == 204

    def test_fr1_2_archive_keeps_history_and_hides_from_staff(self, client, admin_h, staff_h, product):
        client.post(f"/api/products/{product['id']}/archive", headers=admin_h)
        assert client.get("/api/products", headers=staff_h).json()["total"] == 0
        assert client.get(f"/api/products/{product['id']}", headers=staff_h).status_code == 404
        assert client.get(f"/api/stock/movements?product_id={product['id']}", headers=admin_h).json()["total"] == 1
        # archived products cannot take new movements until restored
        assert move(client, admin_h, product["id"], "IN", 1).status_code == 409
        client.post(f"/api/products/{product['id']}/restore", headers=admin_h)
        assert move(client, admin_h, product["id"], "IN", 1).status_code == 201

    def test_fr1_3_search_and_filter(self, client, admin_h, staff_h, product):
        client.post("/api/products", headers=admin_h, json={"sku": "HH-1", "name": "Bar Soap", "category_id": 2, "unit_price": 60, "reorder_threshold": 10, "initial_stock": 3})
        assert client.get("/api/products?q=soap", headers=staff_h).json()["total"] == 1
        assert client.get("/api/products?q=bev", headers=staff_h).json()["total"] == 1
        assert client.get("/api/products?category_id=2", headers=staff_h).json()["items"][0]["sku"] == "HH-1"
        low = client.get("/api/products?low_stock=true", headers=staff_h).json()
        assert [p["sku"] for p in low["items"]] == ["HH-1"]
        items = client.get("/api/products?sort=stock&order=desc", headers=staff_h).json()["items"]
        assert items[0]["current_stock"] >= items[-1]["current_stock"]


# ---------------- FR2 Stock management ----------------
class TestFR2Stock:
    def test_fr2_1_stock_in_increases(self, client, staff_h, product):
        r = move(client, staff_h, product["id"], "IN", 15)
        assert r.status_code == 201 and r.json()["current_stock"] == 35

    def test_fr2_2_stock_out_decreases(self, client, staff_h, product):
        r = move(client, staff_h, product["id"], "OUT", 5)
        assert r.status_code == 201 and r.json()["current_stock"] == 15

    def test_fr2_2_negative_stock_rejected_for_staff_even_with_override(self, client, staff_h, admin_h, product):
        r = move(client, staff_h, product["id"], "OUT", 21, override=True)
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "INSUFFICIENT_STOCK" and body["available"] == 20 and body["can_override"] is False
        assert client.get(f"/api/products/{product['id']}", headers=admin_h).json()["current_stock"] == 20

    def test_fr2_2_admin_without_override_rejected(self, client, admin_h, product):
        r = move(client, admin_h, product["id"], "OUT", 25)
        assert r.status_code == 409 and r.json()["can_override"] is True

    def test_fr2_2_admin_override_allows_negative_and_is_flagged(self, client, admin_h, product):
        r = move(client, admin_h, product["id"], "OUT", 25, override=True, note="Count correction")
        assert r.status_code == 201
        assert r.json()["current_stock"] == -5 and r.json()["movement"]["override"] is True

    def test_override_flag_ignored_when_not_needed(self, client, admin_h, product):
        r = move(client, admin_h, product["id"], "OUT", 1, override=True)
        assert r.json()["movement"]["override"] is False

    @pytest.mark.parametrize("qty", [0, -3, "x", 1.5])
    def test_nfr8_invalid_quantity_rejected(self, client, staff_h, product, qty):
        assert move(client, staff_h, product["id"], "IN", qty).status_code == 422

    def test_unknown_product_404(self, client, staff_h):
        assert move(client, staff_h, 9999, "IN", 1).status_code == 404

    def test_fr2_3_stock_level_visible_immediately(self, client, staff_h, product):
        move(client, staff_h, product["id"], "OUT", 4)
        assert client.get(f"/api/products/{product['id']}", headers=staff_h).json()["current_stock"] == 16

    def test_fr2_4_history_is_chronological(self, client, staff_h, product):
        for q in (1, 2, 3):
            move(client, staff_h, product["id"], "IN", q)
        items = client.get(f"/api/stock/movements?product_id={product['id']}", headers=staff_h).json()["items"]
        assert [m["quantity"] for m in items] == [3, 2, 1, 20]  # newest first
        assert [m["stock_after"] for m in items] == [26, 23, 21, 20]

    def test_failed_movement_rolls_back(self, client, admin_h, product, db, monkeypatch):
        from app.services import stock_service
        from sqlalchemy.exc import OperationalError

        orig = stock_service.StockMovement

        class Boom(orig):  # noqa
            def __init__(self, *a, **k):
                raise OperationalError("insert", {}, Exception("disk full"))

        monkeypatch.setattr(stock_service, "StockMovement", Boom)
        r = move(client, admin_h, product["id"], "IN", 5)
        assert r.status_code == 500
        monkeypatch.setattr(stock_service, "StockMovement", orig)
        assert client.get(f"/api/products/{product['id']}", headers=admin_h).json()["current_stock"] == 20


# ---------------- FR3 Suppliers ----------------
class TestFR3Suppliers:
    def _supplier(self, client, h, name="Kenya Distributors Ltd"):
        r = client.post("/api/suppliers", headers=h, json={"name": name, "phone": "+254700000000", "email": "sales@kd.co.ke"})
        assert r.status_code == 201, r.text
        return r.json()

    def test_fr3_1_create_and_edit(self, client, admin_h):
        s = self._supplier(client, admin_h)
        r = client.patch(f"/api/suppliers/{s['id']}", headers=admin_h, json={"contact_person": "Wanjiru"})
        assert r.json()["contact_person"] == "Wanjiru"

    def test_fr3_1_invalid_email_rejected(self, client, admin_h):
        assert client.post("/api/suppliers", headers=admin_h, json={"name": "X", "email": "not-an-email"}).status_code == 422

    def test_fr3_1_unlinked_supplier_deleted(self, client, admin_h):
        s = self._supplier(client, admin_h)
        r = client.delete(f"/api/suppliers/{s['id']}", headers=admin_h)
        assert r.json()["action"] == "deleted"
        assert client.get(f"/api/suppliers/{s['id']}", headers=admin_h).status_code == 404

    def test_fr3_1_linked_supplier_deactivated(self, client, admin_h, product):
        s = self._supplier(client, admin_h)
        client.put(f"/api/products/{product['id']}/suppliers", headers=admin_h, json={"supplier_ids": [s["id"]]})
        r = client.delete(f"/api/suppliers/{s['id']}", headers=admin_h)
        assert r.json()["action"] == "deactivated"
        assert client.get(f"/api/suppliers/{s['id']}", headers=admin_h).json()["is_active"] is False

    def test_fr3_2_link_multiple_suppliers(self, client, admin_h, product):
        a, b = self._supplier(client, admin_h, "A Ltd"), self._supplier(client, admin_h, "B Ltd")
        r = client.put(f"/api/products/{product['id']}/suppliers", headers=admin_h, json={"supplier_ids": [a["id"], b["id"]]})
        assert sorted(s["name"] for s in r.json()["suppliers"]) == ["A Ltd", "B Ltd"]
        assert client.get(f"/api/suppliers/{a['id']}", headers=admin_h).json()["product_count"] == 1

    def test_fr3_2_cannot_link_inactive_supplier(self, client, admin_h, product):
        s = self._supplier(client, admin_h)
        client.post(f"/api/suppliers/{s['id']}/deactivate", headers=admin_h)
        r = client.put(f"/api/products/{product['id']}/suppliers", headers=admin_h, json={"supplier_ids": [s["id"]]})
        assert r.status_code == 422


# ---------------- FR5 Low stock ----------------
class TestFR5LowStock:
    def test_fr5_1_flag_at_threshold(self, client, staff_h, product):
        r = move(client, staff_h, product["id"], "OUT", 14)  # 6 > 5
        assert r.json()["low_stock"] is False
        r = move(client, staff_h, product["id"], "OUT", 1)  # 5 <= 5
        assert r.json()["low_stock"] is True
        dash = client.get("/api/dashboard", headers=staff_h).json()
        assert dash["low_stock_count"] == 1 and dash["low_stock"][0]["sku"] == "BEV-001"

    def test_fr5_1_raising_threshold_flags_product(self, client, admin_h, product):
        client.patch(f"/api/products/{product['id']}", headers=admin_h, json={"reorder_threshold": 25})
        assert client.get("/api/dashboard", headers=admin_h).json()["low_stock_count"] == 1

    def test_dashboard_totals(self, client, admin_h, product):
        d = client.get("/api/dashboard", headers=admin_h).json()
        assert d["active_products"] == 1 and d["total_units"] == 20 and d["stock_value"] == "900.00"
        assert len(d["recent_movements"]) == 1


# ---------------- FR6 Reports, FR7 Audit ----------------
class TestFR6FR7Reports:
    def test_fr6_1_stock_report(self, client, admin_h, staff_h, product):
        move(client, staff_h, product["id"], "OUT", 7)
        r = client.get("/api/reports/stock", headers=admin_h)
        assert r.status_code == 200
        row = r.json()["rows"][0]
        assert (row["qty_in"], row["qty_out"], row["current_stock"]) == (20, 7, 13)
        assert r.json()["totals"]["movements"] == 2

    def test_fr6_1_date_range_excludes_outside(self, client, admin_h, product):
        r = client.get("/api/reports/stock?start=2020-01-01&end=2020-01-31", headers=admin_h).json()
        assert r["rows"][0]["movement_count"] == 0 and r["movements"] == []

    def test_fr6_1_invalid_range(self, client, admin_h):
        assert client.get("/api/reports/stock?start=2026-02-01&end=2026-01-01", headers=admin_h).status_code == 422

    def test_fr6_2_csv_export(self, client, admin_h, product):
        r = client.get("/api/reports/stock.csv", headers=admin_h)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers["content-disposition"]
        rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
        assert rows[0][0] == "SKU" and rows[1][0] == "BEV-001"

    def test_fr6_2_csv_formula_injection_neutralised(self, client, admin_h):
        client.post("/api/products", headers=admin_h, json={"sku": "X1", "name": "=HYPERLINK(\"evil\")", "category_id": 1, "unit_price": 1, "reorder_threshold": 0, "initial_stock": 1})
        r = client.get("/api/reports/stock.csv", headers=admin_h)
        assert "'=HYPERLINK" in r.text

    def test_fr7_1_audit_records_user_and_timestamp(self, client, admin_h, staff_h, product):
        move(client, staff_h, product["id"], "OUT", 2, note="Sold")
        log = client.get("/api/reports/audit", headers=admin_h).json()
        latest = log["items"][0]
        assert latest["user"]["name"] == "Sam Staff" and latest["type"] == "OUT"
        assert latest["created_at"].endswith("+00:00")

    def test_fr7_1_audit_filter_and_csv(self, client, admin_h, staff_h, product):
        move(client, staff_h, product["id"], "OUT", 2)
        staff_id = [u for u in client.get("/api/users", headers=admin_h).json() if u["role"] == "STAFF"][0]["id"]
        assert client.get(f"/api/reports/audit?user_id={staff_id}", headers=admin_h).json()["total"] == 1
        r = client.get("/api/reports/movements.csv", headers=admin_h)
        lines = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
        assert lines[0][0] == "Timestamp (local)" and len(lines) == 3

    def test_nfr5_every_movement_has_user_and_time(self, client, admin_h, staff_h, product, db):
        move(client, staff_h, product["id"], "IN", 3)
        move(client, admin_h, product["id"], "OUT", 30, override=True)
        for m in db.query(StockMovement).all():
            assert m.user_id and m.created_at


def test_validation_errors_are_readable(client, admin_h):
    r = client.post("/api/products", headers=admin_h, json={"sku": "", "name": "a"})
    body = r.json()
    assert r.status_code == 422 and "fields" in body and "sku" in body["fields"]


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
