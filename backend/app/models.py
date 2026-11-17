"""Persistent entities. Mirrors the class diagram in SRS Appendix B.1.

Multi-business (multi-tenant): every row belongs to one Business, and every
query is filtered by the signed-in user's business_id. Uniqueness rules
(SKU, barcode, category name) apply within a business, not across them.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Index,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Role(str, enum.Enum):
    SYSTEM_ADMIN = "SYSTEM_ADMIN"  # StockWise staff: oversees the platform, belongs to no business
    MANAGER = "MANAGER"            # runs one business: products, suppliers, reports, team
    STAFF = "STAFF"                # records stock in one business


BUSINESS_ROLES = (Role.MANAGER, Role.STAFF)


class Unit(str, enum.Enum):
    """How a product is counted and sold (SI symbols). Pieces are whole numbers;
    weight, volume and length allow decimals, so loose (kadogo) sales can be recorded."""

    PIECE = "PIECE"
    KG = "KG"
    G = "G"
    L = "L"
    ML = "ML"
    M = "M"

    @property
    def symbol(self) -> str:
        return UNIT_SYMBOLS[self]

    @property
    def whole_only(self) -> bool:
        return self is Unit.PIECE


UNIT_SYMBOLS = {Unit.PIECE: "pc", Unit.KG: "kg", Unit.G: "g", Unit.L: "L", Unit.ML: "mL", Unit.M: "m"}
QTY = Numeric(12, 3)  # up to 999,999,999.999 in the product's unit


def fmt_qty(q) -> str:
    """12.500 -> '12.5', 24.000 -> '24'."""
    d = Decimal(q).normalize()
    return f"{d:f}" if d != d.to_integral() else str(int(d))


class MovementType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class MovementSource(str, enum.Enum):
    """How a movement entered the system. Every channel feeds the same StockService."""

    MANUAL = "MANUAL"    # typed into a form
    SCANNER = "SCANNER"  # USB/Bluetooth barcode scanner
    CAMERA = "CAMERA"    # phone/tablet camera scan in the browser
    IMPORT = "IMPORT"    # spreadsheet import (reserved, Phase 2)
    TILL = "TILL"        # point-of-sale integration (reserved, Phase 2)
    API = "API"          # other systems (reserved)


class Business(Base):
    """A shop using StockWise. Like a Slack workspace: its data is private to its members."""

    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


def _business_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"), index=True)


# Association table resolving Product <-> Supplier many-to-many (ProductSupplier).
product_suppliers = Table(
    "product_suppliers",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("supplier_id", ForeignKey("suppliers.id", ondelete="RESTRICT"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    # System admins belong to no business; everyone else belongs to exactly one.
    __table_args__ = (
        CheckConstraint(
            "(role = 'SYSTEM_ADMIN' AND business_id IS NULL) OR "
            "(role <> 'SYSTEM_ADMIN' AND business_id IS NOT NULL)",
            name="ck_users_role_business",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    # Globally unique: one account belongs to exactly one business.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), default=Role.STAFF)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    business: Mapped[Business | None] = relationship()
    movements: Mapped[list[StockMovement]] = relationship(back_populates="user")

    def has_role(self, role: Role) -> bool:
        return self.role == role


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_categories_business_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = _business_fk()
    name: Mapped[str] = mapped_column(String(100))

    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("business_id", "sku", name="uq_products_business_sku"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = _business_fk()
    sku: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit: Mapped[Unit] = mapped_column(Enum(Unit, name="unit"), default=Unit.PIECE, server_default=Unit.PIECE.value)
    reorder_threshold: Mapped[Decimal] = mapped_column(QTY, default=0)
    current_stock: Mapped[Decimal] = mapped_column(QTY, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    category: Mapped[Category] = relationship(back_populates="products")
    suppliers: Mapped[list[Supplier]] = relationship(
        secondary=product_suppliers, back_populates="products"
    )
    movements: Mapped[list[StockMovement]] = relationship(back_populates="product")
    barcodes: Mapped[list[ProductBarcode]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductBarcode.id"
    )

    @property
    def barcode_codes(self) -> list[str]:
        return [b.code for b in self.barcodes]

    def is_low_stock(self) -> bool:
        """FR5.1: low when current stock <= reorder threshold."""
        return self.current_stock <= self.reorder_threshold

    @property
    def low_stock(self) -> bool:
        return self.is_low_stock()

    def apply_movement(self, type_: MovementType, qty: Decimal) -> None:
        self.current_stock += qty if type_ == MovementType.IN else -qty


class ProductBarcode(Base):
    """A product can carry several barcodes (e.g. single unit and carton)."""

    __tablename__ = "product_barcodes"
    __table_args__ = (UniqueConstraint("business_id", "code", name="uq_product_barcodes_business_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Same as the product's business; stored so a barcode is unique within a business.
    business_id: Mapped[int] = _business_fk()
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), index=True)

    product: Mapped[Product] = relationship(back_populates="barcodes")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = _business_fk()
    name: Mapped[str] = mapped_column(String(200))
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    products: Mapped[list[Product]] = relationship(
        secondary=product_suppliers, back_populates="suppliers"
    )

    @property
    def product_count(self) -> int:
        return len(self.products)

    def can_be_deleted(self) -> bool:
        """FR3.1: only a supplier with no linked products may be hard-deleted."""
        return len(self.products) == 0


class StockMovement(Base):
    """Immutable stock event; doubles as the audit trail (FR7.1)."""

    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_business_created", "business_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Same as the product's business; stored so audit queries filter without a join.
    # (Indexed by ix_stock_movements_business_created.)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"))
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    type: Mapped[MovementType] = mapped_column(Enum(MovementType, name="movement_type"))
    source: Mapped[MovementSource] = mapped_column(
        Enum(MovementSource, name="movement_source"),
        default=MovementSource.MANUAL,
        server_default=MovementSource.MANUAL.value,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(QTY)
    stock_after: Mapped[Decimal] = mapped_column(QTY)
    override: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    product: Mapped[Product] = relationship(back_populates="movements")
    user: Mapped[User] = relationship(back_populates="movements")


class Invite(Base):
    """A one-time link a manager shares so a new member can join their business."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = _business_fk()
    # Only the SHA-256 of the token is stored; the token itself is shown once to the manager.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), default=Role.STAFF)  # MANAGER or STAFF
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    business: Mapped[Business] = relationship()
    created_by: Mapped[User] = relationship()

    def is_usable(self, now: datetime) -> bool:
        return self.accepted_at is None and self.revoked_at is None and now < self.expires_at


class ActivityLog(Base):
    """Who changed what, with before/after values (like Zoho / Google Workspace admin logs).

    Stock movements keep their own audit trail (FR7.1); this log covers everything else:
    products, suppliers, categories, users, invites and business settings. Entries are
    never edited or deleted. Actions a System Admin takes on a business are logged against
    that business, so its managers can see them.
    """

    __tablename__ = "activity_logs"
    __table_args__ = (Index("ix_activity_business_created", "business_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL for platform-level entries (e.g. a System Admin account being created).
    business_id: Mapped[int | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=True
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    # Copied at the time, so the entry still reads correctly if the person is renamed later.
    actor_name: Mapped[str] = mapped_column(String(120))
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(40))        # e.g. product.updated
    entity_type: Mapped[str] = mapped_column(String(20))   # product, supplier, user, ...
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(String(255))
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {field: [before, after]}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    actor: Mapped[User | None] = relationship()
