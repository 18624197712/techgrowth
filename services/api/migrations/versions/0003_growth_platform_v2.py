"""Add growth platform v2 state.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "curriculum_state" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "curriculum_state",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("active_track_key", sa.String(40), nullable=False, server_default="java"),
            sa.Column("algorithm_days_per_week", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("catalog_version", sa.String(24), nullable=False, server_default="v2"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    if "curriculum_state" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("curriculum_state")
