"""The signed-in user's business (workspace) settings."""
from fastapi import APIRouter

from ..deps import AdminUser, CurrentUser, DbSession
from ..schemas import BusinessOut, BusinessUpdate

router = APIRouter(prefix="/api/business", tags=["business"])


@router.get("", response_model=BusinessOut)
def get_business(user: CurrentUser):
    return user.business


@router.patch("", response_model=BusinessOut)
def rename_business(body: BusinessUpdate, db: DbSession, admin: AdminUser):
    admin.business.name = body.name
    db.commit()
    return admin.business
