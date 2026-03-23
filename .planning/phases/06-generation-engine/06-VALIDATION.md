---
phase: 6
slug: generation-engine
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-23
audited: 2026-03-23
---

# Phase 6 — Validation Strategy

> Per-phase validation contract rekonstruiert aus PLAN und SUMMARY Artefakten.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x mit pytest-asyncio |
| **Config file** | `pytest.ini` (`asyncio_mode = auto`) |
| **Quick run command** | `pytest tests/test_generator.py -x -q` |
| **Full suite command** | `pytest tests/ -m 'not integration' -q` |
| **Estimated runtime** | ~1 Sekunde |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | WORK-03 | unit | `pytest tests/test_generator.py -x -q` | ✅ | ✅ green |
| 6-01-02 | 01 | 0 | WORK-04 (unit) | unit | `pytest tests/test_generator.py::TestGenerateAngebot::test_hil_hinweis_present -x -q` | ✅ | ✅ green |
| 6-01-03 | 01 | 0 | WORK-04 (UI-Rendering) | manual | — | n/a | 📋 manual-only |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · 📋 manual-only*

---

## Test Coverage Detail

| Test | Behavior |
|------|----------|
| `test_returns_dict_with_required_keys` | Alle Pflicht-Keys im Rückgabe-Dict |
| `test_zusammenfassung_is_string` | zusammenfassung ist str |
| `test_lieferumfang_is_list` | lieferumfang ist list[str] |
| `test_offene_punkte_is_list` | offene_punkte ist list[str] |
| `test_sources_contains_chunk_filenames` | sources enthält Dateinamen aus Chunks |
| `test_sources_deduplicated` | sources ohne Duplikate |
| `test_hil_hinweis_present` | hil_hinweis-Key vorhanden und nicht leer |
| `test_cost_eur_returned` | cost_eur ist float |
| `test_empty_chunks_handled_gracefully` | Leere Chunks → kein Fehler |
| `test_invalid_json_raises_value_error` | Kein JSON → ValueError |
| `test_missing_key_raises_value_error` | Fehlender Pflicht-Key → ValueError |
| `test_logs_token_cost` | Token-Kosten werden geloggt |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `hil_hinweis` erscheint als sichtbare Chat-Nachricht in Chainlit | WORK-04 (UI-Rendering) | Benötigt laufende Chainlit-UI — Unit-Test prüft nur Dict-Key-Präsenz. UI-Rendering-Gap wird in Phase 9 geschlossen. | 1. App starten. 2. Lastenheft hochladen. 3. Angebotserstellung auslösen. 4. HIL-Hinweis im Chat prüfen. |

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

Rekonstruiert aus 06-01-PLAN.md und 06-01-SUMMARY.md. 12/12 Tests in `test_generator.py` grün.
WORK-04 auf Unit-Ebene vollständig abgedeckt. UI-Rendering-Aspekt ist manual-only und wird in Phase 9 (Workflow Code Quality) als eigenständiger Gap behandelt.
