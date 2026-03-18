# Roadmap: KI-Dokumenten-Assistent

## Milestones

- ✅ **v1.0 Pilot-Ready + Workflow Engine** — Phases 1–7 (shipped 2026-03-18)
- 🔧 **v1.1 Gap Closure** — Phases 8–9 (in progress)

## Phases

<details>
<summary>✅ v1.0 Pilot-Ready + Workflow Engine (Phases 1–7) — SHIPPED 2026-03-18</summary>

- [x] Phase 1: Tech Debt Foundation (4/4 plans) — completed 2026-03-16
- [x] Phase 2: CI/CD Stabilization (1/1 plan) — completed 2026-03-17
- [x] Phase 3: Chat History and Multi-Turn Context (5/5 plans) — completed 2026-03-17
- [x] Phase 4: Output Foundation (1/1 plan) — completed 2026-03-17
- [x] Phase 5: Extraction Engine (1/1 plan) — completed 2026-03-17
- [x] Phase 6: Generation Engine (1/1 plan) — completed 2026-03-17
- [x] Phase 7: Workflow UI (1/1 plan) — completed 2026-03-17

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### 🔧 v1.1 — Gap Closure

Schließt alle offenen Gaps aus dem v1.0-Audit (UI/UX-Phase die nie ausgeführt wurde + Workflow-Code-Qualität).

#### Phase 8: UI/UX Polish
**Goal:** Alle UI/UX-Requirements aus v1.0 sind verifiziert und vollständig implementiert — `/dokumente`-Befehl für mid-session Dokumenten-Liste, verifizierte Willkommensnachricht, vollständige deutsche Fehlerbehandlung, visuelle Quellenangaben
**Requirements:** UI-01, UI-02, UI-03, UI-04
**Gap Closure:** Schließt Audit-Gaps UI-01..04 (v1.0 UI-Phase die durch Workflow Engine ersetzt wurde)
**Plans:** 2 plans

- [ ] Phase 8: UI/UX Polish (0/2 plans)

Plans:
- [ ] 08-01-PLAN.md — Testgeruest (xfail-Stubs) fuer UI-01..04
- [ ] 08-02-PLAN.md — Implementierung: /dokumente, Willkommensnachricht, Fehlertext-Bereinigung, cl.Text-Quellenangaben

#### Phase 9: Workflow Code Quality
**Goal:** `hil_hinweis` ist im Chainlit-Chat sichtbar; toter Import `create_angebotsentwurf` ist bereinigt; doppelte Singletons konsolidiert
**Requirements:** WORK-04, WORK-06
**Gap Closure:** Schließt Audit-Gaps WORK-04, WORK-06 + Integration-Issues (dead code, dual singletons)

- [ ] Phase 9: Workflow Code Quality (0/1 plans)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Tech Debt Foundation | v1.0 | 4/4 | Complete | 2026-03-16 |
| 2. CI/CD Stabilization | v1.0 | 1/1 | Complete | 2026-03-17 |
| 3. Chat History + Multi-Turn | v1.0 | 5/5 | Complete | 2026-03-17 |
| 4. Output Foundation | v1.0 | 1/1 | Complete | 2026-03-17 |
| 5. Extraction Engine | v1.0 | 1/1 | Complete | 2026-03-17 |
| 6. Generation Engine | v1.0 | 1/1 | Complete | 2026-03-17 |
| 7. Workflow UI | v1.0 | 1/1 | Complete | 2026-03-17 |
| 8. UI/UX Polish | v1.1 | 0/2 | Pending | — |
| 9. Workflow Code Quality | v1.1 | 0/1 | Pending | — |
