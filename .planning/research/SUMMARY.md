# Project Research Summary

**Project:** KI-Dokumenten-Assistent — PoC to Pilot-Ready
**Domain:** RAG document assistant (KMU / Mittelstand)
**Researched:** 2026-03-12
**Confidence:** MEDIUM (external web tools unavailable; based on codebase inspection + training knowledge through August 2025)

## Executive Summary

This project has a working PoC with the core RAG pipeline implemented: file upload, vector search via Supabase pgvector, Ollama embeddings over Tailscale, Anthropic Claude for answer generation, and a Chainlit UI. The transition to pilot-ready is not a greenfield build — it is a targeted hardening effort across four well-scoped areas: fixing foundational tech debt (blocking async calls, stale test mocks, connection singletons), stabilizing CI/CD, improving RAG answer quality with a minimal evaluation harness, and adding the two features that every pilot customer will expect on day one: persistent chat history and multi-turn conversation context.

The recommended approach is to attack tech debt first and in full before adding features. The blocking `embed_and_store()` call inside Chainlit's async event loop is a load-bearing defect: it makes the UI freeze during uploads, prevents concurrent usage, and undermines every other feature that depends on a stable session. Once the foundation is solid, chat history and multi-turn context can be added with minimal new infrastructure — both features re-use the existing Supabase instance and require no new external services. The only genuinely new dependency is RAGAS for evaluation, and even that runs against the existing Anthropic API.

The key risks are: (1) the Chainlit 2.x `BaseDataLayer` API surface has changed across versions and must be verified before implementing session persistence — the research recommends an explicit, non-framework-coupled pattern in `src/history.py` as a safer alternative; (2) RAGAS API surface changed between 0.0.x and 0.1.x and must be verified against the installed version; (3) the Tailscale-dependent CI/CD pipeline has no retry logic and no test gate, meaning a failed test can still result in a broken image being deployed. Addressing these three risks in the correct order produces a pilot-ready product in 5 focused phases.

---

## Key Findings

### Recommended Stack

The existing stack (Python 3.11, LangChain 0.3+, Chainlit 2.0+, Supabase, Ollama, Anthropic Claude) is correct and requires no new major dependencies for the pilot milestone. Chat history and multi-turn context are implemented using packages already present: `langchain-core` (`RunnableWithMessageHistory` or manual messages-array prepend), `supabase-py` (two new tables), and Chainlit hooks. The only new packages needed are `ragas` and `datasets` for evaluation.

