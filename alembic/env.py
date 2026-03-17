"""Alembic Migrationsumgebung – liest DATABASE_URL aus .env."""

import os

from dotenv import load_dotenv
from sqlalchemy import pool
from alembic import context
from pgvector.sqlalchemy import Vector

load_dotenv()

# Synchrone Verbindung (postgresql://) fuer Alembic – NICHT asyncpg
DATABASE_URL = os.environ["DATABASE_URL"]

alembic_config = context.config
alembic_config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Migrationen im Offline-Modus ausfuehren (nur SQL-Ausgabe)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=None,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    """Migrationen mit gegebener Verbindung ausfuehren.

    Args:
        connection: Aktive SQLAlchemy-Verbindung.
    """
    # pgvector-Typ registrieren damit Alembic vector(768) kennt
    connection.dialect.ischema_names["vector"] = Vector
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrationen im Online-Modus gegen echte DB ausfuehren."""
    from sqlalchemy import create_engine

    engine = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        _do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
