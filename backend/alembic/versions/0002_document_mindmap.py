"""Create document mindmap table.

Revision ID: 0002_document_mindmap
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_document_mindmap"
down_revision = "0001_workspace_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_mindmaps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("tree_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index("ix_mindmaps_tenant_scope", "document_mindmaps", ["user_id", "workspace_id", "document_id"])
    op.create_index("ix_document_mindmaps_user_id", "document_mindmaps", ["user_id"])
    op.create_index("ix_document_mindmaps_workspace_id", "document_mindmaps", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_document_mindmaps_workspace_id", table_name="document_mindmaps")
    op.drop_index("ix_document_mindmaps_user_id", table_name="document_mindmaps")
    op.drop_index("ix_mindmaps_tenant_scope", table_name="document_mindmaps")
    op.drop_table("document_mindmaps")
