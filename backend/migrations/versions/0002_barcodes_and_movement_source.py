"""barcodes and movement source

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-06 09:14:46.067747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('product_barcodes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_barcodes_code'), 'product_barcodes', ['code'], unique=True)
    op.create_index(op.f('ix_product_barcodes_product_id'), 'product_barcodes', ['product_id'], unique=False)
    op.add_column('stock_movements', sa.Column('source', sa.Enum('MANUAL', 'SCANNER', 'CAMERA', 'IMPORT', 'TILL', 'API', name='movement_source'), server_default='MANUAL', nullable=False))
    op.create_index(op.f('ix_stock_movements_source'), 'stock_movements', ['source'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_movements_source'), table_name='stock_movements')
    op.drop_column('stock_movements', 'source')
    op.drop_index(op.f('ix_product_barcodes_product_id'), table_name='product_barcodes')
    op.drop_index(op.f('ix_product_barcodes_code'), table_name='product_barcodes')
    op.drop_table('product_barcodes')
