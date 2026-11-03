"""StockService: the single place stock levels change.

Implements the sequence diagram in SRS Appendix B.3:
  begin transaction -> SELECT ... FOR UPDATE on the product row
  -> negative-stock check (FR2.2) with admin-only override
  -> update current_stock + insert StockMovement (audit entry, FR7.1)
  -> commit, or roll back on any failure.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import MovementType, Product, Role, StockMovement, User


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

    def __init__(self, detail: str, available: int, requested: int, can_override: bool):
        super().__init__(detail)
        self.available = available
        self.requested = requested
        self.can_override = can_override


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
    quantity: int,
    note: str | None = None,
    override: bool = False,
    allow_archived: bool = False,
) -> MovementOutcome:
    if quantity <= 0:
        raise StockError("Quantity must be greater than zero")

    try:
        # Row lock: two simultaneous stock-outs cannot both consume the same units.
        product = db.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        ).scalar_one_or_none()

        if product is None:
            raise ProductNotFound("Product not found")
        if product.archived and not allow_archived:
            raise ProductArchived("Product is archived; restore it before recording stock")

        used_override = False
        if type_ == MovementType.OUT and product.current_stock - quantity < 0:
            is_admin = user.role == Role.ADMIN
            if not (is_admin and override):
                raise InsufficientStock(
                    f"Insufficient stock: {product.current_stock} available, {quantity} requested",
                    available=product.current_stock,
                    requested=quantity,
                    can_override=is_admin,
                )
            used_override = True

        product.apply_movement(type_, quantity)
        movement = StockMovement(
            product_id=product.id,
            user_id=user.id,
            type=type_,
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
