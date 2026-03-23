---
phase: 3
slug: chat-history-and-multi-turn-context
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-17
audited: 2026-03-23
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
| 3-01-01 | 01 | 0 | CHAT-01/02/03 | unit stubs | `pytest tests/ -m 'not integration' -x -q` | ✅ | ✅ green |
| 3-02-01 | 02 | 1 | ALL | integration | `pytest tests/test_migrations.py -m integration -x` | ✅ | ✅ green (integration) |
| 3-03-01 | 03 | 1 | CHAT-01 | unit | `pytest tests/test_pipeline.py -x -q` | ✅ | ✅ green |
| 3-04-01 | 04 | 1 | CHAT-03 | unit | `pytest tests/test_retrieval.py -x -q` | ✅ | ✅ green |
| 3-05-01 | 05 | 2 | CHAT-01 | unit | `pytest tests/test_app_history.py -x -q` | ✅ | ✅ green |
| 3-06-01 | 06 | 2 | CHAT-02 | unit | `pytest tests/test_app_resume.py -x -q` | ✅ | ✅ green |
| 3-06-02 | 06 | 2 | CHAT-02 | unit | `pytest tests/test_data_layer.py -x -q` | ✅ | ✅ green |
| 3-07-01 | 05 | 2 | CHAT-03 | unit | `pytest tests/test_app_filter.py -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_app_history.py` — CHAT-01: user_session history accumulation
- [x] `tests/test_app_resume.py` — CHAT-02: on_chat_resume history reconstruction
- [x] `tests/test_data_layer.py` — CHAT-02: data_layer registration smoke test
- [x] `tests/test_migrations.py` — ALL: Alembic migration smoke test (integration-marked)
- [x] `tests/test_pipeline.py` — CHAT-01: TestMultiTurn (history injection + window cap)
- [x] `tests/test_retrieval.py` — CHAT-03: TestSourceFilter (filter + triple match_count)
- [x] `tests/test_app_filter.py` — CHAT-03: /filter command handler in app.py

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Session-Liste im Chainlit UI nach Logout/Login sichtbar | CHAT-02 | Requires running Chainlit UI + browser | 1. Start app, upload doc, ask question. 2. Refresh page. 3. Verify session list appears in sidebar. |

---

## Validation Sign-Off

- [x] All tasks have automated verify
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all requirements
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-03-23

---

## Validation Audit 2026-03-23

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |

### Resolved Gaps
1. **CHAT-02 data_layer**: Stale `xfail(strict=True)` marker entfernt — `get_data_layer()` ist implementiert, Test läuft grün
2. **CHAT-03 /filter command**: Neuer Test `tests/test_app_filter.py` — verifiziert `/filter datei.pdf` setzt source_filter, `/filter` (ohne Argument) setzt auf None
