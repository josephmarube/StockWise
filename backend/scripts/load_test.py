"""NFR3 performance check: N concurrent logged-in users doing standard CRUD-style requests.

Usage (API must be running, seeded with a known SEED_PASSWORD):
    SEED_PASSWORD=... python -m scripts.load_test --base http://localhost:8000 --users 10 --rounds 20

Each simulated user logs in, then repeatedly: lists products, opens the dashboard,
opens a product, and records a stock-in of 1 unit. Reports p50/p95/max latency per
operation and checks them against the 1-second target.
"""
import argparse
import asyncio
import os
import statistics
import time
from collections import defaultdict

import httpx

# Demo accounts from scripts/seed.py; they share the password given to the seed (SEED_PASSWORD).
ACCOUNTS = ["admin@stockwise.co.ke", "grace@stockwise.co.ke", "brian@stockwise.co.ke"]


async def user_session(client: httpx.AsyncClient, idx: int, rounds: int, timings: dict, errors: list, pw: str):
    email = ACCOUNTS[idx % len(ACCOUNTS)]
    r = await client.post("/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    products = (await client.get("/api/products?limit=100", headers=h)).json()["items"]

    async def timed(name, coro):
        t0 = time.perf_counter()
        resp = await coro
        timings[name].append(time.perf_counter() - t0)
        if resp.status_code >= 400:
            errors.append((name, resp.status_code, resp.text[:120]))
        return resp

    for i in range(rounds):
        p = products[(idx + i) % len(products)]
        await timed("list products", client.get("/api/products?q=&limit=50", headers=h))
        await timed("dashboard", client.get("/api/dashboard", headers=h))
        await timed("get product", client.get(f"/api/products/{p['id']}", headers=h))
        await timed(
            "record stock in",
            client.post("/api/stock/movements", headers=h,
                        json={"product_id": p["id"], "type": "IN", "quantity": 1, "note": "load test"}),
        )


async def main(base: str, users: int, rounds: int, password: str):
    timings: dict[str, list[float]] = defaultdict(list)
    errors: list = []
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        t0 = time.perf_counter()
        await asyncio.gather(*(user_session(client, i, rounds, timings, errors, password) for i in range(users)))
        wall = time.perf_counter() - t0

    print(f"\n{users} concurrent users x {rounds} rounds  ({wall:.1f}s wall)\n")
    print(f"{'operation':<18}{'n':>6}{'p50 ms':>10}{'p95 ms':>10}{'max ms':>10}")
    worst_p95 = 0.0
    for name, ts in timings.items():
        ts = sorted(ts)
        p95 = ts[int(len(ts) * 0.95) - 1]
        worst_p95 = max(worst_p95, p95)
        print(f"{name:<18}{len(ts):>6}{statistics.median(ts)*1000:>10.0f}{p95*1000:>10.0f}{ts[-1]*1000:>10.0f}")
    print(f"\nErrors: {len(errors)}")
    for e in errors[:5]:
        print("  ", e)
    ok = worst_p95 < 1.0 and not errors
    print(f"NFR3 (p95 < 1000 ms, no errors): {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=20)
    ap.add_argument("--password", default=os.getenv("SEED_PASSWORD"), help="demo account password (default: $SEED_PASSWORD)")
    a = ap.parse_args()
    if not a.password:
        ap.error("give --password or set SEED_PASSWORD to the password used when seeding")
    raise SystemExit(0 if asyncio.run(main(a.base, a.users, a.rounds, a.password)) else 1)
