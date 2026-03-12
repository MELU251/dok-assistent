# Architecture Research

**Domain:** RAG Chatbot — Persistent Sessions + Multi-Turn Context + CI/CD
**Researched:** 2026-03-12
**Confidence:** MEDIUM (external web tools blocked; based on codebase analysis + training knowledge up to Aug 2025)

---

## Standard Architecture

### System Overview (Current + Target)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ENTRY POINT                                      │
│  app.py (Chainlit UI)          ingest_cli.py (CLI)                  │
│  - @cl.password_auth_callback  - argparse, sequential ingest        │
│  - @cl.on_chat_start           - tenant_id flag                     │
│  - @cl.on_message                                                   │
│  - @cl.data_layer (NEW)  ←── Persistent session hook                │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────┐
│                     CORE MODULES                                     │
│  src/config.py        ← Pydantic BaseSettings, LRU-cached           │
│  src/ingest.py        ← load → chunk → embed → store                │
│  src/retrieval.py     ← embed query → Supabase RPC search           │
│  src/pipeline.py      ← retrieval + history + Claude → answer dict  │
│                          ↑ NEW: accept conversation_history param    │
│  src/history.py (NEW) ← session CRUD, message persistence           │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────┐
│                     DATA LAYER                                       │
│  Supabase pgvector (existing)                                        │
│  - document_chunks               ← unchanged                        │
│  - chat_sessions (NEW)           ← one row per conversation         │
│  - chat_messages (NEW)           ← one row per turn                 │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────┐
│                     EXTERNAL SERVICES                                │
│  Ollama VPS (Tailscale)    Supabase (pgvector)   Anthropic Claude  │
└─────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CI/CD PIPELINE (GitHub Actions)                  │
│                                                                      │
│  push to master                                                      │
│       │                                                              │
│       ▼                                                              │
│  [Job: test]                                                         │
│    pytest (unit + connection) → pass/fail gate                       │
│       │                                                              │
│       ▼                                                              │
│  [Job: build]  (needs: test)                                         │
│    docker/build-push-action → ghcr.io image                         │
│       │                                                              │
│       ▼                                                              │
│  [Job: deploy] (needs: build)                                        │
│    tailscale connect → ssh VPS → docker compose pull + up            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Responsibility | Boundary |
|-----------|----------------|----------|
| `app.py` | Chainlit hooks, UI routing, data layer registration | Owns session lifecycle in UI; delegates persistence to `src/history.py` |
| `src/history.py` (new) | Session CRUD, message read/write, conversation context assembly | Only touches `chat_sessions` + `chat_messages` tables; no RAG logic |
| `src/pipeline.py` | RAG answer generation; accepts optional conversation_history | Does not own history; receives it as parameter, does not store it |
| `src/retrieval.py` | Vector search, query embedding | Unchanged; stateless |
| `src/ingest.py` | Document processing pipeline | Unchanged |
| `src/config.py` | Validated settings singleton | Unchanged |
| Supabase `chat_sessions` | Session metadata (user, timestamps, title) | Append-only; never update message content |
| Supabase `chat_messages` | Per-turn messages (role, content, cost) | Ordered by `created_at`; read N most recent for context window |

---

## Recommended Project Structure

```
src/
├── config.py           # Unchanged
├── ingest.py           # Unchanged
├── retrieval.py        # Unchanged
├── pipeline.py         # Modified: accept conversation_history param
└── history.py          # NEW: session + message persistence

app.py                  # Modified: register data layer, pass history to pipeline
```

No new top-level directories needed. `src/history.py` stays thin — pure data access, no business logic.

---

## Architectural Patterns

### Pattern 1: Chainlit Custom Data Layer

**What:** Chainlit 1.x+ exposes a `@cl.data_layer` decorator (or `cl.data.set_data_layer()`) that hooks into the framework's session and message lifecycle. Implementing `BaseDataLayer` lets Chainlit automatically persist messages as they are sent.

