---
phase: 05-extraction-engine
plan: "01"
subsystem: extractor
tags: [claude, pydantic, json, AngebotData, extract_requirements]

# Dependency graph
requires:
  - phase: 04-01
    provides: output infrastructure (output.py, AngebotData-Typen-Grundlage)

provides:
  - src/extractor.py mit AngebotData (Pydantic) und extract_requirements() (WORK-02)
  - Token-Kosten-Logging (identisches Muster wie pipeline.py)
  - tests/test_extractor.py (9 Tests, alle grün)

---

## One-liner
`extract_requirements(chunks) -> AngebotData` zerlegt ein Lastenheft via Claude in title, summary, requirements und special_requests — JSON-validiert und Pydantic-typisiert.

## What was built

**`src/extractor.py`**:
- `AngebotData` Pydantic-Modell (title, summary, requirements: list[str], special_requests: list[str])
- `extract_requirements(chunks)`: baut Kontext-String, ruft Claude claude-sonnet-4-6 auf, parsed JSON-Antwort
- Markdown-Code-Block-Stripping falls Claude Backticks hinzufügt
- Definierte Fehler bei leeren Chunks (ValueError) und API-Ausfall (RuntimeError)
- Token-Kosten in EUR geloggt (INPUT: $3/1M, OUTPUT: $15/1M, ×0.86 EUR)

## Test results
9/9 Tests grün (test_extractor.py)

## Status
COMPLETE — alle Success Criteria erfüllt
