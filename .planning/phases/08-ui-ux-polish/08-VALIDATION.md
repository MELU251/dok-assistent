---
phase: 8
slug: ui-ux-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml |
| **Quick run command** | `pytest tests/test_app_ui.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_app_ui.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 0 | UI-01..04 | unit | `pytest tests/test_app_ui.py -x -q` | ❌ W0 | ⬜ pending |
| 8-01-02 | 01 | 1 | UI-01 | unit | `pytest tests/test_app_ui.py::test_welcome_message -x -q` | ✅ W0 | ⬜ pending |
| 8-01-03 | 01 | 1 | UI-02 | unit | `pytest tests/test_app_ui.py::test_dokumente_command -x -q` | ✅ W0 | ⬜ pending |
| 8-01-04 | 01 | 1 | UI-03 | unit | `pytest tests/test_app_ui.py::test_german_error_handling -x -q` | ✅ W0 | ⬜ pending |
| 8-01-05 | 01 | 1 | UI-04 | unit | `pytest tests/test_app_ui.py::test_source_display -x -q` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_app_ui.py` — stubs for UI-01, UI-02, UI-03, UI-04
- [ ] Stubs should import app.py functions and mock Chainlit context

*Existing infrastructure (pytest) covers test runner — only new test file needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `/dokumente` renders correctly in chat UI | UI-02 | Chainlit rendering requires live browser | Start app, type `/dokumente`, verify list displays |
| Source citations appear inline (not sidebar) | UI-04 | `cl.Text display="inline"` behavior is visual | Start app, ask question, verify sources appear in chat |
| Welcome message displays on session start | UI-01 | Requires live Chainlit session | Start app, open new browser tab, verify welcome message |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
