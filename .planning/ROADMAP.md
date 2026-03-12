# Roadmap: KI-Dokumenten-Assistent — PoC to Pilot-Ready

## Overview

Der PoC ist technisch funktionsfähig. Dieser Milestone bringt das Produkt auf Pilot-Reife: zuerst wird das technische Fundament stabilisiert (async-Fix, Singletons, korrekte Test-Mocks), dann die CI/CD-Pipeline abgesichert, dann die vom Pilotkunden erwarteten Chat-Features implementiert (Multi-Turn und Persistenz), und schließlich die Oberfläche auf professionellen Ersteindruck gebracht. Jede Phase liefert einen abgeschlossenen, verifizierbaren Zustand.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Tech Debt Foundation** - Stabiles, concurrent-sicheres Fundament als Voraussetzung für alle weiteren Features
- [ ] **Phase 2: CI/CD Stabilization** - Drei-Job-Pipeline (test → build → deploy) mit Pytest-Gate und Post-Deploy-Health-Check
- [ ] **Phase 3: Chat History and Multi-Turn Context** - Persistente Gesprächs-Sessions und Multi-Turn-Kontext als table-stakes Pilot-Features
- [ ] **Phase 4: UI/UX Polish** - Professioneller Ersteindruck: Onboarding, Dokument-Inventar, deutsche Fehlermeldungen, prominente Quellenangaben

## Phase Details

### Phase 1: Tech Debt Foundation
**Goal**: Der Chainlit-Event-Loop blockiert nicht mehr; alle externen Clients werden als Singletons gecacht; Tests decken den tatsächlichen Code-Pfad ab; der Delete-Flow ist atomar korrekt
**Depends on**: Nothing (first phase)
**Requirements**: TECH-01, TECH-02, TECH-03, TECH-04, TECH-05
**Success Criteria** (what must be TRUE):
  1. Ein Dokument-Upload blockiert die UI nicht mehr — andere Nutzer-Aktionen bleiben während des Uploads ansprechbar
  2. Nach 20 aufeinanderfolgenden Queries hat die App keine TCP-Verbindungserschöpfung auf dem VPS (OllamaEmbeddings- und Supabase-Client-Instanzen sind Singletons)
  3. `pytest` läuft grün und testet tatsächlich `OllamaEmbeddings` (nicht OpenAI); Dimension-Assertion ist 768, nicht 1536
  4. Ein `/loeschen`-Befehl, der die lokale Datei nicht findet, hinterlässt die Supabase-Records unberührt
**Plans**: TBD

### Phase 2: CI/CD Stabilization
**Goal**: Kein gebrochener Code erreicht den VPS — Tests laufen vor jedem Build, Build läuft vor jedem Deploy, und der Deploy wird aktiv verifiziert
**Depends on**: Phase 1
**Requirements**: CICD-01, CICD-02, CICD-03
**Success Criteria** (what must be TRUE):
  1. Ein Commit mit einem fehlschlagenden `pytest` resultiert in einem roten CI-Status — kein Docker-Image wird gebaut, kein Deploy findet statt
  2. Ein erfolgreicher Workflow zeigt drei separate grüne Jobs in der GitHub-Actions-UI: `test`, `build`, `deploy` mit sichtbaren `needs:`-Abhängigkeiten
  3. Nach `docker compose up -d` auf dem VPS führt der Workflow einen Health-Check durch und schlägt fehl (statt stillschweigend zu passieren), wenn der Container nicht healthy ist
  4. Tailscale-Verbindungsfehler im Deploy-Job werden mindestens einmal wiederholt, bevor der Job fehlschlägt
**Plans**: TBD

### Phase 3: Chat History and Multi-Turn Context
**Goal**: Nutzer können ein Gespräch fortsetzen — sowohl innerhalb einer Session (KI kennt vorherige Turns) als auch über Sessions hinweg (frühere Chats sind wieder abrufbar)
**Depends on**: Phase 1
**Requirements**: CHAT-01, CHAT-02, CHAT-03
**Success Criteria** (what must be TRUE):
  1. Eine Folgefrage ("Was sagt er noch dazu?") wird korrekt beantwortet — die KI bezieht sich auf das Thema der vorherigen Frage ohne Wiederholung des Kontexts durch den Nutzer
  2. Nach dem Logout und erneutem Login sieht der Nutzer eine Liste früherer Chat-Sessions und kann eine davon öffnen — die Nachrichten erscheinen vollständig
  3. Nutzer kann eine Frage auf ein spezifisches hochgeladenes Dokument eingrenzen — die Antwort referenziert nur Chunks aus diesem Dokument
**Plans**: TBD

### Phase 4: UI/UX Polish
**Goal**: Ein Pilotkunde ohne technisches Vorwissen kann sich beim ersten Login selbstständig orientieren, Dokumente hochladen, Fragen stellen und die Antworten vertrauenswürdig einordnen
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. Ein neuer Nutzer sieht beim ersten Chat-Start eine deutschsprachige Willkommensnachricht, die erklärt was das System kann, wie man ein Dokument hochlädt, und wie man eine Frage stellt — ohne Suche im Handbuch
  2. Nutzer kann jederzeit während eines laufenden Chats eine Liste der aktuell geladenen Dokumente abrufen (nicht nur beim Session-Start)
  3. Kein englischer Fehlertext (RuntimeError, connection refused, stack trace) ist für den Nutzer sichtbar — alle Fehlerzustände erscheinen als verständliche deutsche Meldungen
  4. Quellenangaben erscheinen visuell hervorgehoben (Dateiname + Seite als formatierte Karte), nicht als Fließtext am Ende der Antwort
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Tech Debt Foundation | 0/TBD | Not started | - |
| 2. CI/CD Stabilization | 0/TBD | Not started | - |
| 3. Chat History and Multi-Turn Context | 0/TBD | Not started | - |
| 4. UI/UX Polish | 0/TBD | Not started | - |
