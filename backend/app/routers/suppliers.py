"""FR3.1 Supplier management (managers only), limited to the manager's business."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from ..activity import diff, record, snapshot
from ..deps import ManagerUser, DbSession
from ..models import Supplier, User
from ..schemas import SupplierCreate, SupplierDeleteResult, SupplierOut, SupplierUpdate

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])

FIELDS = ("name", "contact_person", "phone", "email", "address")


def _load(db, supplier_id: int, user: User) -> Supplier:
    s = db.execute(
        select(Supplier)
        .options(selectinload(Supplier.products))
        .where(Supplier.id == supplier_id, Supplier.business_id == user.business_id)
    ).scalar_one_or_none()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return s


@router.get("", response_model=list[SupplierOut])
def list_suppliers(
    db: DbSession,
    admin: ManagerUser,
    q: str | None = Query(default=None, max_length=100),
    include_inactive: bool = True,
):
    stmt = (
        select(Supplier)
        .options(selectinload(Supplier.products))
        .where(Supplier.business_id == admin.business_id)
        .order_by(Supplier.name)
    )
    if not include_inactive:
        stmt = stmt.where(Supplier.is_active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Supplier.name.ilike(like), Supplier.contact_person.ilike(like)))
    return db.execute(stmt).scalars().all()


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int, db: DbSession, admin: ManagerUser):
    return _load(db, supplier_id, admin)


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(body: SupplierCreate, db: DbSession, admin: ManagerUser):
    s = Supplier(**body.model_dump(), business_id=admin.business_id)
    db.add(s)
    db.flush()
    record(db, admin, "supplier.created", "supplier", s.id, f"Added supplier {s.name}",
           {k: [None, v] for k, v in snapshot(s, FIELDS).items() if v})
    db.commit()
    return _load(db, s.id, admin)


@router.patch("/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, body: SupplierUpdate, db: DbSession, admin: ManagerUser):
    s = _load(db, supplier_id, admin)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and not (data["name"] or "").strip():
        raise HTTPException(422, "Name cannot be empty")
    before = snapshot(s, FIELDS)
    for k, v in data.items():
        setattr(s, k, v.strip() if isinstance(v, str) else v)
    changes = diff(before, snapshot(s, FIELDS))
    if changes:
        record(db, admin, "supplier.updated", "supplier", s.id, f"Edited supplier {s.name}", changes)
    db.commit()
    return _load(db, s.id, admin)


@router.post("/{supplier_id}/deactivate", response_model=SupplierOut)
def deactivate_supplier(supplier_id: int, db: DbSession, admin: ManagerUser):
    s = _load(db, supplier_id, admin)
    if s.is_active:
        s.is_active = False
        record(db, admin, "supplier.deactivated", "supplier", s.id, f"Deactivated supplier {s.name}")
    db.commit()
    return _load(db, s.id, admin)


@router.post("/{supplier_id}/activate", response_model=SupplierOut)
def activate_supplier(supplier_id: int, db: DbSession, admin: ManagerUser):
    s = _load(db, supplier_id, admin)
    if not s.is_active:
        s.is_active = True
        record(db, admin, "supplier.activated", "supplier", s.id, f"Reactivated supplier {s.name}")
    db.commit()
    return _load(db, s.id, admin)


@router.delete("/{supplier_id}", response_model=SupplierDeleteResult)
def delete_supplier(supplier_id: int, db: DbSession, admin: ManagerUser):
    """FR3.1: hard-delete only when unlinked; otherwise deactivate."""
    s = _load(db, supplier_id, admin)
    if s.can_be_deleted():
        record(db, admin, "supplier.deleted", "supplier", s.id, f"Deleted supplier {s.name}")
        db.delete(s)
        db.commit()
        return SupplierDeleteResult(action="deleted", detail="Supplier deleted")
    if s.is_active:
        s.is_active = False
        record(db, admin, "supplier.deactivated", "supplier", s.id,
               f"Deactivated supplier {s.name} (linked to products, so not deleted)")
    db.commit()
    return SupplierDeleteResult(
        action="deactivated",
        detail=f"Supplier is linked to {len(s.products)} product(s), so it was deactivated instead",
    )
