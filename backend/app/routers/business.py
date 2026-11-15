"""The signed-in user's business (workspace) settings."""
from fastapi import APIRouter

from ..deps import CurrentUser
from ..schemas import BusinessOut

router = APIRouter(prefix="/api/business", tags=["business"])


@router.get("", response_model=BusinessOut)
def get_business(user: CurrentUser):
    return user.business


# Renaming a business is a System Admin action (PATCH /api/platform/businesses/{id}),
# so a business's name can't be changed to impersonate another shop.
