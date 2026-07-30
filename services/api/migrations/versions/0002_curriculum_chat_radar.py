"""Add curriculum task details, agent actions, and run metadata.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    task_columns = _column_names("learning_tasks")
    additions = (
        ("curriculum_version", sa.String(24), "legacy"),
        ("track_key", sa.String(40), "legacy"),
        ("stage_key", sa.String(40), "legacy"),
        ("node_key", sa.String(120), "legacy"),
        ("prerequisites", sa.JSON(), "[]"),
        ("deliverables", sa.JSON(), "[]"),
        ("acceptance_checks", sa.JSON(), "[]"),
        ("remediation_hint", sa.Text(), ""),
    )
    for name, column_type, default in additions:
        if name not in task_columns:
            op.add_column(
                "learning_tasks",
                sa.Column(name, column_type, nullable=False, server_default=default),
            )
    task_indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("learning_tasks")
    }
    if "ix_learning_tasks_node_key" not in task_indexes:
        op.create_index("ix_learning_tasks_node_key", "learning_tasks", ["node_key"])

    run_columns = _column_names("agent_runs")
    if "details" not in run_columns:
        op.add_column(
            "agent_runs",
            sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        )

    if "agent_actions" not in tables:
        op.create_table(
            "agent_actions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "session_id",
                sa.String(36),
                sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("action_type", sa.String(80), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_agent_actions_session_id", "agent_actions", ["session_id"])
        op.create_index("ix_agent_actions_action_type", "agent_actions", ["action_type"])
        op.create_index("ix_agent_actions_status", "agent_actions", ["status"])
        op.create_index("ix_agent_actions_expires_at", "agent_actions", ["expires_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "agent_actions" in inspector.get_table_names():
        op.drop_table("agent_actions")
    run_columns = _column_names("agent_runs")
    if "details" in run_columns:
        op.drop_column("agent_runs", "details")
    task_indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("learning_tasks")
    }
    if "ix_learning_tasks_node_key" in task_indexes:
        op.drop_index("ix_learning_tasks_node_key", table_name="learning_tasks")
    task_columns = _column_names("learning_tasks")
    for name in (
        "remediation_hint",
        "acceptance_checks",
        "deliverables",
        "prerequisites",
        "node_key",
        "stage_key",
        "track_key",
        "curriculum_version",
    ):
        if name in task_columns:
            op.drop_column("learning_tasks", name)
