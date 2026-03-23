---
phase: 08-ui-ux-polish
plan: 01
subsystem: testing
tags: [pytest, xfail, tdd, chainlit, ui-testing, wave0]

# Dependency graph
requires:
  - phase: 03-chat-history-and-multi-turn-context
    provides: app.py with _run_rag_flow, _run_upload_flow, _run_delete_flow, _run_workflow_generation
provides:
  - Wave 0 xfail test scaffold for UI-01, UI-02, UI-03, UI-04
  - Executable spec for all four UI requirements before implementation
affects: [08-02-ui-ux-polish]

# Tech tracking
tech-stack:
  added: []
  patterns: [xfail(strict=True) wave-0 test scaffold, asyncio_mode=auto async test methods]

key-files:
  created: [tests/test_app_ui.py]
  modified: []

key-decisions:
  - "UI-01 tests target file-format mention and input-field guidance — both absent in current _build_welcome_content()"
  - "UI-02 tests verify /dokumente command handler exists — currently not implemented in on_message()"
  - "UI-03 tests assert no _Intern: marker and no raw exception type names in error messages"
  - "UI-04 tests verify cl.Text with display=inline is used for sources — currently sources appended as text in cl.Message"
  - "xfail(strict=True) used for all Wave 0 stubs — accidental pass causes test error, protecting against false greens"

patterns-established:
  - "Wave 0 pattern: write xfail tests that characterise missing behaviour before implementing — same pattern as Phase 03"
  - "capture_message helper: side_effect on cl.Message to collect sent content strings for assertion"

requirements-completed: [UI-01, UI-02, UI-03, UI-04]

# Metrics
duration: 2min
completed: 2026-03-23
---

# Phase 08 Plan 01: UI Test Scaffold Summary

**Wave 0 xfail test scaffold for four UI/UX requirements — 11 tests covering welcome message content, /dokumente command, German error messages, and cl.Text source citations**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-23T20:44:23Z
- **Completed:** 2026-03-23T20:46:35Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `tests/test_app_ui.py` with 4 test classes and 11 tests, all `xfail(strict=True)`
- Tests correctly fail against the current implementation, preventing false greens
- Existing 71-test suite passes without regression
- Two initially XPASS tests (UI-01) were tightened: now assert file-format mentions (PDF/DOCX/XLSX) and explicit input-field guidance, which the current welcome message lacks

## Task Commits

1. **Task 1: Testgeruest tests/test_app_ui.py mit xfail-Stubs erstellen** - `408f079` (test)

## Files Created/Modified

- `tests/test_app_ui.py` — Wave 0 xfail test scaffold for UI-01 to UI-04 (11 tests, 4 classes)

## Decisions Made

- `test_welcome_contains_upload_instructions` tests for file-format names (PDF, DOCX, XLSX) — the current welcome message only says "Dokument hochladen" without naming formats. This matches UI-01 requirement for comprehensive onboarding.
- `test_welcome_contains_question_instructions` tests for explicit input-field reference phrases — current message says "Stellen Sie einfach eine Frage" but does not point to the text-entry field.
- `test_rag_flow_error_no_internal_type` asserts "RuntimeError" and "_Intern:" are absent — current `_run_rag_flow` error contains `_(Intern: {type(exc).__name__})_` so this correctly xfails.
- `test_rag_flow_uses_cl_text_element` and `test_cl_text_display_inline` assert `cl.Text` is called with `display="inline"` — current implementation appends sources as inline markdown text in `cl.Message`, not as a `cl.Text` element.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened two UI-01 test assertions to prevent XPASS**
- **Found during:** Task 1 (test execution verification)
- **Issue:** First run showed `test_welcome_contains_upload_instructions` and `test_welcome_contains_question_instructions` as XPASS (strict) — the current `_build_welcome_content()` already contains "hochlad" and "klicken sie" which matched the initial assertions
- **Fix:** Rewrote assertions to target behaviours truly absent in current implementation: file-format names (PDF/DOCX/XLSX) and explicit input-field references
- **Files modified:** `tests/test_app_ui.py`
- **Verification:** Re-run showed 11 xfailed, 0 failed, 0 passed
- **Committed in:** 408f079 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — test correctness fix)
**Impact on plan:** Necessary for Wave 0 integrity — xfail(strict=True) only works if tests actually fail. Tightened assertions better represent the UI-01 requirements anyway.

## Issues Encountered

None beyond the XPASS adjustment documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 scaffold complete — Plan 02 can implement UI-01 to UI-04 and turn these xfail tests green
- Tests are precise: each test body clearly specifies the contract the implementation must fulfil
- Pattern established: Plan 02 must make all 11 tests pass (xfail → pass)

---
*Phase: 08-ui-ux-polish*
*Completed: 2026-03-23*

## Self-Check: PASSED

- FOUND: tests/test_app_ui.py
- FOUND: .planning/phases/08-ui-ux-polish/08-01-SUMMARY.md
- FOUND: commit 408f079
