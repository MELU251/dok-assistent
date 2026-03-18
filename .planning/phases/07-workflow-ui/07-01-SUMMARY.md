---
phase: 07-workflow-ui
plan: "01"
subsystem: workflow
tags: [chainlit, workflow, create_angebotsentwurf, hil, docx-download]

# Dependency graph
requires:
  - phase: 04-01
    provides: write_docx, _deliver_file
  - phase: 05-01
    provides: extract_requirements, AngebotData
  - phase: 06-01
    provides: generate_angebot

provides:
  - src/workflow.py mit create_angebotsentwurf() — kompletter Orchestrierungs-Workflow (WORK-06)
  - _run_workflow_flow() in app.py mit HIL-Bestätigung und .docx-Download (WORK-07)
  - tests/test_workflow.py (5 Tests, alle grün)

---

## One-liner
`create_angebotsentwurf()` orchestriert den Vollablauf (laden → extrahieren → RAG → generieren → .docx) und `_run_workflow_flow()` integriert ihn als Chainlit-Guided-Flow mit Human-in-the-Loop.

## What was built

**`src/workflow.py`**:
- `create_angebotsentwurf(file_path, tenant_id)`: 5-Schritt-Pipeline (load → chunk → extract → search → generate → write_docx)
- Rückgabe: `tuple[Path, AngebotData, dict]` für HIL-Verifikationsschritt in app.py
- Output-Dateiname: `Angebotsentwurf_{stem}.docx`

**`app.py`** Integration:
- `_run_workflow_flow()`: AskFileMessage → Extraktion → Zwischenmeldung mit Anforderungen → Nutzerbestätigung → Generierung → `_deliver_file()`
- Nicht-unterstützte Formate werden mit deutscher Fehlermeldung abgefangen

## Test results
5/5 Tests grün (test_workflow.py)

## Status
COMPLETE — alle Success Criteria erfüllt
