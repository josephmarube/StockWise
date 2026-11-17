"""StockService: the single place stock levels change.

Implements the sequence diagram in SRS Appendix B.3:
  begin transaction -> SELECT ... FOR UPDATE on the product row
  -> negative-stock check (FR2.2) with admin-only override
  -> update current_stock + insert StockMovement (audit entry, FR7.1)
  -> commit, or roll back on any failure.
"""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import MovementSource, MovementType, Product, Role, StockMovement, User, fmt_qty


class StockError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class ProductNotFound(StockError):
    status_code = 404


class ProductArchived(StockError):
    status_code = 409


class InsufficientStock(StockError):
    status_code = 409

    def __init__(self, detail: str, available: Decimal, requested: Decimal, can_override: bool):
        super().__init__(detail)
        self.available = available
        self.requested = requested
        self.can_override = can_override


class InvalidQuantity(StockError):
    status_code = 422


class StockPersistenceError(StockError):
    status_code = 500


@dataclass
class MovementOutcome:
    movement: StockMovement
    current_stock: int
    low_stock: bool


def record_movement(
    db: Session,
    *,
    user: User,
    product_id: int,
    type_: MovementType,
    quantity: Decimal | int,
    note: str | None = None,
    override: bool = False,
    allow_archived: bool = False,
    source: MovementSource = MovementSource.MANUAL,
) -> MovementOutcome:
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise StockError("Quantity must be greater than zero")

    try:
        # Row lock: two simultaneous stock-outs cannot both consume the same units.
        product = db.execute(
            select(Product)
            .where(Product.id == product_id, Product.business_id == user.business_id)
            .with_for_update()
        ).scalar_one_or_none()

        if product is None:
            raise ProductNotFound("Product not found")
        if product.archived and not allow_archived:
            raise ProductArchived("Product is archived; restore it before recording stock")
        if product.unit.whole_only and quantity != quantity.to_integral_value():
            raise InvalidQuantity(f"{product.name} is counted in pieces, so use a whole number")

        used_override = False
        if type_ == MovementType.OUT and product.current_stock - quantity < 0:
            is_admin = user.role == Role.MANAGER
            if not (is_admin and override):
                u = "" if product.unit.whole_only else f" {product.unit.symbol}"
                raise InsufficientStock(
                    f"Insufficient stock: {fmt_qty(product.current_stock)}{u} available, "
                    f"{fmt_qty(quantity)}{u} requested",
                    available=product.current_stock,
                    requested=quantity,
                    can_override=is_admin,
                )
            used_override = True

        product.apply_movement(type_, quantity)
        movement = StockMovement(
            business_id=product.business_id,
            product_id=product.id,
            user_id=user.id,
            type=type_,
            source=source,
            quantity=quantity,
            stock_after=product.current_stock,
            override=used_override,
            note=(note or "").strip() or None,
        )
        db.add(movement)
        db.commit()
    except StockError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise StockPersistenceError("Could not save the stock movement; no data was changed") from exc

    db.refresh(movement)
    return MovementOutcome(
        movement=movement,
        current_stock=product.current_stock,
        low_stock=product.is_low_stock(),
    )
