# Phase 3: Chat History and Multi-Turn Context - Research

**Researched:** 2026-03-17
**Domain:** Chainlit 2.x data persistence, Alembic/SQLAlchemy migrations, LangChain conversation history, pgvector source filtering
**Confidence:** HIGH (most findings verified against installed packages and live source inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Alembic + SQLAlchemy** als Migration- und ORM-Stack (kein Prisma, kein Liquibase)
- Ziel: `alembic upgrade head` auf neuer DB = vollstaendiges Schema, kein manuelles SQL
- **Baseline-Migration** fuer bestehendes `document_chunks`-Schema (inkl. pgvector-Extension + ivfflat-Index)
- **Neue Migration** fuer `chat_sessions`-Tabelle
- **Neue Migration** fuer `chat_messages`-Tabelle
- Bestehender Supabase-Python-Client-Code (ingest.py, retrieval.py) bleibt **unangetastet**
- SQLAlchemy nur fuer neue Chat-Tabellen als Query-Layer verwenden
- Chat-Sessions und Nachrichten in Supabase persistieren (gleiche DB)
- Chainlit-Session-Lifecycle als Trigger fuer Session-Erstellung

### Claude's Discretion
- Konkrete Implementierung: LangChain Memory-Klasse vs. manuell
- Chainlit-UI-Mechanismus fuer Dokument-Filter (Dropdown, `/`-Befehl, etc.)

### Deferred Ideas (OUT OF SCOPE)
- Multi-Tenant-Session-Isolation (Phase 4+ oder SaaS-Milestone)
- Volltextsuche ueber Chat-Historie
- Chat-Export-Funktion
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CHAT-01 | Im laufenden Gespraech kennt die KI die letzten 3 Gespraechs-Turns (6 Messages) als Kontext — Folgefragen werden korrekt beantwortet | LangChain `InMemoryChatMessageHistory` + manual slice of last 6 messages injected into Claude API call; `cl.user_session` holds the history object per-session |
| CHAT-02 | Nutzer sieht nach dem Login eine Liste seiner frueheren Chat-Sessions und kann eine davon wieder oeffnen (persistiert in Supabase) | Chainlit 2.10.0 `SQLAlchemyDataLayer` with `@cl.data_layer` decorator + `@cl.on_chat_resume` hook; requires 5 tables: users, threads, steps, elements, feedbacks |
| CHAT-03 | Nutzer kann Fragen auf ein bestimmtes hochgeladenes Dokument eingrenzen (Filter in der UI, der `source` an `retrieval.search()` weitergibt) | Add optional `source_filter: str | None` param to `search()`; post-filter RPC results by source field OR pass source in RPC filter dict; `/filter [filename]` command is the simplest UI approach |
</phase_requirements>

---

## Summary

Phase 3 has three distinct technical sub-problems that each require different solutions. CHAT-01 (multi-turn context) is the simplest: inject a window of previous messages into the existing Anthropic Claude API call. The `pipeline.answer()` function already sends `messages=[{"role": "user", "content": prompt}]` — this just needs to become a proper multi-turn message list. No LangChain memory classes are needed; the Anthropic SDK directly supports `messages=[...]` with alternating `user`/`assistant` turns. Store the running history in `cl.user_session` per Chainlit session.

CHAT-02 (persistent sessions) is the most architecturally significant change. Chainlit 2.10.0 ships a production-ready `SQLAlchemyDataLayer` (verified by source inspection) that manages threads, steps, users, elements, and feedbacks via 5 SQL tables. Registering it with `@cl.data_layer` gives the sidebar thread history UI automatically. The tables must be created in Supabase before the app starts — this is where Alembic comes in. The complication: Chainlit's `SQLAlchemyDataLayer` uses raw SQL against these 5 tables with **camelCase quoted column names** (e.g., `"createdAt"`, `"userId"`, `"threadId"`). These tables must be created by an Alembic migration matching Chainlit's exact schema.

CHAT-03 (document filter) requires a small extension to `retrieval.search()`. The `source` field is a direct TEXT column in `document_chunks` (not in JSONB metadata), so it cannot be filtered through the existing `match_document_chunks` RPC `filter` dict. The cleanest PoC approach is post-filtering: call the RPC with `match_count` larger than needed, then filter Python-side by source. This keeps the Supabase-side code untouched.

**Primary recommendation:** Use Chainlit's built-in `SQLAlchemyDataLayer` for CHAT-02 (do not build a custom data layer). Use manual message list injection (not LangChain Memory classes) for CHAT-01 since the project uses the raw Anthropic SDK. Use `/filter [filename]` command for CHAT-03 UI.

---

## Standard Stack

### Core (all already in requirements.txt except alembic, pgvector, asyncpg)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chainlit | 2.10.0 (installed) | Chat UI + data persistence hooks | Already installed; includes `SQLAlchemyDataLayer` |
| sqlalchemy | 2.0.48 (installed) | ORM base for Alembic migrations | Already installed; Alembic requires it |
| alembic | 1.18.4 (latest, not yet installed) | Database migrations | Standard Python migration tool for SQLAlchemy |
| asyncpg | latest | Async PostgreSQL driver for Chainlit SQLAlchemyDataLayer | Required by `create_async_engine` in SQLAlchemyDataLayer |
| pgvector | latest | Registers `vector` type with SQLAlchemy for Alembic reflection | Required so `alembic check` does not fail on the vector column |

### New Dependencies Required

```bash
pip install alembic asyncpg pgvector
```

Add to requirements.txt:
```
alembic>=1.13.0
asyncpg>=0.29.0
pgvector>=0.3.0
```

**Note:** `alembic` is not currently installed (verified). `asyncpg` and `pgvector` are also not installed. All three are needed before Phase 3 can run.

---

## Architecture Patterns

### Recommended Project Structure

```
dok-assistent/
├── alembic.ini                    # Alembic configuration
├── alembic/
│   ├── env.py                     # Migration environment (reads .env)
│   └── versions/
│       ├── 0001_baseline.py       # document_chunks + pgvector extension
│       ├── 0002_chat_sessions.py  # Chainlit users + threads tables
│       └── 0003_chat_steps.py     # Chainlit steps + elements + feedbacks tables
├── src/
│   ├── history.py                 # NEW: conversation history helpers
│   └── ... (existing, untouched)
└── app.py                         # Updated: add @cl.data_layer, @cl.on_chat_resume
```

### Pattern 1: Alembic env.py Reading from .env

The `env.py` must load the database URL from `.env` (not hardcode it). Supabase requires the **direct connection** (port 5432, not pgbouncer port 6543) for migrations. Alembic also needs `pgvector` registered in `ischema_names` so it does not fail when reflecting the `vector(768)` column type.

```python
# alembic/env.py
import os
from dotenv import load_dotenv
from sqlalchemy import pool
from alembic import context
from pgvector.sqlalchemy import Vector  # registers the type

load_dotenv()

# Direct connection (NOT pgbouncer) for migrations
# Format: postgresql://postgres:[PWD]@db.[REF].supabase.co:5432/postgres
DATABASE_URL = os.environ["DATABASE_URL"]  # Sync URL for migrations

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

def run_migrations_offline():
    context.configure(url=DATABASE_URL, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    # Register pgvector type so Alembic does not choke on vector(768)
    connection.dialect.ischema_names["vector"] = Vector
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from sqlalchemy import create_engine
    engine = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Key:** Use `target_metadata=None` because migrations are hand-written (baseline pattern), not autogenerated from models. The `NullPool` prevents connection leaks during migration runs.

### Pattern 2: Baseline Migration for document_chunks

The baseline migration captures the existing schema so `alembic upgrade head` on a new DB creates everything. It uses `op.execute()` for raw SQL (pgvector extension, ivfflat index) because Alembic's standard `op.create_table()` does not support the `VECTOR` column type without additional setup.

```python
# alembic/versions/0001_baseline.py
"""Baseline: document_chunks with pgvector extension and ivfflat index."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
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

def downgrade():
    op.execute("DROP TABLE IF EXISTS document_chunks;")
```

**Important:** Use `IF NOT EXISTS` throughout the baseline so running it against an existing DB (with the table already present) is a no-op. This is the standard baseline pattern for existing databases.

### Pattern 3: Chainlit Tables Migration

`SQLAlchemyDataLayer` expects these 5 tables with **exact camelCase quoted column names**. This was verified by inspecting the installed Chainlit 2.10.0 source code.

```python
# alembic/versions/0002_chainlit_tables.py
"""Chainlit SQLAlchemyDataLayer tables: users, threads, steps, elements, feedbacks."""
from alembic import op

revision = "0002"
down_revision = "0001"

def upgrade():
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
            id              TEXT PRIMARY KEY,
            "createdAt"     TEXT,
            name            TEXT,
            "userId"        TEXT REFERENCES users(id) ON DELETE CASCADE,
            "userIdentifier" TEXT,
            tags            TEXT[],
            metadata        JSONB
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

def downgrade():
    op.execute("DROP TABLE IF EXISTS feedbacks;")
    op.execute("DROP TABLE IF EXISTS elements;")
    op.execute("DROP TABLE IF EXISTS steps;")
    op.execute("DROP TABLE IF EXISTS threads;")
    op.execute("DROP TABLE IF EXISTS users;")
```

**Source:** Column names and table relationships verified by inspecting `chainlit.data.sql_alchemy.SQLAlchemyDataLayer` source (Chainlit 2.10.0 installed in this project).

### Pattern 4: Registering the Data Layer in app.py

```python
# In app.py — add BEFORE the existing @cl.on_chat_start decorator
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from src.config import get_settings

@cl.data_layer
def get_data_layer():
    """Chainlit-Datenpersistenz via SQLAlchemy (Supabase PostgreSQL)."""
    settings = get_settings()
    return SQLAlchemyDataLayer(
        conninfo=settings.database_url,   # postgresql+asyncpg://...
        ssl_require=True,
    )
```

**Critical detail:** The `conninfo` must use the `postgresql+asyncpg://` scheme. `SQLAlchemyDataLayer` calls `create_async_engine()` internally, which requires asyncpg. A new setting `database_url` must be added to `config.py` for the async connection string.

**Two separate DB URLs are needed:**
- `DATABASE_URL` (sync, `postgresql://...`) — for Alembic migrations in env.py
- `ASYNC_DATABASE_URL` or `CHAINLIT_DATABASE_URL` (async, `postgresql+asyncpg://...`) — for Chainlit's async engine at runtime

### Pattern 5: on_chat_resume Hook

```python
# In app.py
@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    """Gespraechtsverlauf beim Wiederoeffnen eines alten Chats wiederherstellen.

    Args:
        thread: Chainlit ThreadDict mit id, name, steps (Nachrichten-Historie).
    """
    # Nachrichten-Historie aus den steps des Threads rekonstruieren
    history = []
    for step in thread.get("steps", []):
        if step.get("type") == "user_message":
            history.append({"role": "user", "content": step.get("input", "")})
        elif step.get("type") == "assistant_message":
            history.append({"role": "assistant", "content": step.get("output", "")})
    cl.user_session.set("history", history)
    cl.user_session.set("thread_id", thread["id"])
```

**Verified:** `@cl.on_chat_resume` is available in Chainlit 2.10.0 (confirmed by `dir(cl)` and source inspection). It receives a `ThreadDict` with `id`, `createdAt`, `name`, `userId`, `userIdentifier`, `tags`, `metadata`, `steps`, `elements`.

### Pattern 6: Multi-Turn Context Injection (CHAT-01)

The existing `pipeline.answer()` uses the Anthropic SDK directly (not LangChain LCEL). The simplest approach for CHAT-01: extend `answer()` to accept a `history` parameter (list of `{"role": ..., "content": ...}` dicts) and build the messages list for Claude.

```python
# src/pipeline.py — modified answer() signature
def answer(
    question: str,
    tenant_id: str = "default",
    source_filter: str | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """...existing docstring..."""
    settings = get_settings()
    docs = search(question, tenant_id=tenant_id, source_filter=source_filter)

    if not docs:
        return {"answer": "Diese Information ist in den vorliegenden Dokumenten nicht enthalten.", ...}

    context = _build_context(docs)
    system_content = _SYSTEM_PROMPT_TEMPLATE.format(context=context)

    # CHAT-01: Letzte 3 Turns (6 Messages) aus der History + aktuelle Frage
    window = (history or [])[-6:]  # max 6 messages = 3 turns
    messages = window + [{"role": "user", "content": question}]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_content,   # Context geht in system prompt
        messages=messages,        # History + aktuelle Frage
    )
```

**Key insight:** Move the context/question into a `system` parameter and keep `messages` purely for the conversational history. This avoids the anti-pattern of stuffing history into a single user message.

In `app.py`, maintain history in `cl.user_session`:

```python
# In _run_rag_flow:
history = cl.user_session.get("history", [])
result = await asyncio.to_thread(answer, question, history=history)

# Nach der Antwort: History aktualisieren
history.append({"role": "user", "content": question})
history.append({"role": "assistant", "content": result["answer"]})
cl.user_session.set("history", history)
```

### Pattern 7: Document Source Filter (CHAT-03)

The `retrieval.search()` currently calls the `match_document_chunks` RPC with `filter: {"tenant_id": tenant_id}`. The `source` is a direct TEXT column, not in the JSONB metadata, so the RPC filter dict cannot filter it natively.

**Recommended approach for PoC:** Extend `search()` with an optional `source_filter` parameter and apply post-filtering on the Python-side results. This keeps the Supabase RPC untouched.

```python
# src/retrieval.py — extended search()
def search(
    query: str,
    tenant_id: str = "default",
    source_filter: str | None = None,
) -> list[Document]:
    """...updated docstring..."""
    # ... embedding unchanged ...
    response = client.rpc(
        "match_document_chunks",
        {
            "query_embedding": query_vector,
            "match_count": settings.top_k_results * 3 if source_filter else settings.top_k_results,
            "filter": {"tenant_id": tenant_id},
        },
    ).execute()

    docs = [Document(...) for row in (response.data or [])]

    # CHAT-03: Optional source filter (post-filter, keeps RPC untouched)
    if source_filter:
        docs = [d for d in docs if d.metadata.get("source") == source_filter]
        docs = docs[:settings.top_k_results]

    return docs
```

**Note:** When filtering, request `top_k_results * 3` to compensate for post-filtering reducing results. The existing `search()` metadata mapping issue must be verified: `row.get("metadata", {})` in the current code does not include `source` and `page` — these are top-level columns in the RPC response. This needs a fix anyway for CHAT-03 to work.

**UI for CHAT-03:** Use a `/filter [filename]` command (same pattern as existing `/loeschen`). Store the active filter in `cl.user_session.set("source_filter", filename)`. Clear with `/filter` (no argument). Simpler than a dropdown, consistent with existing UX.

### Anti-Patterns to Avoid

- **LangChain RunnableWithMessageHistory:** Do not use — the pipeline uses the raw Anthropic SDK, not LangChain chains. Adding RunnableWithMessageHistory would require rewriting pipeline.py as an LCEL chain. Manual history management is simpler and correct here.
- **Chainlit BaseDataLayer custom implementation:** Do not build a custom data layer. `SQLAlchemyDataLayer` is fully implemented in Chainlit 2.10.0 — use it.
- **Using pgbouncer connection for Alembic:** Use the direct connection (port 5432, `db.[ref].supabase.co`) for migrations. pgbouncer/Supavisor (port 6543) is transaction-pooled and breaks multi-statement migrations.
- **Autogenerate migrations for pgvector:** Do not use `alembic revision --autogenerate` for the baseline. Write migrations manually with `op.execute()` for the vector column and ivfflat index.
- **Storing full conversation in RAG prompt:** Do not concatenate history as text in the context string. Use the Anthropic `messages` parameter for history and `system` for the RAG context.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread history UI sidebar | Custom session list page | Chainlit `SQLAlchemyDataLayer` | Auto-provided by Chainlit when data layer is registered |
| Thread persistence | Custom `chat_sessions` + `chat_messages` tables | Chainlit `SQLAlchemyDataLayer` (users/threads/steps tables) | Built-in implementation handles all edge cases |
| DB migrations | Manual SQL scripts | Alembic | Version-controlled, `upgrade head` idempotent |
| Async Postgres driver | Custom connection pool | asyncpg (via SQLAlchemy `create_async_engine`) | Chainlit requires asyncpg internally |

**Key insight:** The most important "don't hand-roll" is the session persistence. Chainlit 2.10.0 already ships a complete `SQLAlchemyDataLayer` — using it means the sidebar history UI, session resumption, and user management are all handled automatically. Building custom `chat_sessions`/`chat_messages` tables would duplicate this work and miss the automatic Chainlit UI integration.

---

## Common Pitfalls

### Pitfall 1: Metadata Not Populated from RPC Response

**What goes wrong:** `retrieval.search()` currently does `metadata=row.get("metadata", {})` which returns an empty dict because the RPC returns `source` and `page` as top-level columns, not nested in a `metadata` object. Document source filtering (CHAT-03) will silently return nothing if this is not fixed.

**Why it happens:** The current code works for displaying answers because `source`/`page` are read from `doc.metadata` later, but they are never actually populated from the RPC response.

**How to avoid:** Fix the Document construction in `search()`:
```python
docs = [
    Document(
        page_content=row["content"],
        metadata={
            "source": row.get("source", "unknown"),
            "page": row.get("page", 0),
            "tenant_id": row.get("tenant_id", "default"),
        },
    )
    for row in (response.data or [])
]
```
**Note:** This is a bug fix, not a new feature. It is required for CHAT-03 to work but also improves CHAT-01 source display.

### Pitfall 2: Chainlit Table Column Names are camelCase

**What goes wrong:** Migration uses snake_case column names (e.g., `created_at`, `user_id`) — `SQLAlchemyDataLayer` queries fail with "column does not exist" at runtime.

**Why it happens:** Chainlit's SQL uses quoted camelCase: `"createdAt"`, `"userId"`, `"threadId"`. PostgreSQL preserves case only when identifiers are quoted.

**How to avoid:** All Chainlit table migrations MUST use quoted camelCase column names. Do not "normalize" to snake_case. The migration DDL in this research document uses the correct names (verified from Chainlit 2.10.0 source).

### Pitfall 3: Two Different Connection Strings Required

**What goes wrong:** Using `postgresql+asyncpg://` for Alembic env.py (sync engine) causes an error. Using `postgresql://` for Chainlit's `SQLAlchemyDataLayer` (async engine) also causes an error.

**Why it happens:** Alembic uses a sync SQLAlchemy engine; Chainlit uses `create_async_engine` which requires `+asyncpg`.

**How to avoid:** Add two env vars:
```
DATABASE_URL=postgresql://postgres:[PWD]@db.[REF].supabase.co:5432/postgres
ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:[PWD]@db.[REF].supabase.co:5432/postgres
```
Alembic's `env.py` reads `DATABASE_URL`. `config.py` exposes `async_database_url` (used by `@cl.data_layer`).

### Pitfall 4: pgvector Type Causes Alembic to Fail

**What goes wrong:** Running `alembic check` or autogenerate fails with "Could not resolve type: vector" because SQLAlchemy does not know the `vector` type by default.

**Why it happens:** pgvector registers a custom PostgreSQL type that is not in SQLAlchemy's default dialect.

**How to avoid:** In `alembic/env.py`, import pgvector and register in `ischema_names`:
```python
from pgvector.sqlalchemy import Vector
# In do_run_migrations():
connection.dialect.ischema_names["vector"] = Vector
```

### Pitfall 5: Chainlit History Not Available on Chat Resume for Multi-Turn

**What goes wrong:** After resuming a thread, the first follow-up question has no history context even though old messages are visible.

**Why it happens:** `cl.user_session` is a new in-memory session. `@cl.on_chat_resume` must explicitly re-populate `cl.user_session.set("history", ...)` from the `ThreadDict.steps`.

**How to avoid:** `@cl.on_chat_resume` must reconstruct the history list from `thread["steps"]` (filter by `type == "user_message"` and `type == "assistant_message"`) and store it in `cl.user_session` before any message is processed.

### Pitfall 6: Source Filter Returns Zero Results

**What goes wrong:** Applying `source_filter` post-RPC with `top_k_results=4` may return 0 results if the document has fewer than 4 relevant chunks overall.

**Why it happens:** The RPC returns the top-4 most similar chunks across ALL documents. If only 1 chunk matches the filter, and it's not in the top-4, it won't appear.

**How to avoid:** When `source_filter` is set, increase `match_count` in the RPC call to `top_k_results * 3` (or a fixed value like 20). This ensures enough candidates before filtering. Return at most `top_k_results` after filtering.

### Pitfall 7: SQLAlchemyDataLayer Warns About Missing Storage Provider

**What goes wrong:** Warning log: "SQLAlchemyDataLayer storage client is not initialized and elements will not be persisted!" appears on every startup.

**Why it happens:** `SQLAlchemyDataLayer` expects a storage provider (S3/Azure/GCS) for file elements. For this PoC, file elements are not needed.

**How to avoid:** The warning is harmless for this PoC since no file elements are sent through Chainlit. Document it as expected behavior. Pass `show_logger=False` to suppress info-level logging if needed.

---

## Code Examples

### Verified Alembic alembic.ini

```ini
[alembic]
script_location = alembic
file_template = %%(rev)s_%%(slug)s
sqlalchemy.url = driver://user:pass@localhost/dbname
```

The `sqlalchemy.url` is overridden in `env.py` — the placeholder value here is never used.

### Verified SQLAlchemyDataLayer Registration

```python
# Source: Chainlit 2.10.0 installed package, chainlit/data/sql_alchemy.py
# SQLAlchemyDataLayer.__init__ signature (verified by inspect):
#   conninfo: str
#   connect_args: Optional[dict] = None
#   ssl_require: bool = False
#   storage_provider: Optional[BaseStorageClient] = None
#   user_thread_limit: Optional[int] = 1000
#   show_logger: Optional[bool] = False

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(
        conninfo="postgresql+asyncpg://postgres:[PWD]@db.[REF].supabase.co:5432/postgres",
        ssl_require=True,
    )
```

### Verified on_chat_resume Signature

```python
# Source: Chainlit 2.10.0, verified via inspect.getsource(cl.on_chat_resume)
# ThreadDict fields (verified via inspect.getsource(ThreadDict)):
#   id: str, createdAt: str, name: Optional[str], userId: Optional[str],
#   userIdentifier: Optional[str], tags: Optional[List[str]],
#   metadata: Optional[Dict], steps: List[StepDict], elements: Optional[List[ElementDict]]

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    # thread["steps"] contains all messages — reconstruct in-memory history here
    pass
```

### Verified InMemoryChatMessageHistory Usage

```python
# Source: langchain-core 1.2.19 (installed), verified via Python import
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

history = InMemoryChatMessageHistory()
history.add_user_message("Was steht auf Seite 3?")
history.add_ai_message("Auf Seite 3 steht...")
msgs = history.messages  # [HumanMessage(...), AIMessage(...)]
```

**Note:** `InMemoryChatMessageHistory` is available and works but is NOT needed for this phase. The `history: list[dict]` approach (plain dicts matching Anthropic message format) is simpler and avoids LangChain dependency for this specific use case.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangChain ConversationBufferWindowMemory | Manual message list or `InMemoryChatMessageHistory` | LangChain 0.3 deprecations | Memory classes deprecated; use `RunnableWithMessageHistory` with LCEL or manage manually |
| Custom data layer (build from scratch) | `SQLAlchemyDataLayer` in Chainlit | Chainlit ~1.1+ | Full implementation shipped in core; no custom code needed |
| `alembic revision --autogenerate` for pgvector tables | Hand-written `op.execute()` migrations | Ongoing limitation | pgvector type not recognized by autogenerate without ischema_names hack |

**Deprecated/outdated:**
- LangChain `ConversationBufferWindowMemory`: Deprecated in LangChain 0.3. Do not use.
- `langchain_community.memory.*`: Most memory classes deprecated. Use `langchain_core.chat_history.InMemoryChatMessageHistory` if needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `pytest.ini` (exists, `asyncio_mode = auto`) |
| Quick run command | `pytest tests/ -m 'not integration' -x -q` |
| Full suite command | `pytest tests/ -m 'not integration' -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHAT-01 | `answer()` with `history` param injects last 6 messages into Claude call | unit | `pytest tests/test_pipeline.py -x -q` | Modify existing |
| CHAT-01 | History window capped at 6 messages (3 turns) | unit | `pytest tests/test_pipeline.py::TestMultiTurn -x -q` | Wave 0 |
| CHAT-01 | `cl.user_session` history accumulates across messages | unit (mock cl) | `pytest tests/test_app_history.py -x -q` | Wave 0 |
| CHAT-02 | `@cl.data_layer` returns `SQLAlchemyDataLayer` instance | unit | `pytest tests/test_data_layer.py -x -q` | Wave 0 |
| CHAT-02 | `on_chat_resume` populates `cl.user_session` history from ThreadDict steps | unit (mock cl) | `pytest tests/test_app_resume.py -x -q` | Wave 0 |
| CHAT-03 | `search()` with `source_filter` returns only matching-source docs | unit | `pytest tests/test_retrieval.py -x -q` | Modify existing |
| CHAT-03 | `search()` with `source_filter` requests `top_k * 3` from RPC | unit | `pytest tests/test_retrieval.py::TestSourceFilter -x -q` | Wave 0 |
| ALL | Alembic migrations run without error on clean DB | integration | `pytest tests/test_migrations.py -m integration -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -m 'not integration' -x -q`
- **Per wave merge:** `pytest tests/ -m 'not integration' -q`
- **Phase gate:** Full non-integration suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_app_history.py` — CHAT-01: user_session history accumulation (mock `cl.user_session`)
- [ ] `tests/test_app_resume.py` — CHAT-02: on_chat_resume history reconstruction from ThreadDict steps
- [ ] `tests/test_data_layer.py` — CHAT-02: data_layer registration smoke test
- [ ] `tests/test_migrations.py` — CHAT-02: Alembic migrations run clean (integration-marked, requires real DB)
- [ ] Modify `tests/test_pipeline.py` — add `TestMultiTurn` class for `history` parameter
- [ ] Modify `tests/test_retrieval.py` — add `TestSourceFilter` class for source_filter parameter

---

## Open Questions

1. **match_document_chunks RPC SQL function definition**
   - What we know: The RPC is called with `filter: {"tenant_id": tenant_id}` — the function accepts a JSONB filter
   - What's unclear: Whether the Supabase SQL function uses `jsonb @>` operator on the metadata column or compares top-level columns. If it uses `metadata @> filter::jsonb` and `source` is a top-level column (not in metadata), adding `source` to the filter dict will NOT work.
   - Recommendation: Use post-filtering (already the recommended approach in this document). If the RPC SQL function can be modified to accept a `source_filter TEXT` parameter, that would be more efficient but is out of scope per the locked constraint.

2. **Supabase IPv6 for direct connection**
   - What we know: Supabase direct connections (port 5432) may only resolve to IPv6 in early 2024+ deployments. The development machine is on Windows 11 — IPv6 is typically supported.
   - What's unclear: Whether the GitHub Actions runner in CI has IPv6 support for the direct connection.
   - Recommendation: For Alembic migrations in CI, use the Supavisor session-mode connection (port 5432 on the pooler host) which is IPv4-compatible. Mark migration tests as `integration` so they do not run in CI (consistent with existing pattern).

3. **Chainlit SQLAlchemyDataLayer and Supabase SSL**
   - What we know: `ssl_require=True` is a supported parameter in `SQLAlchemyDataLayer.__init__`
   - What's unclear: Whether the Supabase direct connection requires a specific SSL certificate verification mode
   - Recommendation: Start with `ssl_require=True` and `connect_args={"ssl": "require"}`. If SSL verification fails, use `ssl.CERT_NONE` context (as shown in the SQLAlchemyDataLayer source code pattern).

---

## Sources

### Primary (HIGH confidence)

- Chainlit 2.10.0 installed package — `chainlit.data.sql_alchemy.SQLAlchemyDataLayer` source inspected directly via `inspect.getsource()`. All column names, constructor params, and SQL queries verified.
- Chainlit 2.10.0 `chainlit.types.ThreadDict` — source inspected directly; all fields documented.
- Chainlit 2.10.0 `chainlit.UserSession` — source inspected; `get()` and `set()` API verified.
- langchain-core 1.2.19 `InMemoryChatMessageHistory`, `RunnableWithMessageHistory` — imports verified with Python interpreter.
- SQLAlchemy 2.0.48 — installed, verified with `import sqlalchemy`.
- [pgvector-python GitHub](https://github.com/pgvector/pgvector-python) — Vector type for SQLAlchemy verified; `ischema_names` pattern documented.
- [Supabase Connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres) — direct connection port 5432 confirmed; Supavisor pooler port 6543 confirmed.

### Secondary (MEDIUM confidence)

- [Alembic Discussion #1324](https://github.com/sqlalchemy/alembic/discussions/1324) — `ischema_names['vector'] = Vector` pattern for pgvector type in Alembic env.py
- [Chainlit SQLAlchemy Data Layer docs](https://docs.chainlit.io/data-layers/sqlalchemy) — setup confirmed; `postgresql+asyncpg://` requirement confirmed; 5-table schema confirmed.
- [Chainlit custom data layer docs](https://docs.chainlit.io/api-reference/data-persistence/custom-data-layer) — BaseDataLayer abstract methods confirmed against live source inspection.

### Tertiary (LOW confidence)

- LangChain memory deprecation patterns — based on known LangChain 0.3 documentation; not individually verified against langchain-core 1.2.19 changelog.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified by direct package inspection and imports
- Architecture (Chainlit SQLAlchemy): HIGH — table schema verified from Chainlit 2.10.0 installed source
- Architecture (Alembic patterns): MEDIUM — baseline migration pattern from official docs + pgvector discussions; not tested against live DB
- Pitfalls (metadata bug in retrieval.py): HIGH — code inspection confirms `row.get("metadata", {})` returns empty dict
- Pitfalls (two connection strings): HIGH — asyncpg requirement verified from Chainlit source
- Source filter approach: MEDIUM — post-filter strategy is sound for PoC; RPC SQL function definition not directly inspected

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable libraries; Chainlit version pinned at 2.10.0)
