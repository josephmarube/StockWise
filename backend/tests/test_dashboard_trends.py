"""Dashboard trends: daily value in/out, fastest movers and stock value by category.

Totals are in Ksh (quantity x selling price) because products use different units."""
from datetime import date


def move(client, h, pid, type_, qty):
    r = client.post("/api/stock/movements", headers=h, json={"product_id": pid, "type": type_, "quantity": qty})
    assert r.status_code == 201, r.text


def trends(client, h, days=14):
    r = client.get(f"/api/dashboard/trends?days={days}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


class TestDashboardTrends:
    def test_one_entry_per_day_ending_today(self, client, admin_h):
        t = trends(client, admin_h, days=7)
        dates = [date.fromisoformat(d["date"]) for d in t["days"]]
        assert len(dates) == 7
        assert all((b - a).days == 1 for a, b in zip(dates, dates[1:]))

    def test_todays_movements_counted(self, client, admin_h, staff_h, product):
        move(client, staff_h, product["id"], "OUT", 3)
        move(client, admin_h, product["id"], "IN", 10)
        today = trends(client, admin_h)["days"][-1]
        # opening stock of 20 is also today's stock in; price is 45.00
        assert (today["value_in"], today["value_out"]) == (30 * 45, 3 * 45)

    def test_top_movers_ranked_by_value_sold(self, client, admin_h, product):
        other = client.post("/api/products", headers=admin_h, json={
            "sku": "gro-001", "name": "Sugar 1kg", "category_id": 1, "unit_price": "175.00",
            "reorder_threshold": 5, "initial_stock": 30,
        }).json()
        move(client, admin_h, product["id"], "OUT", 10)  # 10 x 45 = 450
        move(client, admin_h, other["id"], "OUT", 3)     # 3 x 175 = 525, fewer units but more money
        movers = trends(client, admin_h)["top_movers"]
        assert [m["sku"] for m in movers] == ["GRO-001", "BEV-001"]
        assert (movers[0]["qty_out"], movers[0]["value_out"], movers[0]["unit"]) == (3, 525, "PIECE")

    def test_stock_value_by_category_admin_only(self, client, admin_h, staff_h, product):
        cats = trends(client, admin_h)["by_category"]
        assert len(cats) == 1 and cats[0]["value"] == "900.00" and cats[0]["products"] == 1
        assert trends(client, staff_h)["by_category"] == []

    def test_days_must_be_between_7_and_90(self, client, admin_h):
        for bad in (6, 91):
            assert client.get(f"/api/dashboard/trends?days={bad}", headers=admin_h).status_code == 422

    def test_requires_login(self, client):
        assert client.get("/api/dashboard/trends").status_code == 401

    def test_other_business_sees_nothing(self, client, admin_h, other_h, product):
        move(client, admin_h, product["id"], "OUT", 4)
        t = trends(client, other_h)
        assert sum(d["value_in"] + d["value_out"] for d in t["days"]) == 0
        assert t["top_movers"] == [] and t["by_category"] == []
