"""FR3.1 Supplier management (admin only)."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from ..deps import AdminUser, DbSession
from ..models import Supplier
from ..schemas import SupplierCreate, SupplierDeleteResult, SupplierOut, SupplierUpdate

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


def _load(db, supplier_id: int) -> Supplier:
    s = db.execute(
        select(Supplier).options(selectinload(Supplier.products)).where(Supplier.id == supplier_id)
    ).scalar_one_or_none()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return s


@router.get("", response_model=list[SupplierOut])
def list_suppliers(
    db: DbSession,
    _: AdminUser,
    q: str | None = Query(default=None, max_length=100),
    include_inactive: bool = True,
):
    stmt = select(Supplier).options(selectinload(Supplier.products)).order_by(Supplier.name)
    if not include_inactive:
        stmt = stmt.where(Supplier.is_active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Supplier.name.ilike(like), Supplier.contact_person.ilike(like)))
    return db.execute(stmt).scalars().all()


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int, db: DbSession, _: AdminUser):
    return _load(db, supplier_id)


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(body: SupplierCreate, db: DbSession, _: AdminUser):
    s = Supplier(**body.model_dump())
    db.add(s)
    db.commit()
    return _load(db, s.id)


@router.patch("/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, body: SupplierUpdate, db: DbSession, _: AdminUser):
    s = _load(db, supplier_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and not (data["name"] or "").strip():
        raise HTTPException(422, "Name cannot be empty")
    for k, v in data.items():
        setattr(s, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return _load(db, s.id)


@router.post("/{supplier_id}/deactivate", response_model=SupplierOut)
def deactivate_supplier(supplier_id: int, db: DbSession, _: AdminUser):
    s = _load(db, supplier_id)
    s.is_active = False
    db.commit()
    return _load(db, s.id)


@router.post("/{supplier_id}/activate", response_model=SupplierOut)
def activate_supplier(supplier_id: int, db: DbSession, _: AdminUser):
    s = _load(db, supplier_id)
    s.is_active = True
    db.commit()
    return _load(db, s.id)


@router.delete("/{supplier_id}", response_model=SupplierDeleteResult)
def delete_supplier(supplier_id: int, db: DbSession, _: AdminUser):
    """FR3.1: hard-delete only when unlinked; otherwise deactivate."""
    s = _load(db, supplier_id)
    if s.can_be_deleted():
        db.delete(s)
        db.commit()
        return SupplierDeleteResult(action="deleted", detail="Supplier deleted")
    s.is_active = False
    db.commit()
    return SupplierDeleteResult(
        action="deactivated",
        detail=f"Supplier is linked to {len(s.products)} product(s), so it was deactivated instead",
    )
