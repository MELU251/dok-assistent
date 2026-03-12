# Stack Research

**Domain:** RAG Dokumenten-Assistent — Pilot-Ready additions (chat history, multi-turn, RAG eval, CI/CD)
**Researched:** 2026-03-12
**Confidence:** MEDIUM (training data cutoff August 2025; no live web access available during research; all version-sensitive claims flagged)

---

## Context: What Exists, What's Being Added

The PoC already has a working stack: Python 3.11, LangChain 0.3+, Chainlit 2.0+, Supabase pgvector, Ollama (nomic-embed-text), Anthropic Claude. The existing `pipeline.answer()` function is stateless — it takes a single question, retrieves chunks, calls Claude, returns an answer dict. There is no conversation memory, no session persistence, no history UI.

This research covers four additive areas only:

1. Persistent chat history and session management (Chainlit + Supabase)
2. Multi-turn context (LangChain conversation memory for RAG)
3. RAG answer quality evaluation
4. CI/CD stabilization for Python/Docker on GitHub Actions

---

## Recommended Stack

### 1. Persistent Chat History

#### Core Approach: Chainlit Data Layer + Supabase custom storage

**Confidence: MEDIUM** — Chainlit 2.x's `cl.data_layer` API was introduced in Chainlit 1.x and is the canonical persistence mechanism. Verify the exact interface against https://docs.chainlit.io/data-persistence/overview before implementing.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Chainlit Data Layer (`cl.data_layer`) | Chainlit 2.0+ | Persists threads (sessions), messages, user profiles to a backend | The official Chainlit mechanism; avoids building custom state management. Designed to decouple the UI from the storage backend. |
| Custom `BaseStorageClient` / `BaseDataLayer` impl | Chainlit 2.0+ | Adapter that writes to your existing Supabase instance | You already have Supabase; writing a custom adapter avoids adding a second database (e.g., DynamoDB or Literal AI). 200–300 lines of Python, re-uses `supabase-py` client already present. |
| Supabase (existing) | 2.10+ | Storage backend for threads and messages | Avoids additional infrastructure. Supabase already holds vector data; adding two tables (`threads`, `thread_messages`) keeps everything in one place. |

**Do NOT use:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `chainlit-literal-ai` / Literal AI cloud | External SaaS dependency for history; not needed for a single-customer pilot; adds cost and vendor lock-in | Custom Supabase adapter |
| SQLite file-based storage | Not safe for Docker restarts or multi-container setups; file lives in container, lost on redeploy | Supabase (already deployed) |
| In-memory `cl.user_session` only | Does not survive page reloads or container restarts; fine for PoC but unusable for pilot | Chainlit Data Layer with Supabase backend |

**Schema additions required in Supabase:**

```sql
-- One row per conversation session
create table threads (
  id          text primary key,         -- Chainlit thread ID (UUID string)
  user_id     text not null,            -- maps to Chainlit user identifier
  name        text,                     -- display name shown in history list
  metadata    jsonb default '{}',
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- One row per message (user or assistant)
create table thread_messages (
  id          text primary key,
  thread_id   text not null references threads(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  metadata    jsonb default '{}',
  created_at  timestamptz default now()
);

create index on thread_messages(thread_id, created_at);
```

**Implementation pattern:**

```python
# src/chat_history.py — Supabase-backed Chainlit data layer
from chainlit.data import BaseDataLayer
from chainlit import User, Thread, Message
# ... implement create_thread, get_thread, update_thread,
#     create_message, list_threads_for_user
# Wire up in app.py: cl.data_layer = SupabaseDataLayer()
```

**Confidence note:** The `BaseDataLayer` abstract class interface (method names, signatures) should be confirmed against the installed Chainlit 2.x source before implementing. Run `python -c "from chainlit.data import BaseDataLayer; help(BaseDataLayer)"` to inspect the actual interface.

---

### 2. Multi-Turn Context (LangChain Conversation Memory for RAG)

