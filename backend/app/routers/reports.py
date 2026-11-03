"""FR6 Reporting + CSV export, FR7.1 audit log retrieval (admin only)."""
import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import selectinload

from ..deps import AdminUser, DbSession
from ..models import Category, MovementType, Product, StockMovement
from ..schemas import MovementOut, MovementPage, StockReport, StockReportRow
from ..timeutil import local_date_range_to_utc, to_local, today_local

router = APIRouter(prefix="/api/reports", tags=["reports"])

MAX_RANGE_DAYS = 366


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or today_local()
    start = start or (end - timedelta(days=29))
    if start > end:
        raise HTTPException(422, "Start date must be on or before end date")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(422, "Date range cannot exceed one year")
    return start, end


def _build_rows(db, lo: datetime, hi: datetime, include_archived: bool) -> list[StockReportRow]:
    in_range = and_(
        StockMovement.product_id == Product.id,
        StockMovement.created_at >= lo,
        StockMovement.created_at < hi,
    )
    agg = (
        select(
            Product,
            Category.name,
            func.coalesce(
                func.sum(case((StockMovement.type == MovementType.IN, StockMovement.quantity), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((StockMovement.type == MovementType.OUT, StockMovement.quantity), else_=0)), 0
            ),
            func.count(StockMovement.id),
        )
        .join(Category, Category.id == Product.category_id)
        .outerjoin(StockMovement, in_range)
        .group_by(Product.id, Category.name)
        .order_by(Product.name)
    )
    rows = []
    for p, cat, qin, qout, n in db.execute(agg).all():
        if p.archived and not include_archived and n == 0:
            continue
        rows.append(
            StockReportRow(
                product_id=p.id,
                sku=p.sku,
                name=p.name,
                category=cat,
                unit_price=p.unit_price,
                reorder_threshold=p.reorder_threshold,
                current_stock=p.current_stock,
                stock_value=(Decimal(p.current_stock) * p.unit_price).quantize(Decimal("0.01")),
                low_stock=p.is_low_stock(),
                archived=p.archived,
                qty_in=int(qin),
                qty_out=int(qout),
                movement_count=int(n),
            )
        )
    return rows


def _movements_stmt(lo, hi, product_id=None, user_id=None, type_=None, q=None):
    stmt = (
        select(StockMovement)
        .options(selectinload(StockMovement.product), selectinload(StockMovement.user))
        .where(StockMovement.created_at >= lo, StockMovement.created_at < hi)
    )
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if user_id:
        stmt = stmt.where(StockMovement.user_id == user_id)
    if type_:
        stmt = stmt.where(StockMovement.type == type_)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.join(Product, Product.id == StockMovement.product_id).where(
            or_(Product.name.ilike(like), Product.sku.ilike(like))
        )
    return stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())


@router.get("/stock", response_model=StockReport)
def stock_report(
    db: DbSession,
    _: AdminUser,
    start: date | None = None,
    end: date | None = None,
    include_archived: bool = False,
):
    """FR6.1: current stock levels + movements over a selectable date range."""
    start, end = _range(start, end)
    lo, hi = local_date_range_to_utc(start, end)
    rows = _build_rows(db, lo, hi, include_archived)
    movements = db.execute(_movements_stmt(lo, hi).limit(500)).scalars().all()
    totals = {
        "products": len(rows),
        "units_on_hand": sum(r.current_stock for r in rows),
        "stock_value": str(sum((r.stock_value for r in rows), Decimal("0.00"))),
        "qty_in": sum(r.qty_in for r in rows),
        "qty_out": sum(r.qty_out for r in rows),
        "movements": sum(r.movement_count for r in rows),
        "low_stock": sum(1 for r in rows if r.low_stock and not r.archived),
    }
    return StockReport(
        start=lo,
        end=hi,
        generated_at=datetime.now(timezone.utc),
        rows=rows,
        movements=[MovementOut.model_validate(m) for m in movements],
        totals=totals,
    )


@router.get("/audit", response_model=MovementPage)
def audit_log(
    db: DbSession,
    _: AdminUser,
    start: date | None = None,
    end: date | None = None,
    user_id: int | None = None,
    product_id: int | None = None,
    type: MovementType | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """FR7.1 / NFR5: who did what stock action, and when."""
    start, end = _range(start, end)
    lo, hi = local_date_range_to_utc(start, end)
    stmt = _movements_stmt(lo, hi, product_id, user_id, type, q)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return MovementPage(items=items, total=total)


# ---------- CSV export (FR6.2) ----------
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell(v) -> str:
    """Neutralise spreadsheet formula injection in exported text."""
    s = "" if v is None else str(v)
    if s and s[0] in _FORMULA_PREFIXES and not _is_number(s):
        return "'" + s
    return s


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _csv_response(header: list[str], rows, filename: str) -> StreamingResponse:
    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel opens UTF-8 correctly
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([_cell(c) for c in r])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _fmt_local(dt: datetime) -> str:
    return to_local(dt).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/stock.csv")
def export_stock_csv(
    db: DbSession,
    _: AdminUser,
    start: date | None = None,
    end: date | None = None,
    include_archived: bool = False,
):
    start, end = _range(start, end)
    lo, hi = local_date_range_to_utc(start, end)
    rows = _build_rows(db, lo, hi, include_archived)
    return _csv_response(
        [
            "SKU", "Product", "Category", "Unit price", "Reorder threshold", "Current stock",
            "Stock value", "Low stock", "Archived",
            f"Qty in ({start}..{end})", f"Qty out ({start}..{end})", "Movements",
        ],
        (
            [
                r.sku, r.name, r.category, r.unit_price, r.reorder_threshold, r.current_stock,
                r.stock_value, "YES" if r.low_stock else "NO", "YES" if r.archived else "NO",
                r.qty_in, r.qty_out, r.movement_count,
            ]
            for r in rows
        ),
        f"stockwise-stock-{start}-to-{end}.csv",
    )


@router.get("/movements.csv")
def export_movements_csv(
    db: DbSession,
    _: AdminUser,
    start: date | None = None,
    end: date | None = None,
    user_id: int | None = None,
    product_id: int | None = None,
    type: MovementType | None = None,
):
    """Also serves as the audit-log export (FR7.1)."""
    start, end = _range(start, end)
    lo, hi = local_date_range_to_utc(start, end)
    ms = db.execute(_movements_stmt(lo, hi, product_id, user_id, type)).scalars().all()
    return _csv_response(
        [
            "Timestamp (local)", "Movement ID", "SKU", "Product", "Type", "Quantity",
            "Stock after", "User", "Role", "Override", "Note",
        ],
        (
            [
                _fmt_local(m.created_at), m.id, m.product.sku, m.product.name, m.type.value,
                m.quantity, m.stock_after, m.user.name, m.user.role.value,
                "YES" if m.override else "NO", m.note or "",
            ]
            for m in ms
        ),
        f"stockwise-movements-{start}-to-{end}.csv",
    )
