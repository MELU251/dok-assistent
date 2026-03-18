# Milestones

## v1.0 Pilot-Ready + Workflow Engine (Shipped: 2026-03-18)

**Phases completed:** 7 phases, 14 plans
**Timeline:** 2026-03-11 → 2026-03-18 (7 Tage)
**LOC:** ~3.800 Python

**Key accomplishments:**
1. Stabiles Fundament: OllamaEmbeddings/Supabase als Singletons, asyncio.to_thread, atomarer Delete-Flow (TECH-01–05)
2. Drei-Job CI/CD-Pipeline: test → build → deploy mit Tailscale-Retry und Post-Deploy-Health-Check (CICD-01–03)
3. Persistente Chat-Sessions und Multi-Turn-Kontext: SQLAlchemy DataLayer, Alembic-Migrationen, 3-Turn-History-Fenster (CHAT-01–03)
4. `.docx`-Schreiber + Chainlit-Download-Mechanismus als Ausgabefundament
5. `extract_requirements()` → AngebotData: Strukturierte Lastenheft-Analyse via Claude (Pydantic-typisiert)
6. `generate_angebot()`: 4-Abschnitt-Angebotsentwurf via Claude + RAG-Kontext mit Quellenangaben
7. `create_angebotsentwurf()`: Chainlit-Guided-Flow mit Human-in-the-Loop und .docx-Download

**Known Gaps (accepted tech debt):**
- UI-01–04: UI/UX Polish (Willkommensnachricht, Dokument-Liste, deutsche Fehler, Karten-Quellenangaben) — nicht implementiert, für nächsten Milestone
- TECH-01: In REQUIREMENTS.md als unchecked, laut Phase 1 Plan 03 aber implementiert (asyncio.to_thread)

**Archive:**
- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`

---

