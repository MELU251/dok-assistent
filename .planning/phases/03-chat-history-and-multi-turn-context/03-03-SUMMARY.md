---
phase: 03-chat-history-and-multi-turn-context
plan: "03"
subsystem: database
tags: [retrieval, supabase, pgvector, langchain, metadata, source-filter]

# Dependency graph
requires:
  - phase: 03-01
    provides: "test stubs for retrieval metadata bug and source_filter (xfail markers)"
provides:
  - "Fixed metadata mapping in search() — source/page/tenant_id from top-level RPC columns"
  - "Optional source_filter parameter in search() for document-scoped similarity search"
  - "Triple match_count RPC call strategy when source_filter is set"
affects:
  - 03-04-pipeline
  - app.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Post-filter pattern: fetch 3x candidates via RPC, filter client-side, cap at top_k_results"
    - "get_settings mocked in all retrieval unit tests via @patch('src.retrieval.get_settings')"

key-files:
  created: []
  modified:
    - src/retrieval.py
    - tests/test_retrieval.py

key-decisions:
  - "source_filter is a post-filter (client-side) on RPC results, not a DB-side filter — avoids schema changes"
  - "match_count tripled when source_filter set to ensure sufficient candidates survive the post-filter"
  - "Metadata populated directly from top-level RPC columns (row['source'], row['page']) — NOT from row.get('metadata', {}) which always returned {}"
  - "xfail(strict=True) markers removed from test_retrieval.py after implementation; get_settings mock added to all three tests"

patterns-established:
  - "Retrieval unit tests: patch _get_embedder, _get_supabase_client, AND get_settings — all three required"

requirements-completed:
  - CHAT-03

# Metrics
duration: 6min
completed: 2026-03-17
---

# Phase 3 Plan 03: Retrieval Metadata Fix and Source Filter Summary

**Fixed silent metadata bug (source/page always empty) in search() and added source_filter parameter for document-scoped RAG queries**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-17T17:12:50Z
- **Completed:** 2026-03-17T17:18:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Fixed metadata bug: `row.get("metadata", {})` always returned `{}` because RPC returns top-level columns — replaced with explicit mapping of `source`, `page`, `tenant_id`
- Added `source_filter: str | None = None` parameter to `search()` for document-scoped queries
- When `source_filter` is set, RPC is called with `match_count = top_k_results * 3` to ensure sufficient candidates before client-side post-filtering
- Removed all `xfail` markers from `tests/test_retrieval.py`; added `get_settings` mock to all three tests (required because `search()` calls `get_settings()` directly)

## Task Commits

1. **Task 1: Fix metadata bug and add source_filter to search()** - `fedb7e8` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/retrieval.py` — Fixed metadata mapping in `search()`, added `source_filter` param, triple match_count strategy
- `tests/test_retrieval.py` — Removed xfail markers, added `get_settings` mock to all retrieval tests

## Decisions Made

- `source_filter` implemented as client-side post-filter rather than a DB-side filter to avoid schema changes and keep the RPC interface stable
- `match_count` tripled when filtering to compensate for the reduction in results after post-filtering
- `get_settings` must be mocked in retrieval unit tests because `search()` calls it directly (not via lru_cache getter) to read `top_k_results`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added get_settings mock to all retrieval tests**
- **Found during:** Task 1 (verifying GREEN tests pass)
- **Issue:** The xfail stubs in `test_retrieval.py` did not mock `src.retrieval.get_settings`. After the new Chainlit auth fields (`chainlit_auth_secret`, `chainlit_password`) were added in a prior plan, `get_settings()` fails with a `SystemExit` if `.env` is not present — breaking all retrieval unit tests
- **Fix:** Added `@patch("src.retrieval.get_settings")` decorator and `mock_settings.return_value = MagicMock(top_k_results=4)` to all three tests in `TestSearch` and `TestSourceFilter`
- **Files modified:** `tests/test_retrieval.py`
- **Verification:** `pytest tests/test_retrieval.py -x -q` exits 0 with 3 passed
- **Committed in:** fedb7e8 (committed by linter as part of earlier plan; changes confirmed present)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test setup caused by new required config fields)
**Impact on plan:** Fix necessary for tests to run at all in environments without `.env`. No scope creep.

## Issues Encountered

The linter/formatter auto-saved test file changes between Edit tool calls, causing "file modified since read" errors. Worked around by re-reading before each write. Final state was correctly applied by the linter matching intended changes.

## Next Phase Readiness

- `search()` now correctly returns source/page metadata — all downstream consumers (pipeline.py, app.py) will display correct source citations
- `source_filter` parameter available for Plan 04 (pipeline) to pass document scope from chat context
- All retrieval unit tests green, no regressions in full suite (27 passed, 5 xfailed)

---
*Phase: 03-chat-history-and-multi-turn-context*
*Completed: 2026-03-17*
