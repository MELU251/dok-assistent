---
phase: 01-tech-debt-foundation
plan: 03
subsystem: ui
tags: [asyncio, chainlit, async, event-loop, thread-pool]

# Dependency graph
requires:
  - phase: 01-tech-debt-foundation/01-01
    provides: pytest infrastructure and test scaffolds for TECH-01
provides:
  - asyncio.to_thread wrappers for embed_and_store, answer, delete_document in app.py
  - Non-blocking Chainlit event loop for all heavy operations
affects:
  - Phase 3 (multi-tenant Chainlit UI) — async pattern established here must be maintained

# Tech tracking
tech-stack:
  added: []
  patterns: ["asyncio.to_thread wraps all blocking sync calls inside Chainlit async handlers"]

key-files:
  created: []
  modified:
    - app.py
    - tests/test_app_async.py

key-decisions:
  - "asyncio.to_thread used (not run_in_executor) — simpler API, no explicit executor management needed"
  - "Test mocks for cl.Message().send() must use AsyncMock — MagicMock is not awaitable"

patterns-established:
  - "Blocking I/O pattern: await asyncio.to_thread(sync_fn, *args, **kwargs) inside async Chainlit handlers"

requirements-completed: [TECH-01]

# Metrics
duration: 15min
completed: 2026-03-16
---

# Phase 1 Plan 03: asyncio.to_thread Wrappers Summary

**Three blocking sync calls (embed_and_store, answer, delete_document) wrapped with asyncio.to_thread so the Chainlit event loop is never blocked during document processing or RAG queries**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-16T20:30:00Z
- **Completed:** 2026-03-16T20:45:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Added `import asyncio` and wrapped all three blocking functions in `app.py` with `await asyncio.to_thread()`
- Fixed test infrastructure: `cl.Message().send` mocked as `AsyncMock` so tests can run end-to-end
- All 10 tests pass (2 async + 8 ingest)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add asyncio.to_thread() wrappers to app.py** - `49ad1b3` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `app.py` - Three blocking calls wrapped with `asyncio.to_thread` + `import asyncio` added
- `tests/test_app_async.py` - Fixed `cl.Message` mock to use `AsyncMock` for `.send()`

## Decisions Made

- Used `asyncio.to_thread` over `loop.run_in_executor(None, ...)` — cleaner API, same semantics for default thread pool
- Test mock fix: `cl.Message().send` requires `AsyncMock` because Chainlit messages are awaited

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed AsyncMock missing on cl.Message mock in test suite**
- **Found during:** Task 1 (GREEN phase — running tests)
- **Issue:** `patch("app.cl.Message")` returns a `MagicMock`; calling `await cl.Message(...).send()` raises `TypeError: object MagicMock can't be used in 'await' expression`
- **Fix:** Captured `mock_message` from both test patches and set `mock_message.return_value.send = AsyncMock(return_value=None)`
- **Files modified:** `tests/test_app_async.py`
- **Verification:** `pytest tests/test_app_async.py` — 2 passed
- **Committed in:** `49ad1b3` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test mock)
**Impact on plan:** Necessary for tests to pass end-to-end. No scope creep.

## Issues Encountered

- `app.py` already had `import asyncio` and `delete_document` wrapped (from prior commit `9567633`). Only `embed_and_store` and `answer` wrappers were needed. Edits applied correctly.

## Next Phase Readiness

- TECH-01 resolved: Chainlit event loop no longer blocked during uploads or RAG queries
- Ready for Phase 1 Plan 04 (or any remaining plans in the phase)

---
*Phase: 01-tech-debt-foundation*
*Completed: 2026-03-16*