**Confidence: HIGH** — LangChain's memory/history patterns for RAG are well-documented and stable since 0.2.x. The approach using `RunnableWithMessageHistory` and `ChatMessageHistory` is the current canonical path (replaces deprecated `ConversationBufferMemory`).

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `langchain_core.chat_history.BaseChatMessageHistory` | langchain-core 0.3+ | Interface for storing per-session message history | Stable abstraction; lets you swap in-memory vs Supabase-backed storage without changing pipeline logic |
| `langchain_core.runnables.history.RunnableWithMessageHistory` | langchain-core 0.3+ | Wraps any LangChain Runnable to inject history into the prompt | Current canonical approach; replaces deprecated `ConversationBufferMemory`. Handles session_id-to-history mapping automatically. |
| `langchain_community.chat_message_histories.ChatMessageHistory` | langchain-community 0.3+ | In-memory `BaseChatMessageHistory` implementation | Simple starting point; for persistence, replace with custom Supabase-backed implementation using the `thread_messages` table |

**Do NOT use:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `ConversationBufferMemory` | Deprecated in LangChain 0.3.x; removed or will be removed; belongs to legacy chain API | `RunnableWithMessageHistory` |
| `ConversationChain` | Deprecated; uses old chain API that doesn't compose with LCEL | LCEL-style pipeline with `RunnableWithMessageHistory` |
| Passing full history as raw string into system prompt | Breaks token budget quickly; no compression; defeats LangChain's history management | Windowed message history with `max_token_limit` or last-N messages |

**Pattern for this codebase:**

The existing `pipeline.answer(question, tenant_id)` is a plain function. To add multi-turn, the minimal approach is:

1. Add a `session_id` parameter to `answer()`.
2. Load the last N messages for that session from Supabase `thread_messages`.
3. Prepend the history as `HumanMessage`/`AIMessage` objects to the Claude `messages` array.
4. Store the new turn (question + answer) back to `thread_messages`.

This is simpler than fully refactoring to LCEL `RunnableWithMessageHistory` and avoids a large rewrite risk. The LangChain wrapper is the right long-term direction but the manual approach is safer as a first pilot increment.

**History window strategy:** Limit history to last **6 messages** (3 turns). The existing prompt already consumes ~500–1000 tokens of context chunks. Including full unlimited history risks blowing past Claude's cost target of €0.02/query. Six messages keeps additional cost under ~€0.003 per turn.

**Required package:** No new packages needed — `langchain-core` is already a dependency.

---

### 3. RAG Answer Quality Evaluation

**Confidence: MEDIUM** — RAGAS and DeepEval are both actively developed. Versions and API surfaces change; verify current API before integrating.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `ragas` | 0.1.x (verify current) | Automated RAG metric computation: faithfulness, answer relevancy, context precision, context recall | The de-facto standard for RAG evaluation in Python. Works offline with your own LLM judge (Claude). Does not require OpenAI. Designed for LangChain/LlamaIndex pipelines. |
| `pytest` (existing) | 8.0+ | Test runner for evaluation harness | You already have pytest. RAG eval tests are just pytest tests that assert metric thresholds. No new test framework needed. |

**Core RAGAS metrics for this project:**

| Metric | What It Measures | Why Important for This PoC |
|--------|-----------------|---------------------------|
| `faithfulness` | Does the answer only claim things supported by retrieved chunks? | Prevents hallucination — critical for a document assistant |
| `answer_relevancy` | Is the answer relevant to the question asked? | Guards against off-topic or padded answers |
| `context_precision` | Are the retrieved chunks actually useful for the question? | Validates retrieval quality (k=4 selection) |
| `context_recall` | Did retrieval find all necessary chunks? | Catches cases where relevant content exists but wasn't retrieved |

**Evaluation dataset pattern:**

```python
# tests/eval/test_rag_quality.py
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

EVAL_DATASET = [
    {
        "question": "Was sind die Zahlungsbedingungen laut Vertrag?",
        "ground_truth": "Zahlung innerhalb 30 Tage nach Rechnungsstellung.",
        "answer": ...,          # from pipeline.answer()
        "contexts": [...],      # retrieved chunks
    },
    # ... 10-20 question/answer pairs over pilot documents
]

def test_rag_quality():
    result = evaluate(dataset=EVAL_DATASET, metrics=[faithfulness, answer_relevancy])
    assert result["faithfulness"] >= 0.85
    assert result["answer_relevancy"] >= 0.80
```

