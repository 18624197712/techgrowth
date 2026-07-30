"""Initial TechGrowth schema.

Revision ID: 0001
Revises:
Create Date: 2026-07-30
"""

from alembic import op

from techgrowth_api import models  # noqa: F401
from techgrowth_api.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
