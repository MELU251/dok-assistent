---
phase: 01-tech-debt-foundation
plan: "04"
subsystem: ui
tags: [chainlit, async, atomicity, delete-flow, supabase, file-handling]

# Dependency graph
requires:
  - phase: 01-tech-debt-foundation/01-01
    provides: test infrastructure and pytest-asyncio setup

provides:
  - Atomic-safe _run_delete_flow() in app.py (local file checked and deleted before Supabase)
  - asyncio.to_thread wrapping delete_document for non-blocking I/O
  - test_app_delete.py with both atomicity test cases green

affects:
  - Phase 3 (Chainlit UI enhancements) — delete flow pattern is established

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local-file-first delete order: check existence, unlink locally, then delete from DB"
    - "asyncio.to_thread() for blocking sync calls inside async Chainlit handlers"

key-files:
  created: []
  modified:
    - app.py
    - tests/test_app_delete.py

key-decisions:
  - "Local file presence (DOCS_DIR / filename) is the authoritative guard — get_indexed_documents() pre-flight removed"
  - "local_file.unlink() called BEFORE delete_document to ensure local state is consistent even on DB failure"
  - "asyncio.to_thread(delete_document, filename) used for consistency with Plan 03 pattern"
  - "Test mock for cl.Message.send fixed to AsyncMock to allow success-path await"

patterns-established:
  - "File-first delete: always touch local filesystem before remote DB to prevent phantom records"

requirements-completed:
  - TECH-05

# Metrics
duration: 15min
completed: 2026-03-16
---

# Phase 1 Plan 04: Atomicity Fix for _run_delete_flow() Summary

**_run_delete_flow() rewritten with file-first delete order: local existence check guards Supabase, unlink() precedes delete_document(), crash-safe against partial deletes**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-16T20:30:00Z
- **Completed:** 2026-03-16T20:45:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Removed the `get_indexed_documents()` Supabase pre-flight check that let phantom DB deletes occur when the local file was missing
- Added `local_file.exists()` as the sole guard — the function returns immediately without touching Supabase if the file is absent
- Moved `local_file.unlink()` to execute before `delete_document()` inside `cl.Step`, guaranteeing local file is gone before the DB record is touched
- Added `asyncio.to_thread()` around `delete_document` call (aligns with Plan 03 async pattern; adds `import asyncio`)
- Fixed missing `AsyncMock` on `cl.Message.send` in the test's success path

## Task Commits

1. **Task 1: Rewrite _run_delete_flow() with correct atomicity order** - `9567633` (fix)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `app.py` — _run_delete_flow() rewritten with file-first delete order; `import asyncio` added
- `tests/test_app_delete.py` — AsyncMock fix for cl.Message.send in second test case

## Decisions Made

- Removed `get_indexed_documents()` pre-flight: local file presence is now the single source of truth. If Supabase has no records but the file exists, `delete_document` returns 0 (acceptable) — no error.
- `asyncio.to_thread` used even though Plan 03 may not have run yet, to be consistent and forward-compatible.
- Test bug fixed inline (Rule 1): `patch("app.cl.Message")` in test 2 did not configure `.send` as AsyncMock; the success-path `await cl.Message(...).send()` raised `TypeError`. Fixed by adding `mock_msg.return_value.send = AsyncMock()`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing AsyncMock on cl.Message.send in test_existing_local_file test**
- **Found during:** Task 1 (running pytest after implementation)
- **Issue:** `patch("app.cl.Message")` returned plain MagicMock; `await cl.Message(...).send()` in the success path raised `TypeError: object MagicMock can't be used in 'await' expression`
- **Fix:** Added `mock_msg.return_value.send = AsyncMock()` after capturing the patch context manager return value
- **Files modified:** `tests/test_app_delete.py`
- **Verification:** Both tests pass after fix
- **Committed in:** `9567633` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** The test bug was a direct blocker to verification. Fix is minimal and correct. No scope creep.

## Issues Encountered

- Missing Python dependencies (pytest, chainlit, supabase, tiktoken, langchain packages) were installed during execution as the dev environment was not pre-configured.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TECH-05 is resolved. The delete flow is now atomic and safe against missing-file scenarios.
- Plans 01-02 and 01-03 changes (src/ingest.py, tests/test_app_async.py) remain uncommitted in working tree — they belong to their respective plan commits and should be handled by those plans' executors.

---
*Phase: 01-tech-debt-foundation*
*Completed: 2026-03-16*
