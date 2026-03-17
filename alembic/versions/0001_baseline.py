"""Baseline: document_chunks-Tabelle mit pgvector-Extension und ivfflat-Index."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """pgvector-Extension, document_chunks-Tabelle und Index erstellen."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   TEXT NOT NULL DEFAULT 'default',
            source      TEXT NOT NULL,
            page        INT,
            content     TEXT NOT NULL,
            embedding   vector(768),
            created_at  TIMESTAMPTZ DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)


def downgrade() -> None:
    """document_chunks-Tabelle entfernen."""
    op.execute("DROP TABLE IF EXISTS document_chunks;")
