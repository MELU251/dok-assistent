---
phase: 09-workflow-code-quality
plan: 01
subsystem: api
tags: [python, lru_cache, singleton, chainlit, mocking]

# Dependency graph
requires:
  - phase: 08-ui-ux-polish
    provides: app.py with _run_workflow_generation() workflow flow

provides:
  - src/clients.py with shared _get_embedder() and _get_supabase_client() singletons
  - hil_hinweis cl.Message surfaced in Chainlit chat after Angebot generation
  - Consolidated singleton module replacing duplicates in ingest.py and retrieval.py

affects:
  - any future phase modifying src/ingest.py, src/retrieval.py, or src/clients.py
  - any future phase adding workflow steps to _run_workflow_generation()

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Singleton getters centralized in src/clients.py — single source of truth for external clients
    - Patch at call-site module namespace (src.ingest._get_embedder) not at origin (src.clients) when direct import is used

key-files:
  created:
    - src/clients.py
  modified:
    - src/ingest.py
    - src/retrieval.py
    - app.py
    - tests/test_singletons.py
    - tests/test_app_async.py
    - tests/test_ingest.py
    - tests/test_retrieval.py

key-decisions:
  - "Patch target for test_ingest.py and test_retrieval.py stays at src.ingest.* / src.retrieval.* (not src.clients.*) because direct imports bind the name locally — patching the origin module does not affect the already-bound name"
  - "test_singletons.py patched at src.clients.* since it imports and tests src.clients directly"
  - "hil_hinweis wired with .get() and empty-string guard to handle missing key gracefully"
  - "WORK-06 dead import (create_angebotsentwurf) was already absent from app.py at plan execution time — confirmed by grep, no action needed"

patterns-established:
  - "Pattern: External client singletons in src/clients.py — OllamaEmbeddings and Supabase client live there, not in consuming modules"
  - "Pattern: Mock asyncio.to_thread by call index (not fn.__name__) when local imports make function identity unpredictable in tests"

requirements-completed: [WORK-04, WORK-06]

# Metrics
duration: 22min
completed: 2026-03-29
---

# Phase 9 Plan 01: Workflow Code Quality Summary

**Shared client singletons extracted to src/clients.py; hil_hinweis surfaced as cl.Message in Chainlit chat after Angebot generation**

## Performance

- **Duration:** 22 min
- **Started:** 2026-03-29T13:42:49Z
- **Completed:** 2026-03-29T14:05:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Created `src/clients.py` with `_get_embedder()` and `_get_supabase_client()` using `@lru_cache(maxsize=1)` — single canonical source for both external client singletons
- Removed duplicate singleton definitions from `src/ingest.py` and `src/retrieval.py`; both now import from `src.clients`
- Wired `hil_hinweis` message after `_deliver_file()` in `_run_workflow_generation()` (WORK-04)
- 82 non-integration tests pass with zero failures after all changes

## Task Commits

Each task was committed atomically:

1. **Task 1: Add hil_hinweis test stub** - `eff17e3` (test)
2. **Task 2: Create src/clients.py and consolidate singletons** - `c3c40d0` (feat)
3. **Task 3: Wire hil_hinweis in app.py** - `88bab8f` (feat)

## Files Created/Modified

- `src/clients.py` — New shared singleton module with _get_embedder() and _get_supabase_client()
- `src/ingest.py` — Removed singleton definitions; imports from src.clients; removed lru_cache, OllamaEmbeddings, create_client imports
- `src/retrieval.py` — Removed singleton definitions; imports from src.clients; removed lru_cache, OllamaEmbeddings, create_client imports
- `app.py` — Added hil_hinweis cl.Message block after _deliver_file() in _run_workflow_generation()
- `tests/test_singletons.py` — Rewritten to patch src.clients.*; merged TestSupabaseSingletonIngest and TestSupabaseSingletonRetrieval into TestSupabaseSingleton
- `tests/test_app_async.py` — Added TestHilHinweisMessage; replaced xfail with passing test using call-index side_effect
- `tests/test_ingest.py` — Patch targets kept at src.ingest.* (correct for direct import binding)
- `tests/test_retrieval.py` — Patch targets kept at src.retrieval.* (correct for direct import binding)

## Decisions Made

- **Patch target location for test_ingest.py / test_retrieval.py:** The plan specified changing patches to `src.clients.*` but this breaks tests. When `ingest.py` does `from src.clients import _get_embedder`, the name `_get_embedder` is bound in the `src.ingest` module namespace. Patching `src.clients._get_embedder` replaces the function in clients.py but does not affect the already-bound name in ingest.py. Correct patch target remains `src.ingest._get_embedder`. Applied same logic to retrieval.py.
- **test_singletons.py patches src.clients.*:** Correct since test_singletons.py imports directly from src.clients and tests that module.
- **asyncio.to_thread mock strategy:** Used call-index side_effect (returns results by order) instead of `fn.__name__` comparison. Functions inside the try block are local imports and may be MagicMock objects when their module is patched — `__name__` attribute not reliably set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected mock patch targets for test_ingest.py and test_retrieval.py**

- **Found during:** Task 2 (singleton consolidation)
- **Issue:** Plan specified `patch("src.clients._get_embedder")` for test_ingest.py, but Python name binding means this does not intercept calls in ingest.py. Tests fail with SystemExit from real get_settings() call.
- **Fix:** Kept patch targets at `src.ingest._get_embedder` and `src.ingest._get_supabase_client` (and equivalents for retrieval.py). This is correct per Python mock semantics for direct imports.
- **Files modified:** tests/test_ingest.py, tests/test_retrieval.py
- **Verification:** 13/13 singleton+ingest+retrieval tests pass
- **Committed in:** c3c40d0 (Task 2 commit)

**2. [Rule 1 - Bug] Rewrote hil_hinweis test to use call-index side_effect**

- **Found during:** Task 3 (hil_hinweis implementation)
- **Issue:** Initial test used `fn.__name__` to route asyncio.to_thread results, but functions are local imports inside try block — MagicMock objects have unreliable `__name__` — AttributeError raised.
- **Fix:** Replaced fn.__name__ routing with call-index list approach (position 0=search, 1=generate_angebot, 2=write_docx).
- **Files modified:** tests/test_app_async.py
- **Verification:** hil_hinweis test passes; full suite 82/82 green
- **Committed in:** 88bab8f (Task 3 commit)

**3. [Rule 1 - Non-issue] WORK-06 dead import already absent**

- **Found during:** Task 3 (dead import removal)
- **Issue:** Plan described removing `from src.workflow import create_angebotsentwurf` from app.py line 24. Grep confirmed this import does not exist in the current codebase — it was removed in a prior state.
- **Fix:** No action needed. Confirmed absence via grep. No code change.
- **Files modified:** None

---

**Total deviations:** 3 (2 auto-fixed bugs, 1 non-issue confirmation)
**Impact on plan:** All auto-fixes necessary for correctness. The patch-target deviation preserves correct test semantics. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `src/clients.py` is the canonical location for external client singletons — future phases should import from there
- `hil_hinweis` from `generate_angebot` result is now surfaced in Chainlit chat (WORK-04 satisfied)
- All 82 non-integration tests green, import check passes

---
*Phase: 09-workflow-code-quality*
*Completed: 2026-03-29*
