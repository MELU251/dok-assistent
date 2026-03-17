---
phase: 3
slug: chat-history-and-multi-turn-context
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pytest.ini` (exists, `asyncio_mode = auto`) |
| **Quick run command** | `pytest tests/ -m 'not integration' -x -q` |
| **Full suite command** | `pytest tests/ -m 'not integration' -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -m 'not integration' -x -q`
- **After every plan wave:** Run `pytest tests/ -m 'not integration' -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | CHAT-01/02/03 | unit stubs | `pytest tests/ -m 'not integration' -x -q` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | ALL | integration | `pytest tests/test_migrations.py -m integration -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 1 | CHAT-01 | unit | `pytest tests/test_pipeline.py -x -q` | ✅ modify | ⬜ pending |
| 3-04-01 | 04 | 1 | CHAT-03 | unit | `pytest tests/test_retrieval.py -x -q` | ✅ modify | ⬜ pending |
| 3-05-01 | 05 | 2 | CHAT-01 | unit | `pytest tests/test_app_history.py -x -q` | ❌ W0 | ⬜ pending |
| 3-06-01 | 06 | 2 | CHAT-02 | unit | `pytest tests/test_app_resume.py -x -q` | ❌ W0 | ⬜ pending |
| 3-06-02 | 06 | 2 | CHAT-02 | unit | `pytest tests/test_data_layer.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_app_history.py` — stubs for CHAT-01: user_session history accumulation
- [ ] `tests/test_app_resume.py` — stubs for CHAT-02: on_chat_resume history reconstruction
- [ ] `tests/test_data_layer.py` — stubs for CHAT-02: data_layer registration smoke test
- [ ] `tests/test_migrations.py` — stubs for ALL: Alembic migration smoke test (integration-marked)
- [ ] Extend `tests/test_pipeline.py` — add `TestMultiTurn` stub class
- [ ] Extend `tests/test_retrieval.py` — add `TestSourceFilter` stub class

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Session-Liste im Chainlit UI nach Logout/Login sichtbar | CHAT-02 | Requires running Chainlit UI + browser | 1. Start app, upload doc, ask question. 2. Refresh page. 3. Verify session list appears in sidebar. |
| `/filter [filename]` schränkt Antwort auf Dokument ein | CHAT-03 | Requires Chainlit UI interaction | 1. Upload 2 docs. 2. Use `/filter doc1.pdf`. 3. Ask question. 4. Verify only doc1.pdf referenced. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
