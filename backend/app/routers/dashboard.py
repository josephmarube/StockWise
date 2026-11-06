"""Dashboard summary: stock overview + low-stock alerts (FR2.3, FR5.1)."""
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, DbSession
from ..models import Product, StockMovement
from ..schemas import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
def summary(db: DbSession, _: CurrentUser):
    active = Product.archived.is_(False)
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
