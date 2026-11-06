"""Invite links: an admin shares a one-time link; the new member sets their own name and password.

The token appears only in the link. The database stores its SHA-256 hash, so a
database leak does not reveal usable invite links.
"""
import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import AdminUser, DbSession
from ..models import Invite, User, utcnow
from ..ratelimit import limit
from ..schemas import InviteAccept, InviteCreate, InviteCreated, InviteOut, InvitePreview, TokenResponse
from ..security import hash_password
from .auth import issue_token
from .users import EMAIL_TAKEN, email_taken

router = APIRouter(prefix="/api/invites", tags=["invites"])

INVALID = "This invite link is invalid, expired or already used. Ask your admin for a new one."


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _find_usable(db, token: str) -> Invite:
    inv = db.execute(
        select(Invite).options(selectinload(Invite.business)).where(Invite.token_hash == _hash(token))
    ).scalar_one_or_none()
    if inv is None or not inv.is_usable(utcnow()) or not inv.business.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVALID)
    return inv


@router.post("", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
def create_invite(body: InviteCreate, db: DbSession, admin: AdminUser):
    if body.email and email_taken(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    token = secrets.token_urlsafe(32)
    inv = Invite(
        business_id=admin.business_id,
        token_hash=_hash(token),
        email=body.email.lower() if body.email else None,
        role=body.role,
        created_by_id=admin.id,
        expires_at=utcnow() + timedelta(days=body.days_valid),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return InviteCreated.model_validate({**InviteOut.model_validate(inv).model_dump(), "token": token})


@router.get("", response_model=list[InviteOut])
def list_pending(db: DbSession, admin: AdminUser):
    now = utcnow()
    return db.execute(
        select(Invite)
        .options(selectinload(Invite.created_by))
        .where(
            Invite.business_id == admin.business_id,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
            Invite.expires_at > now,
        )
        .order_by(Invite.created_at.desc())
    ).scalars().all()


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(invite_id: int, db: DbSession, admin: AdminUser):
    inv = db.get(Invite, invite_id)
    if inv is None or inv.business_id != admin.business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if inv.revoked_at is None and inv.accepted_at is None:
        inv.revoked_at = utcnow()
        db.commit()


@router.get(
    "/preview/{token}", response_model=InvitePreview, dependencies=[Depends(limit("invite-preview", 30, 600))]
)
def preview(token: str, db: DbSession):
    """Public: what the join page shows before the person signs up."""
    inv = _find_usable(db, token)
    return InvitePreview(business_name=inv.business.name, role=inv.role, email=inv.email, expires_at=inv.expires_at)


@router.post(
    "/accept",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit("invite-accept", 10, 3600))],
)
def accept(body: InviteAccept, db: DbSession):
    """Public: create the member's account in the inviting business and log them in."""
    inv = db.execute(
        select(Invite).where(Invite.token_hash == _hash(body.token)).with_for_update()
    ).scalar_one_or_none()
    if inv is None or not inv.is_usable(utcnow()) or not inv.business.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVALID)
    email = body.email.lower()
    if inv.email and inv.email != email:
        raise HTTPException(422, "This invite is for a different email address.")
    if email_taken(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    user = User(
        business_id=inv.business_id,
        name=body.name,
        email=email,
        password_hash=hash_password(body.password),
        role=inv.role,
    )
    inv.accepted_at = utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return issue_token(user)
