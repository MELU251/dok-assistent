---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: Completed 03-chat-history-and-multi-turn-context/03-02-PLAN.md
last_updated: "2026-03-17T17:18:14.197Z"
last_activity: 2026-03-12 — Roadmap created; ready to plan Phase 1
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 10
  completed_plans: 9
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Ein KMU-Mitarbeiter lädt ein Dokument hoch und bekommt sofort eine präzise Antwort mit Quellenangabe – ohne Begleitung, ohne technisches Vorwissen.
**Current focus:** Phase 1 — Tech Debt Foundation

## Current Position

Phase: 1 of 4 (Tech Debt Foundation)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-03-12 — Roadmap created; ready to plan Phase 1

Progress: [███░░░░░░░] 25%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-tech-debt-foundation P01 | 5min | 2 tasks | 6 files |
| Phase 01-tech-debt-foundation P04 | 15min | 1 tasks | 2 files |
| Phase 01-tech-debt-foundation P02 | 15min | 1 tasks | 2 files |
| Phase 02-cicd-stabilization P01 | 2min | 2 tasks | 1 files |
| Phase 02-cicd-stabilization P01 | 45min | 3 tasks | 2 files |
| Phase 03-chat-history-and-multi-turn-context P01 | 10min | 2 tasks | 6 files |
| Phase 03-chat-history-and-multi-turn-context P04 | 12min | 1 tasks | 3 files |
| Phase 03-chat-history-and-multi-turn-context P02 | 4min | 2 tasks | 7 files |
| Phase 03-chat-history-and-multi-turn-context P03 | 5min | 1 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: TECH-01 (async fix) identified as single highest-priority prerequisite — Phase 1 must complete before Phase 3 begins
- Roadmap: Phase 2 (CI/CD) depends on Phase 1 but is otherwise independent of Phase 3; can be planned in parallel
- Architecture: Explicit `src/history.py` pattern recommended over Chainlit `BaseDataLayer` to avoid API coupling risk (verify live before Phase 3 starts)
- Architecture: RAGAS evaluation (RAG-01, RAG-02) deferred to v2 — not in v1 roadmap
- [Phase 01-tech-debt-foundation]: Patch target src.ingest.OllamaEmbeddings correct for current code; will shift to _get_embedder after Plan 02
- [Phase 01-tech-debt-foundation]: pytest-asyncio asyncio_mode=auto via pytest.ini to avoid per-test marker drift
- [Phase 01-tech-debt-foundation]: Unsupported-extension test uses .csv (not .txt) because .txt is now in the ingest.py supported set
- [Phase 01-tech-debt-foundation]: Local file presence is the authoritative delete guard — get_indexed_documents() pre-flight removed from _run_delete_flow
- [Phase 01-tech-debt-foundation]: local_file.unlink() called BEFORE delete_document to ensure file-first atomic delete order (TECH-05)
- [Phase 01-tech-debt-foundation]: get_settings() still called directly in embed_and_store() for log message — test must mock get_settings alongside _get_embedder/_get_supabase_client
- [Phase 01-tech-debt-foundation]: Patch target is getter function (_get_embedder) not class (OllamaEmbeddings) when lru_cache is in the call chain — avoids cached real instance in tests
- [Phase 02-cicd-stabilization]: tailscale/github-action@v4 used (not v2): v4 adds ping: pre-flight for VPS reachability before SSH
- [Phase 02-cicd-stabilization]: Wandalen/wretry.action@master wraps nc check with attempt_limit=3 — replaces bare nc with no retry
- [Phase 02-cicd-stabilization]: MAX_WAIT=120s for health check: Docker window is 20s start_period + 3x30s interval = 110s max
- [Phase 02-cicd-stabilization]: packages:write permission only on build job; deploy job uses contents:read only
- [Phase 02-cicd-stabilization]: tailscale/github-action@v4 sets --accept-routes/--accept-dns internally — passing them in args: causes duplicate-flag CI failure; removed after live verification
- [Phase 02-cicd-stabilization]: Integration tests excluded in CI via pytest -m 'not integration' — live Ollama/Supabase unavailable in GitHub-hosted runners
- [Phase 02-cicd-stabilization]: get_settings mock added to test_ingest.py — embed_and_store() calls get_settings() directly for log message, not via singleton getter
- [Phase 03-chat-history-and-multi-turn-context]: xfail(strict=True) used for all Wave 0 stubs — accidental pass-through causes test error, preventing false greens
- [Phase 03-chat-history-and-multi-turn-context]: test_migrations.py uses pytestmark = pytest.mark.integration to auto-exclude from CI non-integration runs
- [Phase 03-chat-history-and-multi-turn-context]: RAG context placed in system= parameter (not merged into user message) — keeps conversation turns clean for multi-turn context (CHAT-01)
- [Phase 03-chat-history-and-multi-turn-context]: _SYSTEM_PROMPT_TEMPLATE replaces _SYSTEM_PROMPT — template has {context} only, question goes into messages=
- [Phase 03-chat-history-and-multi-turn-context]: History window cap: (history or [])[-6:] gives last 3 turns (6 messages) before appending current question
- [Phase 03-chat-history-and-multi-turn-context]: Hand-written op.execute() migrations (not autogenerate) because pgvector vector() type is not natively understood by SQLAlchemy reflection
- [Phase 03-chat-history-and-multi-turn-context]: IF NOT EXISTS guards in all DDL — alembic upgrade head is idempotent on existing DBs with document_chunks
- [Phase 03-chat-history-and-multi-turn-context]: Chainlit 2.10.0 requires exact camelCase column names (createdAt, userId, threadId) — snake_case causes runtime SQL errors
- [Phase 03-chat-history-and-multi-turn-context]: DATABASE_URL (sync postgresql://) for Alembic, ASYNC_DATABASE_URL (postgresql+asyncpg://) for Chainlit SQLAlchemyDataLayer — separate env vars required
- [Phase 03-chat-history-and-multi-turn-context]: source_filter is a client-side post-filter on RPC results (not DB-side) — avoids schema changes, match_count tripled to compensate
- [Phase 03-chat-history-and-multi-turn-context]: Retrieval unit tests must mock get_settings alongside _get_embedder/_get_supabase_client — get_settings() called directly in search() for top_k_results

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 3 prerequisite:** Chainlit 2.x `BaseDataLayer` API surface needs live verification before Phase 3 implementation. Run: `python -c "from chainlit.data import BaseDataLayer; import inspect; print(inspect.getsource(BaseDataLayer))"` before planning Phase 3.
- **Phase 3 prerequisite:** Confirm `RunnableWithMessageHistory` import path in installed `langchain-core` version before starting Phase 3.

## Session Continuity

Last session: 2026-03-17T17:18:04.493Z
Stopped at: Completed 03-chat-history-and-multi-turn-context/03-02-PLAN.md
Resume file: None
