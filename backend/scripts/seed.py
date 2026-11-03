"""Seed demo data: users, categories, suppliers, products and ~3 weeks of movements.

Usage (from backend/):  python -m scripts.seed            # refuses if data exists
                        python -m scripts.seed --reset    # drops and recreates all tables
"""
import random
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app.models import Category, MovementType, Product, Role, StockMovement, Supplier, User, utcnow
from app.security import hash_password

USERS = [
    ("Joseph Marube", "admin@stockwise.co.ke", "Admin@12345", Role.ADMIN),
    ("Grace Wanjiku", "grace@stockwise.co.ke", "Staff@12345", Role.STAFF),
    ("Brian Otieno", "brian@stockwise.co.ke", "Staff@12345", Role.STAFF),
]

SUPPLIERS = [
    ("Bidco Distributors", "Peter Kamau", "+254 711 000 101", "orders@bidco-dist.example", "Industrial Area, Nairobi"),
    ("Kapa Wholesale", "Mary Achieng", "+254 722 000 202", "sales@kapa.example", "Gikomba, Nairobi"),
    ("Brookside Depot", "John Mwangi", "+254 733 000 303", "depot@brookside.example", "Ruaraka, Nairobi"),
    ("Nairobi Stationers", "Faith Njeri", "+254 744 000 404", None, "Moi Avenue, Nairobi"),
]

# sku, name, category, price (KES), threshold, opening stock, supplier indexes
PRODUCTS = [
    ("BEV-001", "Mineral Water 500ml", "Beverages", "45.00", 24, 120, [1]),
    ("BEV-002", "Soda 300ml (crate of 24)", "Beverages", "1150.00", 3, 10, [1]),
    ("BEV-003", "Tea Leaves 250g", "Beverages", "180.00", 10, 40, [0]),
    ("DAI-001", "Fresh Milk 500ml", "Dairy", "65.00", 30, 60, [2]),
    ("DAI-002", "Yoghurt 250ml", "Dairy", "90.00", 12, 30, [2]),
    ("GRO-001", "Maize Flour 2kg", "Groceries", "210.00", 15, 80, [0, 1]),
    ("GRO-002", "Sugar 1kg", "Groceries", "175.00", 20, 50, [1]),
    ("GRO-003", "Cooking Oil 1L", "Groceries", "340.00", 10, 35, [0]),
    ("GRO-004", "Rice 1kg", "Groceries", "160.00", 15, 45, [1]),
    ("HOU-001", "Bar Soap 800g", "Household", "130.00", 12, 40, [0]),
    ("HOU-002", "Washing Powder 1kg", "Household", "260.00", 8, 25, [1]),
    ("HOU-003", "Toilet Paper (10 pack)", "Household", "450.00", 6, 18, [1]),
    ("STA-001", "Exercise Book 96pg", "Stationery", "50.00", 30, 150, [3]),
    ("STA-002", "Ballpoint Pen (blue)", "Stationery", "20.00", 50, 200, [3]),
]


# End state for a few products so the dashboard shows real alerts.
END_LEVEL = {"BEV-002": 0, "DAI-002": 7, "HOU-003": 4, "GRO-003": 9}


def main(reset: bool) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rng = random.Random(42)

    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            sys.exit("Database already has data. Run with --reset to wipe and reseed.")

        users = [User(name=n, email=e, password_hash=hash_password(p), role=r) for n, e, p, r in USERS]
        db.add_all(users)
        cats = {c: Category(name=c) for c in sorted({p[2] for p in PRODUCTS})}
        db.add_all(cats.values())
        sups = [Supplier(name=n, contact_person=c, phone=ph, email=e, address=a) for n, c, ph, e, a in SUPPLIERS]
        db.add_all(sups)
        db.flush()

        now = utcnow()
        start = now - timedelta(days=21)
        for sku, name, cat, price, thr, opening, sidx in PRODUCTS:
            p = Product(
                sku=sku, name=name, category=cats[cat], unit_price=Decimal(price),
                reorder_threshold=thr, current_stock=0, suppliers=[sups[i] for i in sidx],
            )
            db.add(p)
            db.flush()
            t = start
            p.current_stock = opening
            db.add(StockMovement(product_id=p.id, user_id=users[0].id, type=MovementType.IN,
                                 quantity=opening, stock_after=opening, note="Opening stock", created_at=t))
            # daily-ish sales and an occasional restock
            while True:
                t += timedelta(hours=rng.randint(6, 30))
                if t >= now:
                    break
                if p.current_stock <= thr and rng.random() < 0.5:
                    qty, typ, note = opening - p.current_stock + rng.randint(0, 5), MovementType.IN, "Supplier delivery"
                else:
                    qty = rng.randint(1, max(2, opening // 12))
                    if qty > p.current_stock:
                        continue
                    typ, note = MovementType.OUT, rng.choice(["Sale", "Sale", "Sale", None, "Damaged"])
                p.apply_movement(typ, qty)
                db.add(StockMovement(product_id=p.id, user_id=rng.choice(users).id, type=typ, quantity=qty,
                                     stock_after=p.current_stock, note=note, created_at=t))
            target = END_LEVEL.get(sku)
            if target is not None and p.current_stock != target:
                typ = MovementType.OUT if p.current_stock > target else MovementType.IN
                qty = abs(p.current_stock - target)
                p.apply_movement(typ, qty)
                db.add(StockMovement(product_id=p.id, user_id=users[1].id, type=typ, quantity=qty,
                                     stock_after=p.current_stock, note="Sale", created_at=now - timedelta(minutes=rng.randint(20, 300))))
        db.commit()

    print("Seeded. Log in with:")
    for n, e, pw, r in USERS:
        print(f"  {r.value:5}  {e}  /  {pw}")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
