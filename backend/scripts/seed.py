"""Seed demo data: two independent businesses, each with users, categories, suppliers,
products (with barcodes) and about three weeks of stock movements.

The two shops show multi-business isolation: each admin sees only their own shop.

Usage (from backend/):  python -m scripts.seed            # refuses if data exists
                        python -m scripts.seed --reset    # drops and recreates all tables
"""
import random
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.database import SessionLocal
from app.migrate import reset_database, upgrade_to_head
from app.models import (
    Business,
    Category,
    MovementSource,
    MovementType,
    Product,
    ProductBarcode,
    Role,
    StockMovement,
    Supplier,
    User,
    utcnow,
)
from app.security import hash_password


@dataclass
class ShopSpec:
    name: str
    users: list            # (name, email, password, role)
    suppliers: list        # (name, contact, phone, email, address)
    products: list         # (sku, name, category, price KES, threshold, opening, [supplier idx])
    end_level: dict = field(default_factory=dict)  # sku -> final stock, so alerts show
    barcode_base: int = 1000


SHOPS = [
    ShopSpec(
        name="Mama Njeri Duka",
        users=[
            ("Joseph Marube", "admin@stockwise.co.ke", "Admin@12345", Role.ADMIN),
            ("Grace Wanjiku", "grace@stockwise.co.ke", "Staff@12345", Role.STAFF),
            ("Brian Otieno", "brian@stockwise.co.ke", "Staff@12345", Role.STAFF),
        ],
        suppliers=[
            ("Bidco Distributors", "Peter Kamau", "+254 711 000 101", "orders@bidco-dist.example", "Industrial Area, Nairobi"),
            ("Kapa Wholesale", "Mary Achieng", "+254 722 000 202", "sales@kapa.example", "Gikomba, Nairobi"),
            ("Brookside Depot", "John Mwangi", "+254 733 000 303", "depot@brookside.example", "Ruaraka, Nairobi"),
            ("Nairobi Stationers", "Faith Njeri", "+254 744 000 404", None, "Moi Avenue, Nairobi"),
        ],
        products=[
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
        ],
        end_level={"BEV-002": 0, "DAI-002": 7, "HOU-003": 4, "GRO-003": 9},
        barcode_base=1000,
    ),
    ShopSpec(
        name="Kilimani Hardware",
        users=[
            ("Wanjiru Kamau", "wanjiru@kilimanihardware.co.ke", "Admin@12345", Role.ADMIN),
            ("Daniel Mutua", "daniel@kilimanihardware.co.ke", "Staff@12345", Role.STAFF),
        ],
        suppliers=[
            ("Bamburi Cement Depot", "Ali Hassan", "+254 755 000 505", "orders@bamburi-depot.example", "Mombasa Road, Nairobi"),
            ("Crown Paints Distributor", "Lucy Wairimu", "+254 766 000 606", None, "Enterprise Road, Nairobi"),
        ],
        products=[
            ("CEM-001", "Cement 50kg", "Building", "780.00", 20, 60, [0]),
            ("NAI-001", "Wire Nails 3in (1kg)", "Fasteners", "220.00", 15, 40, [0]),
            ("PNT-001", "Emulsion Paint 4L (white)", "Paint", "1850.00", 5, 12, [1]),
            ("PNT-002", "Paint Brush 2in", "Paint", "150.00", 10, 30, [1]),
            ("LCK-001", "Padlock 50mm", "Security", "650.00", 6, 15, []),
            ("PIP-001", "PVC Pipe 1/2in (6m)", "Plumbing", "420.00", 10, 25, []),
        ],
        end_level={"PNT-001": 3, "LCK-001": 0},
        barcode_base=2000,
    ),
]


def ean13(seed: int) -> str:
    """A valid EAN-13 with Kenya's GS1 prefix (616). Demo codes, not real products."""
    body = f"616{seed:09d}"
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


def seed_shop(db, spec: ShopSpec, rng: random.Random) -> None:
    biz = Business(name=spec.name)
    db.add(biz)
    db.flush()
    bid = biz.id
    users = [User(business_id=bid, name=n, email=e, password_hash=hash_password(p), role=r) for n, e, p, r in spec.users]
    cats = {c: Category(business_id=bid, name=c) for c in sorted({p[2] for p in spec.products})}
    sups = [Supplier(business_id=bid, name=n, contact_person=c, phone=ph, email=e, address=a) for n, c, ph, e, a in spec.suppliers]
    db.add_all([*users, *cats.values(), *sups])
    db.flush()

    now = utcnow()
    start = now - timedelta(days=21)
    staff = users[1] if len(users) > 1 else users[0]

    def move(p, user, typ, qty, note, t, source=MovementSource.MANUAL):
        p.apply_movement(typ, qty)
        db.add(StockMovement(business_id=bid, product_id=p.id, user_id=user.id, type=typ, quantity=qty,
                             stock_after=p.current_stock, note=note, created_at=t, source=source))

    for n, (sku, name, cat, price, thr, opening, sidx) in enumerate(spec.products, start=1):
        p = Product(
            business_id=bid, sku=sku, name=name, category=cats[cat], unit_price=Decimal(price),
            reorder_threshold=thr, current_stock=0, suppliers=[sups[i] for i in sidx],
            barcodes=[ProductBarcode(business_id=bid, code=ean13(spec.barcode_base + n))],
        )
        db.add(p)
        db.flush()
        move(p, users[0], MovementType.IN, opening, "Opening stock", start)
        t = start
        while True:  # sales most days, a restock when low
            t += timedelta(hours=rng.randint(6, 30))
            if t >= now:
                break
            if p.current_stock <= thr and rng.random() < 0.5:
                move(p, rng.choice(users), MovementType.IN, opening - p.current_stock + rng.randint(0, 5),
                     "Supplier delivery", t)
            else:
                qty = rng.randint(1, max(2, opening // 12))
                if qty > p.current_stock:
                    continue
                move(p, rng.choice(users), MovementType.OUT, qty,
                     rng.choice(["Sale", "Sale", "Sale", None, "Damaged"]), t,
                     rng.choice([MovementSource.MANUAL] * 3 + [MovementSource.SCANNER]))
        target = spec.end_level.get(sku)
        if target is not None and p.current_stock != target:
            typ = MovementType.OUT if p.current_stock > target else MovementType.IN
            move(p, staff, typ, abs(p.current_stock - target), "Sale",
                 now - timedelta(minutes=rng.randint(20, 300)))


def main(reset: bool) -> None:
    if reset:
        reset_database()
    else:
        upgrade_to_head()
    rng = random.Random(42)

    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            sys.exit("Database already has data. Run with --reset to wipe and reseed.")
        for spec in SHOPS:
            seed_shop(db, spec, rng)
        db.commit()

    print("Seeded two demo businesses. Log in with:")
    for spec in SHOPS:
        print(f"  {spec.name}")
        for _, e, pw, r in spec.users:
            print(f"    {r.value:5}  {e}  /  {pw}")
    print("  (each product has a demo barcode; see Products > product page)")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
