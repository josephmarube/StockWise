"""Dashboard summary: stock overview + low-stock alerts (FR2.3, FR5.1)."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, DbSession
from ..models import Category, MovementType, Product, Role, StockMovement
from ..schemas import CategoryValue, DashboardSummary, DashboardTrends, DayTotals, TopMover
from ..timeutil import local_date_range_to_utc, to_local, today_local

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
def summary(db: DbSession, user: CurrentUser):
    active = (Product.business_id == user.business_id) & Product.archived.is_(False)
    count, units, value = db.execute(
        select(
            func.count(Product.id),
            func.coalesce(func.sum(Product.current_stock), 0),
            func.coalesce(func.sum(Product.current_stock * Product.unit_price), 0),
        ).where(active)
    ).one()

    low = (
        db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.suppliers),
                selectinload(Product.barcodes),
            )
            .where(active, Product.current_stock <= Product.reorder_threshold)
            .order_by((Product.current_stock - Product.reorder_threshold).asc(), Product.name)
        )
        .scalars()
        .all()
    )
    recent = (
        db.execute(
            select(StockMovement)
            .options(selectinload(StockMovement.product), selectinload(StockMovement.user))
            .where(StockMovement.business_id == user.business_id)
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    return DashboardSummary(
        active_products=count,
        total_units=int(units),
        stock_value=Decimal(value).quantize(Decimal("0.01")),
        low_stock_count=len(low),
        out_of_stock_count=sum(1 for p in low if p.current_stock <= 0),
        low_stock=low,
        recent_movements=recent,
    )


@router.get("/trends", response_model=DashboardTrends)
def trends(db: DbSession, user: CurrentUser, days: int = Query(default=14, ge=7, le=90)):
    """Daily units in/out, fastest movers and stock value by category, for this business."""
    end = today_local()
    start = end - timedelta(days=days - 1)
    lo, hi = local_date_range_to_utc(start, end)
    bid = user.business_id

    rows = db.execute(
        select(StockMovement.created_at, StockMovement.type, StockMovement.quantity, StockMovement.product_id)
        .where(StockMovement.business_id == bid, StockMovement.created_at >= lo, StockMovement.created_at < hi)
    ).all()
    per_day = {start + timedelta(days=i): [0, 0] for i in range(days)}
    out_by_product: dict[int, int] = defaultdict(int)
    for created, type_, qty, pid in rows:
        day = to_local(created).date()
        if day in per_day:
            per_day[day][0 if type_ == MovementType.IN else 1] += qty
        if type_ == MovementType.OUT:
            out_by_product[pid] += qty

    top_ids = [pid for pid, _ in sorted(out_by_product.items(), key=lambda kv: -kv[1])[:5]]
    names = {
        p.id: p
        for p in db.execute(select(Product).where(Product.id.in_(top_ids), Product.business_id == bid)).scalars()
    } if top_ids else {}
    top = [
        TopMover(product_id=pid, name=names[pid].name, sku=names[pid].sku, qty_out=out_by_product[pid])
        for pid in top_ids if pid in names
    ]

    cats = db.execute(
        select(
            Category.name,
            func.coalesce(func.sum(Product.current_stock * Product.unit_price), 0),
            func.coalesce(func.sum(Product.current_stock), 0),
        )
        .join(Product, Product.category_id == Category.id)
        .where(Product.business_id == bid, Product.archived.is_(False), Product.current_stock > 0)
        .group_by(Category.name)
    ).all()
    by_category = sorted(
        (CategoryValue(name=n, value=Decimal(v).quantize(Decimal("0.01")), units=int(u)) for n, v, u in cats),
        key=lambda c: -c.value,
    )

    return DashboardTrends(
        days=[DayTotals(date=d, qty_in=v[0], qty_out=v[1]) for d, v in per_day.items()],
        top_movers=top,
        by_category=by_category if user.role == Role.MANAGER else [],
    )