**Alternative: DeepEval**

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| RAGAS | DeepEval | If you want richer assertion syntax (`assert_test()`), CI integration helpers, or plan to move to a managed eval platform later. DeepEval has better pytest-style API but requires more setup and the free tier has limits. For a single-customer pilot, RAGAS is sufficient and lighter. |

**Do NOT use:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Manual/human-only evaluation | Doesn't scale; can't be automated in CI; won't catch regressions when prompt or retrieval changes | RAGAS with a small golden eval dataset |
| LangSmith tracing as substitute for eval | Tracing shows what happened; doesn't measure quality. Good complement but not a replacement. | RAGAS for metrics + LangSmith for debugging (optional) |
| Evaluating every production query | LLM-as-judge costs money; running RAGAS on every user query is €0.05-0.20 per query for the judge LLM. | Run eval only on a fixed golden dataset in CI (not on live queries) |

**New packages needed:**

```
ragas>=0.1.0          # verify current version at https://pypi.org/project/ragas/
datasets>=2.14.0      # RAGAS uses HuggingFace datasets format internally
```

**Confidence note:** RAGAS's API surface changed significantly between 0.0.x and 0.1.x. Verify the `evaluate()` call signature and `EvaluationDataset` format against the installed version before writing tests.

---

### 4. CI/CD Stabilization (GitHub Actions, Python 3.11, Docker)

**Confidence: HIGH** — GitHub Actions patterns for Python/Docker are mature and well-documented. The recommendations below are standard practice.

| Technology | Version/Pattern | Purpose | Why Recommended |
|------------|----------------|---------|-----------------|
| `actions/cache@v4` | v4 | Cache pip dependencies between runs | Reduces install time from ~3-4 min to ~30s on cache hit. Cache key on `requirements.txt` hash. |
| `docker/build-push-action@v6` | v6 | Build and optionally push Docker image | Standard action; integrates with `docker/setup-buildx-action@v3` for layer caching |
| `docker/setup-buildx-action@v3` | v3 | Enable BuildKit layer caching | BuildKit is required for `--cache-from`/`--cache-to` to work; not available with default Docker builder |
| `dorny/paths-filter@v3` | v3 | Skip CI jobs when only docs/non-code files changed | Avoids running full test + build on README changes; cheap optimization |
| `pytest` with `--tb=short -q` flags | existing | Faster test output, less noise in CI logs | `-q` suppresses verbose pass output; `--tb=short` gives just the relevant error lines |
| Docker layer cache via GitHub Actions Cache | — | Persist Docker build layers between CI runs | Cuts Docker build time from ~4 min to ~45s on unchanged layers. Use `type=gha` cache backend with `build-push-action`. |

**Recommended CI job structure:**

```yaml
# .github/workflows/ci.yml (simplified)

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('requirements.txt') }}
      - run: pip install -r requirements.txt
      - run: pytest tests/ -q --tb=short
        env:
          ANTHROPIC_API_KEY: "sk-ant-dummy"   # needed for config validation to pass
          OLLAMA_BASE_URL: "http://localhost:11434"
          SUPABASE_URL: "https://dummy.supabase.co"
          SUPABASE_SERVICE_KEY: "dummy-key"

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          push: false    # pilot: build-only check, no registry push needed yet
          cache-from: type=gha
          cache-to: type=gha,mode=max
          tags: rag-poc:${{ github.sha }}
```

**Common failure modes in this project's current CI (from CONCERNS.md and git history):**

| Failure Mode | Root Cause | Fix |
|-------------|-----------|-----|
| Tests fail due to missing env vars | Config validation raises `SystemExit` during import | Pass dummy (non-placeholder) env vars in CI; `sk-ant-dummy` not `sk-ant-...` |
| `test_ingest.py` patches wrong class | `OpenAIEmbeddings` patched but code uses `OllamaEmbeddings` | Fix the mock target to `src.ingest.OllamaEmbeddings` |
| Docker build slow (3-4 min) | No layer caching enabled | Add `setup-buildx-action` + `cache-from/to: type=gha` |
| Build fails after pip install changes | `requirements.txt` not locked to exact versions | Pin all versions; use `pip-compile` from `pip-tools` to generate locked file |

