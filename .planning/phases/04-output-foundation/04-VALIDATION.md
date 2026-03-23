---
phase: 4
slug: output-foundation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-23
audited: 2026-03-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract rekonstruiert aus PLAN und SUMMARY Artefakten.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x mit pytest-asyncio |
| **Config file** | `pytest.ini` (`asyncio_mode = auto`) |
| **Quick run command** | `pytest tests/test_output.py -x -q` |
| **Full suite command** | `pytest tests/ -m 'not integration' -q` |
| **Estimated runtime** | ~1 Sekunde |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_output.py -x -q`
- **Before `/gsd:verify-work`:** Full suite grün
- **Max feedback latency:** 5 Sekunden

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | WORK-01 | unit | `pytest tests/test_output.py -x -q` | ✅ | ✅ green |
| 4-01-02 | 01 | 0 | WORK-05 | manual | — | n/a | 📋 manual-only |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · 📋 manual-only*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `_deliver_file()` liefert Datei als cl.File-Download im Chat | WORK-05 | Benötigt laufende Chainlit-UI + Browser | 1. App starten. 2. Lastenheft hochladen. 3. Angebot generieren. 4. Download-Element im Chat prüfen. |

---

## Validation Sign-Off

- [x] Alle Tasks haben automatisierten Verify oder Manual-Only Begründung
- [x] Sampling-Kontinuität gewährleistet
- [x] Kein watch-mode
- [x] Feedback-Latenz < 15s
- [x] `nyquist_compliant: true` gesetzt

**Approval:** 2026-03-23

---

## Validation Audit 2026-03-23

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Manual-only | 1 |

Rekonstruiert aus 04-01-PLAN.md und 04-01-SUMMARY.md. Alle 10 Tests in `test_output.py` grün.
WORK-05 (`_deliver_file`) ist by-Design manual-only — Plan verweist explizit auf Phase-7-Verifikation.
