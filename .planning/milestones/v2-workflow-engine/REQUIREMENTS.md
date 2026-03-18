# Requirements: Workflow Engine — Angebotsentwurf auf Knopfdruck

**Milestone:** v2
**Defined:** 2026-03-17
**Core Value:** Ein Vertriebsingenieur lädt ein Lastenheft hoch und erhält in unter 60 Sekunden einen strukturierten Angebotsentwurf als .docx — ohne technisches Wissen, auf Knopfdruck.

---

## v2 Requirements

Requirements für den Workflow-Engine-Milestone. Jedes Requirement mappt auf eine Roadmap-Phase.

### Output-Infrastruktur

- [ ] **WORK-01**: `python-docx` ist in `requirements.txt`; `src/output.py` stellt `write_docx(sections, sources, output_path)` bereit — erzeugt valide .docx mit Header, Abschnitten und Quellenangaben
- [ ] **WORK-05**: Chainlit liefert die generierte .docx dem Nutzer als Download (`cl.File`) — kein manuelles Filesystem-Browsing nötig

### Lastenheft-Extraktion

- [ ] **WORK-02**: `src/extractor.py` stellt `extract_requirements(chunks) -> AngebotData` bereit — Claude extrahiert aus einem Lastenheft ein strukturiertes Pydantic-Objekt mit Zusammenfassung, Anforderungsliste und Sonderwünschen; Kosten-Tracking inklusive

### Angebotsentwurf-Generierung

- [ ] **WORK-03**: `src/generator.py` stellt `generate_angebot(data, retrieved_chunks) -> dict` bereit — Claude generiert einen vollständigen Entwurf mit exakt 4 Pflichtabschnitten: Zusammenfassung, Technische Lösung, Lieferumfang, Offene Punkte
- [ ] **WORK-04**: Jeder generierte Entwurf enthält einen "Human-in-the-Loop"-Hinweis und Quellenangaben, die mindestens 3 historische Dokumente aus dem Retrieval referenzieren

### Workflow & UI

- [ ] **WORK-06**: Chainlit zeigt eine neue Aktion "Angebotsentwurf erstellen" als primären Einstiegspunkt; der Workflow führt den Nutzer in 3 Schritten: Lastenheft hochladen → Extraktion verifizieren → .docx herunterladen
- [ ] **WORK-07**: Nach der Extraktion zeigt die UI die erkannten Anforderungen zur Verifikation an (Human-in-the-Loop); der Nutzer bestätigt oder bricht ab, bevor die Generierung startet

---

## Nicht in Scope (v2)

| Feature | Begründung |
|---------|------------|
| Parallele Verarbeitung mehrerer Lastenhefte | PoC: Ein Dokument pro Workflow-Run |
| Streaming der Generierung (Wort für Wort) | Deferred zu v3 — Einzel-Blocking-Call reicht für < 60s |
| Template-Auswahl (verschiedene Angebots-Layouts) | PoC: Ein festes .docx-Layout |
| Iteratives Verfeinern (Chat nach Download) | Separate Phase nach erstem Feedback |
| Automatische Kunden-/Projektdaten aus CRM | Kein CRM-Zugriff im PoC |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| WORK-01 | Phase 4: Output Foundation | Not started |
| WORK-05 | Phase 4: Output Foundation | Not started |
| WORK-02 | Phase 5: Extraction Engine | Not started |
| WORK-03 | Phase 6: Generation Engine | Not started |
| WORK-04 | Phase 6: Generation Engine | Not started |
| WORK-06 | Phase 7: Workflow UI | Not started |
| WORK-07 | Phase 7: Workflow UI | Not started |

**Coverage:**
- v2 Requirements: 7 total
- Mapped to phases: 7
- Unmapped: 0 — full coverage

---

## Milestone Success Criteria

Alle 3 müssen zutreffen, damit der Milestone als "done" gilt:

1. Ein Nutzer lädt ein Lastenheft hoch und erhält innerhalb von **60 Sekunden** einen .docx-Entwurf zum Download
2. Der Entwurf enthält mindestens **3 Abschnitte mit Inhalt aus historischen Angeboten** — nachweisbar durch Quellenangaben im Dokument
3. Ein **nicht-technischer Nutzer** kann den Workflow ohne Anleitung durchführen (3-Schritt-UI ohne Fehlerzustand)

---
*Defined: 2026-03-17*