**Do NOT use:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `self-hosted runners` for pilot | Operational overhead; not worth it for 1 developer + 1 customer | GitHub-hosted `ubuntu-latest` runners |
| Running tests against real Supabase/Ollama in CI | Slow, flaky, costs money, requires VPN for Ollama | Mock all external services in unit tests; keep integration tests as manual/optional |
| Docker Compose for CI test runs | Adds complexity; starts real services; flaky due to timing | pytest with mocked services; Docker build-only check is sufficient |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|----------------|-------|
| `chainlit 2.0+` | `langchain-core 0.3+` | Chainlit 2.x was redesigned alongside LangChain 0.3; use both at current major versions |
| `ragas 0.1.x` | `langchain-core 0.3+`, `datasets 2.14+` | RAGAS 0.1.x uses HuggingFace `datasets` internally; verify no conflicts with existing `langchain-community` |
| `langchain-core 0.3+` | `langchain-anthropic 0.3+` | Already in project; `RunnableWithMessageHistory` lives in `langchain-core`, no new packages |
| `supabase-py 2.10+` | Chainlit Data Layer (custom) | Custom adapter uses existing `supabase-py` client; no new Supabase package version needed |

---

## Installation

```bash
# RAG evaluation (new)
pip install "ragas>=0.1.0" "datasets>=2.14.0"

# Everything else (chat history, multi-turn) uses existing packages:
# - langchain-core (already present) for RunnableWithMessageHistory
# - supabase (already present) for custom data layer
# - chainlit 2.0+ (already present) for cl.data_layer

# Dev dependencies (pin exact versions after resolving)
pip install pip-tools
pip-compile requirements.in  # generate locked requirements.txt from unpinned .in file
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Custom Supabase `BaseDataLayer` | Literal AI (Chainlit's own persistence SaaS) | If you need analytics, user feedback tracking, or annotation workflows out of the box. Not justified for single-customer pilot. |
| Custom Supabase `BaseDataLayer` | PostgreSQL via asyncpg directly | If Chainlit's data layer API is too limiting. More control, more code. Not worth it for pilot scope. |
| Manual history prepend to Claude messages | Full LCEL `RunnableWithMessageHistory` refactor | If pipeline complexity grows significantly or you add multiple concurrent sessions with complex routing. LCEL approach is architecturally cleaner but requires larger refactor. |
| RAGAS | PromptFoo | If you want a standalone, non-Python eval tool with nice HTML reports. Good for prompt iteration but less integrated with pytest CI flow. |
| GitHub-hosted runners | Fly.io / Railway deploy hooks | If you want zero-downtime deploy automation for the pilot. Not in scope — pilot is Docker on VPS via manual deploy. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `ConversationBufferMemory` | Deprecated in LangChain 0.3.x; API will be removed | `RunnableWithMessageHistory` with `BaseChatMessageHistory` |
| `ConversationChain` | Deprecated; legacy chain API; does not compose with modern LCEL | Explicit LCEL chain with history injection |
| Literal AI / Chainlit Cloud | SaaS lock-in; external data; not necessary for single-tenant pilot | Custom `BaseDataLayer` writing to existing Supabase |
| OpenAI as LLM judge for RAGAS | Requires OpenAI account; contradicts project constraint "kein OpenAI" | Configure RAGAS to use Claude as the judge LLM via `langchain_anthropic` |
| `sqlite3` for chat history | Not Docker-safe (ephemeral container filesystem); concurrency issues | Supabase `threads` + `thread_messages` tables |
| Unlimited conversation history in prompt | Token budget: at k=4 chunks (~2000 tokens context) + system prompt, adding unlimited history overshoots €0.02/query target | Hard cap at 6 messages (3 turns) or implement token-budget-aware truncation |

---

## Stack Patterns by Variant

**If RAGAS requires OpenAI by default:**
- Configure it to use Claude as the judge: `from ragas.llms import LangchainLLMWrapper` + `ChatAnthropic`
- Verify: RAGAS 0.1.x supports custom LLM wrappers; check https://docs.ragas.io/en/latest/howtos/customizations/bring_your_own_llm/ before implementing
- Confidence: MEDIUM (API surface of RAGAS LLM customization changed between versions)

**If Chainlit 2.x `BaseDataLayer` interface differs from expected:**
- Inspect actual abstract methods: `python -c "from chainlit.data import BaseDataLayer; import inspect; print(inspect.getsource(BaseDataLayer))"`
- Implement exactly the methods that are abstract (not the full theoretical interface)
- The `threads` and `thread_messages` schema above is designed to be flexible regardless of exact Chainlit version

**If blocking embed_and_store is fixed (tech debt from CONCERNS.md):**
- Wrap in `asyncio.to_thread(embed_and_store, chunks, tenant_id)` — this is independent of chat history work
- Fix this in the same milestone as chat history to avoid compounding async bugs

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Chainlit Data Layer approach | MEDIUM | Pattern is correct; exact method signatures in `BaseDataLayer` require verification against installed Chainlit 2.x version. Training data covers Chainlit 1.x-2.x transition. |
| LangChain multi-turn (`RunnableWithMessageHistory`) | HIGH | Stable since LangChain 0.2; `ConversationBufferMemory` deprecation is documented. Manual history-prepend approach is even more stable. |
| RAGAS evaluation | MEDIUM | Library correct and widely used; API surface (0.0.x vs 0.1.x) changed; verify `evaluate()` signature before writing tests. |
| RAGAS + Claude as judge (no OpenAI) | MEDIUM | Supported via `LangchainLLMWrapper`; verify against current RAGAS docs before assuming it works out of box. |
| CI/CD GitHub Actions patterns | HIGH | Standard patterns (actions/cache@v4, setup-buildx@v3, build-push@v6) are stable and widely verified. |
| Supabase schema for threads | HIGH | Plain SQL tables; no Chainlit-specific magic; schema is version-independent. |

---

## Gaps to Verify Before Implementation

1. **Chainlit `BaseDataLayer` method signatures** — Run `python -c "from chainlit.data import BaseDataLayer; help(BaseDataLayer)"` on the installed version. Particularly: does it use `Thread` dataclass or dict? What are the required vs optional methods?

2. **RAGAS current version and `evaluate()` API** — Check https://pypi.org/project/ragas/ for current version. The `evaluate(dataset, metrics)` signature and `EvaluationDataset` format changed in 0.1.x.

3. **RAGAS Claude judge configuration** — Confirm `LangchainLLMWrapper` with `ChatAnthropic` works for all four metrics (faithfulness uses an LLM judge internally).

4. **Chainlit thread list UI** — Confirm Chainlit 2.x shows a thread/history sidebar automatically when `data_layer` is configured, or whether custom UI code is needed. This affects scope estimate significantly.

5. **`RunnableWithMessageHistory` import path in langchain-core 0.3.x** — Confirm: `from langchain_core.runnables.history import RunnableWithMessageHistory` is correct for the installed version.

---

## Sources

- Codebase analysis: `.planning/codebase/STACK.md`, `ARCHITECTURE.md`, `CONCERNS.md` — HIGH confidence (direct inspection)
- LangChain deprecation of `ConversationBufferMemory` / `ConversationChain` — HIGH confidence (documented in LangChain 0.3 migration guide; training data covers this transition)
- Chainlit `BaseDataLayer` / data persistence — MEDIUM confidence (training data covers Chainlit 1.x-2.x; exact 2.x API needs live verification)
- RAGAS evaluation framework — MEDIUM confidence (training data covers 0.0.x-0.1.x; current API needs live verification at https://docs.ragas.io)
- GitHub Actions action versions (cache@v4, setup-buildx@v3, build-push@v6) — HIGH confidence (stable; verified against training data through mid-2025)
- Note: WebSearch, WebFetch, and Bash tool access were denied during research. All claims are from training data (cutoff August 2025). Version numbers marked MEDIUM confidence should be re-verified against live docs before implementation.

---

*Stack research for: RAG Dokumenten-Assistent — Pilot-Ready milestone*
*Researched: 2026-03-12*
