"""Chainlit SQLAlchemyDataLayer Tabellen: users, threads, steps, elements, feedbacks."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Chainlit-Persistenz-Tabellen erstellen (camelCase-Spaltennamen beibehalten)."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            identifier  TEXT NOT NULL UNIQUE,
            "createdAt" TEXT,
            metadata    JSONB NOT NULL DEFAULT '{}'
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id               TEXT PRIMARY KEY,
            "createdAt"      TEXT,
            name             TEXT,
            "userId"         TEXT REFERENCES users(id) ON DELETE CASCADE,
            "userIdentifier" TEXT,
            tags             TEXT[],
            metadata         JSONB
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            type            TEXT NOT NULL,
            "threadId"      TEXT REFERENCES threads(id) ON DELETE CASCADE,
            "parentId"      TEXT,
            streaming       BOOLEAN NOT NULL DEFAULT FALSE,
            "waitForAnswer" BOOLEAN DEFAULT FALSE,
            "isError"       BOOLEAN DEFAULT FALSE,
            metadata        JSONB,
            tags            TEXT[],
            input           TEXT,
            output          TEXT,
            "createdAt"     TEXT,
            start           TEXT,
            "end"           TEXT,
            generation      JSONB,
            "showInput"     TEXT,
            language        TEXT,
            indent          INT
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS elements (
            id              TEXT PRIMARY KEY,
            "threadId"      TEXT REFERENCES threads(id) ON DELETE CASCADE,
            type            TEXT,
            "chainlitKey"   TEXT,
            url             TEXT,
            "objectKey"     TEXT,
            name            TEXT NOT NULL,
            display         TEXT,
            size            TEXT,
            language        TEXT,
            page            INT,
            "forId"         TEXT,
            mime            TEXT,
            props           JSONB
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id          TEXT PRIMARY KEY,
            "forId"     TEXT NOT NULL,
            "threadId"  TEXT REFERENCES threads(id) ON DELETE CASCADE,
            value       FLOAT NOT NULL,
            comment     TEXT
        );
    """)


def downgrade() -> None:
    """Chainlit-Tabellen in Abhaengigkeitsreihenfolge entfernen."""
    op.execute("DROP TABLE IF EXISTS feedbacks;")
    op.execute("DROP TABLE IF EXISTS elements;")
    op.execute("DROP TABLE IF EXISTS steps;")
    op.execute("DROP TABLE IF EXISTS threads;")
    op.execute("DROP TABLE IF EXISTS users;")
