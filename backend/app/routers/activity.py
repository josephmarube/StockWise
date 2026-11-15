"""Activity log for a business: who changed what (managers only).

Includes actions a System Admin took on this business, so oversight is never hidden.
"""
from fastapi import APIRouter, Query
from sqlalchemy import func, select

from ..deps import DbSession, ManagerUser
from ..models import ActivityLog
from ..schemas import ActivityPage

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("", response_model=ActivityPage)
def list_activity(
    db: DbSession,
    manager: ManagerUser,
    entity_type: str | None = Query(default=None, max_length=20),
    actor_id: int | None = None,
    system_admin_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(ActivityLog).where(ActivityLog.business_id == manager.business_id)
    if entity_type:
        stmt = stmt.where(ActivityLog.entity_type == entity_type)
    if actor_id:
        stmt = stmt.where(ActivityLog.actor_id == actor_id)
    if system_admin_only:
        stmt = stmt.where(ActivityLog.actor_role == "SYSTEM_ADMIN")
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.execute(
        stmt.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return ActivityPage(items=items, total=total)
