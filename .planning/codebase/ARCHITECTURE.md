# ARCHITECTURE.md

## Pattern

**Layered RAG (Retrieval-Augmented Generation) Architecture**

A linear pipeline with clear separation of concerns. No dependency injection framework — modules import a shared cached `get_settings()` singleton. Stateless functions throughout; no in-process state beyond the LRU-cached settings object.

```
[Entry Points]
   app.py (Chainlit UI)        ingest_cli.py (CLI)
          |                           |
          ↓                           ↓
[Core Modules]
   src/config.py        ← Pydantic BaseSettings, LRU-cached
   src/ingest.py        ← load → chunk → embed → store
   src/retrieval.py     ← embed query → Supabase RPC search
   src/pipeline.py      ← retrieval + Claude → answer dict

[External Services]
   Ollama VPS (Tailscale)      Supabase (pgvector)      Anthropic Claude API
```

---

## Layers

### Layer 1: Configuration (`src/config.py`)
- `Settings(BaseSettings)` — reads `.env`, validates at startup
- `get_settings()` — `@lru_cache(maxsize=1)` singleton, raises `SystemExit` on bad config
- `check_ollama_connection()` — live HTTP health-check on `{ollama_base_url}/api/tags`
- Validators reject placeholder values from `.env.example`

### Layer 2: Ingestion (`src/ingest.py`)
Three composable functions, called sequentially:

1. `load_document(file_path)` → `list[Document]`
   - `.txt` → `TextLoader`, others → `UnstructuredFileLoader(mode="elements", strategy="fast")`
   - Normalizes `source` and `page` metadata on every document
2. `chunk_document(docs)` → `list[Document]`
   - `RecursiveCharacterTextSplitter` with `tiktoken` (`cl100k_base`) for token counting
   - Parameters: `chunk_size=500`, `chunk_overlap=50` (from settings)
3. `embed_and_store(chunks, tenant_id, callback)` → `int`
   - Batches of 10 chunks → `OllamaEmbeddings.embed_documents()`
   - Bulk-inserts rows `{id, tenant_id, source, page, content, embedding}` into Supabase
   - Optional `callback(current, total)` for progress reporting
4. `delete_document(source, tenant_id)` → `int` — GDPR-compliant removal

### Layer 3: Retrieval (`src/retrieval.py`)
- `search(query, tenant_id)` → `list[Document]`
  - Embeds query via `OllamaEmbeddings.embed_query()`
  - Calls `match_document_chunks` Supabase RPC directly (bypasses LangChain's `SupabaseVectorStore` due to supabase-py 2.x incompatibility)
  - Returns up to `TOP_K_RESULTS` (default 4) documents
- `get_indexed_documents(tenant_id)` → `list[str]` — lists unique filenames in Supabase

### Layer 4: Pipeline (`src/pipeline.py`)
- `answer(question, tenant_id)` → `dict[answer, sources, cost_eur]`
  - Calls `retrieval.search()` → `_build_context()` → Claude `messages.create()`
  - Returns early with "not found" message if no chunks retrieved
  - Calculates EUR cost from token usage (claude-sonnet-4-6 pricing)
- Private helpers: `_build_context()`, `_extract_sources()`, `_estimate_cost()`

### Layer 5: Entry Points

**`app.py` — Chainlit Web UI**
- `@cl.password_auth_callback` — username/password from `.env`
- `@cl.on_chat_start` — shows welcome + indexed doc list + upload button
- `@cl.on_message` — routes to upload flow, `/loeschen` command, or RAG flow
- `_run_upload_flow()` — async, uses `cl.AskFileMessage` + `cl.Step` for progress
- `_run_delete_flow()` — deletes from Supabase and local `docs/` dir
- `_run_rag_flow()` — calls `pipeline.answer()`, formats response with sources + cost

**`ingest_cli.py` — CLI Ingestion**
- `argparse` with `--file` and `--tenant` flags
- Calls load → chunk → embed_and_store in sequence with print progress

---

## Data Flow

### Upload/Ingestion Flow
```
User uploads file
  → Chainlit saves to docs/
  → load_document() → list[Document] (pages/elements)
  → chunk_document() → list[Document] (500-token chunks)
  → embed_and_store():
      → OllamaEmbeddings (batches of 10) → float[768] per chunk
      → Supabase INSERT document_chunks {tenant_id, source, page, content, embedding}
  → UI shows success + updated doc list
```

### Query/Answer Flow
```
User asks question
  → pipeline.answer(question, tenant_id)
      → retrieval.search():
          → OllamaEmbeddings.embed_query() → float[768]
          → Supabase RPC match_document_chunks → top-4 chunks
      → _build_context() → formatted string with [N] source labels
      → Anthropic(claude-sonnet-4-6).messages.create() → text response
      → _extract_sources() → deduplicated source list
      → _estimate_cost() → EUR float
  → UI renders answer + sources + cost note
```

---

## Multi-Tenancy

`tenant_id` parameter threads through all layers:
- `embed_and_store(chunks, tenant_id)` — stored in `document_chunks.tenant_id`
- `search(query, tenant_id)` — passed as `filter` to Supabase RPC
- `get_indexed_documents(tenant_id)` — filters by tenant
- UI currently hardcodes `tenant_id="default"` (no per-user isolation yet)

---

## Error Handling Strategy

- All external calls (Ollama, Supabase, Claude) wrapped in `try/except`
- `src/` modules raise `RuntimeError` with descriptive German messages
- `app.py` catches `RuntimeError` and sends user-friendly `cl.Message`
- `ingest_cli.py` catches and `sys.exit(1)` with readable error
- `get_settings()` raises `SystemExit` on config failure (fail-fast at startup)

---

## Abstractions

| Abstraction | Purpose |
|---|---|
| `get_settings()` | Single config access point, validated at startup |
| `load_document()` | Normalizes all file types to `list[Document]` |
| `chunk_document()` | Uniform chunking regardless of source format |
| `embed_and_store()` | Encapsulates entire embedding+persistence pipeline |
| `search()` | Hides Supabase RPC details behind simple query interface |
| `answer()` | Complete RAG pipeline as single function call |

---

## Entry Point Summary

| File | How to Run | Purpose |
|---|---|---|
| `app.py` | `chainlit run app.py` | Web chat UI |
| `ingest_cli.py` | `python ingest_cli.py --file doc.pdf` | Batch ingestion |
| `tests/test_connection.py` | `pytest tests/test_connection.py -v -s` | Live connectivity check |
