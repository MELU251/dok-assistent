---
phase: 01-tech-debt-foundation
plan: 02
subsystem: database
tags: [lru_cache, singletons, ollama, supabase, pgvector, embeddings, connection-pooling]

# Dependency graph
requires:
  - phase: 01-tech-debt-foundation/01-01
    provides: "pytest infrastructure and base test coverage for ingest/retrieval modules"
provides:
  - "_get_embedder() and _get_supabase_client() lru_cache singletons in src/ingest.py (done in 01-03 deviation)"
  - "_get_embedder() and _get_supabase_client() lru_cache singletons in src/retrieval.py"
  - "No inline OllamaEmbeddings() or create_client() in any hot-path function"
  - "test_ingest.py patches getter functions for lru_cache safety"
affects:
  - Phase 3 RAG pipeline
  - Any future code calling embed_and_store, search, get_indexed_documents, delete_document

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "lru_cache(maxsize=1) module-level singleton getters for expensive HTTP connections"
    - "Patch getter functions (_get_embedder, _get_supabase_client) instead of class-level names in tests when lru_cache is involved"

key-files:
  created: []
  modified:
    - src/retrieval.py
    - tests/test_ingest.py

key-decisions:
  - "get_settings() still called directly in embed_and_store() for settings.ollama_embed_model log message — test must mock get_settings too"
  - "Patch target is src.ingest._get_embedder (getter level) not src.ingest.OllamaEmbeddings (class level) to avoid lru_cache returning a cached real instance"

patterns-established:
  - "Singleton pattern: module-level @lru_cache(maxsize=1) getter functions for all external HTTP connections (Ollama, Supabase)"
  - "Test isolation: patch getter functions, not the underlying class, whenever lru_cache is in the call chain"

requirements-completed: [TECH-02, TECH-03]

# Metrics
duration: 15min
completed: 2026-03-16
---

# Phase 1 Plan 02: Singleton Getters for Connection Reuse Summary

**lru_cache(maxsize=1) singleton getters for OllamaEmbeddings and Supabase client added to both src/ingest.py and src/retrieval.py, eliminating repeated TCP connection creation on every RAG call**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-16T20:40:00Z
- **Completed:** 2026-03-16T20:55:00Z
- **Tasks:** 1 (Task 2 only — Task 1 was completed by 01-03 agent as a deviation)
- **Files modified:** 2

## Accomplishments
- Added `_get_embedder()` and `_get_supabase_client()` with `@lru_cache(maxsize=1)` to `src/retrieval.py`
- Replaced inline `OllamaEmbeddings(...)` in `search()` and inline `create_client(...)` in both `search()` and `get_indexed_documents()` with singleton getter calls
- Updated `tests/test_ingest.py` to patch `_get_embedder` and `_get_supabase_client` (getter level) instead of class-level names — safe against lru_cache caching real instances
- Deleted 7 garbage files (`=0.2.0`, `=0.23`, `=0.27.0`, `=0.3.0`, `=0.40.0`, `=2.0.0`, `=2.10.0`) from project root

## Task Commits

Each task was committed atomically:

1. **Task 2: Singletons in retrieval.py + test_ingest.py mock fix** - `69bff4a` (feat)

## Files Created/Modified
- `src/retrieval.py` - Added `from functools import lru_cache`, two singleton getters, updated `search()` and `get_indexed_documents()` to use them
- `tests/test_ingest.py` - Updated `test_stores_correct_number_of_chunks` to patch `_get_embedder` and `_get_supabase_client` at getter level

## Decisions Made
- `get_settings()` is still called directly inside `embed_and_store()` for a log message (`settings.ollama_embed_model`), so `@patch("src.ingest.get_settings")` must remain in the test with a minimal mock providing only `ollama_embed_model`. This avoids changing the source function's logging behavior.
- Getter-level patching (`src.ingest._get_embedder`) is the correct approach post-lru_cache: patching the class (`src.ingest.OllamaEmbeddings`) would not intercept calls that return a cached real instance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Re-added get_settings mock to test after getter refactor**
- **Found during:** Task 2 (test_ingest.py mock update)
- **Issue:** After switching to getter-level patches, `embed_and_store()` still calls `get_settings()` directly for `settings.ollama_embed_model` in a log statement. Test was failing with `SystemExit` from config validation (missing `.env` values added in plan 01-04 not yet in local `.env`).
- **Fix:** Added `@patch("src.ingest.get_settings")` back to the test with a minimal `MagicMock` providing only `ollama_embed_model`. The getters (`_get_embedder`, `_get_supabase_client`) remain the primary mock targets.
- **Files modified:** tests/test_ingest.py
- **Verification:** `pytest tests/test_singletons.py tests/test_ingest.py` — 11 passed
- **Committed in:** 69bff4a (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing mock for still-present get_settings() call)
**Impact on plan:** Fix required for test correctness. No scope creep.

## Issues Encountered
- Local `.env` on dev machine lacked `chainlit_auth_secret` and `chainlit_password` fields added by plan 01-04. Tests that indirectly called `get_settings()` without mocking it hit `SystemExit`. Resolved by keeping `get_settings` mock in the affected test.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both `src/ingest.py` and `src/retrieval.py` now use singleton getters — no inline connection creation remains in any hot-path function
- TECH-02 (connection leak in ingest) and TECH-03 (connection leak in retrieval) resolved
- Ready for Phase 2 (CI/CD) and Phase 3 (RAG pipeline enhancements)

---
*Phase: 01-tech-debt-foundation*
*Completed: 2026-03-16*
