"""FR1.5 Units of measure: products sold by piece, weight, volume or length (SI units).

Loose (kadogo) sales such as 0.25 kg of sugar or 1.5 m of cable can be recorded;
products counted in pieces still take whole numbers only.
"""
import csv
import io


def make(client, h, **over):
    body = {"sku": "gro-loose", "name": "Sugar (loose)", "category_id": 1, "unit_price": "170.00",
            "unit": "KG", "reorder_threshold": "2.5", "initial_stock": "10", **over}
    r = client.post("/api/products", headers=h, json=body)
    return r


def move(client, h, pid, type_, qty, **extra):
    return client.post("/api/stock/movements", headers=h,
                       json={"product_id": pid, "type": type_, "quantity": qty, **extra})


class TestFR1_5Units:
    def test_existing_products_default_to_pieces(self, client, admin_h, product):
        assert client.get(f"/api/products/{product['id']}", headers=admin_h).json()["unit"] == "PIECE"

    def test_create_product_sold_by_kg(self, client, admin_h):
        r = make(client, admin_h)
        assert r.status_code == 201, r.text
        p = r.json()
        assert (p["unit"], p["current_stock"], p["reorder_threshold"]) == ("KG", 10, 2.5)

    def test_kadogo_sale_in_decimals(self, client, staff_h, admin_h):
        p = make(client, admin_h).json()
        r = move(client, staff_h, p["id"], "OUT", "0.25")
        assert r.status_code == 201, r.text
        assert r.json()["current_stock"] == 9.75
        assert r.json()["movement"]["quantity"] == 0.25
        assert move(client, staff_h, p["id"], "OUT", 1.5).json()["current_stock"] == 8.25

    def test_low_stock_with_decimals(self, client, staff_h, admin_h):
        p = make(client, admin_h).json()
        move(client, staff_h, p["id"], "OUT", "7.5")  # 2.5 left = reorder level
        assert client.get(f"/api/products/{p['id']}", headers=admin_h).json()["low_stock"] is True

    def test_pieces_must_be_whole_numbers(self, client, staff_h, product):
        r = move(client, staff_h, product["id"], "OUT", "0.5")
        assert r.status_code == 422 and "whole number" in r.json()["detail"]
        assert client.get(f"/api/products/{product['id']}", headers=staff_h).json()["current_stock"] == 20

    def test_piece_product_rejects_decimal_setup(self, client, admin_h):
        r = make(client, admin_h, sku="pc-1", unit="PIECE", reorder_threshold="1.5", initial_stock="3")
        assert r.status_code == 422 and "whole number" in r.json()["detail"]

    def test_at_most_three_decimals(self, client, staff_h, admin_h):
        p = make(client, admin_h).json()
        assert move(client, staff_h, p["id"], "OUT", "0.1234").status_code == 422

    def test_unknown_unit_rejected(self, client, admin_h):
        assert make(client, admin_h, unit="BAG").status_code == 422

    def test_switch_to_pieces_needs_whole_stock(self, client, admin_h, staff_h):
        p = make(client, admin_h).json()
        move(client, staff_h, p["id"], "OUT", "0.5")  # 9.5 kg left
        r = client.patch(f"/api/products/{p['id']}", headers=admin_h, json={"unit": "PIECE"})
        assert r.status_code == 422
        assert client.patch(f"/api/products/{p['id']}", headers=admin_h, json={"unit": "G"}).status_code == 200

    def test_not_enough_stock_message_has_unit(self, client, staff_h, admin_h):
        p = make(client, admin_h).json()
        r = move(client, staff_h, p["id"], "OUT", "12.5")
        assert r.status_code == 409
        body = r.json()
        assert body["available"] == 10 and body["requested"] == 12.5
        assert "10 kg available" in body["detail"] and "12.5 kg requested" in body["detail"]

    def test_unit_change_is_logged(self, client, admin_h):
        p = make(client, admin_h).json()
        client.patch(f"/api/products/{p['id']}", headers=admin_h, json={"unit": "G", "reorder_threshold": 2500})
        e = client.get("/api/activity", headers=admin_h, params={"entity_type": "product"}).json()["items"][0]
        assert e["changes"]["unit"] == ["KG", "G"] and e["changes"]["reorder_threshold"] == ["2.5", "2500"]

    def test_reports_and_csv_show_units(self, client, admin_h, staff_h):
        p = make(client, admin_h).json()
        move(client, staff_h, p["id"], "OUT", "0.75")
        row = next(r for r in client.get("/api/reports/stock", headers=admin_h).json()["rows"] if r["product_id"] == p["id"])
        assert (row["unit"], row["qty_out"], row["current_stock"]) == ("KG", 0.75, 9.25)
        stock = list(csv.reader(io.StringIO(client.get("/api/reports/stock.csv", headers=admin_h).text.lstrip("﻿"))))
        hdr = stock[0]
        line = next(r for r in stock if r[0] == "GRO-LOOSE")
        assert line[hdr.index("Unit")] == "kg" and line[hdr.index("Current stock")] == "9.25"
        moves = list(csv.reader(io.StringIO(client.get("/api/reports/movements.csv", headers=admin_h).text.lstrip("﻿"))))
        out = next(r for r in moves if r[2] == "GRO-LOOSE" and r[4] == "OUT")
        assert out[moves[0].index("Quantity")] == "0.75" and out[moves[0].index("Unit")] == "kg"