**Core technologies:**
- `langchain-core` (`RunnableWithMessageHistory`): multi-turn history — already a dependency; `ConversationBufferMemory` is deprecated and must not be used
- `supabase-py` + two new tables (`chat_sessions`, `chat_messages`): session and message persistence — no new external services
- `ragas` + `datasets`: automated RAG quality metrics (faithfulness, answer relevancy, context precision, context recall) — new; configure with Claude as judge, not OpenAI
- GitHub Actions (`actions/cache@v4`, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6`): CI/CD hardening — replace current single monolithic job with test → build → deploy chain
- `asyncio.to_thread()`: wrapping all blocking I/O in async handlers — no new package; critical correctness fix

**Critical version note:** Pin all requirements to exact versions using `pip-compile` before pilot launch. Loose pins have already caused silent breakage when LangChain or Chainlit release minor versions with breaking changes.

### Expected Features

The PoC already covers: file upload (PDF/DOCX/XLSX), single-turn Q&A with source attribution, per-query cost tracking, document deletion, password auth, Docker deployment.

**Must have (table stakes — blocks pilot without these):**
- Multi-turn conversation context — without it, every follow-up question is treated as unrelated; pilot customer will immediately notice
- Persistent chat history (thread list) — users expect to return tomorrow and find yesterday's conversations
- Onboarding/first-run guidance — KMU employees are not technical; blank chat box with no instructions creates confusion
- Document inventory accessible mid-conversation — not just at session start
- All user-facing error messages in German — any English error destroys trust in a German-language product
- Stable async event loop — the blocking embed_and_store is a prerequisite for all of the above working correctly

**Should have (competitive, add after pilot validation):**
- Answer quality indicator with similarity score threshold
- Document-scoped question filtering (filter by specific uploaded file)
- Streaming responses (only if latency feedback is negative)

**Defer to v2+ (SaaS phase):**
- Multi-user account management and RBAC
- GDPR data export and audit logs
- Email notifications and analytics dashboard
- OCR for scanned PDFs (hi_res strategy)

**Anchor insight:** The pilot customer's reference point is plain ChatGPT. ChatGPT has chat history and multi-turn context by default. Without these two features, the pilot customer says "ChatGPT already does this." These features are non-negotiable for the pilot to feel like a step forward, not backward.

### Architecture Approach

The architecture is additive: the four existing modules (`config.py`, `ingest.py`, `retrieval.py`, `pipeline.py`) are largely unchanged. A new `src/history.py` module handles session CRUD and message persistence against two new Supabase tables. `pipeline.answer()` gains an optional `conversation_history` parameter (backward-compatible). `app.py` wires session creation in `on_chat_start` and history load/save around `on_message`. The explicit pattern (calling `history.py` functions directly in `app.py` hooks) is recommended over implementing `BaseDataLayer` to avoid Chainlit API coupling risk. For multi-turn context, the correct mechanism is the Anthropic messages array — RAG context in the `system=` parameter, conversation history in the `messages=[...]` array, never mixed into the system prompt as a string.

**Major components:**
1. `src/history.py` (new) — session CRUD and message persistence; pure data access; no RAG logic
2. `src/pipeline.py` (modified) — accepts `conversation_history` parameter; separates static system instructions from RAG context and conversation history
3. Supabase `chat_sessions` + `chat_messages` tables (new) — append-only message log with per-message cost tracking and cascade delete
4. GitHub Actions test → build → deploy jobs (refactored) — test gate prevents broken images reaching the registry; Tailscale connect moved to deploy job only
5. RAGAS evaluation harness (`tests/eval/`) — 10-20 golden question/answer pairs; run in CI against fixed dataset only (not on live queries)

### Critical Pitfalls

1. **Blocking sync code inside Chainlit's async event loop** — `embed_and_store()` and `answer()` are called directly in `async def` handlers; this blocks the entire server during uploads (20-60 seconds for large PDFs). Fix: wrap all blocking calls with `asyncio.to_thread()`. This is the single highest-priority fix; everything else depends on a stable event loop.

2. **OllamaEmbeddings and Supabase client recreated per call** — new TCP connections on every call causes exhaustion on the VPS after ~10-20 requests. Fix: module-level singleton with `@lru_cache(maxsize=1)` for both `OllamaEmbeddings` and the Supabase client; 5-line change per module.

3. **Stale test mocks giving false CI confidence** — `test_ingest.py` patches `src.ingest.OpenAIEmbeddings` but the module uses `OllamaEmbeddings`; the patch is a no-op; CI passes while hiding real integration failures. Fix: update patch target to `src.ingest.OllamaEmbeddings`; add `mock.assert_called_once()`; update dimension assertions from 1536 to 768.

4. **No test gate in CI — broken images can be deployed** — the current workflow has no `pytest` step; a broken commit can push an image to GHCR and deploy to VPS before any failure is detected. Fix: split into three sequential jobs (test → build → deploy); build only runs if tests pass.

5. **No RAG evaluation — quality degrades silently** — adding more documents can degrade retrieval quality with no signal. Without a golden evaluation set, this is only discovered through pilot customer negative feedback. Fix: create 10-20 question/answer pairs before pilot launch; score with RAGAS metrics (target: faithfulness ≥ 0.85, answer relevancy ≥ 0.80).

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Tech Debt Foundation
**Rationale:** Every other feature depends on a stable event loop and correct test infrastructure. Shipping features on top of the async bug means they will be unreliable. This phase has no feature value to the end user but is the prerequisite for all subsequent phases being trustworthy.
**Delivers:** Stable, concurrent-safe event loop; correct test mocks with accurate CI signal; singleton connection clients; delete operation correctness
**Addresses:** Table-stakes prerequisite (stable login, upload progress that works)
**Avoids:** Pitfalls 1 (blocking event loop), 2 (TCP exhaustion), 3 (stale mocks), 4 (delete race condition)
**Research flag:** Standard patterns — `asyncio.to_thread()` and `@lru_cache` singletons are well-documented; no phase research needed

### Phase 2: CI/CD Stabilization
**Rationale:** CI must be reliable before new features are merged. A flaky pipeline that deploys broken code makes feature development slower and riskier. CI work is independent of session history work and can run in parallel with Phase 3 if capacity allows, but must complete before Phase 4 merges.
**Delivers:** Three-job pipeline (test → build → deploy) with pytest gate; Docker layer caching; Tailscale retry logic; health check post-deploy
**Uses:** `actions/cache@v4`, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6`
**Avoids:** Pitfall 4 (no test gate), Pitfall 6 (flaky Tailscale deploys)
**Research flag:** Standard GitHub Actions patterns — HIGH confidence; no phase research needed

### Phase 3: RAG Quality Evaluation
**Rationale:** Must be completed before pilot launch, not after. If retrieval quality is poor, the pilot customer experience is poor and no UX improvement fixes it. Establishing a baseline now also provides regression protection when prompts or retrieval parameters change later.
**Delivers:** Golden evaluation dataset (10-20 Q/A pairs); RAGAS metrics in CI; tuned chunk size and k parameter if baseline is below threshold; document quality validation (empty chunk detection for scanned PDFs)
**Uses:** `ragas`, `datasets` (new packages); Claude as LLM judge via `LangchainLLMWrapper`
**Avoids:** Pitfall 5 (silent quality degradation), Pitfall 7 (silent empty extraction from scanned PDFs)
**Research flag:** RAGAS API surface needs verification before writing tests — confirm `evaluate()` signature and `EvaluationDataset` format against installed version; also confirm Claude-as-judge configuration via `LangchainLLMWrapper`

### Phase 4: Chat History and Multi-Turn Context
**Rationale:** These are the two table-stakes features blocking pilot launch. They are grouped together because they share the same Supabase migration and the same `src/history.py` module. Multi-turn context within a session is partially independent of persistence (can be done in-memory first), but persistence is equally required for the pilot and the implementation cost is the same if done together.
**Delivers:** `src/history.py` module; `chat_sessions` + `chat_messages` Supabase tables; `pipeline.answer()` multi-turn messages array; `app.py` session lifecycle integration; conversation history visible on return
**Uses:** `langchain-core` (already present); `supabase-py` (already present); Chainlit `on_chat_start` / `on_message` hooks
**Implements:** `src/history.py` component; Supabase schema additions; pipeline modification
**Avoids:** Anti-pattern of storing history in Chainlit user session only; anti-pattern of embedding history in system prompt string; anti-pattern of passing unlimited history (cap at 6 messages / 3 turns)
**Research flag:** Chainlit 2.x `BaseDataLayer` method signatures need live verification before deciding between explicit pattern vs. framework-integrated pattern — run `python -c "from chainlit.data import BaseDataLayer; help(BaseDataLayer)"` on installed version before starting implementation

### Phase 5: UI/UX Polish for Pilot Launch
**Rationale:** With the foundation solid and core features working, the final phase addresses the pilot customer's first-impression experience: onboarding guidance, accessible document inventory, German error messages on all paths, and source attribution visibility.
**Delivers:** Onboarding `on_chat_start` welcome message; mid-conversation document inventory command; German-language error messages on all error paths; prominent source citation formatting
**Addresses:** All remaining table-stakes features (onboarding, document inventory mid-conversation, German errors)
**Research flag:** No research needed — these are UI copy and Chainlit message formatting; standard patterns

### Phase Ordering Rationale

- Phase 1 must come first: every other feature is unreliable until the event loop is stable and tests are trustworthy
- Phase 2 is independent of Phases 3-5 but should complete before Phase 4 merges, so all new code passes CI before going to VPS
- Phase 3 must complete before pilot launch even if it comes after Phase 4 in calendar time; sequencing here reflects dependency criticality
- Phase 4 is the core feature delivery; it requires Phase 1 to be complete (stable session lifecycle)
- Phase 5 is independent of Phase 4 but must come last — polish on top of a working foundation, not before

### Research Flags

Phases needing deeper research during planning:
- **Phase 3 (RAG Evaluation):** Verify current RAGAS `evaluate()` API signature and `EvaluationDataset` format against installed version; confirm Claude-as-judge configuration
- **Phase 4 (Chat History):** Verify Chainlit 2.x `BaseDataLayer` abstract method signatures before choosing implementation pattern; confirm `RunnableWithMessageHistory` import path in installed `langchain-core` version

Phases with standard patterns (skip research-phase):
- **Phase 1 (Tech Debt):** `asyncio.to_thread()` and `@lru_cache` singleton patterns are stable and well-documented; no research needed
- **Phase 2 (CI/CD):** GitHub Actions job dependency, caching, and Docker build patterns are stable; no research needed
- **Phase 5 (UI/UX):** Chainlit message formatting and hook patterns are stable at the level used here; no research needed

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Existing stack confirmed via codebase inspection (HIGH); new additions (RAGAS, Chainlit data layer) need live API verification (MEDIUM); version pins are currently loose |
| Features | HIGH | Based on direct codebase audit and known product gap analysis; competitor feature set (ChatGPT, Copilot) is well-established |
| Architecture | MEDIUM | Anthropic messages API and LangChain patterns are HIGH confidence; Chainlit 2.x data layer API surface is MEDIUM (changed between 1.x and 2.x); exact method signatures need live verification |
| Pitfalls | HIGH | All critical pitfalls sourced from direct codebase inspection (CONCERNS.md, code audit); async/event loop, singleton, and mock patterns are definitively identified from source code |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Chainlit 2.x `BaseDataLayer` interface:** Run `python -c "from chainlit.data import BaseDataLayer; import inspect; print(inspect.getsource(BaseDataLayer))"` on the installed version before Phase 4 implementation begins. This determines whether to use the explicit `src/history.py` pattern or the framework-integrated pattern.

- **RAGAS current version and API:** Check installed version with `pip show ragas`; verify `evaluate()` call signature and `EvaluationDataset` format before writing Phase 3 tests. The 0.0.x → 0.1.x migration changed these interfaces.

- **RAGAS + Claude as judge:** Confirm `LangchainLLMWrapper` with `ChatAnthropic` works for all four RAGAS metrics before committing the evaluation harness to CI. Faithfulness metric uses an LLM judge internally.

- **Chainlit thread/session UI:** Confirm whether Chainlit 2.x automatically renders a sessions/threads sidebar when a data layer is configured, or whether custom UI code is required. This significantly affects Phase 4 scope.

- **`asyncio.to_thread()` for history writes:** Decide in Phase 4 whether `src/history.py` should be async-native or sync (wrapped at call site in `app.py`). The decision affects code organization but not correctness; make it before writing any `history.py` code.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `app.py`, `src/pipeline.py`, `src/ingest.py`, `src/retrieval.py`, `src/config.py` — async patterns, singleton usage, call sites
- `.planning/codebase/CONCERNS.md` — full tech debt and fragility audit
- `.planning/codebase/TESTING.md` — known test coverage gaps and stale mock documentation
- `.planning/codebase/ARCHITECTURE.md` — data flow and layer boundaries
- `.github/workflows/deploy.yml` — CI/CD pipeline inspection
- Anthropic `messages.create()` API format — stable, verified against existing `pipeline.py`

### Secondary (MEDIUM confidence)
- LangChain 0.3 deprecation of `ConversationBufferMemory` / `ConversationChain` — documented migration path; training data covers this transition
- GitHub Actions patterns (`actions/cache@v4`, `setup-buildx@v3`, `build-push@v6`) — stable standard patterns
- Chainlit 1.x-2.x data layer / `BaseDataLayer` API — training data covers transition period; exact 2.x method signatures need live verification
- RAGAS 0.1.x `evaluate()` API and LLM customization — well-documented framework; specific API surface needs version check
- Competitor feature sets (ChatGPT, Microsoft Copilot) — well-known products verified against training knowledge

### Tertiary (LOW confidence — validate before implementing)
- Chainlit 2.x built-in threads/sessions sidebar behavior — whether it auto-renders when data layer is configured; not confirmed in training data
- RAGAS `LangchainLLMWrapper` + `ChatAnthropic` for all four metrics — supported in principle; needs empirical verification

---

*Research completed: 2026-03-12*
*Ready for roadmap: yes*
