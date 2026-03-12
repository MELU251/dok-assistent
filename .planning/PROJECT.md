# KI-Dokumenten-Assistent (RAGPoC)

## What This Is

Ein lokaler KI-Assistent für KMUs, der Mitarbeitern ermöglicht, PDF-, DOCX- und XLSX-Dokumente hochzuladen und in natürlicher Sprache Fragen dazu zu stellen. Antworten werden immer mit Quellenangabe (Dateiname + Seite) geliefert. Aktuell im PoC-Stadium mit dem Ziel, pilotfähig für einen ersten Kunden zu werden.

## Core Value

Ein Mitarbeiter lädt ein Dokument hoch, stellt eine Frage – und bekommt sofort eine präzise Antwort mit Quellenangabe, ohne externe API-Abhängigkeit bei den Embeddings.

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

### Active

- [ ] Stabile CI/CD-Pipeline (aktuell in Test-Phase, noch fehlerhaft)
- [ ] Chat-History: Persistente Gesprächs-Sessions (frühere Chats wieder öffnen)
- [ ] Chat-History: Multi-Turn-Kontext im laufenden Gespräch (KI kennt vorherige Fragen)
- [ ] Onboarding: Neuer Nutzer versteht sofort was er tun soll
- [ ] UI/UX-Polish: Oberfläche wirkt professionell und ist intuitiv bedienbar
- [ ] Antwortqualität: Evaluierung und Verbesserung der RAG-Güte
- [ ] Tech-Debt-Fixes: OllamaEmbeddings-Singleton, Async-Blocking, Supabase-Client-Caching
- [ ] Deployment: Stabile VPS-Erreichbarkeit via IP/Port für Pilotkunden

### Out of Scope

- Multi-Tenancy (UI-seitig) — nicht wichtig für Pilot; tenant_id="default" reicht
- OAuth / OIDC Auth — Pilot läuft via Tailscale-gesichertem VPS; Passwort-Auth ausreichend
- GDPR / Compliance-Features — Pilot-Phase, kein reguliertes Umfeld
- Eigene Domain / HTTPS — VPS direkt via IP/Port für Pilot ausreichend
- Skalierung > 5 gleichzeitige Nutzer — Pilot hat 1 Kunde

## Context

Der PoC ist technisch weitgehend funktionsfähig. Die Kernpipeline (load → chunk → embed → search → answer) läuft. Die CI/CD-Pipeline befindet sich aktuell im Test und ist noch nicht stabil. Bekannte technische Schulden: OllamaEmbeddings wird bei jedem Call neu instanziiert (Performance-Problem), Supabase-Client ebenso, und embed_and_store() blockiert den Chainlit-Eventloop synchron.

Der Pilotkunde soll das Produkt vollständig selbstständig nutzen können (einloggen, Dokumente hochladen, Fragen stellen, frühere Chats aufrufen) – ohne Begleitung. Das Ziel des Pilots ist Feedback sammeln, nicht sofortiger Verkauf.

Deployment-Ziel: Docker auf Hostinger VPS, erreichbar via IP:Port.

## Constraints

- **Tech Stack**: Python 3.11, LangChain, Chainlit, Supabase, Ollama — festgelegt, keine Grundsatzänderungen
- **Embeddings**: nomic-embed-text via Ollama auf VPS (768 Dimensionen) — kein OpenAI
- **Kosten**: Nur Anthropic API kostet; Ziel < €0,02 pro Query
- **Deployment**: Docker auf VPS, kein Kubernetes, kein Cloud-Managed-Service
- **Sprache**: Kommentare, Logs, Antworten auf Deutsch

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Chainlit als UI-Framework | Schnelle Demo-UI ohne Frontend-Entwicklung | — Pending (UI-Limitierungen sichtbar) |
| Supabase RPC direkt statt LangChain VectorStore | supabase-py 2.x Inkompatibilität mit LangChain-Wrapper | ✓ Good |
| Ollama via Tailscale statt öffentlichem Port | Sicherheit ohne Infrastrukturaufwand | ✓ Good |
| tenant_id hardcoded auf "default" | Multi-Tenancy für Pilot nicht nötig | — Pending |
| Blocking embed_and_store in async Kontext | Schnelle Implementierung, technische Schuld bekannt | ⚠️ Revisit |

---
*Last updated: 2026-03-12 after initialization*
