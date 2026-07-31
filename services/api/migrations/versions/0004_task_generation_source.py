"""Record whether a task was produced by AI or the deterministic fallback.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    task_columns = {column["name"] for column in inspector.get_columns("learning_tasks")}
    if "generation_source" not in task_columns:
        op.add_column(
            "learning_tasks",
            sa.Column("generation_source", sa.String(24), nullable=False, server_default="legacy"),
        )
    state_columns = {column["name"] for column in inspector.get_columns("curriculum_state")}
    if "target_stage" not in state_columns:
        op.add_column(
            "curriculum_state",
            sa.Column("target_stage", sa.String(40), nullable=False, server_default="foundation"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    state_columns = {column["name"] for column in inspector.get_columns("curriculum_state")}
    if "target_stage" in state_columns:
        op.drop_column("curriculum_state", "target_stage")
    task_columns = {column["name"] for column in inspector.get_columns("learning_tasks")}
    if "generation_source" in task_columns:
        op.drop_column("learning_tasks", "generation_source")
