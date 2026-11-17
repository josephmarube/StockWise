"""units of measure and decimal quantities

Each product gets a unit (piece, kg, g, L, mL, m). Quantities become DECIMAL(12,3)
so weighed and measured goods can be sold in small amounts. Existing products
become pieces and keep their whole-number stock.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNIT = sa.Enum("PIECE", "KG", "G", "L", "ML", "M", name="unit")
QTY = sa.Numeric(12, 3)
COLUMNS = [("products", "reorder_threshold"), ("products", "current_stock"),
           ("stock_movements", "quantity"), ("stock_movements", "stock_after")]


def upgrade() -> None:
    op.add_column("products", sa.Column("unit", UNIT, nullable=False, server_default="PIECE"))
    for table, col in COLUMNS:
        op.alter_column(table, col, existing_type=sa.Integer(), type_=QTY, existing_nullable=False)


def downgrade() -> None:
    # Rounds any fractional quantities to whole numbers.
    for table, col in COLUMNS:
        op.alter_column(table, col, existing_type=QTY, type_=sa.Integer(), existing_nullable=False)
    op.drop_column("products", "unit")
