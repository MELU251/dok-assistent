# Codebase Map: KI-Dokumenten-Assistent (RAGPoC)

**Generated:** 2026-03-17

---

## 1. Overall Architecture

### Pattern

Single-process Python application with a thin Chainlit UI layer over a synchronous RAG pipeline. The architecture is a classic three-layer stack with no internal bus or message queue:

```
[Chainlit UI (app.py)]
        |
        | asyncio.to_thread()  ← offloads blocking calls
        v
[RAG Pipeline (src/pipeline.py)]
        |                   |
        v                   v
[Ingest (src/ingest.py)]  [Retrieval (src/retrieval.py)]
        |                   |
        v                   v
[Supabase pgvector]     [Ollama VPS via Tailscale]
        |
        v
[Anthropic Claude API]
```

### Module Responsibilities

| File | Role |
|------|------|
| `app.py` | Chainlit event hooks, UI flows, session state management |
| `src/config.py` | `pydantic_settings.BaseSettings` — all env vars, validated at startup, `lru_cache` singleton |
| `src/ingest.py` | `load_document()` → `chunk_document()` → `embed_and_store()` pipeline |
| `src/retrieval.py` | `search()` via Supabase RPC, `get_indexed_documents()` for UI listing |
| `src/pipeline.py` | `answer()` — combines retrieval + Claude call + cost tracking |
| `ingest_cli.py` | Standalone CLI wrapper for `src/ingest.py` (no Chainlit dependency) |
| `alembic/` | DB migration scripts for pgvector table + Chainlit persistence tables |

### Key Design Decisions

- **No LangChain chains in the RAG flow.** `pipeline.py` calls `src.retrieval.search()` directly and constructs the Anthropic `client.messages.create()` call manually. LangChain is used only for `Document`, `OllamaEmbeddings`, `RecursiveCharacterTextSplitter`, and `UnstructuredFileLoader`.
- **Retrieval bypasses `langchain_community.SupabaseVectorStore`** — incompatible with `supabase-py 2.x`. Instead, `retrieval.py` calls the `match_document_chunks` Supabase RPC function directly.
- **RAG context goes into `system=`** (not merged into user messages). This keeps history turns clean for multi-turn context (CHAT-01 decision).
- **`source_filter` is a client-side post-filter** applied after the RPC returns. To compensate, `match_count` is tripled when a filter is active. No schema change was needed.
- **History window** is capped at 6 messages (3 turns) inside `pipeline.answer()`, not in `app.py`. `_run_rag_flow()` passes the full session history.

---

## 2. Current Features

### Implemented and Working

| Feature | Where |
|---------|-------|
| Password authentication | `app.py` `auth_callback()` — username/password from `.env` |
| File upload (PDF, DOCX, XLSX) | `app.py` `_run_upload_flow()` — AskFileMessage → load → chunk → embed |
| Document listing | `retrieval.get_indexed_documents()` → shown in welcome message and after upload |
| Document deletion | `app.py` `_run_delete_flow()` — `/loeschen [filename]` command, file-first atomic delete |
| Source filter | `app.py` `/filter [filename]` command stores `source_filter` in `cl.user_session` |
| RAG Q&A with citations | `pipeline.answer()` — retrieves k=4 chunks, calls Claude, formats source list |
| Per-query cost display | `pipeline.answer()` returns `cost_eur`; shown as `<sub>` note in chat |
| Multi-turn context (in-session) | `pipeline.answer(history=...)` injects last 6 messages into Claude call |
| Persistent chat sessions (CHAT-02) | `SQLAlchemyDataLayer` in `app.py`, backed by Supabase PostgreSQL via `asyncpg` pooler |
| Session resume | `app.py` `on_chat_resume()` — reconstructs in-memory `history` from Chainlit `steps` |
| Progress steps in UI | `cl.Step(...)` context managers show inline progress during upload and RAG query |

### Commands Available to Users

- `/filter [dateiname]` — restrict search to a single document; `/filter` (no arg) clears
- `/loeschen [dateiname]` — remove document from disk and Supabase
- Upload button (Chainlit `Action`) — triggers `AskFileMessage` dialog

---

## 3. Data Layer

