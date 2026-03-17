---
phase: 03-chat-history-and-multi-turn-context
plan: "04"
subsystem: api
tags: [anthropic, rag, pipeline, multi-turn, conversation-history]

# Dependency graph
requires:
  - phase: 03-01
    provides: Wave 0 xfail test stubs for CHAT-01 multi-turn context

provides:
  - answer() with history and source_filter params
  - RAG context in system= parameter, conversation turns in messages= list
  - History window capped at last 6 entries (3 turns)

affects:
  - 03-05-app-history-wiring

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "system/messages split: RAG context in system=, user/assistant turns in messages="
    - "History window slicing: (history or [])[-6:] for last 3 turns"

key-files:
  created: []
  modified:
    - src/pipeline.py
    - tests/test_pipeline.py
    - tests/test_retrieval.py

key-decisions:
  - "RAG context placed in system= parameter, not merged into user message — cleaner separation of concerns for multi-turn"
  - "_SYSTEM_PROMPT renamed to _SYSTEM_PROMPT_TEMPLATE with {context} only (no {question})"
  - "History window cap of 6 messages (3 turns) applied as (history or [])[-6:] slice"
  - "test_retrieval.py get_settings mock added — chainlit fields added in prior plan broke retrieval tests that never mocked settings"

patterns-established:
  - "History param: None means no history (single-turn); list of role/content dicts means multi-turn"
  - "source_filter forwarded from answer() to search() for document-scoped queries"

requirements-completed: [CHAT-01]

# Metrics
duration: 12min
completed: 2026-03-17
---

# Phase 3 Plan 04: Multi-Turn History Parameter Summary

**answer() extended with system/messages split: RAG context in system=, history window (max 6 entries) + current question in messages= for multi-turn Claude calls**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-17T17:52:47Z
- **Completed:** 2026-03-17T18:04:51Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Renamed `_SYSTEM_PROMPT` to `_SYSTEM_PROMPT_TEMPLATE` with context-only placeholder (question removed from system prompt)
- Extended `answer()` signature with `source_filter` and `history` params; Anthropic call now uses `system=` and `messages=`
- History window capped at last 6 messages via `(history or [])[-6:]` slice
- Removed `xfail` markers from `TestMultiTurn` — all 9 pipeline tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add history parameter to answer() and restructure Anthropic call** - `c010f9e` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/pipeline.py` - `_SYSTEM_PROMPT_TEMPLATE`, updated `answer()` with `history`/`source_filter` params, system/messages split
- `tests/test_pipeline.py` - Removed xfail markers from `TestMultiTurn`
- `tests/test_retrieval.py` - Added `get_settings` mock to fix 3 pre-existing test failures

## Decisions Made
- RAG context goes into `system=` (not merged into user message) — keeps conversation turns clean and avoids context-document mixing as history grows
- `_SYSTEM_PROMPT_TEMPLATE` replaces `_SYSTEM_PROMPT` — template no longer has `{question}` since the question goes into `messages=`
- History window is `[-6:]` (last 6 messages = 3 turns) applied before appending current question

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing test_retrieval.py failures due to missing get_settings mock**
- **Found during:** Task 1 verification (`pytest tests/ -m 'not integration' -q`)
- **Issue:** `test_retrieval.py` tests called `search()` which internally calls `get_settings()` directly for `top_k_results`. A prior plan added `chainlit_auth_secret` and `chainlit_password` as required Settings fields, causing `SystemExit` in tests that never mocked `get_settings`.
- **Fix:** Added `@patch("src.retrieval.get_settings")` decorator and `mock_get_settings.return_value = MagicMock(top_k_results=4)` to all 3 affected test methods in `TestSearch` and `TestSourceFilter`.
- **Files modified:** `tests/test_retrieval.py`
- **Verification:** `pytest tests/ -m 'not integration' -q` — 27 passed, 5 xfailed, 0 failures
- **Committed in:** `c010f9e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix unblocked the full test suite; no scope creep. Pre-existing regression from prior plan's config changes.

## Issues Encountered
- `test_retrieval.py` had 3 previously xfailed tests (for source_filter, which was implemented in retrieval.py) that became real failures once source_filter was implemented but settings mock was never updated. Fixed inline as Rule 1 deviation.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `answer()` is ready to accept `history=` kwarg from Plan 05 (app.py wiring)
- `source_filter` param available for future document-scoped query UI
- All non-integration tests pass cleanly

---
*Phase: 03-chat-history-and-multi-turn-context*
*Completed: 2026-03-17*
