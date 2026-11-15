"""Activity log: who changed what, with before/after values.

Call record() inside the same transaction as the change, so the log entry and the
change are saved together or not at all.
"""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from .models import ActivityLog, User

ROLE_LABELS = {"SYSTEM_ADMIN": "System Admin", "MANAGER": "Manager", "STAFF": "Staff"}


def _plain(v):
    """A JSON-safe version of a value (Decimal, enum and dates become strings)."""
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (list, tuple, set)):
        return sorted(_plain(x) for x in v)
    return v


def snapshot(obj, fields) -> dict:
    """Current values of the given attributes, for comparing before and after a change."""
    return {f: _plain(getattr(obj, f)) for f in fields}


def diff(before: dict, after: dict) -> dict:
    """{field: [before, after]} for the fields that changed."""
    return {k: [before.get(k), after.get(k)] for k in after if before.get(k) != after.get(k)}


def record(
    db: Session,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    changes: dict | None = None,
    business_id: int | None = ...,
) -> ActivityLog:
    """Add an entry. By default it belongs to the actor's business; a System Admin acting on
    a business passes that business's id, so the business can see what was done to it."""
    entry = ActivityLog(
        business_id=actor.business_id if business_id is ... else business_id,
        actor_id=actor.id,
        actor_name=actor.name,
        actor_role=actor.role.value,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:255],
        changes=changes or None,
    )
    db.add(entry)
    return entry
