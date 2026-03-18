# Roadmap: Workflow Engine — Angebotsentwurf auf Knopfdruck

**Milestone:** v2
**Depends on:** v1 milestone (Pilot-Ready)
**Created:** 2026-03-17

## Overview

Der dok-assistent ist pilot-ready. Dieser Milestone implementiert den primären Use-Case:
Ein Vertriebsingenieur lädt ein Lastenheft hoch und erhält auf Knopfdruck einen strukturierten
Angebotsentwurf als .docx — basierend auf historischen Angeboten aus der Wissensdatenbank.

Die vier Phasen bauen aufeinander auf: zuerst die Output-Infrastruktur (.docx-Schreiber),
dann die zwei KI-Module (Extraktor + Generator), zuletzt die Chainlit-UI als Kleber.

## Phases

- [x] **Phase 4: Output Foundation** — python-docx-Schreiber und Chainlit-Download-Mechanismus als Basis für alle folgenden Phasen (completed 2026-03-17)
- [x] **Phase 5: Extraction Engine** — Strukturierte Lastenheft-Analyse: Claude zerlegt ein PDF/DOCX in ein typisiertes AngebotData-Objekt (completed 2026-03-17)
- [x] **Phase 6: Generation Engine** — Angebotsentwurf-Generierung: Claude produziert einen 4-Abschnitt-Entwurf auf Basis von AngebotData + RAG-Retrieval (completed 2026-03-17)
- [x] **Phase 7: Workflow UI** — Chainlit-Workflow-Modus: 3-Schritt-Guided-Flow mit Human-in-the-Loop-Verifikation und .docx-Download (completed 2026-03-17)

## Phase Details

### Phase 4: Output Foundation
**Goal**: Die App kann formatierte .docx-Dateien schreiben und als Download an den Nutzer liefern — unabhängig von KI-Inhalt
**Depends on**: v1 milestone (existing ingest/retrieval stack)
**Requirements**: WORK-01, WORK-05
**New files**: `src/output.py`, `output/.gitkeep`
**Changed files**: `requirements.txt`, `app.py` (deliver_file helper)
**Test file**: `tests/test_output.py`
**Success Criteria** (was muss WAHR sein):
  1. `write_docx(sections, sources, output_path)` erzeugt eine valide .docx-Datei mit Firmen-Header, nummerierten Abschnitten und Quellenangaben-Anhang
  2. Chainlit kann die Datei dem Nutzer als Download-Element anbieten (`cl.File`) ohne Fehler
  3. `output/` Verzeichnis existiert und generierte .docx-Dateien sind in `.gitignore` ausgeschlossen

### Phase 5: Extraction Engine
**Goal**: Claude kann ein hochgeladenes Lastenheft in strukturierte Anforderungen zerlegen — verifizierbar und maschinenlesbar
**Depends on**: Phase 4 (uses ingest stack, output types)
**Requirements**: WORK-02
**New files**: `src/extractor.py`
**Changed files**: None
**Test file**: `tests/test_extractor.py`
**Success Criteria** (was muss WAHR sein):
  1. `extract_requirements(chunks) -> AngebotData` gibt ein valides Pydantic-Objekt zurück: `title`, `summary` (str), `requirements` (list[str]), `special_requests` (list[str])
  2. Bei einem leeren oder unlesbaren Dokument wirft der Extraktor einen definierten Fehler — kein stiller Fehlschlag
  3. Token-Kosten des Extraktions-Aufrufs werden geloggt (identisches Muster wie `pipeline.py`)

### Phase 6: Generation Engine
**Goal**: Claude generiert auf Basis extrahierter Anforderungen + RAG-Kontext einen vollständigen 4-Abschnitt-Angebotsentwurf
**Depends on**: Phase 5 (AngebotData model), Phase 4 (output.py schema)
**Requirements**: WORK-03, WORK-04
**New files**: `src/generator.py`
**Changed files**: None
**Test file**: `tests/test_generator.py`
**Success Criteria** (was muss WAHR sein):
  1. `generate_angebot(data, retrieved_chunks) -> dict` liefert alle 4 Pflicht-Keys: `zusammenfassung`, `technische_loesung`, `lieferumfang`, `offene_punkte`
  2. Jedes Key hat einen nicht-leeren String-Wert; `offene_punkte` ist eine Liste von Strings
  3. Der zurückgegebene Dict enthält einen `sources`-Key mit den Dateinamen der verwendeten Chunks — mindestens 3 verschiedene Quellen bei >3 Chunks im Retrieval-Ergebnis
  4. Das Generierungs-Ergebnis enthält den Human-in-the-Loop-Hinweis-Text als Pflichtfeld

### Phase 7: Workflow UI
**Goal**: Ein nicht-technischer Nutzer kann über die Chainlit-UI in unter 60 Sekunden einen .docx-Entwurf herunterladen — ohne Anleitung, ohne Fehler
**Depends on**: Phase 4, 5, 6
**Requirements**: WORK-06, WORK-07
**New files**: `src/workflow.py`
**Changed files**: `app.py` (Workflow-Action, _run_workflow_flow)
**Test file**: `tests/test_workflow.py`
**Success Criteria** (was muss WAHR sein):
  1. Nutzer klickt "Angebotsentwurf erstellen", lädt Lastenheft hoch und erhält .docx in < 60 Sekunden (gemessen end-to-end auf dem VPS)
  2. Nach der Extraktion erscheint eine Zwischennachricht mit den erkannten Anforderungen; Nutzer kann via Aktion bestätigen oder abbrechen
  3. Die erzeugte .docx enthält Quellenangaben aus mindestens 3 historischen Dokumenten aus der Wissensdatenbank
  4. Bei Upload eines nicht-unterstützten Formats (z.B. .xlsx) erscheint eine deutsche Fehlermeldung — kein Stack Trace

## Execution Order

Phasen führen strikt sequenziell aus: 4 → 5 → 6 → 7

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 4. Output Foundation | 1/1 | Complete | 2026-03-17 |
| 5. Extraction Engine | 1/1 | Complete | 2026-03-17 |
| 6. Generation Engine | 1/1 | Complete | 2026-03-17 |
| 7. Workflow UI | 1/1 | Complete | 2026-03-17 |

## Architecture Preview

```
app.py
  └── _run_workflow_flow()
        |
        ├── 1. AskFileMessage → Lastenheft hochladen
        ├── 2. src/ingest.load_document() + chunk_document()
        ├── 3. src/extractor.extract_requirements(chunks)  ← Phase 5
        ├── 4. UI: Anforderungen anzeigen → Nutzer bestätigt
        ├── 5. src/retrieval.search(requirements.summary)  ← existing
        ├── 6. src/generator.generate_angebot(data, chunks) ← Phase 6
        ├── 7. src/output.write_docx(sections, sources)    ← Phase 4
        └── 8. cl.File → Download-Link an Nutzer
```

---
*Roadmap created: 2026-03-17*
