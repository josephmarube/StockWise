"""FR1.4 product barcodes, FR2.5 scan-to-record, FR7.2 movement source."""
import csv
import io

import pytest


def new_product(client, h, sku="SNK-001", barcodes=None, **extra):
    body = {
        "sku": sku, "name": f"Product {sku}", "category_id": 1, "unit_price": "50",
        "reorder_threshold": 2, "initial_stock": 10, "barcodes": barcodes or [], **extra,
    }
    return client.post("/api/products", headers=h, json=body)


class TestFR1_4Barcodes:
    def test_create_with_barcodes(self, client, admin_h):
        r = new_product(client, admin_h, barcodes=["6161234567893", " 12345678 ", "6161234567893"])
        assert r.status_code == 201, r.text
        assert r.json()["barcodes"] == ["6161234567893", "12345678"]  # trimmed, de-duplicated

    def test_barcode_unique_across_products(self, client, admin_h):
        new_product(client, admin_h, "A1", barcodes=["111222333"])
        r = new_product(client, admin_h, "A2", barcodes=["111222333"])
        assert r.status_code == 409
        assert "already used by Product A1" in r.json()["detail"]

    @pytest.mark.parametrize("bad", ["12", "has space", "x" * 65, "café123"])
    def test_invalid_barcode_rejected(self, client, admin_h, bad):
        assert new_product(client, admin_h, barcodes=[bad]).status_code == 422

    def test_edit_replaces_barcodes_and_keeps_own(self, client, admin_h):
        p = new_product(client, admin_h, barcodes=["AAA111", "BBB222"]).json()
        r = client.patch(f"/api/products/{p['id']}", headers=admin_h, json={"barcodes": ["BBB222", "CCC333"]})
        assert r.status_code == 200 and r.json()["barcodes"] == ["BBB222", "CCC333"]
        # Freed barcode can now be used by another product
        assert new_product(client, admin_h, "OTHER", barcodes=["AAA111"]).status_code == 201

    def test_edit_cannot_steal_another_products_barcode(self, client, admin_h):
        new_product(client, admin_h, "A1", barcodes=["TAKEN1"])
        p2 = new_product(client, admin_h, "A2").json()
        r = client.patch(f"/api/products/{p2['id']}", headers=admin_h, json={"barcodes": ["TAKEN1"]})
        assert r.status_code == 409

    def test_edit_without_barcodes_field_leaves_them(self, client, admin_h):
        p = new_product(client, admin_h, barcodes=["KEEP123"]).json()
        r = client.patch(f"/api/products/{p['id']}", headers=admin_h, json={"name": "Renamed"})
        assert r.json()["barcodes"] == ["KEEP123"]

    def test_search_matches_exact_barcode(self, client, admin_h, staff_h):
        new_product(client, admin_h, "A1", barcodes=["6160000010011"])
        new_product(client, admin_h, "A2", barcodes=["6160000010028"])
        r = client.get("/api/products?q=6160000010011", headers=staff_h).json()
        assert [p["sku"] for p in r["items"]] == ["A1"]

    def test_staff_cannot_set_barcodes(self, client, admin_h, staff_h):
        p = new_product(client, admin_h).json()
        r = client.patch(f"/api/products/{p['id']}", headers=staff_h, json={"barcodes": ["X12345"]})
        assert r.status_code == 403


class TestFR2_5ScanLookup:
    def test_lookup_by_barcode(self, client, admin_h, staff_h):
        p = new_product(client, admin_h, barcodes=["6160000010011"]).json()
        r = client.get("/api/products/by-barcode/6160000010011", headers=staff_h)
        assert r.status_code == 200 and r.json()["id"] == p["id"]

    def test_unknown_barcode_404_with_message(self, client, staff_h):
        r = client.get("/api/products/by-barcode/0000000000", headers=staff_h)
        assert r.status_code == 404 and "No product has barcode 0000000000" in r.json()["detail"]

    def test_archived_product_hidden_from_staff_scan(self, client, admin_h, staff_h):
        p = new_product(client, admin_h, barcodes=["ARCH01"]).json()
        client.post(f"/api/products/{p['id']}/archive", headers=admin_h)
        assert client.get("/api/products/by-barcode/ARCH01", headers=staff_h).status_code == 404
        assert client.get("/api/products/by-barcode/ARCH01", headers=admin_h).json()["archived"] is True

    def test_lookup_requires_login(self, client):
        assert client.get("/api/products/by-barcode/123456").status_code == 401


class TestFR7_2MovementSource:
    def test_default_source_is_manual(self, client, staff_h, product):
        r = client.post("/api/stock/movements", headers=staff_h,
                        json={"product_id": product["id"], "type": "IN", "quantity": 1})
        assert r.json()["movement"]["source"] == "MANUAL"

    @pytest.mark.parametrize("src", ["SCANNER", "CAMERA"])
    def test_source_recorded(self, client, staff_h, product, src):
        r = client.post("/api/stock/movements", headers=staff_h,
                        json={"product_id": product["id"], "type": "OUT", "quantity": 1, "source": src})
        assert r.status_code == 201 and r.json()["movement"]["source"] == src

    def test_invalid_source_rejected(self, client, staff_h, product):
        r = client.post("/api/stock/movements", headers=staff_h,
                        json={"product_id": product["id"], "type": "IN", "quantity": 1, "source": "TELEPATHY"})
        assert r.status_code == 422

    def test_same_rules_apply_to_every_source(self, client, staff_h, product):
        """One core: a scanned stock-out obeys the same negative-stock rule (FR2.2)."""
        r = client.post("/api/stock/movements", headers=staff_h,
                        json={"product_id": product["id"], "type": "OUT", "quantity": 999, "source": "CAMERA"})
        assert r.status_code == 409

    def test_filter_history_audit_and_csv_by_source(self, client, admin_h, staff_h, product):
        for src in ("SCANNER", "SCANNER", "CAMERA"):
            client.post("/api/stock/movements", headers=staff_h,
                        json={"product_id": product["id"], "type": "IN", "quantity": 1, "source": src})
        assert client.get("/api/stock/movements?source=SCANNER", headers=staff_h).json()["total"] == 2
        assert client.get("/api/reports/audit?source=CAMERA", headers=admin_h).json()["total"] == 1
        assert client.get("/api/reports/audit?source=MANUAL", headers=admin_h).json()["total"] == 1  # initial stock
        r = client.get("/api/reports/movements.csv", headers=admin_h)
        rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
        assert rows[0][5] == "Source"
        assert sorted(row[5] for row in rows[1:]) == ["Camera", "Manual", "Scanner", "Scanner"]
