# KI-Dokumenten-Assistent (RAGPoC)

## What This Is

Ein lokaler KI-Assistent für KMUs, der Mitarbeitern ermöglicht, PDF-, DOCX- und XLSX-Dokumente hochzuladen und in natürlicher Sprache Fragen dazu zu stellen. Antworten werden immer mit Quellenangabe (Dateiname + Seite) geliefert. Der primäre Workflow-Use-Case: Ein Vertriebsingenieur lädt ein Lastenheft hoch und erhält auf Knopfdruck einen strukturierten Angebotsentwurf als .docx-Download — basierend auf historischen Angeboten aus der Wissensdatenbank.

## Core Value

Ein Mitarbeiter lädt ein Dokument hoch, stellt eine Frage – und bekommt sofort eine präzise Antwort mit Quellenangabe. Oder: er lädt ein Lastenheft hoch und bekommt in 30 Sekunden einen strukturierten Angebotsentwurf als .docx.

## Requirements

### Validated

- ✓ RAG-Pipeline (load → chunk → embed → store → search → answer) — existing
- ✓ Chainlit Web-UI mit Passwort-Auth — existing
- ✓ Datei-Upload über UI (PDF, DOCX, XLSX) — existing
- ✓ Dokument-Löschung über `/loeschen`-Befehl — existing
- ✓ Ollama-Embeddings via Tailscale VPN (nomic-embed-text, 768-dim) — existing
- ✓ Supabase pgvector als Vektordatenbank — existing
- ✓ Claude Sonnet als LLM mit deutschen Antworten + Quellenangabe — existing
- ✓ Kostentracking pro Query (EUR) — existing
- ✓ Docker-Containerisierung + docker-compose — existing
- ✓ CLI-Ingestion-Tool (ingest_cli.py) — existing
- ✓ OllamaEmbeddings/Supabase als Singletons — v1.0 (TECH-02, TECH-03)
- ✓ asyncio.to_thread für non-blocking Upload/Answer — v1.0 (TECH-01)
- ✓ Atomarer Delete-Flow (lokale Datei zuerst) — v1.0 (TECH-05)
- ✓ pytest testet OllamaEmbeddings korrekt (768-dim) — v1.0 (TECH-04)
- ✓ Drei-Job CI/CD-Pipeline: test → build → deploy mit Tailscale-Retry — v1.0 (CICD-01–03)
- ✓ Multi-Turn-Kontext (letzte 3 Turns im Gespräch) — v1.0 (CHAT-01)
- ✓ Persistente Chat-Sessions (Login → frühere Chats öffnen) — v1.0 (CHAT-02)
- ✓ Dokument-Filter: Fragen auf bestimmtes Dokument einschränken — v1.0 (CHAT-03)
- ✓ .docx-Schreiber + Chainlit-Download-Mechanismus — v1.0
- ✓ extract_requirements() → AngebotData (Pydantic, JSON-validiert) — v1.0
- ✓ generate_angebot(): 4-Abschnitt-Entwurf via Claude + RAG — v1.0
- ✓ create_angebotsentwurf() Guided-Flow mit Human-in-the-Loop + .docx-Download — v1.0

### Active (Next Milestone)

- [ ] UI/UX Polish: Deutschsprachige Willkommensnachricht beim ersten Login (UI-01)
- [ ] UI/UX Polish: Dokument-Liste jederzeit im Chat abrufbar (UI-02)
- [ ] UI/UX Polish: Alle Fehlermeldungen auf Deutsch, keine englischen Stack Traces (UI-03)
- [ ] UI/UX Polish: Quellenangaben als formatierte Karte prominent dargestellt (UI-04)
- [ ] RAG-Qualität: RAGAS-Evaluierung mit Golden Dataset (RAG-01)
- [ ] Antwortqualität-Indikator: HIL-Hinweis bei niedriger Cosine-Similarity (RAG-02)

### Out of Scope

- Multi-Tenancy (UI-seitig) — nicht wichtig für Pilot; tenant_id="default" reicht
- OAuth / OIDC Auth — Pilot läuft via Tailscale-gesichertem VPS; Passwort-Auth ausreichend
- GDPR / Compliance-Features — Pilot-Phase, kein reguliertes Umfeld
- Eigene Domain / HTTPS — VPS direkt via IP/Port für Pilot ausreichend
- Skalierung > 5 gleichzeitige Nutzer — Pilot hat 1 Kunde
- Streaming-Antworten — nur wenn Pilot-Feedback Latenz als Problem benennt (v2+)
- Dokumenten-Versionierung — nicht nötig für Pilot

## Context

**Current State (nach v1.0):**
- ~3.800 LOC Python (src/, app.py, tests/)
- Tech Stack: Python 3.11, LangChain, Chainlit, Supabase, Ollama, Claude, Docker
- Deployment: Docker auf Hostinger VPS, erreichbar via Tailscale-IP
- CI/CD: GitHub Actions, drei Jobs (test/build/deploy), Health-Check nach Deploy
- Datenbank: Supabase pgvector für Embeddings + SQLAlchemy für Chat-History (Chainlit DataLayer)

**Shipped v1.0:** Vollständige RAG-Pipeline + CI/CD + Chat-History + Angebotsentwurf-Workflow als .docx. Bereit für Pilot-Test mit erstem Kunden.

**Next:** Feedback aus Pilot sammeln, dann UI/UX-Polish und RAG-Qualitätsverbesserungen angehen.

## Constraints

- **Tech Stack**: Python 3.11, LangChain, Chainlit, Supabase, Ollama — festgelegt, keine Grundsatzänderungen
- **Embeddings**: nomic-embed-text via Ollama auf VPS (768 Dimensionen) — kein OpenAI
- **Kosten**: Nur Anthropic API kostet; Ziel < €0,02 pro Query
- **Deployment**: Docker auf VPS, kein Kubernetes, kein Cloud-Managed-Service
- **Sprache**: Kommentare, Logs, Antworten auf Deutsch

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Chainlit als UI-Framework | Schnelle Demo-UI ohne Frontend-Entwicklung | ⚠️ Revisit — UI-Customization limitiert |
| Supabase RPC direkt statt LangChain VectorStore | supabase-py 2.x Inkompatibilität mit LangChain-Wrapper | ✓ Good |
| Ollama via Tailscale statt öffentlichem Port | Sicherheit ohne Infrastrukturaufwand | ✓ Good |
| tenant_id hardcoded auf "default" | Multi-Tenancy für Pilot nicht nötig | ✓ Good |
| asyncio.to_thread für embed_and_store/answer | Non-blocking Chainlit Event-Loop | ✓ Good |
| SQLAlchemy DataLayer (explizit) vs BaseDataLayer | Vermeidet API-Coupling-Risiko in Chainlit 2.x | ✓ Good |
| DATABASE_URL (sync) + ASYNC_DATABASE_URL (async) | Chainlit 2.x benötigt asyncpg; Alembic braucht sync psycopg2 | ✓ Good |
| RAG context in system= Parameter | Hält conversation turns sauber für Multi-Turn (CHAT-01) | ✓ Good |
| source_filter als client-seitiger Post-Filter | Vermeidet Schema-Änderungen; match_count verdreifacht als Ausgleich | — Pending |
| Angebotsentwurf als Guided-Flow mit HIL | Nutzer prüft Extraktion vor Generierung; reduziert halluziniertes Output | ✓ Good |

---
*Last updated: 2026-03-18 after v1.0 milestone*