### Database Schema (Supabase PostgreSQL)

**Migration 0001** (`alembic/versions/0001_baseline.py`):
```sql
CREATE TABLE document_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    source      TEXT NOT NULL,         -- filename, e.g. "handbuch.pdf"
    page        INT,
    content     TEXT NOT NULL,
    embedding   vector(768),           -- nomic-embed-text dimensions
    created_at  TIMESTAMPTZ DEFAULT now()
);
-- Index: ivfflat cosine, lists=100
```

**Migration 0002** (`alembic/versions/0002_chainlit_tables.py`):
Chainlit `SQLAlchemyDataLayer` tables — `users`, `threads`, `steps`, `elements`, `feedbacks`. Column names are camelCase (`createdAt`, `userId`, `threadId`) because Chainlit 2.x requires this exact casing.

### Connection URLs

Two separate env vars required (documented in `src/config.py`):
- `DATABASE_URL` — sync direct connection `postgresql://` port 5432, for Alembic migrations only
- `ASYNC_DATABASE_URL` — async pooler `postgresql+asyncpg://` port 6543, for Chainlit `SQLAlchemyDataLayer` at runtime

### Retrieval Pipeline

1. `retrieval.search(query, tenant_id, source_filter)` in `src/retrieval.py`
2. Embeds query via Ollama (`OllamaEmbeddings` singleton, `nomic-embed-text`, 768 dims)
3. Calls Supabase RPC `match_document_chunks` with `{"tenant_id": tenant_id}` filter
4. Post-filters by `source_filter` if set; caps result at `top_k_results` (default 4)
5. Returns list of `langchain_core.documents.Document` objects with `source`, `page`, `tenant_id` metadata

### Ingestion Pipeline

1. `ingest.load_document(file_path)` — `UnstructuredFileLoader(mode="elements", strategy="fast")` for PDF/DOCX/XLSX; `TextLoader` for `.txt`
2. `ingest.chunk_document(docs)` — `RecursiveCharacterTextSplitter`, size=500 tokens, overlap=50, length measured via `tiktoken cl100k_base`
3. `ingest.embed_and_store(chunks, tenant_id, callback)` — batches of 10 chunks via Ollama, inserts rows into `document_chunks` via Supabase client

---

## 4. Workflow Engine Gap Analysis

### What "Workflow Engine" Means Here

A workflow engine that takes a PDF/DOCX input and produces a `.docx` output — i.e., a **document transformation pipeline**: ingest a source document, extract/analyze content via LLM, and write a structured output document.

### What Is Already Built

| Capability | Status | Files |
|------------|--------|-------|
| Read PDF/DOCX/XLSX from disk | Built | `src/ingest.load_document()` |
| Chunk and parse document elements | Built | `src/ingest.chunk_document()` |
| Embed and retrieve chunks | Built | `src/ingest.embed_and_store()`, `src/retrieval.search()` |
| Call Claude with structured prompt | Built | `src/pipeline.answer()` |
| Multi-step UI progress reporting | Built | `cl.Step()` in `app.py` |
| Source filter (single-doc focus) | Built | `retrieval.search(source_filter=...)` |
| CLI entry point (no UI) | Built | `ingest_cli.py` |
| Cost tracking per call | Built | `pipeline._estimate_cost()` |

### What Is Missing

| Gap | Impact | Notes |
|-----|--------|-------|
| **No `.docx` output writer** | Blocking | No dependency on `python-docx` or `docxtpl`. Nothing in the codebase writes formatted Word output. |
| **No structured extraction prompt** | Blocking | `pipeline.answer()` is a Q&A function. There is no prompt template designed to extract structured fields, tables, or sections for output rendering. |
| **No workflow orchestration layer** | Blocking | All flows are request-response (question → answer). There is no looping, conditional branching, or multi-step document assembly logic. |
| **No output schema / template definition** | Blocking | No data model for what the output `.docx` should contain (sections, fields, tables). |
| **No file output path management** | Moderate | `docs/` dir exists for input only. No output directory, no naming convention, no download delivery mechanism to the user. |
| **No Chainlit file download support** | Moderate | Chainlit `cl.File` elements can deliver files to users but are not used anywhere. |
| **No batch processing** | Low (for PoC) | One document at a time. No queue, no job tracking. |
| **Streaming responses not implemented** | Low | `pipeline.answer()` uses blocking `client.messages.create()`. For long generation (full-doc output) this will block. Deferred to v2 per REQUIREMENTS.md. |
| **OCR for scanned PDFs** | Low | `strategy="fast"` only. Scanned PDFs would produce empty content. Deferred per REQUIREMENTS.md. |

