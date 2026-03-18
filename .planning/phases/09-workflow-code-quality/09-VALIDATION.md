---
phase: 9
slug: workflow-code-quality
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 0 | WORK-04 | unit | `pytest tests/ -x -q` | ❌ W0 (stub) | ⬜ pending |
| 9-01-02 | 01 | 1 | WORK-04 | unit | `pytest tests/ -x -q` | ✅ W0 | ⬜ pending |
| 9-01-03 | 01 | 1 | WORK-06 | unit | `pytest tests/ -x -q` | ✅ existing | ⬜ pending |
| 9-01-04 | 01 | 2 | WORK-04, WORK-06 | unit | `pytest tests/ -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_app_async.py` — add `hil_hinweis` visibility stub (if not already present)
- [ ] `tests/test_clients.py` — stubs for consolidated singleton tests (if new file needed)

*Existing infrastructure (pytest) covers test runner — only new stubs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `hil_hinweis` text appears in Chainlit chat after Angebot generation | WORK-04 | Requires live Chainlit session | Start app, trigger Angebot workflow, verify Hinweis message appears in chat |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
