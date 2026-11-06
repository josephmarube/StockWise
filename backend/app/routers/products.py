"""FR1 Product Management, FR1.4 barcodes, FR3.2 product-supplier links."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..deps import AdminUser, CurrentUser, DbSession
from ..models import Category, MovementType, Product, ProductBarcode, Role, StockMovement, Supplier
from ..schemas import (
    ProductCreate,
    ProductOut,
    ProductPage,
    ProductSuppliersUpdate,
    ProductUpdate,
)
from ..services.stock_service import record_movement

router = APIRouter(prefix="/api/products", tags=["products"])

SORTS = {
    "name": Product.name,
    "sku": Product.sku,
    "stock": Product.current_stock,
    "price": Product.unit_price,
    "updated": Product.updated_at,
}


LOAD_OPTS = (
    selectinload(Product.category),
    selectinload(Product.suppliers),
    selectinload(Product.barcodes),
)


def _load(db, product_id: int) -> Product:
    p = db.execute(
        select(Product).options(*LOAD_OPTS).where(Product.id == product_id)
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return p


def _resolve_suppliers(db, ids: list[int]) -> list[Supplier]:
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    found = db.execute(select(Supplier).where(Supplier.id.in_(ids))).scalars().all()
    if len(found) != len(ids):
        raise HTTPException(422, "One or more suppliers do not exist")
    inactive = [s.name for s in found if not s.is_active]
    if inactive:
        raise HTTPException(
            422,
            f"Cannot link deactivated supplier(s): {', '.join(inactive)}",
        )
    return list(found)


def _check_category(db, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(422, "Category does not exist")


def _check_barcodes_free(db, codes: list[str], exclude_product_id: int | None = None) -> None:
    """FR1.4: a barcode identifies exactly one product."""
    if not codes:
        return
    q = (
        select(ProductBarcode.code, Product.name)
        .join(Product, Product.id == ProductBarcode.product_id)
        .where(ProductBarcode.code.in_(codes))
    )
    if exclude_product_id:
        q = q.where(ProductBarcode.product_id != exclude_product_id)
    clash = db.execute(q).first()
    if clash:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Barcode {clash[0]} is already used by {clash[1]}"
        )


def _set_barcodes(product: Product, codes: list[str]) -> None:
    keep = {b.code: b for b in product.barcodes}
    product.barcodes = [keep.get(c) or ProductBarcode(code=c) for c in codes]


def _sku_taken(db, sku: str, exclude_id: int | None = None) -> bool:
    q = select(Product.id).where(func.upper(Product.sku) == sku.upper())
    if exclude_id:
        q = q.where(Product.id != exclude_id)
    return db.execute(q).first() is not None


@router.get("", response_model=ProductPage)
def list_products(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=100),
    category_id: int | None = None,
    low_stock: bool = False,
    include_archived: bool = False,
    archived_only: bool = False,
    sort: Literal["name", "sku", "stock", "price", "updated"] = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """FR1.3: searchable, filterable catalogue with current stock level."""
    stmt = select(Product).options(*LOAD_OPTS)

    # Staff only ever see active products.
    if user.role != Role.ADMIN:
        stmt = stmt.where(Product.archived.is_(False))
    elif archived_only:
        stmt = stmt.where(Product.archived.is_(True))
    elif not include_archived:
        stmt = stmt.where(Product.archived.is_(False))

    if q:
        term = q.strip()
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.sku.ilike(like),
                Product.barcodes.any(ProductBarcode.code == term),
            )
        )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if low_stock:
        stmt = stmt.where(Product.current_stock <= Product.reorder_threshold)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = SORTS[sort]
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), Product.id)
    items = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return ProductPage(items=items, total=total)


@router.get("/by-barcode/{code}", response_model=ProductOut)
def get_by_barcode(code: str, db: DbSession, user: CurrentUser):
    """FR2.5: resolve a scanned barcode to its product."""
    p = db.execute(
        select(Product)
        .options(*LOAD_OPTS)
        .join(ProductBarcode, ProductBarcode.product_id == Product.id)
        .where(ProductBarcode.code == code.strip())
    ).scalar_one_or_none()
    if p is None or (p.archived and user.role != Role.ADMIN):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No product has barcode {code.strip()}")
    return p


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession, user: CurrentUser):
    p = _load(db, product_id)
    if p.archived and user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return p


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(body: ProductCreate, db: DbSession, admin: AdminUser):
    """FR1.1: reject duplicate SKU or invalid fields."""
    if _sku_taken(db, body.sku):
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU '{body.sku}' already exists")
    _check_category(db, body.category_id)
    _check_barcodes_free(db, body.barcodes)
    suppliers = _resolve_suppliers(db, body.supplier_ids)

    product = Product(
        sku=body.sku,
        name=body.name,
        category_id=body.category_id,
        unit_price=body.unit_price,
        reorder_threshold=body.reorder_threshold,
        current_stock=0,
        suppliers=suppliers,
        barcodes=[ProductBarcode(code=c) for c in body.barcodes],
    )
    db.add(product)
    db.commit()

    # Initial stock goes through StockService so it appears in the audit trail.
    if body.initial_stock > 0:
        record_movement(
            db,
            user=admin,
            product_id=product.id,
            type_=MovementType.IN,
            quantity=body.initial_stock,
            note="Initial stock",
        )
    return _load(db, product.id)


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, body: ProductUpdate, db: DbSession, _: AdminUser):
    """FR1.2 edit. Stock level is not editable here; use stock movements."""
    p = _load(db, product_id)
    data = body.model_dump(exclude_unset=True)
    if "sku" in data and data["sku"] is not None and _sku_taken(db, data["sku"], exclude_id=p.id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU '{data['sku']}' already exists")
    if data.get("category_id") is not None:
        _check_category(db, data["category_id"])
    if "barcodes" in data:
        codes = data.pop("barcodes") or []
        _check_barcodes_free(db, codes, exclude_product_id=p.id)
        _set_barcodes(p, codes)
    for field, value in data.items():
        if value is None:
            raise HTTPException(422, f"{field} cannot be empty")
        setattr(p, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    return _load(db, p.id)


@router.put("/{product_id}/suppliers", response_model=ProductOut)
def set_product_suppliers(
    product_id: int, body: ProductSuppliersUpdate, db: DbSession, _: AdminUser
):
    """FR3.2: associate one or more suppliers with a product."""
    p = _load(db, product_id)
    keep = {s.id for s in p.suppliers}
    new_ids = [i for i in body.supplier_ids if i not in keep]
    _resolve_suppliers(db, new_ids)  # validates only newly linked suppliers are active
    p.suppliers = list(
        db.execute(select(Supplier).where(Supplier.id.in_(body.supplier_ids))).scalars().all()
    ) if body.supplier_ids else []
    db.commit()
    return _load(db, p.id)


@router.post("/{product_id}/archive", response_model=ProductOut)
def archive_product(product_id: int, db: DbSession, _: AdminUser):
    p = _load(db, product_id)
    p.archived = True
    db.commit()
    return _load(db, p.id)


@router.post("/{product_id}/restore", response_model=ProductOut)
def restore_product(product_id: int, db: DbSession, _: AdminUser):
    p = _load(db, product_id)
    p.archived = False
    db.commit()
    return _load(db, p.id)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: DbSession, _: AdminUser):
    """FR1.2 / Business Rule: products with movement history can only be archived."""
    p = _load(db, product_id)
    has_history = db.execute(
        select(StockMovement.id).where(StockMovement.product_id == p.id).limit(1)
    ).first()
    if has_history:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This product has stock movement history and cannot be deleted. Archive it instead.",
        )
    db.delete(p)
    db.commit()
