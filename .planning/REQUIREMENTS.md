# Requirements: KI-Dokumenten-Assistent (RAGPoC)

**Defined:** 2026-03-12
**Core Value:** Ein KMU-Mitarbeiter lädt ein Dokument hoch und bekommt sofort eine präzise Antwort mit Quellenangabe – ohne Begleitung, ohne technisches Vorwissen.

## v1 Requirements

Requirements für den Pilot-Launch. Jedes Requirement mappt auf eine Roadmap-Phase.

### Tech Debt

- [ ] **TECH-01**: `embed_and_store()` und `pipeline.answer()` laufen in separaten Threads (asyncio.to_thread()), sodass der Chainlit-Event-Loop nicht blockiert wird
- [x] **TECH-02**: `OllamaEmbeddings`-Instanz wird als Modul-Level-Singleton gecacht – nicht bei jedem Embedding-Call neu erstellt
- [x] **TECH-03**: Supabase-Client wird als Singleton gecacht – nicht in `ingest.py`, `retrieval.py` und `app.py` mehrfach instanziiert
- [x] **TECH-04**: `test_ingest.py` patcht `OllamaEmbeddings` (nicht `OpenAIEmbeddings`) – CI testet den tatsächlichen Embedding-Pfad
- [x] **TECH-05**: Delete-Flow löscht zuerst die lokale Datei, dann die Supabase-Records; bei Datei-Fehler wird Supabase nicht angefasst

### CI/CD

- [ ] **CICD-01**: pytest-Schritt läuft als eigener GitHub-Actions-Job vor Build und Deploy – fehlgeschlagene Tests blockieren das Deployment
- [ ] **CICD-02**: Workflow ist in separate Jobs aufgeteilt: `test → build → deploy` mit expliziten `needs:`-Abhängigkeiten
- [ ] **CICD-03**: Tailscale-Verbindung im Deploy-Job hat Retry-Logik; nach `docker compose up -d` wird ein Container-Health-Check ausgeführt

### Chat & Kontext

- [ ] **CHAT-01**: Im laufenden Gespräch kennt die KI die letzten 3 Gesprächs-Turns (6 Messages) als Kontext – Folgefragen werden korrekt beantwortet
- [ ] **CHAT-02**: Nutzer sieht nach dem Login eine Liste seiner früheren Chat-Sessions und kann eine davon wieder öffnen (persistiert in Supabase)
- [ ] **CHAT-03**: Nutzer kann Fragen auf ein bestimmtes hochgeladenes Dokument eingrenzen (Filter in der UI, der `source` an `retrieval.search()` weitergibt)

### UI/UX

- [ ] **UI-01**: Beim ersten Chat-Start erscheint eine deutschsprachige Willkommensnachricht die erklärt: wie man ein Dokument hochlädt, wie man Fragen stellt, und was das System kann und nicht kann
- [ ] **UI-02**: Nutzer kann jederzeit im laufenden Chat die Liste der aktuell geladenen Dokumente abrufen (nicht nur beim Session-Start)
- [ ] **UI-03**: Alle benutzersichtbaren Fehlermeldungen erscheinen auf Deutsch; keine technischen englischen Fehlertexte (RuntimeError, connection refused etc.) erreichen den Nutzer
- [ ] **UI-04**: Quellenangaben werden als formatierte Karte prominent dargestellt (Dateiname + Seite visuell hervorgehoben), nicht als Fließtext am Antwortende

## v2 Requirements

Zurückgestellt auf nach dem Pilot. Wird nach Kundenfeedback priorisiert.

### RAG-Qualität

- **RAG-01**: Golden Dataset (10–20 domänenspezifische Fragen) erstellt und als RAGAS-Evaluierung in CI integriert
- **RAG-02**: Antwortqualitäts-Indikator: Bei niedriger Cosine-Similarity (<0,6) erscheint ein Hinweis auf unsichere Antwort

### Features

- **FEAT-01**: Streaming-Antworten (Wort-für-Wort-Ausgabe wie ChatGPT)
- **FEAT-02**: Dokumenten-Versionierung (gleicher Dateiname erzeugt neue Version statt Überschreiben)

## Out of Scope

Explizit ausgeschlossen. Begründung verhindert späteres Scope-Creep.

| Feature | Begründung |
|---------|------------|
| Multi-User-Verwaltung (Admin-UI) | Pilot: 1 Kunde, 1–3 Nutzer; Passwort-Auth via .env ausreichend |
| Rollenbasierte Zugriffskontrolle (RBAC) | Kein Bedarf im Pilot; kein isoliertes Dokumenten-Zugriffsszenario |
| GDPR-Compliance-Features (Exportpflicht, Audit-Log) | Pilot-Phase; kein reguliertes Umfeld |
| E-Mail-Benachrichtigungen | Kein Mehrwert im Pilot; UI-Progress-Steps reichen |
| Analytics-Dashboard | Raw Supabase-Daten für Feedback-Auswertung ausreichend |
| OCR für gescannte PDFs (strategy="hi_res") | 5-10x längere Ingest-Zeit; Pilot-Dokumente sollen Text-PDFs sein |
| OAuth / OIDC | Tailscale-gesicherter VPS; Passwort-Auth für Pilot ausreichend |
| Eigene Domain / HTTPS-Zertifikat | VPS direkt via IP:Port für Pilot ausreichend |
| Streaming-Antworten | v2 – nur wenn Pilot-Feedback Latenz als Problem benennt |
| Multi-Tenancy (UI-seitig) | tenant_id="default" für Single-Customer-Pilot ausreichend |

## Traceability

Welche Phasen welche Requirements abdecken.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TECH-01 | Phase 1 | Pending |
| TECH-02 | Phase 1 | Complete |
| TECH-03 | Phase 1 | Complete |
| TECH-04 | Phase 1 | Complete |
| TECH-05 | Phase 1 | Complete |
| CICD-01 | Phase 2 | Pending |
| CICD-02 | Phase 2 | Pending |
| CICD-03 | Phase 2 | Pending |
| CHAT-01 | Phase 3 | Pending |
| CHAT-02 | Phase 3 | Pending |
| CHAT-03 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |

**Coverage:**
- v1 Requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 — full coverage

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-12 after roadmap creation*
