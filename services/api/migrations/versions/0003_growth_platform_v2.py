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
    task_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("learning_tasks")
    }
    additions = (
        ("task_kind", sa.String(24), "coding"),
        ("learning_objectives", sa.JSON(), "[]"),
        ("theory_brief", sa.Text(), ""),
        ("problem_statement", sa.Text(), ""),
        ("constraints", sa.JSON(), "[]"),
        ("starter_context", sa.Text(), ""),
        ("hints", sa.JSON(), "[]"),
        ("revealed_hint_level", sa.Integer(), "0"),
        ("solution_outline", sa.Text(), ""),
        ("regeneration_reason", sa.Text(), ""),
    )
    for name, column_type, default in additions:
        if name not in task_columns:
            op.add_column(
                "learning_tasks",
                sa.Column(name, column_type, nullable=False, server_default=default),
            )
    if "solution_revealed_at" not in task_columns:
        op.add_column(
            "learning_tasks", sa.Column("solution_revealed_at", sa.DateTime(timezone=True))
        )
    if "replaces_task_id" not in task_columns:
        op.add_column(
            "learning_tasks",
            sa.Column(
                "replaces_task_id",
                sa.String(36),
                sa.ForeignKey("learning_tasks.id", ondelete="SET NULL"),
            ),
        )
        op.create_index(
            "ix_learning_tasks_replaces_task_id", "learning_tasks", ["replaces_task_id"]
        )
    if "regeneration_key" not in task_columns:
        op.add_column(
            "learning_tasks", sa.Column("regeneration_key", sa.String(120), nullable=True)
        )
        op.create_unique_constraint(
            "uq_learning_tasks_regeneration_key", "learning_tasks", ["regeneration_key"]
        )
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
    repository_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("repositories")
    }
    repository_additions = (
        ("provider_id", sa.String(120), True, None),
        ("canonical_remote", sa.String(500), True, None),
        ("local_fingerprint", sa.String(300), False, ""),
        ("match_status", sa.String(24), False, "unmatched"),
    )
    for name, column_type, nullable, default in repository_additions:
        if name not in repository_columns:
            op.add_column(
                "repositories",
                sa.Column(
                    name,
                    column_type,
                    nullable=nullable,
                    server_default=default,
                ),
            )
            op.create_index(f"ix_repositories_{name}", "repositories", [name])


def downgrade() -> None:
    repository_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("repositories")
    }
    for name in ("match_status", "local_fingerprint", "canonical_remote", "provider_id"):
        if name in repository_columns:
            op.drop_index(f"ix_repositories_{name}", table_name="repositories")
            op.drop_column("repositories", name)
    if "curriculum_state" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("curriculum_state")
    task_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("learning_tasks")
    }
    if "regeneration_key" in task_columns:
        op.drop_constraint("uq_learning_tasks_regeneration_key", "learning_tasks", type_="unique")
    for name in (
        "regeneration_key",
        "regeneration_reason",
        "replaces_task_id",
        "solution_revealed_at",
        "solution_outline",
        "revealed_hint_level",
        "hints",
        "starter_context",
        "constraints",
        "problem_statement",
        "theory_brief",
        "learning_objectives",
        "task_kind",
    ):
        if name in task_columns:
            op.drop_column("learning_tasks", name)