**Confidence:** MEDIUM — Chainlit's data layer API existed in 1.x. The exact decorator name and method signatures for 2.0+ should be verified against the current Chainlit docs before implementation.

**When to use:** When you want Chainlit's message history to be stored automatically without manually calling persistence code on every `cl.Message`.

**Trade-offs:**
- Pro: Framework integration is tight; history saves even if `on_message` errors after send
- Pro: Chainlit's thread/session model maps directly to `chat_sessions`/`chat_messages`
- Con: API may change across Chainlit versions; coupling to framework internals
- Con: Requires understanding Chainlit's internal thread model (sessions = "threads")

**Practical approach for this codebase:**

Given the constraints (Chainlit 2.0+, single-user pilot, no multi-tenancy), a simpler hybrid approach is lower risk: implement a thin `src/history.py` module called explicitly in `app.py` hooks, without relying on `BaseDataLayer`. This avoids API coupling while achieving the same result.

```python
# src/history.py — explicit pattern (lower coupling)
def create_session(user_id: str, tenant_id: str) -> str:
    """Neue Session anlegen, session_id zurückgeben."""
    ...

def add_message(session_id: str, role: str, content: str, cost_eur: float = 0.0) -> None:
    """Nachricht an Session anhängen."""
    ...

def get_history(session_id: str, last_n: int = 6) -> list[dict]:
    """Letzte N Nachrichten der Session abrufen (für Context Window)."""
    ...

def list_sessions(user_id: str) -> list[dict]:
    """Alle Sessions eines Nutzers auflisten."""
    ...
```

```python
# app.py — integration points
@cl.on_chat_start
async def on_chat_start() -> None:
    session_id = history.create_session(user_id=cl.user_session.get("user"), tenant_id="default")
    cl.user_session.set("session_id", session_id)
    ...

async def _run_rag_flow(question: str) -> None:
    session_id = cl.user_session.get("session_id")
    conv_history = history.get_history(session_id, last_n=6)  # last 3 turns = 6 messages
    result = answer(question, conversation_history=conv_history)
    history.add_message(session_id, "user", question)
    history.add_message(session_id, "assistant", result["answer"], result["cost_eur"])
    ...
```

### Pattern 2: Multi-Turn Context via Messages Array

**What:** Claude's API natively accepts a `messages` list with `role: user/assistant` alternation. Pass the last N message pairs directly into `client.messages.create(messages=[...])`. The RAG context goes in the system prompt; conversation history goes in the messages array.

**Confidence:** HIGH — This is the standard Anthropic API pattern, verified against the existing `pipeline.py` which already uses `client.messages.create()`.

**When to use:** Always for multi-turn; this is the only correct way to provide history to Claude's API.

**Trade-offs:**
- Pro: Claude natively understands conversation history via the messages format
- Pro: No change to retrieval logic; only `pipeline.answer()` changes
- Con: Each additional turn increases input token count linearly; at N=6 turns this is manageable but must be monitored for cost impact

**Modification to `pipeline.answer()`:**

```python
def answer(
    question: str,
    tenant_id: str = "default",
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    ...
    # Build messages array with history + new question
    messages = []
    if conversation_history:
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})  # prompt includes RAG context

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT_BASE,  # system prompt separate from messages
        messages=messages,
    )
```

Note: Current code embeds the RAG context in the user message via `_SYSTEM_PROMPT.format(...)`. With multi-turn, separate the static system instructions (role, language, citation format) into a `system=` parameter, and keep RAG context in the user message. This avoids repeating the system prompt in every turn.

### Pattern 3: Separated Test → Build → Deploy Jobs in CI

**What:** Split the current single `build-and-deploy` job into three sequential jobs: `test` (run pytest), `build` (Docker build + push), `deploy` (SSH + docker compose). Each job only runs if the previous succeeded.

**Confidence:** HIGH — This is GitHub Actions best practice; the existing workflow is a single monolithic job that has no test gate.

**When to use:** Always when deploying to production. A broken test should stop the pipeline before a Docker image is built.

