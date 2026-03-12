# STRUCTURE.md

## Directory Layout

```
RAGPoC/                          ← project root
├── app.py                       ← Chainlit web UI entry point
├── ingest_cli.py                ← CLI ingestion entry point
├── chainlit.toml                ← Chainlit app name, theme, upload config
├── Dockerfile                   ← Production container (python:3.11-slim)
├── docker-compose.yml           ← App + volume mounts
├── requirements.txt             ← Python dependencies (pinned)
├── .env                         ← Secrets (gitignored)
├── .env.example                 ← Template (committed)
├── .gitignore
├── CLAUDE.md                    ← Project instructions for Claude Code
├── README.md
│
├── src/                         ← Core library modules
│   ├── __init__.py
│   ├── config.py                ← Pydantic Settings + health check
│   ├── ingest.py                ← load_document, chunk_document, embed_and_store, delete_document
│   ├── retrieval.py             ← search, get_indexed_documents
│   └── pipeline.py              ← answer (full RAG pipeline)
│
├── tests/                       ← Test suite
│   ├── __init__.py
│   ├── test_connection.py       ← Integration: live Ollama/Supabase/Claude checks
│   ├── test_ingest.py           ← Unit: load, chunk, embed_and_store
│   ├── test_pipeline.py         ← Unit: _build_context, _extract_sources, answer
│   └── test_embeddings.py       ← Embedding dimension / Ollama integration tests
│
├── docs/                        ← Uploaded document storage (gitignored)
│   └── .gitkeep
│
└── .planning/                   ← GSD planning artifacts
    └── codebase/                ← Codebase map documents
```

---

## Key File Locations

| What | Where |
|---|---|
| Environment config | `.env` (gitignored), `.env.example` |
| All settings | `src/config.py` — single `Settings` class |
| Document ingestion logic | `src/ingest.py` |
| Vector search | `src/retrieval.py` |
| RAG pipeline | `src/pipeline.py` |
| Web UI | `app.py` |
| CLI tool | `ingest_cli.py` |
| Chainlit config | `chainlit.toml` |
| Container config | `Dockerfile`, `docker-compose.yml` |
| Live service tests | `tests/test_connection.py` |
| Unit tests | `tests/test_ingest.py`, `tests/test_pipeline.py` |

---

## Naming Conventions

### Files
- `snake_case.py` for all Python files
- Test files: `test_<module>.py` matching the module they test
- Entry points at root level (`app.py`, `ingest_cli.py`)
- Config/template files lowercase (`chainlit.toml`, `requirements.txt`)

### Python
- Classes: `PascalCase` (`Settings`, `TestLoadDocument`)
- Functions/methods: `snake_case` (`load_document`, `embed_and_store`)
- Private helpers: leading underscore (`_build_context`, `_estimate_cost`, `_EMBED_BATCH_SIZE`)
- Constants: `SCREAMING_SNAKE_CASE` (`_EMBED_BATCH_SIZE`, `_INPUT_COST_PER_1M`)
- Test classes: `TestFunctionName` grouping related test methods

### Modules
- One responsibility per module (`ingest.py` = ingestion only)
- Public API = functions without leading `_`
- Private helpers = functions with `_` prefix within module

---

## Where to Add New Code

| Scenario | Location |
|---|---|
| New document format support | `src/ingest.py` → `load_document()` |
| New embedding provider | `src/ingest.py` + `src/retrieval.py` |
| New LLM provider | `src/pipeline.py` |
| New config variable | `src/config.py` → `Settings` class |
| New UI feature | `app.py` |
| New CLI command | New file at root (e.g., `delete_cli.py`) |
| New env variable | `src/config.py` + `.env.example` |
| Multi-tenant UI | `app.py` auth callback → pass user tenant to pipeline |

---

## Infrastructure Files

### `Dockerfile`
- Base: `python:3.11-slim`
- Installs system deps for Unstructured.io (libmagic, poppler-utils, etc.)
- Copies `requirements.txt` first (layer cache optimization)
- CMD: `chainlit run app.py --host 0.0.0.0 --port 8000`

### `docker-compose.yml`
- Single `app` service
- Volume: `./docs:/app/docs` for document persistence
- Env: loaded from `.env` file
- Port: 8000 exposed

### `chainlit.toml`
- App name, description, theme
- Upload: enabled, max size 50MB, accepted types
- Authentication: enabled (password)
