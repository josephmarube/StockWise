from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..activity import record
from ..deps import ManagerUser, CurrentUser, DbSession
from ..models import Category
from ..schemas import CategoryCreate, CategoryOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbSession, user: CurrentUser):
    return db.execute(
        select(Category).where(Category.business_id == user.business_id).order_by(Category.name)
    ).scalars().all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, db: DbSession, admin: ManagerUser):
    exists = db.execute(
        select(Category).where(
            Category.business_id == admin.business_id, func.lower(Category.name) == body.name.lower()
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Category already exists")
    cat = Category(name=body.name, business_id=admin.business_id)
    db.add(cat)
    db.flush()
    record(db, admin, "category.created", "category", cat.id, f"Added category {cat.name}")
    db.commit()
    db.refresh(cat)
    return cat
