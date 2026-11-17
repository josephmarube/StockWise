"""System Admin area: oversight of all businesses using StockWise.

System Admins see metadata only (names, dates, counts, last login). They never see a
business's products, prices, suppliers, stock or how much it trades. Every change they make to a business is written
to that business's activity log, so its managers can see it.
"""
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select

from ..activity import record
from ..deps import DbSession, SystemAdminUser
from ..models import ActivityLog, Business, Product, Role, User, utcnow
from ..schemas import ActivityOut, ActivityPage, PlatformBusiness, PlatformBusinessUpdate, PlatformSummary

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _rows(db, business_ids=None, q: str | None = None) -> list[PlatformBusiness]:
    users = (
        select(
            User.business_id.label("bid"),
            func.sum(case((User.role == Role.MANAGER, 1), else_=0)).label("managers"),
            func.sum(case((User.role == Role.STAFF, 1), else_=0)).label("staff"),
            func.max(User.last_login_at).label("last_login"),
        )
        .where(User.business_id.is_not(None))
        .group_by(User.business_id)
        .subquery()
    )
    products = (
        select(Product.business_id.label("bid"), func.count().label("n"))
        .where(Product.archived.is_(False))
        .group_by(Product.business_id)
        .subquery()
    )
    stmt = (
        select(
            Business,
            func.coalesce(users.c.managers, 0),
            func.coalesce(users.c.staff, 0),
            func.coalesce(products.c.n, 0),
            users.c.last_login,
        )
        .outerjoin(users, users.c.bid == Business.id)
        .outerjoin(products, products.c.bid == Business.id)
        .order_by(Business.created_at.desc(), Business.id.desc())
    )
    if business_ids is not None:
        stmt = stmt.where(Business.id.in_(business_ids))
    if q:
        stmt = stmt.where(Business.name.ilike(f"%{q.strip()}%"))
    return [
        PlatformBusiness(
            id=b.id, name=b.name, is_active=b.is_active, created_at=b.created_at,
            managers=int(m), staff=int(s), products=int(p), last_active=last,
        )
        for b, m, s, p, last in db.execute(stmt).all()
    ]


@router.get("/summary", response_model=PlatformSummary)
def summary(db: DbSession, admin: SystemAdminUser):
    since = utcnow() - timedelta(days=30)
    return PlatformSummary(
        businesses=db.scalar(select(func.count()).select_from(Business)),
        active_businesses=db.scalar(select(func.count()).select_from(Business).where(Business.is_active.is_(True))),
        users=db.scalar(select(func.count()).select_from(User).where(User.business_id.is_not(None))),
        new_businesses_30d=db.scalar(select(func.count()).select_from(Business).where(Business.created_at >= since)),
    )


@router.get("/businesses", response_model=list[PlatformBusiness])
def list_businesses(db: DbSession, admin: SystemAdminUser, q: str | None = Query(default=None, max_length=100)):
    return _rows(db, q=q)


@router.patch("/businesses/{business_id}", response_model=PlatformBusiness)
def update_business(business_id: int, body: PlatformBusinessUpdate, db: DbSession, admin: SystemAdminUser):
    """Rename, deactivate or reactivate a business. Each change is visible to the business."""
    biz = db.get(Business, business_id)
    if biz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    reason = f" Reason: {body.reason.strip()}" if body.reason and body.reason.strip() else ""

    if body.name is not None and body.name != biz.name:
        old = biz.name
        biz.name = body.name
        record(db, admin, "business.renamed", "business", biz.id,
               f"StockWise renamed the business from {old} to {biz.name}.{reason}",
               {"name": [old, biz.name]}, business_id=biz.id)
    if body.is_active is not None and body.is_active != biz.is_active:
        biz.is_active = body.is_active
        verb = "reactivated" if body.is_active else "deactivated"
        record(db, admin, f"business.{verb}", "business", biz.id,
               f"StockWise {verb} the business.{reason}",
               {"is_active": [not body.is_active, body.is_active]}, business_id=biz.id)
    db.commit()
    return _rows(db, business_ids=[biz.id])[0]


@router.get("/activity", response_model=ActivityPage)
def platform_activity(
    db: DbSession,
    admin: SystemAdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """What System Admins have done, and new businesses signing up. No shop-internal entries."""
    stmt = select(ActivityLog, Business.name).outerjoin(Business, Business.id == ActivityLog.business_id).where(
        (ActivityLog.actor_role == Role.SYSTEM_ADMIN.value) | (ActivityLog.action == "business.created")
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(limit).offset(offset)
    ).all()
    items = [ActivityOut.model_validate(a).model_copy(update={"business_name": name}) for a, name in rows]
    return ActivityPage(items=items, total=total)
