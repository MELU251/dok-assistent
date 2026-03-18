---
phase: 06-generation-engine
plan: "01"
subsystem: generator
tags: [claude, json, generate_angebot, AngebotData, RAG, hil-hinweis]

# Dependency graph
requires:
  - phase: 05-01
    provides: AngebotData Pydantic-Modell aus extractor.py
  - phase: 04-01
    provides: output.py SECTION_ORDER und write_docx-Schema

provides:
  - src/generator.py mit generate_angebot(data, retrieved_chunks) -> dict (WORK-03, WORK-04)
  - HIL-Hinweis als Pflichtfeld im Rückgabe-Dict
  - sources-Deduplizierung aus RAG-Chunks
  - tests/test_generator.py (11 Tests, alle grün)

---

## One-liner
`generate_angebot()` produziert einen vollständigen 4-Abschnitt-Angebotsentwurf via Claude auf Basis von AngebotData + RAG-Kontext — JSON-validiert mit HIL-Hinweis und Quellenangaben.

## What was built

**`src/generator.py`**:
- `generate_angebot(data, retrieved_chunks)`: baut User-Message aus AngebotData + RAG-Kontext, ruft Claude claude-sonnet-4-6 auf
- Pflicht-Keys: zusammenfassung, technische_loesung, lieferumfang (list), offene_punkte (list)
- `sources`: deduplizierte Quelldateinamen aus Chunks
- `hil_hinweis`: Pflichttext "KI-generierter Entwurf — Pflichtprüfung..."
- `cost_eur`: Token-Kostenberechnung (identisches Muster wie extractor.py)
- Leere Chunks werden gracefully behandelt (kein Fehler, "Keine historischen Angebote verfügbar")

## Test results
11/11 Tests grün (test_generator.py)

## Status
COMPLETE — alle Success Criteria erfüllt
