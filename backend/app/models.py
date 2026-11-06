"""Persistent entities. Mirrors the class diagram in SRS Appendix B.1."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    STAFF = "STAFF"


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


# Association table resolving Product <-> Supplier many-to-many (ProductSupplier).
product_suppliers = Table(
    "product_suppliers",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("supplier_id", ForeignKey("suppliers.id", ondelete="RESTRICT"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), default=Role.STAFF)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    movements: Mapped[list[StockMovement]] = relationship(back_populates="user")

    def has_role(self, role: Role) -> bool:
        return self.role == role


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reorder_threshold: Mapped[int] = mapped_column(Integer, default=0)
    current_stock: Mapped[int] = mapped_column(Integer, default=0)
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

    def apply_movement(self, type_: MovementType, qty: int) -> None:
        self.current_stock += qty if type_ == MovementType.IN else -qty


class ProductBarcode(Base):
    """A product can carry several barcodes (e.g. single unit and carton)."""

    __tablename__ = "product_barcodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    product: Mapped[Product] = relationship(back_populates="barcodes")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
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

    id: Mapped[int] = mapped_column(primary_key=True)
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
    quantity: Mapped[int] = mapped_column(Integer)
    stock_after: Mapped[int] = mapped_column(Integer)
    override: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    product: Mapped[Product] = relationship(back_populates="movements")
    user: Mapped[User] = relationship(back_populates="movements")
