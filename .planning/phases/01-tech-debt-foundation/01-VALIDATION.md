---
phase: 1
slug: tech-debt-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — runs with `pytest` from project root |
| **Quick run command** | `pytest tests/test_ingest.py tests/test_pipeline.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_ingest.py tests/test_pipeline.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | TECH-04 | unit | `pytest tests/test_ingest.py -x -q` | ✅ (needs fix) | ⬜ pending |
| 1-01-02 | 01 | 0 | TECH-02, TECH-03 | unit | `pytest tests/test_singletons.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | TECH-01 | unit | `pytest tests/test_app_async.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 0 | TECH-05 | unit | `pytest tests/test_app_delete.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | TECH-02, TECH-03 | unit | `pytest tests/test_singletons.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | TECH-01 | unit | `pytest tests/test_app_async.py -x -q` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 1 | TECH-05 | unit | `pytest tests/test_app_delete.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_singletons.py` — stubs for TECH-02, TECH-03: singleton identity tests with `cache_clear()` teardown
- [ ] `tests/test_app_async.py` — stubs for TECH-01: async handler thread-offload verification
- [ ] `tests/test_app_delete.py` — stubs for TECH-05: delete flow atomicity test (missing local file → Supabase untouched)
- [ ] Fix `tests/test_ingest.py` — TECH-04: correct patch target (`OllamaEmbeddings`), dimension 768, settings mock, `.txt` extension test

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UI bleibt während Upload ansprechbar | TECH-01 | Requires live Chainlit UI + concurrent user action | Upload a large PDF; immediately send a chat message; verify response arrives before upload completes |
| Keine TCP-Erschöpfung nach 20 Queries | TECH-02, TECH-03 | Requires VPS connection monitoring | Run 20 queries via UI; check VPS with `ss -s` or `netstat` for connection count |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
