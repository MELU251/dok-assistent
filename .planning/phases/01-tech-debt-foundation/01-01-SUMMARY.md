---
phase: 01-tech-debt-foundation
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, ollama, embeddings, tdd, red-green, unit-tests]

# Dependency graph
requires: []
provides:
  - "Fixed test_ingest.py: correct OllamaEmbeddings mock, 768-dim vectors, .csv for unsupported extension"
  - "RED test scaffold test_singletons.py: singleton identity tests for _get_embedder() and _get_supabase_client()"
  - "RED test scaffold test_app_async.py: asyncio.to_thread assertion tests for upload and RAG flows"
  - "RED test scaffold test_app_delete.py: atomic delete order tests"
  - "pytest-asyncio>=0.23 added to requirements.txt with asyncio_mode=auto in pytest.ini"
affects:
  - 01-tech-debt-foundation/01-02
  - 01-tech-debt-foundation/01-03
  - 01-tech-debt-foundation/01-04

# Tech tracking
tech-stack:
  added: [pytest-asyncio>=0.23]
  patterns: [TDD RED scaffolds written before implementation, asyncio_mode=auto via pytest.ini]

key-files:
  created:
    - tests/test_singletons.py
    - tests/test_app_async.py
    - tests/test_app_delete.py
    - pytest.ini
  modified:
    - tests/test_ingest.py
    - requirements.txt

key-decisions:
  - "Patch target for OllamaEmbeddings is src.ingest.OllamaEmbeddings (not openai) — aligns with actual import in ingest.py"
  - "pytest-asyncio asyncio_mode=auto chosen to avoid per-test @pytest.mark.asyncio boilerplate drift"
  - "Unsupported-extension test uses .csv (not .txt) because .txt is in the supported set in ingest.py"

patterns-established:
  - "RED scaffolds written first: test files for Plan 02/03/04 intentionally fail with ImportError until implementation completes"
  - "teardown_method calls cache_clear() on lru_cache singletons to ensure test isolation"

requirements-completed: [TECH-04]

# Metrics
duration: 5min
completed: 2026-03-16
---

# Phase 1 Plan 01: Test Infrastructure (Wave 0) Summary

**Wave-0 Nyquist compliance: fixed OllamaEmbeddings/768-dim test, created RED scaffolds for singleton, async offload, and atomic-delete contracts**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-16T20:20:33Z
- **Completed:** 2026-03-16T20:25:31Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Fixed test_ingest.py: replaced OpenAIEmbeddings with OllamaEmbeddings, updated dimensions from 1536 to 768, fixed unsupported-extension test to use .csv
- Created three RED test scaffolds (test_singletons.py, test_app_async.py, test_app_delete.py) that define behavioral contracts for Plans 02, 03, 04
- Added pytest-asyncio to requirements.txt and configured asyncio_mode=auto in pytest.ini

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix test_ingest.py (TECH-04)** - `882ea4a` (fix)
2. **Task 2: Create RED test scaffolds** - `31e854c` (test)

**Plan metadata:** committed with docs commit below

## Files Created/Modified
- `tests/test_ingest.py` - Fixed OllamaEmbeddings mock, 768 dimensions, .csv for unsupported extension
- `tests/test_singletons.py` - RED tests for _get_embedder() and _get_supabase_client() singleton identity (Plan 02 target)
- `tests/test_app_async.py` - RED tests asserting asyncio.to_thread wrapping embed_and_store and answer() (Plan 03 target)
- `tests/test_app_delete.py` - RED tests for atomic delete: no Supabase call when local file absent (Plan 04 target)
- `pytest.ini` - asyncio_mode=auto for pytest-asyncio
- `requirements.txt` - Added pytest-asyncio>=0.23

## Decisions Made
- Patch target `src.ingest.OllamaEmbeddings` is correct for current code structure (Plan 02 will shift the target to `_get_embedder` once singleton is introduced)
- asyncio_mode=auto via pytest.ini chosen over per-test markers for consistency
- .csv used for unsupported extension test because .txt is now supported in ingest.py supported set

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added pytest-asyncio and pytest.ini**
- **Found during:** Task 2 (creating async test files)
- **Issue:** pytest-asyncio not in requirements.txt; @pytest.mark.asyncio tests would fail at collection
- **Fix:** Added pytest-asyncio>=0.23 to requirements.txt, created pytest.ini with asyncio_mode=auto, installed in venv
- **Files modified:** requirements.txt, pytest.ini (new)
- **Verification:** pytest-asyncio 1.3.0 confirmed importable; async tests collected without errors
- **Committed in:** 31e854c (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical test infrastructure)
**Impact on plan:** Required for async tests to be collectable. No scope creep.

## Issues Encountered
- test_connection.py and some test_pipeline.py tests fail due to missing live VPS connection — expected, pre-existing behavior, out of scope.

## Next Phase Readiness
- Plan 02 (singleton extraction): test_singletons.py is ready with RED tests — implement _get_embedder() and _get_supabase_client() to turn them GREEN
- Plan 03 (async offload): test_app_async.py is ready with RED tests — wrap embed_and_store and answer() in asyncio.to_thread
- Plan 04 (atomic delete): test_app_delete.py is ready with RED tests — fix delete order in _run_delete_flow()
- test_ingest.py is fully GREEN (8/8 passing)

---
*Phase: 01-tech-debt-foundation*
*Completed: 2026-03-16*
