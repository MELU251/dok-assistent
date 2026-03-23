---
phase: 5
slug: extraction-engine
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-23
audited: 2026-03-23
---

# Phase 5 — Validation Strategy

> Per-phase validation contract rekonstruiert aus PLAN und SUMMARY Artefakten.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x mit pytest-asyncio |
| **Config file** | `pytest.ini` (`asyncio_mode = auto`) |
| **Quick run command** | `pytest tests/test_extractor.py -x -q` |
| **Full suite command** | `pytest tests/ -m 'not integration' -q` |
| **Estimated runtime** | ~1 Sekunde |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_extractor.py -x -q`
- **Before `/gsd:verify-work`:** Full suite grün
- **Max feedback latency:** 5 Sekunden

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | WORK-02 | unit | `pytest tests/test_extractor.py -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · 📋 manual-only*

---

## Test Coverage Detail

| Test | Behavior |
|------|----------|
| `test_returns_angebot_data` | Valide Antwort → AngebotData-Objekt |
| `test_title_and_summary_populated` | title und summary nicht leer |
| `test_requirements_is_list` | requirements ist list[str] |
| `test_special_requests_is_list` | special_requests ist list[str] |
| `test_empty_special_requests_allowed` | special_requests darf [] sein |
| `test_empty_chunks_raises_value_error` | Leere chunks → ValueError |
| `test_invalid_json_raises_value_error` | Kein JSON → ValueError |
| `test_logs_token_cost` | Token-Kosten werden geloggt |
| `test_markdown_code_block_stripped` | Backtick-Blöcke werden entfernt |

---

## Manual-Only Verifications

Keine — alle Behaviors vollständig automatisiert abgedeckt.

---

## Validation Sign-Off

- [x] Alle Tasks haben automatisierten Verify
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
| Manual-only | 0 |

Rekonstruiert aus 05-01-PLAN.md und 05-01-SUMMARY.md. 9/9 Tests in `test_extractor.py` grün.