### Minimum additions for a Document-to-Document workflow

1. **Output writer module** (e.g., `src/output.py`) using `python-docx` — takes a dict of extracted fields/sections and renders a `.docx`
2. **Extraction prompt** in `src/pipeline.py` (or a new `src/extractor.py`) — a structured prompt that instructs Claude to return JSON or labeled sections instead of a free-form answer
3. **Workflow function** that chains: `load_document()` → `chunk_document()` → `embed_and_store()` → loop/extract → `write_docx()` — either a new `src/workflow.py` or extended `ingest_cli.py`
4. **Output delivery in UI** — `cl.File(path=..., name=..., display="inline")` in `app.py` to let the user download the produced `.docx`
5. **Output directory** — e.g., `output/` parallel to `docs/`, with `.gitkeep` and gitignore entry for generated files

---

## 5. Test Coverage Summary

Tests live in `tests/` (13 files). All unit tests mock external dependencies (`OllamaEmbeddings`, Supabase client, Anthropic). Integration tests are marked `@pytest.mark.integration` and excluded from CI.

| Test File | What it covers |
|-----------|----------------|
| `test_pipeline.py` | `_build_context`, `_extract_sources`, `answer()`, multi-turn history injection and windowing |
| `test_ingest.py` | `load_document`, `chunk_document`, `embed_and_store` (mocked embedder + supabase) |
| `test_retrieval.py` | `search()` with source_filter, `get_indexed_documents()` |
| `test_app_history.py` | `_run_rag_flow` history accumulation in user session |
| `test_app_resume.py` | `on_chat_resume` history reconstruction from thread steps |
| `test_app_delete.py` | `_run_delete_flow` atomic delete order |
| `test_app_async.py` | `asyncio.to_thread` wrapping of blocking calls |
| `test_singletons.py` | `lru_cache` singleton behavior for embedder and Supabase client |
| `test_connection.py` | Ollama + Supabase connectivity (integration, excluded from CI) |
| `test_data_layer.py` | `SQLAlchemyDataLayer` (xfail — decorator signature mismatch, noted as future cleanup) |
| `test_migrations.py` | Alembic migration run (integration, excluded from CI) |
| `test_embeddings.py` | Embedding dimension validation (768 not 1536) |

---

## 6. File Tree (Relevant Source Only)

```
RAGPoC/
├── app.py                        ← Chainlit UI + event hooks
├── ingest_cli.py                 ← CLI ingestion entry point
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py                 ← pydantic_settings, lru_cache singleton
│   ├── ingest.py                 ← load / chunk / embed / store
│   ├── retrieval.py              ← vector search + document listing
│   └── pipeline.py               ← RAG answer + Claude call + cost
├── tests/
│   ├── test_pipeline.py
│   ├── test_ingest.py
│   ├── test_retrieval.py
│   ├── test_app_*.py (4 files)
│   ├── test_singletons.py
│   ├── test_connection.py        ← integration
│   ├── test_data_layer.py        ← xfail
│   ├── test_migrations.py        ← integration
│   └── test_embeddings.py
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 0001_baseline.py      ← document_chunks table + pgvector
│       └── 0002_chainlit_tables.py ← users/threads/steps/elements/feedbacks
├── docs/                         ← runtime document storage (not committed)
├── .planning/
│   ├── REQUIREMENTS.md
│   ├── ROADMAP.md
│   ├── STATE.md
│   └── phases/
│       ├── 01-tech-debt-foundation/
│       ├── 02-cicd-stabilization/
│       └── 03-chat-history-and-multi-turn-context/
└── .github/workflows/            ← CI/CD: test → build → deploy
```

---

*Map written 2026-03-17*
