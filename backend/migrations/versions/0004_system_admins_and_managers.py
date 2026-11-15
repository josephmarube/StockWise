"""system admins, managers and the activity log

Roles become SYSTEM_ADMIN (platform staff, no business), MANAGER (runs one
business; previously ADMIN) and STAFF. Existing ADMIN accounts and invites
become MANAGER. Adds activity_logs (who changed what, before/after).

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = sa.Enum("ADMIN", "STAFF", name="role")
BRIDGE = sa.Enum("ADMIN", "SYSTEM_ADMIN", "MANAGER", "STAFF", name="role")
NEW = sa.Enum("SYSTEM_ADMIN", "MANAGER", "STAFF", name="role")
CHECK = (
    "(role = 'SYSTEM_ADMIN' AND business_id IS NULL) OR "
    "(role <> 'SYSTEM_ADMIN' AND business_id IS NOT NULL)"
)


def upgrade() -> None:
    for table in ("users", "invites"):
        op.alter_column(table, "role", existing_type=OLD, type_=BRIDGE, existing_nullable=False)
        op.execute(sa.text(f"UPDATE {table} SET role = 'MANAGER' WHERE role = 'ADMIN'"))
        op.alter_column(table, "role", existing_type=BRIDGE, type_=NEW, existing_nullable=False)

    # System admins have no business. MySQL needs the FK dropped to change the column.
    op.drop_constraint("fk_users_business", "users", type_="foreignkey")
    op.alter_column("users", "business_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key("fk_users_business", "users", "businesses", ["business_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_users_role_business", "users", CHECK)

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sa.String(length=120), nullable=False),
        sa.Column("actor_role", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_business_created", "activity_logs", ["business_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_business_created", table_name="activity_logs")
    op.drop_table("activity_logs")
    op.execute(sa.text("DELETE FROM users WHERE role = 'SYSTEM_ADMIN'"))
    op.drop_constraint("ck_users_role_business", "users", type_="check")
    op.drop_constraint("fk_users_business", "users", type_="foreignkey")
    op.alter_column("users", "business_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key("fk_users_business", "users", "businesses", ["business_id"], ["id"], ondelete="RESTRICT")
    for table in ("users", "invites"):
        op.alter_column(table, "role", existing_type=NEW, type_=BRIDGE, existing_nullable=False)
        op.execute(sa.text(f"UPDATE {table} SET role = 'ADMIN' WHERE role = 'MANAGER'"))
        op.alter_column(table, "role", existing_type=BRIDGE, type_=OLD, existing_nullable=False)
