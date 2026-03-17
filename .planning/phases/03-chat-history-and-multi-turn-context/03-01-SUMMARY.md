---
phase: 03-chat-history-and-multi-turn-context
plan: 01
subsystem: testing

tags: [pytest, xfail, wave-0, stubs, chainlit, alembic, sqlalchemy]

# Dependency graph
requires:
  - phase: 02-cicd-stabilization
    provides: stable CI pipeline with non-integration pytest run

provides:
  - Wave 0 test infrastructure for all Phase 3 plans
  - xfail stubs for CHAT-01 (history accumulation), CHAT-02 (resume + data layer), CHAT-03 (source filter)
  - test_retrieval.py with TestSearch metadata bug stub and TestSourceFilter stubs
  - test_migrations.py integration-marked smoke test stub

affects:
  - 03-02 (metadata bug fix — targets TestSearch)
  - 03-03 (source_filter impl — targets TestSourceFilter)
  - 03-04 (history param in pipeline — targets TestMultiTurn)
  - 03-05 (Chainlit data layer — targets TestDataLayer + TestOnChatResume)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 xfail stub pattern: pytest.mark.xfail(strict=True) keeps suite green while marking RED intent"
    - "pytestmark = pytest.mark.integration to exclude DB-dependent tests from CI"

key-files:
  created:
    - tests/test_app_history.py
    - tests/test_app_resume.py
    - tests/test_data_layer.py
    - tests/test_migrations.py
    - tests/test_retrieval.py
  modified:
    - tests/test_pipeline.py

key-decisions:
  - "xfail(strict=True) used for all stubs — will turn into test errors if production code passes unexpectedly, preventing false greens"
  - "test_retrieval.py created fresh (did not exist); TestSearch metadata bug also marked xfail to track known bug"
  - "test_migrations.py uses pytestmark = pytest.mark.integration to auto-exclude from CI non-integration runs"

patterns-established:
  - "Wave 0 stubs: create xfail test files before implementation plans to ensure every verify command has a target"
  - "TestMultiTurn and TestSourceFilter: xfail stubs defining the exact API shape (history=, source_filter=) before implementation"

requirements-completed:
  - CHAT-01
  - CHAT-02
  - CHAT-03

# Metrics
duration: 10min
completed: 2026-03-17
---

# Phase 3 Plan 01: Wave 0 Test Infrastructure Summary

**Six xfail stub test files establishing Nyquist compliance — every Phase 3 plan's verify command now has an existing target file with correctly-marked stubs**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-17T17:08:17Z
- **Completed:** 2026-03-17T17:18:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Created four new test stub files covering CHAT-01, CHAT-02, and integration migration testing
- Created tests/test_retrieval.py (previously missing) with TestSearch metadata bug stub and TestSourceFilter stubs
- Extended tests/test_pipeline.py with TestMultiTurn class (2 xfail stubs for history parameter)
- Full suite: 22 passed, 10 xfailed, 0 failed, 0 errors — all green

## Task Commits

Each task was committed atomically:

1. **Task 1: Create stub test files (app_history, app_resume, data_layer, migrations)** - `adb65d7` (test)
2. **Task 2: Extend test_pipeline with TestMultiTurn, create test_retrieval** - `7f1dc3d` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `tests/test_app_history.py` - CHAT-01: TestAppHistory with 2 xfail stubs for history accumulation in app.py
- `tests/test_app_resume.py` - CHAT-02: TestOnChatResume with 2 xfail stubs for on_chat_resume ThreadDict reconstruction
- `tests/test_data_layer.py` - CHAT-02: TestDataLayer with 1 xfail stub for SQLAlchemyDataLayer registration
- `tests/test_migrations.py` - ALL: integration-marked migration smoke test stub (excluded from CI)
- `tests/test_retrieval.py` - New file: TestSearch (metadata bug xfail) + TestSourceFilter (2 source_filter xfail stubs)
- `tests/test_pipeline.py` - Extended with TestMultiTurn (2 xfail stubs for history param in answer())

## Decisions Made

- Used `xfail(strict=True)` for all stubs so that accidental pass-through of production code causes a test error (not a silent green)
- TestSearch metadata bug also marked xfail to track the known retrieval metadata mapping bug before Plan 02 fixes it
- `pytestmark = pytest.mark.integration` in test_migrations.py ensures it is always excluded from `pytest -m 'not integration'` CI runs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all stubs collected correctly and reported xfail on first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All Phase 3 plan verify commands now have existing target files
- Plan 02 (metadata bug fix) targets `TestSearch::test_returns_documents_with_populated_metadata`
- Plan 03 (source_filter) targets `TestSourceFilter` in test_retrieval.py
- Plan 04 (history in pipeline) targets `TestMultiTurn` in test_pipeline.py
- Plan 05 (Chainlit data layer) targets `TestDataLayer` and `TestOnChatResume`

---
*Phase: 03-chat-history-and-multi-turn-context*
*Completed: 2026-03-17*
