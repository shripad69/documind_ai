"""Expand vector dimension from 384 to 1024 for BAAI/bge-m3.

Revision ID: 0003_vector_dim_1024
Revises: 0002_add_bm25_tsvector
Create Date: 2026-11-15
"""
from alembic import op

revision = "0003_vector_dim_1024"
down_revision = "0002_add_bm25_tsvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop existing HNSW index (cannot ALTER vector column dimension with active index)
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw;")

    # 2. Clear existing document chunks and cached mind maps (384-d vectors cannot be cast to 1024-d)
    op.execute("DELETE FROM document_chunks;")
    op.execute("DELETE FROM document_mindmaps;")

    # 3. Alter vector column to 1024 dimensions
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024);")

    # 4. Rebuild HNSW vector index with 1024 dimensions
    op.execute("""
        CREATE INDEX ix_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # 5. Mark all indexed documents as processing for re-indexing
    op.execute("""
        UPDATE documents
        SET status = 'processing', indexed_at = NULL, error_message = NULL
        WHERE status = 'indexed';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw;")
    op.execute("DELETE FROM document_chunks;")
    op.execute("DELETE FROM document_mindmaps;")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(384);")
    op.execute("""
        CREATE INDEX ix_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    op.execute("""
        UPDATE documents
        SET status = 'processing', indexed_at = NULL, error_message = NULL
        WHERE status = 'indexed';
    """)
