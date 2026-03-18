# Retrospective

Living document — updated after each milestone.

---

## Milestone: v1.0 — Pilot-Ready + Workflow Engine

**Shipped:** 2026-03-18
**Phases:** 7 | **Plans:** 14
**Timeline:** 7 Tage (2026-03-11 → 2026-03-18)

### What Was Built

1. **Tech Debt Foundation** — OllamaEmbeddings/Supabase als Singletons, asyncio.to_thread, atomarer Delete-Flow, pytest testet korrekten Embedding-Pfad
2. **CI/CD-Pipeline** — Drei-Job GitHub Actions (test → build → deploy) mit Tailscale-Retry und Post-Deploy-Health-Check
3. **Chat History** — Persistente Sessions via Chainlit SQLAlchemy DataLayer, Alembic-Migrationen, Multi-Turn-Kontext (3 Turns), Dokument-Filter
4. **Output Foundation** — python-docx-Schreiber mit Firmen-Header + HIL-Hinweis, Chainlit File-Message Download
5. **Extraction Engine** — `extract_requirements()` zerlegt Lastenheft via Claude → AngebotData (Pydantic, JSON-retry)
6. **Generation Engine** — `generate_angebot()` erzeugt 4-Abschnitt-Angebotsentwurf via Claude + RAG-Retrieval
7. **Workflow UI** — `create_angebotsentwurf()` Guided-Flow: laden → extrahieren → HIL-Review → generieren → .docx-Download

### What Worked

- **Pydantic-typisiertes Output** für Extraktion + Generierung hat Halluzination drastisch reduziert: Modell liefert validiertes JSON statt Freitext
- **Human-in-the-Loop** vor Generierung war die richtige Entscheidung: Nutzer kann fehlerhafte Extraktion korrigieren, bevor teures Generate läuft
- **asyncio.to_thread** für Chainlit war einfach und wirkungsvoll: ein Wrapper behebt den Event-Loop-Block ohne Architekturumbau
- **SQLAlchemy DataLayer explizit** statt Chainlit BaseDataLayer: vermeidet versionspezifische API-Überraschungen
- **Separate DB URLs** (sync für Alembic, async für Chainlit) war einmal Aufwand, danach reibungslos

### What Was Inefficient

- **REQUIREMENTS.md-Checkboxen** wurden während der Implementierung nicht gepflegt — mehrere Requirements als "Pending" geführt obwohl implementiert (TECH-01)
- **v1 UI/UX-Phase (Phase 4 original)** wurde nie geplant und durch die v2 Workflow Engine ersetzt, ohne den Plan explizit zu entfernen — ROADMAP enthielt tote Phasen
- **Milestone-Version in GSD-Config** (v1.0) stimmte nicht mit der tatsächlichen Arbeit überein (v2 Workflow Engine lief parallel) — das führte zu gemischten Roadmaps

### Patterns Established

- **Workflow = load → extract → HIL → generate → output**: bewährte Reihenfolge für dokument-basierte KI-Workflows
- **AngebotData als zentrale Daten-Struktur**: typisiertes Objekt als Übergabe zwischen Extraktion und Generierung verhindert Kontextverlust
- **RAG-Kontext im system= Parameter** (nicht in user message): hält conversation turns sauber und Multi-Turn funktionsfähig

### Key Lessons

- **Checkboxen sofort pflegen**: REQUIREMENTS.md nach jedem Plan-Abschluss aktualisieren, nicht erst beim Milestone-Abschluss
- **Klare Milestone-Grenzen**: Wenn ein neuer Milestone beginnt, GSD-Config und ROADMAP sofort aktualisieren — nicht beides parallel im selben ROADMAP pflegen
- **Pydantic + JSON-Retry ist Pflicht für Extraktion**: LLM-Output immer gegen ein Schema validieren; retry bei ungültigem JSON ist billiger als Fehlerhandling nachträglich

### Cost Observations

- Model: claude-sonnet-4-6 für Antworten + Extraktion + Generierung
- Embeddings: nomic-embed-text via Ollama auf eigenem VPS — 0 €
- Ziel: < €0,02 pro Query (Chat)
- Angebotsentwurf-Workflow: ca. 2–4 Claude-Calls (Extraktion + Generierung) → schätzungsweise €0,05–0,15 pro Angebotsentwurf

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Duration | Key Theme |
|-----------|--------|-------|----------|-----------|
| v1.0 | 7 | 14 | 7 Tage | PoC → Pilot + Workflow Engine |