**Trade-offs:**
- Pro: Failed tests block deployment; no broken image pushed to ghcr.io
- Pro: Tailscale and SSH setup only runs when actually deploying (after build succeeds)
- Pro: Easier to debug which stage failed
- Con: Slightly slower total pipeline (job setup overhead ~30s per job)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --ignore=tests/test_connection.py
        # test_connection.py requires live Ollama/Supabase — skip in CI

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write, actions: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: "${{ github.actor }}", password: "${{ secrets.GITHUB_TOKEN }}" }
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/melu251/dok-assistent:latest
          cache-from: type=gha
          cache-to: type=gha,mode=min

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: tailscale/github-action@v2
        with: { authkey: "${{ secrets.TAILSCALE_AUTH_KEY }}" }
      - name: SSH deploy
        run: |
          ssh -i ... user@vps "cd /opt/dok-assistent && docker compose pull && docker compose up -d"
```

---

## Data Flow

### New: Conversation Session Flow

```
User logs in (Chainlit auth)
  → on_chat_start:
      → history.create_session(user_id, tenant_id)
      → session_id stored in cl.user_session
      → (optional) list_sessions() → show "Früherer Chat" button

User sends message
  → on_message:
      → conv_history = history.get_history(session_id, last_n=6)
      → pipeline.answer(question, conversation_history=conv_history)
          → retrieval.search() → top-4 chunks (unchanged)
          → _build_context() → RAG context string (unchanged)
          → Anthropic messages.create(system=..., messages=[history + current]) → answer
      → history.add_message(session_id, "user", question)
      → history.add_message(session_id, "assistant", answer, cost)
      → cl.Message(answer).send()
