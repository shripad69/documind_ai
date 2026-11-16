"""Add BM25 tsvector column and GIN index to document_chunks

Revision ID: 0002_add_bm25_tsvector
Revises: 0002_document_mindmap
Create Date: 2026-11-07
"""
from alembic import op

revision = "0002_add_bm25_tsvector"
down_revision = "0002_document_mindmap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add tsvector column to document_chunks
    op.execute("""
        ALTER TABLE document_chunks
        ADD COLUMN IF NOT EXISTS tsv_content tsvector;
    """)

    # 2. Backfill existing rows from content column
    op.execute("""
        UPDATE document_chunks
        SET tsv_content = to_tsvector('english', coalesce(content, ''))
        WHERE tsv_content IS NULL;
    """)

    # 3. Create GIN index for fast full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chunks_tsv_content_gin
        ON document_chunks
        USING gin (tsv_content);
    """)

    # 4. Create trigger function to auto-maintain tsv_content
    op.execute("""
        CREATE OR REPLACE FUNCTION document_chunks_tsv_update_trigger()
        RETURNS trigger AS $$
        BEGIN
            NEW.tsv_content := to_tsvector('english', coalesce(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    # 5. Attach trigger to document_chunks table
    op.execute("""
        DROP TRIGGER IF EXISTS trg_document_chunks_tsv_update ON document_chunks;
    """)
    op.execute("""
        CREATE TRIGGER trg_document_chunks_tsv_update
        BEFORE INSERT OR UPDATE OF content ON document_chunks
        FOR EACH ROW
        EXECUTE FUNCTION document_chunks_tsv_update_trigger();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_tsv_update ON document_chunks;")
    op.execute("DROP FUNCTION IF EXISTS document_chunks_tsv_update_trigger();")
    op.execute("DROP INDEX IF EXISTS ix_chunks_tsv_content_gin;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS tsv_content;")
