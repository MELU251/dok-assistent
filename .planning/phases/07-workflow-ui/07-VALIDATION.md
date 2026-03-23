---
phase: 7
slug: workflow-ui
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-23
audited: 2026-03-23
---

# Phase 7 — Validation Strategy

> Per-phase validation contract rekonstruiert aus PLAN und SUMMARY Artefakten.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x mit pytest-asyncio |
| **Config file** | `pytest.ini` (`asyncio_mode = auto`) |
| **Quick run command** | `pytest tests/test_workflow.py -x -q` |
| **Full suite command** | `pytest tests/ -m 'not integration' -q` |
| **Estimated runtime** | ~2 Sekunden |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | WORK-06 (Orchestrierung) | unit | `pytest tests/test_workflow.py -x -q` | ✅ | ✅ green |
| 7-01-02 | 01 | 0 | WORK-06 (UI-Flow) | manual | — | n/a | 📋 manual-only |
| 7-01-03 | 01 | 0 | WORK-07 | manual | — | n/a | 📋 manual-only |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · 📋 manual-only*

---

## Test Coverage Detail

| Test | Behavior |
|------|----------|
| `test_returns_tuple_of_three` | Rückgabe ist tuple[Path, AngebotData, dict] |
| `test_returns_docx_path` | Erster Tuple-Wert ist ein .docx-Pfad |
| `test_returns_angebot_data` | Zweiter Tuple-Wert ist AngebotData-Instanz |
| `test_output_filename_contains_source_stem` | Dateiname enthält Lastenheft-Stem |
| `test_rag_search_uses_summary` | RAG-Search wird mit AngebotData.summary aufgerufen |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `_run_workflow_flow()` zeigt Schritt-für-Schritt-UI, Datei-Upload, Extraktion, HIL-Bestätigung | WORK-06 | `cl.AskFileMessage` und `cl.Step` sind nicht unit-testbar ohne vollständige Chainlit-Runtime | 1. App starten. 2. `/angebot` eingeben. 3. PDF hochladen. 4. Extraktions-Schritt beobachten. 5. Bestätigung erteilen. |
| Nicht-technischer Nutzer kann in unter 60 Sekunden .docx herunterladen | WORK-07 | E2E-Flow benötigt laufende Chainlit-UI + reale Dokumente | 1. App starten. 2. Vollständigen Workflow durchlaufen. 3. Gesamtzeit messen. 4. Download-Link prüfen. |

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
| Manual-only | 2 |

Rekonstruiert aus 07-01-PLAN.md und 07-01-SUMMARY.md. 5/5 Tests in `test_workflow.py` grün.
`_run_workflow_flow()` und WORK-07 sind by-Design manual-only — Chainlit AskFileMessage/Step
erfordern eine laufende Runtime und sind nicht sinnvoll unit-testbar.
