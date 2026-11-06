"""businesses and invites (multi-business)

Every row now belongs to a business. Existing data from a single-shop
install is moved into one business, so nothing is lost on upgrade.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = ["users", "categories", "products", "product_barcodes", "suppliers", "stock_movements"]
DEFAULT_BUSINESS_NAME = "My Business"


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("role", sa.Enum("ADMIN", "STAFF", name="role"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_invites_business_id", "invites", ["business_id"])

    # 1. Add business_id (nullable for now).
    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("business_id", sa.Integer(), nullable=True))

    # 2. Move any existing single-shop data into one business.
    conn = op.get_bind()
    has_data = any(
        conn.execute(sa.text(f"SELECT 1 FROM {t} LIMIT 1")).first()
        for t in ("users", "categories", "products", "suppliers")
    )
    if has_data:
        conn.execute(
            sa.text("INSERT INTO businesses (name, is_active, created_at) VALUES (:n, 1, UTC_TIMESTAMP())"),
            {"n": DEFAULT_BUSINESS_NAME},
        )
        bid = conn.execute(sa.text("SELECT MAX(id) FROM businesses")).scalar()
        for table in TENANT_TABLES:
            conn.execute(sa.text(f"UPDATE {table} SET business_id = :b"), {"b": bid})

    # 3. Require it, and make uniqueness per business.
    for table in TENANT_TABLES:
        op.alter_column(table, "business_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(f"fk_{table}_business", table, "businesses", ["business_id"], ["id"], ondelete="RESTRICT")
    for table in ("users", "categories", "products", "product_barcodes", "suppliers"):
        op.create_index(f"ix_{table}_business_id", table, ["business_id"])
    op.create_index("ix_stock_movements_business_created", "stock_movements", ["business_id", "created_at"])

    op.drop_index("name", table_name="categories")
    op.create_unique_constraint("uq_categories_business_name", "categories", ["business_id", "name"])

    op.drop_index("ix_products_sku", table_name="products")
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_unique_constraint("uq_products_business_sku", "products", ["business_id", "sku"])

    op.drop_index("ix_product_barcodes_code", table_name="product_barcodes")
    op.create_index("ix_product_barcodes_code", "product_barcodes", ["code"])
    op.create_unique_constraint("uq_product_barcodes_business_code", "product_barcodes", ["business_id", "code"])


def downgrade() -> None:
    # Only meaningful while a single business exists. MySQL needs the foreign keys
    # dropped before the indexes they use.
    for table in TENANT_TABLES:
        op.drop_constraint(f"fk_{table}_business", table, type_="foreignkey")

    op.drop_constraint("uq_product_barcodes_business_code", "product_barcodes", type_="unique")
    op.drop_index("ix_product_barcodes_code", table_name="product_barcodes")
    op.create_index("ix_product_barcodes_code", "product_barcodes", ["code"], unique=True)
    op.drop_constraint("uq_products_business_sku", "products", type_="unique")
    op.drop_index("ix_products_sku", table_name="products")
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
    op.drop_constraint("uq_categories_business_name", "categories", type_="unique")
    op.create_index("name", "categories", ["name"], unique=True)

    op.drop_index("ix_stock_movements_business_created", table_name="stock_movements")
    for table in ("users", "categories", "products", "product_barcodes", "suppliers"):
        op.drop_index(f"ix_{table}_business_id", table_name=table)
    for table in TENANT_TABLES:
        op.drop_column(table, "business_id")

    op.drop_table("invites")  # also drops its indexes
    op.drop_table("businesses")
