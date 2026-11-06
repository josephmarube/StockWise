"""FR2 Stock Management: record stock in/out, view movement history."""
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, DbSession
from ..models import MovementSource, MovementType, Product, Role, StockMovement
from ..schemas import MovementCreate, MovementOut, MovementPage, MovementResult
from ..services.stock_service import InsufficientStock, StockError, record_movement
from ..timeutil import local_date_range_to_utc

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.post(
    "/movements",
    response_model=MovementResult,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Insufficient stock or archived product"}},
)
def create_movement(body: MovementCreate, db: DbSession, user: CurrentUser):
    """FR2.1 / FR2.2. Returns 201 only after commit; 409 when stock would go negative."""
    try:
        outcome = record_movement(
            db,
            user=user,
            product_id=body.product_id,
            type_=body.type,
            quantity=body.quantity,
            note=body.note,
            override=body.override,
            source=body.source,
        )
    except InsufficientStock as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "detail": e.detail,
                "code": "INSUFFICIENT_STOCK",
                "available": e.available,
                "requested": e.requested,
                "can_override": e.can_override,
            },
        )
    except StockError as e:
        raise HTTPException(e.status_code, e.detail)

    m = db.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.product), selectinload(StockMovement.user))
        .where(StockMovement.id == outcome.movement.id)
    ).scalar_one()
    return MovementResult(
        movement=MovementOut.model_validate(m),
        current_stock=outcome.current_stock,
        low_stock=outcome.low_stock,
    )


@router.get("/movements", response_model=MovementPage)
def list_movements(
    db: DbSession,
    user: CurrentUser,
    product_id: int | None = None,
    type: MovementType | None = None,
    source: MovementSource | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """FR2.4: chronological stock-in/out history (newest first)."""
    stmt = select(StockMovement).options(
        selectinload(StockMovement.product), selectinload(StockMovement.user)
    )
    if user.role != Role.ADMIN:
        stmt = stmt.join(Product).where(Product.archived.is_(False))
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if type:
        stmt = stmt.where(StockMovement.type == type)
    if source:
        stmt = stmt.where(StockMovement.source == source)
    if start or end:
        lo, hi = local_date_range_to_utc(start, end)
        if lo:
            stmt = stmt.where(StockMovement.created_at >= lo)
        if hi:
            stmt = stmt.where(StockMovement.created_at < hi)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = (
        db.execute(
            stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return MovementPage(items=items, total=total)
