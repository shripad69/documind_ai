"""Create workspace RAG schema.

Revision ID: 0001_workspace_platform
"""
from alembic import op

from app.db import Base
from app.models import entities  # noqa: F401

revision = "0001_workspace_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
