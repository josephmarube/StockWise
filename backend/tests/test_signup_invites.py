"""Business signup, invite links, business settings and rate limiting."""
from datetime import timedelta

import pytest

SIGNUP = {"business_name": "Kilimani Hardware", "name": "Wanjiru Kamau",
          "email": "Wanjiru@KilimaniHardware.co.ke", "password": "Hardware123"}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestSignup:
    def test_creates_business_and_admin_and_logs_in(self, client):
        r = client.post("/api/auth/signup", json=SIGNUP)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["user"]["role"] == "ADMIN" and body["user"]["email"] == "wanjiru@kilimanihardware.co.ke"
        assert body["user"]["business"]["name"] == "Kilimani Hardware"
        h = auth(body["access_token"])
        # brand-new business starts empty
        assert client.get("/api/products", headers=h).json()["total"] == 0
        assert client.get("/api/categories", headers=h).json() == []
        assert [u["email"] for u in client.get("/api/users", headers=h).json()] == ["wanjiru@kilimanihardware.co.ke"]
        # and can log in again with the password
        assert client.post("/api/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}).status_code == 200

    def test_new_business_works_end_to_end(self, client):
        h = auth(client.post("/api/auth/signup", json=SIGNUP).json()["access_token"])
        cat = client.post("/api/categories", headers=h, json={"name": "Building"}).json()
        p = client.post("/api/products", headers=h, json={
            "sku": "CEM-1", "name": "Cement 50kg", "category_id": cat["id"], "unit_price": 780,
            "reorder_threshold": 5, "initial_stock": 10}).json()
        r = client.post("/api/stock/movements", headers=h, json={"product_id": p["id"], "type": "OUT", "quantity": 6})
        assert r.status_code == 201 and r.json()["low_stock"] is True

    def test_email_already_registered(self, client):
        r = client.post("/api/auth/signup", json={**SIGNUP, "email": "admin@shop.co.ke"})
        assert r.status_code == 409 and "already registered" in r.json()["detail"]

    @pytest.mark.parametrize("bad", [
        {"business_name": ""}, {"business_name": "A"}, {"name": ""},
        {"email": "not-an-email"}, {"password": "short"},
    ])
    def test_validation(self, client, bad):
        assert client.post("/api/auth/signup", json={**SIGNUP, **bad}).status_code == 422


class TestBusinessSettings:
    def test_admin_can_rename(self, client, admin_h):
        r = client.patch("/api/business", headers=admin_h, json={"name": "  Test Shop Ltd  "})
        assert r.status_code == 200 and r.json()["name"] == "Test Shop Ltd"
        assert client.get("/api/auth/me", headers=admin_h).json()["business"]["name"] == "Test Shop Ltd"

    def test_staff_cannot_rename(self, client, staff_h):
        assert client.get("/api/business", headers=staff_h).json()["name"] == "Test Shop"
        assert client.patch("/api/business", headers=staff_h, json={"name": "Mine now"}).status_code == 403


class TestInvites:
    def _invite(self, client, h, **body):
        r = client.post("/api/invites", headers=h, json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def test_full_flow(self, client, admin_h):
        inv = self._invite(client, admin_h, role="STAFF")
        assert len(inv["token"]) >= 40
        pre = client.get(f"/api/invites/preview/{inv['token']}")
        assert pre.status_code == 200 and pre.json()["business_name"] == "Test Shop" and pre.json()["role"] == "STAFF"
        r = client.post("/api/invites/accept", json={
            "token": inv["token"], "name": "New Cashier", "email": "cashier@gmail.com", "password": "Cashier123"})
        assert r.status_code == 201, r.text
        me = r.json()["user"]
        assert me["role"] == "STAFF" and me["business"]["name"] == "Test Shop"
        # joined the right business: sees its products, appears in its user list
        assert "cashier@gmail.com" in [u["email"] for u in client.get("/api/users", headers=admin_h).json()]
        # link is single-use
        again = client.post("/api/invites/accept", json={
            "token": inv["token"], "name": "Second", "email": "second@gmail.com", "password": "Second123"})
        assert again.status_code == 404
        assert client.get(f"/api/invites/preview/{inv['token']}").status_code == 404

    def test_admin_role_invite(self, client, admin_h):
        inv = self._invite(client, admin_h, role="ADMIN")
        r = client.post("/api/invites/accept", json={
            "token": inv["token"], "name": "Co-owner", "email": "co@gmail.com", "password": "Coowner123"})
        assert r.json()["user"]["role"] == "ADMIN"

    def test_email_locked_invite(self, client, admin_h):
        inv = self._invite(client, admin_h, email="Named@Gmail.com")
        wrong = client.post("/api/invites/accept", json={
            "token": inv["token"], "name": "X", "email": "other@gmail.com", "password": "Password1"})
        assert wrong.status_code == 422
        right = client.post("/api/invites/accept", json={
            "token": inv["token"], "name": "Named", "email": "named@gmail.com", "password": "Password1"})
        assert right.status_code == 201

    def test_revoked_and_expired(self, client, admin_h, db):
        from app.models import Invite, utcnow

        inv = self._invite(client, admin_h)
        assert client.delete(f"/api/invites/{inv['id']}", headers=admin_h).status_code == 204
        assert client.get(f"/api/invites/preview/{inv['token']}").status_code == 404

        inv2 = self._invite(client, admin_h)
        row = db.get(Invite, inv2["id"])
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
        assert client.post("/api/invites/accept", json={
            "token": inv2["token"], "name": "Late", "email": "late@gmail.com", "password": "Password1"}).status_code == 404

    def test_pending_list_hides_token_and_used_invites(self, client, admin_h):
        a = self._invite(client, admin_h)
        b = self._invite(client, admin_h)
        client.post("/api/invites/accept", json={"token": a["token"], "name": "A", "email": "a@gmail.com", "password": "Password1"})
        pending = client.get("/api/invites", headers=admin_h).json()
        assert [i["id"] for i in pending] == [b["id"]] and "token" not in pending[0]

    def test_token_not_stored_in_plain_text(self, client, admin_h, db):
        from app.models import Invite

        inv = self._invite(client, admin_h)
        row = db.get(Invite, inv["id"])
        assert inv["token"] not in row.token_hash and len(row.token_hash) == 64

    def test_existing_email_cannot_join(self, client, admin_h):
        inv = self._invite(client, admin_h)
        r = client.post("/api/invites/accept", json={
            "token": inv["token"], "name": "X", "email": "boss@othershop.co.ke", "password": "Password1"})
        assert r.status_code == 409

    def test_garbage_token(self, client):
        assert client.get("/api/invites/preview/" + "x" * 43).status_code == 404

    def test_staff_cannot_invite(self, client, staff_h):
        assert client.post("/api/invites", headers=staff_h, json={}).status_code == 403
        assert client.get("/api/invites", headers=staff_h).status_code == 403

    def test_cannot_see_or_revoke_other_business_invites(self, client, admin_h, other_h):
        inv = self._invite(client, admin_h)
        assert client.get("/api/invites", headers=other_h).json() == []
        assert client.delete(f"/api/invites/{inv['id']}", headers=other_h).status_code == 404
        assert client.get(f"/api/invites/preview/{inv['token']}").status_code == 200


class TestRateLimits:
    def test_login_brute_force_is_throttled(self, client):
        codes = [client.post("/api/auth/login", json={"email": "admin@shop.co.ke", "password": f"guess{i}"}).status_code
                 for i in range(22)]
        assert codes[:20] == [401] * 20 and codes[20:] == [429, 429]
        r = client.post("/api/auth/login", json={"email": "admin@shop.co.ke", "password": "AdminPass123"})
        assert r.status_code == 429 and "Retry-After" in r.headers and "Too many attempts" in r.json()["detail"]

    def test_signup_is_throttled(self, client):
        codes = [client.post("/api/auth/signup", json={**SIGNUP, "email": f"s{i}@gmail.com"}).status_code for i in range(6)]
        assert codes == [201] * 5 + [429]
