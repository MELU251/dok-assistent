---
phase: 03-chat-history-and-multi-turn-context
plan: 02
subsystem: database
tags: [alembic, asyncpg, pgvector, migrations, postgresql, chainlit, sqlalchemy]

# Dependency graph
requires:
  - phase: 03-01
    provides: "Wave 0 stub tests and project structure for Phase 3"
provides:
  - "Alembic migration infrastructure (alembic.ini, env.py)"
  - "Baseline migration 0001: pgvector extension, document_chunks table, ivfflat index"
  - "Chainlit migration 0002: users, threads, steps, elements, feedbacks tables with camelCase columns"
  - "Settings.database_url (sync, postgresql://) for Alembic"
  - "Settings.async_database_url (postgresql+asyncpg://) for Chainlit SQLAlchemyDataLayer"
affects:
  - 03-03-chainlit-data-layer
  - 03-04-rag-pipeline-integration

# Tech tracking
tech-stack:
  added: [alembic>=1.13.0, asyncpg>=0.29.0, pgvector>=0.3.0]
  patterns:
    - "Hand-written migrations using op.execute() with IF NOT EXISTS guards — no autogenerate"
    - "pgvector Vector type registered via ischema_names in env.py to avoid type errors"
    - "Sync postgresql:// URL for Alembic engine, async postgresql+asyncpg:// for Chainlit"
    - "DATABASE_URL read directly from os.environ in alembic/env.py (not via Settings class)"

key-files:
  created:
    - alembic.ini
    - alembic/env.py
    - alembic/versions/0001_baseline.py
    - alembic/versions/0002_chainlit_tables.py
  modified:
    - requirements.txt
    - src/config.py
    - .env.example

key-decisions:
  - "Hand-written op.execute() migrations (not autogenerate) because pgvector vector() type is not natively understood by SQLAlchemy reflection"
  - "IF NOT EXISTS guards in all DDL statements — running alembic upgrade head on an existing DB with document_chunks is a no-op"
  - "Chainlit 2.10.0 requires exact camelCase column names (createdAt, userId, threadId, etc.) — snake_case causes 'column does not exist' at runtime"
  - "DATABASE_URL (sync) and ASYNC_DATABASE_URL (asyncpg) are separate env vars — Alembic cannot use asyncpg driver"
  - "Placeholder validator in Settings extended to reject template URLs for database_url and async_database_url"

patterns-established:
  - "Migration chain: 0001 (baseline infra) -> 0002 (application tables) — clear dependency ordering via down_revision"
  - "alembic/env.py uses load_dotenv() + os.environ directly, bypassing pydantic-settings to keep Alembic dependency-light"

requirements-completed: [CHAT-02]

# Metrics
duration: 4min
completed: 2026-03-17
---

# Phase 3 Plan 02: Alembic Migrations and DB URL Config Summary

**Alembic migration infrastructure with two hand-crafted migrations (pgvector baseline + Chainlit 5 camelCase tables) and asyncpg/sync URL settings in config.py**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T17:12:55Z
- **Completed:** 2026-03-17T17:16:35Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Alembic initialized with custom env.py that reads DATABASE_URL from .env and registers pgvector Vector type
- Migration 0001 creates pgvector extension, document_chunks table (vector(768)), and ivfflat index — all idempotent with IF NOT EXISTS
- Migration 0002 creates all 5 Chainlit SQLAlchemyDataLayer tables with exact quoted camelCase column names matching Chainlit 2.10.0 SQL queries
- Settings class extended with database_url and async_database_url fields, both with placeholder validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Install packages, init Alembic, write alembic.ini and env.py** - `8a3b707` (chore)
2. **Task 2: Write migration files and extend config.py** - `18797c5` (feat)

## Files Created/Modified
- `alembic.ini` - Alembic configuration with numeric file_template (%%(rev)s_%%(slug)s)
- `alembic/env.py` - Migration environment: loads DATABASE_URL from .env, registers pgvector, runs migrations online/offline
- `alembic/README` - Alembic scaffold file
- `alembic/script.py.mako` - Alembic revision template
- `alembic/versions/0001_baseline.py` - Baseline: pgvector extension + document_chunks table + ivfflat index
- `alembic/versions/0002_chainlit_tables.py` - Chainlit 5 tables with camelCase columns (users, threads, steps, elements, feedbacks)
- `requirements.txt` - Added alembic>=1.13.0, asyncpg>=0.29.0, pgvector>=0.3.0
- `src/config.py` - Added database_url and async_database_url fields with placeholder validation
- `.env.example` - Added DATABASE_URL and ASYNC_DATABASE_URL template entries with port 5432 note

## Decisions Made
- Hand-written op.execute() migrations chosen over autogenerate because SQLAlchemy cannot reflect pgvector vector() columns natively
- IF NOT EXISTS guards on all DDL so alembic upgrade head is safe to run against an existing DB that already has document_chunks from manual SQL
- Chainlit 2.10.0 requires exact camelCase column names in quoted identifiers — verified against SQLAlchemy data layer source
- Two separate DB URL env vars: DATABASE_URL (postgresql://) for synchronous Alembic engine, ASYNC_DATABASE_URL (postgresql+asyncpg://) for Chainlit async operations

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

**DATABASE_URL and ASYNC_DATABASE_URL must be added to .env before running migrations.**

Steps:
1. In Supabase: Project → Settings → Database → Connection string → URI (use port 5432, not 6543)
2. Copy the URI into .env as `DATABASE_URL=postgresql://postgres:PASSWORD@db.REF.supabase.co:5432/postgres`
3. Copy again with asyncpg scheme: `ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres`
4. Run: `alembic upgrade head` to create all tables

## Next Phase Readiness
- Alembic is ready: `alembic upgrade head` creates all required tables on a clean or existing DB
- Chainlit SQLAlchemyDataLayer can be wired up in Phase 3 Plan 03 using async_database_url
- No blockers — all migration infrastructure is in place

---
*Phase: 03-chat-history-and-multi-turn-context*
*Completed: 2026-03-17*
