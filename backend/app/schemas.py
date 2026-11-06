"""Pydantic request/response models. Server-side validation for NFR8."""
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, field_validator

from .models import MovementSource, MovementType, Role


def _as_utc(d: datetime) -> str:
    # Timestamps are stored as naive UTC; emit them with an explicit offset.
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.isoformat()


UTCDateTime = Annotated[datetime, PlainSerializer(_as_utc, return_type=str)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _strip(v):
    return v.strip() if isinstance(v, str) else v


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "MeOut"


class SignupRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    _s = field_validator("business_name", "name")(_strip)


# ---------- Business ----------
class BusinessOut(ORM):
    id: int
    name: str
    created_at: UTCDateTime


class BusinessUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    _s = field_validator("name")(_strip)


# ---------- Invites ----------
class InviteCreate(BaseModel):
    role: Role = Role.STAFF
    email: EmailStr | None = None  # if set, only this email can accept
    days_valid: int = Field(default=7, ge=1, le=30)

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, v):
        return None if v in ("", None) else v


class InviteOut(ORM):
    id: int
    role: Role
    email: str | None
    created_at: UTCDateTime
    expires_at: UTCDateTime
    created_by: "UserBrief"


class InviteCreated(InviteOut):
    token: str  # shown once; only its hash is stored


class InvitePreview(BaseModel):
    business_name: str
    role: Role
    email: str | None
    expires_at: UTCDateTime


class InviteAccept(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    _s = field_validator("name")(_strip)


# ---------- Users ----------
class UserOut(ORM):
    id: int
    name: str
    email: str
    role: Role
    is_active: bool
    created_at: UTCDateTime


class MeOut(UserOut):
    business: BusinessOut


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.STAFF

    _s = field_validator("name")(_strip)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


# ---------- Categories ----------
class CategoryOut(ORM):
    id: int
    name: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    _s = field_validator("name")(_strip)


# ---------- Suppliers ----------
class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return _strip(v)

    @field_validator("contact_person", "phone", "address", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        v = _strip(v)
        return None if v == "" else v

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, v):
        return None if v in ("", None) else v


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, v):
        return None if v == "" else v


class SupplierBrief(ORM):
    id: int
    name: str
    is_active: bool


class SupplierOut(ORM):
    id: int
    name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    is_active: bool
    product_count: int = 0


class SupplierDeleteResult(BaseModel):
    action: str  # "deleted" | "deactivated"
    detail: str


# ---------- Products ----------
BARCODE_RE = re.compile(r"^[!-~]{3,64}$")  # printable ASCII, no spaces


def _clean_barcodes(v):
    if v is None:
        return v
    out: list[str] = []
    for raw in v:
        code = str(raw).strip()
        if not code:
            continue
        if not BARCODE_RE.match(code):
            raise ValueError(f"Barcode '{code}' must be 3-64 characters with no spaces")
        if code not in out:
            out.append(code)
    if len(out) > 10:
        raise ValueError("A product can have at most 10 barcodes")
    return out


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._\-]+$")
    name: str = Field(min_length=1, max_length=200)
    category_id: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    reorder_threshold: int = Field(ge=0, le=1_000_000)
    initial_stock: int = Field(default=0, ge=0, le=1_000_000)
    supplier_ids: list[int] = Field(default_factory=list)
    barcodes: list[str] = Field(default_factory=list)

    _b = field_validator("barcodes")(_clean_barcodes)

    @field_validator("sku", "name", mode="before")
    @classmethod
    def strip(cls, v):
        return _strip(v)

    @field_validator("sku")
    @classmethod
    def upper_sku(cls, v: str) -> str:
        return v.upper()


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._\-]+$")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: int | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    reorder_threshold: int | None = Field(default=None, ge=0, le=1_000_000)
    barcodes: list[str] | None = None

    _b = field_validator("barcodes")(_clean_barcodes)

    @field_validator("sku", mode="before")
    @classmethod
    def upper_sku(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class ProductSuppliersUpdate(BaseModel):
    supplier_ids: list[int]


class ProductOut(ORM):
    id: int
    sku: str
    name: str
    category: CategoryOut
    unit_price: Decimal
    reorder_threshold: int
    current_stock: int
    archived: bool
    low_stock: bool
    barcodes: list[str] = Field(default_factory=list, validation_alias="barcode_codes")
    suppliers: list[SupplierBrief] = []
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int


# ---------- Stock ----------
class MovementCreate(BaseModel):
    product_id: int = Field(gt=0)
    type: MovementType
    quantity: int = Field(gt=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=500)
    override: bool = False
    source: MovementSource = MovementSource.MANUAL


class UserBrief(ORM):
    id: int
    name: str
    role: Role


class ProductBrief(ORM):
    id: int
    sku: str
    name: str


class MovementOut(ORM):
    id: int
    product: ProductBrief
    user: UserBrief
    type: MovementType
    source: MovementSource
    quantity: int
    stock_after: int
    override: bool
    note: str | None
    created_at: UTCDateTime


class MovementResult(BaseModel):
    movement: MovementOut
    current_stock: int
    low_stock: bool


class MovementPage(BaseModel):
    items: list[MovementOut]
    total: int


# ---------- Dashboard / reports ----------
class DashboardSummary(BaseModel):
    active_products: int
    total_units: int
    stock_value: Decimal
    low_stock_count: int
    out_of_stock_count: int
    low_stock: list[ProductOut]
    recent_movements: list[MovementOut]


class StockReportRow(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    unit_price: Decimal
    reorder_threshold: int
    current_stock: int
    stock_value: Decimal
    low_stock: bool
    archived: bool
    qty_in: int
    qty_out: int
    movement_count: int


class StockReport(BaseModel):
    start: UTCDateTime
    end: UTCDateTime
    generated_at: UTCDateTime
    rows: list[StockReportRow]
    movements: list[MovementOut]
    totals: dict


TokenResponse.model_rebuild()
InviteOut.model_rebuild()
InviteCreated.model_rebuild()
