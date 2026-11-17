"""Roles (System Admin / Manager / Staff), platform oversight and the activity log."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import select

from app.models import ActivityLog, Role, User
from tests.conftest import SYSTEM_ADMIN, new_password

PW = new_password()


def other_business_id(client, other_h):
    return client.get("/api/business", headers=other_h).json()["id"]


def activity(client, h, **params):
    r = client.get("/api/activity", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


class TestSystemAdminAccount:
    def test_logs_in_without_a_business(self, client):
        r = client.post("/api/auth/login", json=SYSTEM_ADMIN)
        assert r.status_code == 200
        me = r.json()["user"]
        assert me["role"] == "SYSTEM_ADMIN" and me["business"] is None

    def test_me_works(self, client, sys_h):
        me = client.get("/api/auth/me", headers=sys_h).json()
        assert me["role"] == "SYSTEM_ADMIN" and me["business"] is None

    def test_cannot_open_any_shop_data(self, client, sys_h, product):
        # Metadata only: no products, stock, suppliers, reports, users or activity of a shop
        for path in ("/api/products", f"/api/products/{product['id']}", "/api/stock/movements",
                     "/api/suppliers", "/api/reports/stock", "/api/reports/audit", "/api/users",
                     "/api/dashboard", "/api/business", "/api/activity", "/api/categories"):
            assert client.get(path, headers=sys_h).status_code == 403, path
        r = client.post("/api/stock/movements", headers=sys_h,
                        json={"product_id": product["id"], "type": "OUT", "quantity": 1})
        assert r.status_code == 403

    def test_cannot_be_created_through_the_web(self, client, admin_h):
        r = client.post("/api/users", headers=admin_h,
                        json={"name": "X", "email": "x@shop.co.ke", "password": PW, "role": "SYSTEM_ADMIN"})
        assert r.status_code == 422
        assert client.post("/api/invites", headers=admin_h, json={"role": "SYSTEM_ADMIN"}).status_code == 422
        staff_id = [u for u in client.get("/api/users", headers=admin_h).json() if u["role"] == "STAFF"][0]["id"]
        assert client.patch(f"/api/users/{staff_id}", headers=admin_h, json={"role": "SYSTEM_ADMIN"}).status_code == 422

    def test_shop_accounts_cannot_use_platform(self, client, admin_h, staff_h):
        for h in (admin_h, staff_h):
            assert client.get("/api/platform/businesses", headers=h).status_code == 403
            assert client.patch("/api/platform/businesses/1", headers=h, json={"name": "Hacked"}).status_code == 403

    @pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL", "").startswith("mysql"),
                        reason="runs the command in a separate process, which needs a real database")
    def test_command_creates_system_admin(self, engine, db):
        # The test schema comes from the models; mark it as up to date so the command doesn't migrate.
        from alembic import command
        from app import migrate
        with engine.begin() as c:
            command.stamp(migrate._config(c), "head")
        env = {**os.environ, "DATABASE_URL": str(engine.url.render_as_string(hide_password=False)),
               "SYSTEM_ADMIN_PASSWORD": PW}
        r = subprocess.run([sys.executable, "-m", "scripts.create_system_admin", "--email", "Ops@StockWise.co.ke",
                            "--name", "Ops Person"], capture_output=True, text=True, env=env, cwd=".")
        assert r.returncode == 0, r.stderr
        db.expire_all()
        u = db.execute(select(User).where(User.email == "ops@stockwise.co.ke")).scalar_one()
        assert u.role == Role.SYSTEM_ADMIN and u.business_id is None
        again = subprocess.run([sys.executable, "-m", "scripts.create_system_admin", "--email", "ops@stockwise.co.ke",
                                "--name", "Ops"], capture_output=True, text=True, env=env, cwd=".")
        assert again.returncode != 0 and "already" in again.stderr


class TestPlatformOversight:
    def test_lists_businesses_with_metadata_only(self, client, sys_h, admin_h, product):
        rows = client.get("/api/platform/businesses", headers=sys_h).json()
        shop = next(b for b in rows if b["name"] == "Test Shop")
        assert (shop["managers"], shop["staff"], shop["products"]) == (1, 1, 1)
        assert shop["is_active"] is True
        # last login only: nothing about the shop's stock or trading
        assert set(shop) == {"id", "name", "is_active", "created_at", "managers", "staff", "products", "last_active"}

    def test_last_active_is_the_latest_login(self, client, sys_h, admin_h):
        def last_active(name):
            rows = client.get("/api/platform/businesses", headers=sys_h).json()
            return next(b for b in rows if b["name"] == name)["last_active"]
        assert last_active("Test Shop") is not None  # admin_h logged in
        assert last_active("Other Shop") is None      # nobody from it has logged in yet

    def test_summary(self, client, sys_h):
        s = client.get("/api/platform/summary", headers=sys_h).json()
        assert s["businesses"] == 2 and s["active_businesses"] == 2 and s["users"] == 3

    def test_rename_is_visible_to_the_business(self, client, sys_h, other_h):
        bid = other_business_id(client, other_h)
        r = client.patch(f"/api/platform/businesses/{bid}", headers=sys_h,
                         json={"name": "Other Shop Ltd", "reason": "Matches their registration"})
        assert r.status_code == 200 and r.json()["name"] == "Other Shop Ltd"
        assert client.get("/api/business", headers=other_h).json()["name"] == "Other Shop Ltd"
        entry = activity(client, other_h)[0]
        assert entry["action"] == "business.renamed" and entry["actor_role"] == "SYSTEM_ADMIN"
        assert entry["changes"] == {"name": ["Other Shop", "Other Shop Ltd"]}
        assert "Matches their registration" in entry["summary"]
        assert activity(client, other_h, system_admin_only=True)[0]["id"] == entry["id"]

    def test_deactivate_locks_business_out_and_is_logged(self, client, sys_h, other_h):
        from tests.conftest import OTHER_ADMIN
        bid = other_business_id(client, other_h)
        assert client.patch(f"/api/platform/businesses/{bid}", headers=sys_h, json={"is_active": False}).status_code == 200
        assert client.get("/api/products", headers=other_h).status_code == 401
        assert client.post("/api/auth/login", json=OTHER_ADMIN).status_code == 403
        assert client.patch(f"/api/platform/businesses/{bid}", headers=sys_h, json={"is_active": True}).status_code == 200
        h = {"Authorization": "Bearer " + client.post("/api/auth/login", json=OTHER_ADMIN).json()["access_token"]}
        actions = [a["action"] for a in activity(client, h)]
        assert actions[:2] == ["business.reactivated", "business.deactivated"]

    def test_unknown_business(self, client, sys_h):
        assert client.patch("/api/platform/businesses/99999", headers=sys_h, json={"name": "Nope"}).status_code == 404

    def test_platform_activity_shows_own_actions_not_shop_internals(self, client, sys_h, other_h, admin_h, product):
        bid = other_business_id(client, other_h)
        client.patch(f"/api/platform/businesses/{bid}", headers=sys_h, json={"name": "Renamed Co"})
        items = client.get("/api/platform/activity", headers=sys_h).json()["items"]
        assert [i["action"] for i in items] == ["business.renamed"]
        assert items[0]["business_name"] == "Renamed Co"
        assert not any(i["entity_type"] == "product" for i in items)


class TestActivityLog:
    def test_product_edit_records_before_and_after(self, client, admin_h, product):
        client.patch(f"/api/products/{product['id']}", headers=admin_h, json={"unit_price": "50.00", "name": "Water 500ml"})
        e = activity(client, admin_h, entity_type="product")[0]
        assert e["action"] == "product.updated" and e["actor_name"] == "Amina Admin" and e["actor_role"] == "MANAGER"
        assert e["changes"] == {"name": ["Mineral Water 500ml", "Water 500ml"], "unit_price": ["45.00", "50.00"]}

    def test_no_entry_when_nothing_changed(self, client, admin_h, product):
        before = len(activity(client, admin_h))
        client.patch(f"/api/products/{product['id']}", headers=admin_h, json={"name": "Mineral Water 500ml"})
        assert len(activity(client, admin_h)) == before

    def test_create_archive_restore_and_delete_logged(self, client, admin_h, product):
        client.post(f"/api/products/{product['id']}/archive", headers=admin_h)
        client.post(f"/api/products/{product['id']}/restore", headers=admin_h)
        p2 = client.post("/api/products", headers=admin_h, json={
            "sku": "tmp-1", "name": "Temp", "category_id": 1, "unit_price": "1.00", "reorder_threshold": 0}).json()
        client.delete(f"/api/products/{p2['id']}", headers=admin_h)
        actions = [a["action"] for a in activity(client, admin_h, entity_type="product")]
        assert actions == ["product.deleted", "product.created", "product.restored", "product.archived", "product.created"]

    def test_user_changes_hide_passwords(self, client, admin_h):
        r = client.post("/api/users", headers=admin_h, json={"name": "Neo", "email": "neo@shop.co.ke", "password": PW})
        uid = r.json()["id"]
        new_pw = new_password()
        client.patch(f"/api/users/{uid}", headers=admin_h, json={"role": "MANAGER", "password": new_pw})
        e = activity(client, admin_h, entity_type="user")[0]
        assert e["changes"]["role"] == ["STAFF", "MANAGER"]
        assert e["changes"]["password"] == ["(hidden)", "reset"]
        assert new_pw not in str(e) and PW not in str(e)

    def test_supplier_invite_and_join_logged(self, client, admin_h):
        s = client.post("/api/suppliers", headers=admin_h, json={"name": "Bidco"}).json()
        client.patch(f"/api/suppliers/{s['id']}", headers=admin_h, json={"phone": "+254 700 000 000"})
        inv = client.post("/api/invites", headers=admin_h, json={"role": "STAFF"}).json()
        client.post("/api/invites/accept", json={"token": inv["token"], "name": "Joy", "email": "joy@gmail.com", "password": PW})
        actions = [a["action"] for a in activity(client, admin_h)]
        assert actions[:4] == ["user.joined", "invite.created", "supplier.updated", "supplier.created"]
        joined = activity(client, admin_h)[0]
        assert joined["actor_name"] == "Joy" and joined["actor_role"] == "STAFF"

    def test_signup_logs_business_created(self, client):
        r = client.post("/api/auth/signup", json={"business_name": "New Duka", "name": "Owner",
                                                  "email": "owner@newduka.co.ke", "password": PW})
        h = {"Authorization": "Bearer " + r.json()["access_token"]}
        assert activity(client, h)[0]["action"] == "business.created"

    def test_managers_only(self, client, staff_h):
        assert client.get("/api/activity", headers=staff_h).status_code == 403

    def test_other_business_activity_is_private(self, client, admin_h, other_h, product):
        client.patch(f"/api/products/{product['id']}", headers=admin_h, json={"name": "Secret rename"})
        assert all("Secret" not in a["summary"] for a in activity(client, other_h))

    def test_entries_are_saved_with_the_change(self, client, admin_h, product, db):
        # a rejected change leaves no log entry
        r = client.patch(f"/api/products/{product['id']}", headers=admin_h, json={"sku": ""})
        assert r.status_code == 422
        db.expire_all()
        assert not db.execute(select(ActivityLog).where(ActivityLog.action == "product.updated")).first()