```

### Existing: Upload + RAG flows remain unchanged

The ingestion flow and document deletion flow do not interact with chat sessions. They are not modified.

### CI/CD Deployment Flow

```
git push → master
  → path filter check (src/**, app.py, requirements.txt, Dockerfile)
  → [test job]
      → pip install requirements.txt
      → pytest tests/ (unit tests only, no live services)
      → PASS → trigger build
  → [build job]  (needs: test)
      → docker buildx build (with GHA cache)
      → push ghcr.io/melu251/dok-assistent:latest
  → [deploy job] (needs: build)
      → tailscale connect
      → ssh-keyscan VPS
      → scp docker-compose.yml to VPS
      → ssh: write .env, docker login, docker compose pull, docker compose up -d
      → healthcheck: curl http://localhost:8000/health (within deploy step)
```

---

## Supabase Schema for Conversation History

```sql
-- Sessions: one row per conversation
create table chat_sessions (
  id          uuid primary key default gen_random_uuid(),
  user_id     text not null,              -- Chainlit username (cl.User.identifier)
  tenant_id   text not null default 'default',
  title       text,                       -- auto-generated from first message (first 80 chars)
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

create index on chat_sessions (user_id, created_at desc);

-- Messages: one row per turn (user or assistant)
create table chat_messages (
  id          uuid primary key default gen_random_uuid(),
  session_id  uuid not null references chat_sessions(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  cost_eur    numeric(10, 6) default 0,   -- 0 for user messages, actual cost for assistant
  created_at  timestamptz default now()
);

create index on chat_messages (session_id, created_at asc);
```

**Design decisions:**

- `user_id` is the Chainlit `cl.User.identifier` (username string), not a UUID. This matches the single-user pilot constraint without adding a `users` table.
- `tenant_id` is preserved for future multi-tenancy, consistent with `document_chunks`.
- `title` is nullable; set from the first user message on session creation (first 80 chars, trimmed).
- `cost_eur` on `chat_messages` enables per-session cost rollup: `SELECT SUM(cost_eur) FROM chat_messages WHERE session_id = $1`.
- No `updated_at` trigger required for messages (immutable once written).
- `on delete cascade` on `chat_messages.session_id` ensures clean session deletion.

---

## Build Order: What Must Be Done Before What

```
1. FOUNDATION (no dependencies)
   ├── SQL migration: create chat_sessions + chat_messages tables in Supabase
   └── Fix known tech debt: Supabase client singleton (src/config.py or module-level)
       (Required before adding history.py; the bug causes connection pool issues under load)

2. HISTORY MODULE (depends on: 1)
   └── src/history.py: create_session, add_message, get_history, list_sessions
       → Unit tests with mocked Supabase client

3. PIPELINE EXTENSION (depends on: 2)
   └── src/pipeline.answer(): add conversation_history parameter
       → Refactor system prompt: separate system= from user message content
       → Unit tests for message array construction

4. APP INTEGRATION (depends on: 2, 3)
   └── app.py: on_chat_start creates session, on_message passes history
       → Manual test: multi-turn conversation retains context

5. CI/CD SPLIT (independent of 1-4, can run in parallel track)
   └── Split build-and-deploy into test + build + deploy jobs
       → Add pytest to test job (unit tests only)
       → Add health check verification step in deploy job
       → Verify Tailscale + SSH pattern still works after refactor

6. SESSION UI (depends on: 4)
   └── "Früherer Chat" sidebar or session list (Chainlit UI constraints apply)
       → Evaluate what Chainlit 2.0 exposes for thread/session navigation
       → Flag: Chainlit's built-in thread resume may require BaseDataLayer; investigate
```

**Critical path:** 1 → 2 → 3 → 4. The Supabase migration must land before any history code runs in production.

**CI/CD is independent** of the history work. It can be done first, in parallel, or after — it does not block or depend on the session feature.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user (pilot) | Current monolith + Supabase is fine. No changes to Docker/infrastructure needed. |
| 5 concurrent users | Fix OllamaEmbeddings singleton (CONCERNS.md) and Supabase client caching. Blocking embed_and_store becomes the bottleneck. Wrap in `asyncio.to_thread()`. |
| 20+ users | Chainlit concurrency limits become visible. Evaluate FastAPI + WebSocket migration. Ollama VPS becomes embedding throughput bottleneck. |
| 100+ users | Separate embedding service (Ollama cluster or alternative), connection pooling for Supabase, Redis for session cache. Out of scope for pilot. |

For the pilot milestone, only the 1-user scale matters. Architecture decisions should optimize for simplicity and correctness, not premature scaling.

---

## Anti-Patterns

### Anti-Pattern 1: Storing Conversation History in Chainlit User Session Only

**What people do:** Use `cl.user_session.set("history", [...])` to accumulate messages in memory during a session.

**Why it's wrong:** `cl.user_session` is in-process memory. It is lost on container restart, on browser refresh, or on deployment. This gives the appearance of multi-turn context without actual persistence. The current codebase already avoids this correctly (no history is stored anywhere), so this anti-pattern would be a regression.

**Do this instead:** Write to Supabase `chat_messages` on every turn. Read from Supabase on session start. Memory cache is acceptable for the current session only, backed by database.

### Anti-Pattern 2: Embedding Full Conversation History in the System Prompt

**What people do:** Inject all previous Q&A pairs into `_SYSTEM_PROMPT.format(history=..., context=..., question=...)` as a single string.

**Why it's wrong:** Claude's API has a dedicated `messages` parameter for conversation history. Embedding history in the system prompt mixes concerns, wastes tokens on repetitive formatting, and breaks Claude's ability to properly track conversational roles (user vs assistant).

**Do this instead:** Put system instructions and RAG context in `system=`, put conversation history in `messages=[{"role": "user"/"assistant", "content": ...}]`, and append the current question as the final user message.

### Anti-Pattern 3: Running Tests Inside the Deploy Job

**What people do:** Run `pytest` as a step inside the same job that builds and deploys (as the current workflow does — it has no test step at all).

**Why it's wrong:** A test failure after the Docker image is pushed means a broken image is already in the registry. If `docker compose pull` runs before the failure is detected, the VPS may be running broken code.

**Do this instead:** Gate the `build` job on `needs: test`. The image is only built if tests pass.

### Anti-Pattern 4: Passing All Chat History to Claude

**What people do:** Retrieve all messages in a session and pass them all as context.

**Why it's wrong:** Long sessions accumulate dozens of turns. At 6 turns per session with average 200 tokens per message, 30 turns = ~6000 tokens of history. Combined with the 4 RAG chunks (~2000 tokens context), this pushes toward 10K input tokens per query, increasing cost to ~€0.03/query (above the €0.02 target). More critically, very old context is usually irrelevant and can confuse the model.

**Do this instead:** Retrieve only the last N turns (recommend: last 3 user + 3 assistant = 6 messages). Make N configurable via settings (`HISTORY_CONTEXT_MESSAGES`, default 6).

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Supabase | Direct supabase-py client calls (existing RPC pattern) | `chat_sessions` and `chat_messages` use standard `.table().insert()`/`.select()` — no custom RPC needed |
| Anthropic Claude | `messages.create(system=..., messages=[...])` | Add `system=` parameter (currently unused); move RAG context from user message |
| Chainlit | `cl.user_session` for in-memory session_id; `@cl.on_chat_start` / `@cl.on_message` hooks | Keep explicit pattern; avoid `BaseDataLayer` for now (API change risk) |
| GitHub Actions | Native SSH + Tailscale (existing pattern, confirmed working) | Split into 3 jobs; no change to SSH/Tailscale mechanics |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `app.py` ↔ `src/history.py` | Direct function calls | `app.py` owns session_id lifecycle; `history.py` is pure data access |
| `app.py` ↔ `src/pipeline.py` | Direct function call with new `conversation_history` param | Backward-compatible: default is `None` (no history), existing call sites continue to work |
| `src/pipeline.py` ↔ Anthropic | `messages.create(system=..., messages=[...])` | Refactor from current single-user-message format |
| `src/history.py` ↔ Supabase | supabase-py client (same pattern as `retrieval.py`) | Share the singleton client (after tech-debt fix) |

---

## Sources

- Codebase analysis: `app.py`, `src/pipeline.py`, `src/retrieval.py`, `src/config.py` (2026-03-12)
- Existing workflow: `.github/workflows/deploy.yml` (codebase)
- Anthropic API messages format: Training knowledge (HIGH confidence — stable API surface)
- Chainlit data layer API: Training knowledge up to Aug 2025 (MEDIUM confidence — verify Chainlit 2.0 docs before implementation; API surface changed between 1.x and 2.x)
- GitHub Actions job dependency (`needs:`): Training knowledge (HIGH confidence — stable feature)
- Supabase schema patterns: Training knowledge + consistency with existing `document_chunks` table

---

## Open Questions (Flag for Implementation Phase)

1. **Chainlit 2.0 data layer API** — Does Chainlit 2.0 expose `@cl.data_layer` decorator or `cl.data.set_data_layer()`? Does it support resume/re-open of previous threads? Verify against official Chainlit 2.0 docs before committing to the explicit vs. framework-integrated history pattern. CONFIDENCE: LOW until verified.

2. **Session UI affordance** — What does Chainlit 2.0 natively provide for "previous conversations" navigation? If it offers a built-in threads panel (known from 1.x), integrating with `BaseDataLayer` may be worthwhile. If not, a simple `/sessions` command or welcome screen dropdown is sufficient.

3. **`asyncio.to_thread()` for history writes** — `history.add_message()` calls Supabase synchronously. This is a new async-in-sync concern mirroring the existing `embed_and_store` blocking issue. Wrap all Supabase writes in `asyncio.to_thread()` in `app.py` or make `history.py` async-native.

4. **Session title auto-generation** — Best approach: truncate first user message to 80 chars. Alternatively: call Claude to generate a title (adds cost and latency). Recommend the truncation approach for pilot.

---

*Architecture research for: RAG Chatbot — Persistent Sessions + Multi-Turn Context + CI/CD*
*Researched: 2026-03-12*
