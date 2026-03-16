# Phase 1: Tech Debt Foundation - Research

**Researched:** 2026-03-16
**Domain:** Python asyncio / Chainlit event-loop safety, singleton patterns, pytest mocking, atomic delete flows
**Confidence:** HIGH — all findings are based on direct source-code inspection of the actual codebase

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TECH-01 | `embed_and_store()` und `pipeline.answer()` laufen in separaten Threads (`asyncio.to_thread()`), sodass der Chainlit-Event-Loop nicht blockiert wird | Direct code audit: both calls are blocking sync calls inside async handlers in `app.py` |
| TECH-02 | `OllamaEmbeddings`-Instanz wird als Modul-Level-Singleton gecacht | Direct code audit: created fresh per call in both `ingest.py` and `retrieval.py` |
| TECH-03 | Supabase-Client wird als Singleton gecacht | Direct code audit: `create_client()` called inline in 4 separate locations across 2 modules |
| TECH-04 | `test_ingest.py` patcht `OllamaEmbeddings` (nicht `OpenAIEmbeddings`) | Direct code audit: test patches `src.ingest.OpenAIEmbeddings` which does not exist in that module namespace |
| TECH-05 | Delete-Flow löscht zuerst die lokale Datei, dann die Supabase-Records; bei Datei-Fehler wird Supabase nicht angefasst | Direct code audit: current flow in `app.py` deletes Supabase first, local file second |
</phase_requirements>

---

## Summary

This phase is a pure refactoring/bug-fix phase with no new features. All five requirements address concrete, verifiable defects identified by direct inspection of the existing codebase. There is no ambiguity about what is broken — the code is readable and the bugs are localized to specific lines.

The most impactful fix is TECH-01: the Chainlit event-loop is blocked on every document upload and every query because `embed_and_store()` and `answer()` are synchronous functions called directly from `async` Chainlit handlers. Python's asyncio rule is absolute: blocking calls in the event loop freeze the entire process. The fix is `asyncio.to_thread()`, which off-loads the synchronous work to a ThreadPoolExecutor without requiring the callees to be rewritten as async.

TECH-02 and TECH-03 are connection-leak bugs. Every call to `embed_and_store()`, `search()`, `get_indexed_documents()`, or `delete_document()` currently creates new HTTP connections (OllamaEmbeddings) or new PostgREST client instances (Supabase). Under repeated load this exhausts the TCP connection pool on the Ollama VPS. The fix is module-level singleton instances initialized once at import time using a `functools.lru_cache`-wrapped getter or a plain module-level variable — the same pattern already used for `get_settings()`.

TECH-04 is a broken test: the mock target `src.ingest.OpenAIEmbeddings` does not exist in the module, so `@patch` silently does nothing and the test would attempt a real network call (or fail on import). The fix is to change the patch target to `src.ingest.OllamaEmbeddings` and update the dimension assertion from 1536 to 768. A secondary broken test in the same file (`test_raises_for_unsupported_extension`) tests `.txt` as unsupported but the real code accepts `.txt` — this must also be corrected.

TECH-05 is an atomicity bug: the current delete flow in `app.py` deletes Supabase records first and the local file second, meaning a crash between the two steps leaves the DB clean but the file present, or (worse from the requirement's perspective) the flow deletes DB records even when the local file was never present. The required order is: (1) check local file exists, (2) delete local file, (3) delete Supabase records.

**Primary recommendation:** Fix all five items as surgical, minimal changes — do not restructure modules, do not introduce new abstractions beyond what is strictly needed.

---

## Standard Stack

### Core (already in use — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio.to_thread` | stdlib (Python 3.9+) | Off-load sync functions to thread pool from async context | Zero-dependency, idiomatic asyncio solution |
| `functools.lru_cache` | stdlib | Singleton pattern for expensive-to-create objects | Already used in `config.py` via `get_settings()`; consistent pattern |
| `langchain_ollama.OllamaEmbeddings` | >=0.2.0 | Embedding client | Already in use in `ingest.py` and `retrieval.py` |
| `supabase.create_client` | >=2.10.0 | Supabase PostgREST client | Already in use across all modules |
| `pytest` + `unittest.mock.patch` | >=8.0.0 | Unit testing and mocking | Already in use |

### No new dependencies required

All five fixes are achievable with stdlib (`asyncio`, `functools`) and the libraries already installed.

---

## Architecture Patterns

### Recommended Project Structure (unchanged)

The current structure is correct. No module reorganization is needed. Changes are surgical additions within existing files.

```
src/
├── config.py      # get_settings() already uses lru_cache — Singleton pattern to copy
├── ingest.py      # Add: _get_embedder() singleton, _get_supabase_client() singleton
│                  # Change: embed_and_store and delete_document use singletons
├── retrieval.py   # Add: _get_embedder() and _get_supabase_client() use shared singletons
└── pipeline.py    # No changes needed (answer() is synchronous; async wrapping is in app.py)
app.py             # Change: wrap embed_and_store and answer calls with asyncio.to_thread()
                   # Change: fix delete flow order
tests/
└── test_ingest.py # Fix: patch target and dimension assertions
```

### Pattern 1: Module-Level Singleton via lru_cache Getter

**What:** A module-level getter function decorated with `@lru_cache(maxsize=1)` returns the same instance on every call. This is the identical pattern used by `get_settings()` in `config.py`.

**When to use:** Any external client that is expensive to construct and safe to reuse across calls (stateless HTTP clients like OllamaEmbeddings and Supabase client).

**Example:**
```python
# src/ingest.py — following existing get_settings() pattern from config.py
from functools import lru_cache
from langchain_ollama import OllamaEmbeddings
from supabase import create_client, Client

@lru_cache(maxsize=1)
def _get_embedder() -> OllamaEmbeddings:
    """OllamaEmbeddings-Singleton (wird einmal erstellt und wiederverwendet)."""
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )

@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    """Supabase-Client-Singleton (wird einmal erstellt und wiederverwendet)."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
```

The same two functions go into `retrieval.py`. Alternatively, they can be defined once in a shared `src/clients.py` module and imported by both `ingest.py` and `retrieval.py` — this is the cleaner long-term approach but involves creating a new file. Both are valid; the planner should choose based on desired scope.

### Pattern 2: asyncio.to_thread() for Blocking Sync Calls in Async Context

**What:** `asyncio.to_thread(sync_fn, *args, **kwargs)` runs `sync_fn` in the default thread pool executor and returns a coroutine that the event loop can await. The synchronous function is unchanged.

**When to use:** Any synchronous blocking call (network I/O, file I/O, CPU work) invoked from inside a Chainlit `async` handler.

**Example:**
```python
# app.py — inside async _run_upload_flow()
# Before (blocking):
stored = embed_and_store(chunks, callback=progress)

# After (non-blocking):
stored = await asyncio.to_thread(embed_and_store, chunks, callback=progress)

# app.py — inside async _run_rag_flow()
# Before (blocking):
result = answer(question)

# After (non-blocking):
result = await asyncio.to_thread(answer, question)
```

`asyncio.to_thread` is available since Python 3.9. The project uses Python 3.11, so no compatibility concern.

### Pattern 3: Correct Delete Flow Order (TECH-05)

**What:** The delete operation must be atomic-safe: check local file existence first, abort if missing, then delete local file, then delete Supabase records. This ensures Supabase records are never touched when the local file is absent.

**Current broken flow in `app.py` `_run_delete_flow()`:**
1. Check if indexed in Supabase (get_indexed_documents)
2. Call `delete_document(filename)` — Supabase delete ← HAPPENS FIRST
3. Delete local file if exists ← HAPPENS SECOND

**Correct flow:**
1. Check if local file exists in `DOCS_DIR`
2. If local file does NOT exist → send error message, return (Supabase untouched)
3. Delete local file (`local_file.unlink()`)
4. Call `delete_document(filename)` — Supabase delete

**Note:** The Supabase check (`get_indexed_documents`) can remain as a pre-flight check for user-facing "file not found" messaging, but must not be confused with the atomicity guard. The atomicity guard is the local file check BEFORE any Supabase mutation.

### Pattern 4: Correct pytest Mock Target for OllamaEmbeddings (TECH-04)

**What:** `unittest.mock.patch` patches the name as it appears in the module under test, not the module where it is originally defined.

**Current broken patch in `test_ingest.py`:**
```python
@patch("src.ingest.OpenAIEmbeddings")   # WRONG: this name does not exist in src.ingest
```

**Correct patch:**
```python
@patch("src.ingest.OllamaEmbeddings")   # CORRECT: matches the import in ingest.py
```

**Dimension assertion must also change:**
```python
# Before (wrong — OpenAI dimension):
mock_embedder.embed_documents.return_value = [[0.1] * 1536] * len(sample_chunks)

# After (correct — nomic-embed-text dimension):
mock_embedder.embed_documents.return_value = [[0.1] * 768] * len(sample_chunks)
```

**Settings mock must also change:** The mock currently provides `openai_api_key` which does not exist in `Settings`. It must provide `ollama_embed_model`, `ollama_base_url`, `supabase_url`, `supabase_service_key`.

### Anti-Patterns to Avoid

- **Creating clients inside hot paths:** Do not instantiate `OllamaEmbeddings` or `create_client` inside any function that is called per-request or per-chunk. Always use the singleton getter.
- **Making pipeline functions async:** Do not convert `embed_and_store()` or `answer()` to async. Keep them synchronous; the `asyncio.to_thread()` wrapper in `app.py` is the correct boundary. Mixing sync and async in LangChain internals causes subtle bugs.
- **Thread-unsafe shared mutable state in singletons:** `OllamaEmbeddings` and Supabase client are read-only after construction (stateless HTTP clients). Safe to share across threads. Do not add mutable state to singletons.
- **Reversing the delete order:** Never delete Supabase records before deleting the local file. The local file is the source of truth for "did this ingest actually happen on this machine."

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe singleton | Double-checked locking, class with `__new__` | `functools.lru_cache(maxsize=1)` | Thread-safe by design in CPython; already proven in this codebase via `get_settings()` |
| Running sync code from async | `loop.run_in_executor()` with explicit executor setup | `asyncio.to_thread()` | Simpler API, no boilerplate, available since Python 3.9 |
| Mocking module-level imports | Manual monkey-patching via `sys.modules` | `unittest.mock.patch` with correct target path | Standard, reversible, thread-safe in test context |

---

## Common Pitfalls

### Pitfall 1: Patch Target Is the Import Location, Not the Definition Location
**What goes wrong:** Test uses `@patch("langchain_ollama.OllamaEmbeddings")` instead of `@patch("src.ingest.OllamaEmbeddings")`. The patch is applied to the wrong namespace; `ingest.py` still uses the real class.
**Why it happens:** Confusing where a symbol is defined vs. where it is used.
**How to avoid:** Always patch the name in the module that uses it: `src.ingest.OllamaEmbeddings`.
**Warning signs:** Test passes even when Ollama VPS is unreachable — real call was made and somehow didn't error.

### Pitfall 2: lru_cache Singleton Bleeds Between Tests
**What goes wrong:** One test patches `src.ingest.OllamaEmbeddings`, but a previous test already populated the `lru_cache` for `_get_embedder()`. The cache returns the real instance from the previous call; the patch has no effect.
**Why it happens:** `lru_cache` persists across the entire test session unless explicitly cleared.
**How to avoid:** In tests that exercise code using cached singletons, either: (a) patch the singleton getter itself (`@patch("src.ingest._get_embedder")`), or (b) call `_get_embedder.cache_clear()` in test teardown. Option (a) is simpler and more robust.
**Warning signs:** Tests pass in isolation but fail when run together (`pytest tests/`).

### Pitfall 3: asyncio.to_thread Swallows Exceptions as RuntimeErrors
**What goes wrong:** Exceptions raised inside `asyncio.to_thread(fn, ...)` propagate back as-is to the awaiting coroutine. However, if the surrounding `try/except` in `app.py` catches `RuntimeError`, it will still catch exceptions correctly because `embed_and_store` already wraps its errors in `RuntimeError`. No change needed to exception handling.
**Why it happens:** Misunderstanding of how `to_thread` propagates exceptions.
**How to avoid:** No change needed — the existing `try/except RuntimeError` blocks in `app.py` work correctly with `asyncio.to_thread`.
**Warning signs:** None — this is a non-issue but worth confirming.

### Pitfall 4: Supabase Client Reuse Across Threads
**What goes wrong:** `asyncio.to_thread()` runs the function in a thread pool. If the Supabase client singleton is not thread-safe, concurrent calls could corrupt state.
**Why it happens:** Uncertainty about `supabase-py` thread safety.
**How to avoid:** The `supabase-py` client uses `httpx` internally. `httpx.Client` is safe to use across threads for independent requests. The singleton pattern is safe here. No connection pool exhaustion risk — `lru_cache` ensures a single client instance.
**Warning signs:** None expected — but if concurrent upload + query causes errors, investigate Supabase client thread safety in the installed version.

### Pitfall 5: Secondary Broken Test — .txt Extension
**What goes wrong:** `test_raises_for_unsupported_extension` in `test_ingest.py` creates a `.txt` file and expects `ValueError`. But `ingest.py` includes `.txt` in the `supported` set and loads it via `TextLoader`. This test WILL FAIL when run.
**Why it happens:** The test was written when `.txt` was not supported; the implementation was later updated without updating the test.
**How to avoid:** Fix the test to use an actually unsupported extension (e.g., `.csv` or `.mp4`).
**Warning signs:** `pytest` reports `Failed: DID NOT RAISE` on this test.

---

## Code Examples

Verified patterns from direct source inspection:

### Correct Singleton Getter (following existing get_settings() pattern)
```python
# Pattern already proven in src/config.py lines 94-109
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    ...

# Apply same pattern for clients in src/ingest.py and src/retrieval.py
from functools import lru_cache

@lru_cache(maxsize=1)
def _get_embedder() -> OllamaEmbeddings:
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )

@lru_cache(maxsize=1)
def _get_supabase_client() -> "Client":
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
```

### asyncio.to_thread Wrapping in app.py
```python
import asyncio

# In _run_upload_flow() — Step 4:
stored = await asyncio.to_thread(embed_and_store, chunks, callback=progress)

# In _run_rag_flow():
result = await asyncio.to_thread(answer, question)
```

### Correct Delete Flow
```python
async def _run_delete_flow(filename: str) -> None:
    local_file = DOCS_DIR / filename

    # Schritt 1: Lokale Datei prüfen — wenn nicht vorhanden, Supabase NICHT anfassen
    if not local_file.exists():
        await cl.Message(
            content=(
                f"Lokale Datei '{filename}' nicht gefunden.\n"
                "Supabase-Einträge wurden nicht verändert."
            )
        ).send()
        return

    async with cl.Step(name=f"Loesche '{filename}'...") as step:
        # Schritt 2: Lokale Datei zuerst löschen
        local_file.unlink()
        step.output = f"Datei '{filename}' aus /docs entfernt"

        # Schritt 3: Dann Supabase-Records löschen
        try:
            deleted_chunks = await asyncio.to_thread(delete_document, filename)
            step.output += f" | {deleted_chunks} Chunks aus Datenbank entfernt"
        except RuntimeError as exc:
            logger.error("Delete DB failed for '%s': %s", filename, exc)
            await cl.Message(
                content=f"Datei wurde gelöscht, aber Datenbankfehler: {type(exc).__name__}"
            ).send()
            return
```

### Correct Test Mock for OllamaEmbeddings
```python
@patch("src.ingest.create_client")
@patch("src.ingest.OllamaEmbeddings")   # Correct: matches import in ingest.py
@patch("src.ingest.get_settings")
def test_stores_correct_number_of_chunks(
    self, mock_settings, mock_embeddings_cls, mock_create_client, sample_chunks
):
    mock_settings.return_value = MagicMock(
        ollama_embed_model="nomic-embed-text",
        ollama_base_url="http://100.x.x.x:11434",
        supabase_url="https://x.supabase.co",
        supabase_service_key="key",
    )

    mock_embedder = MagicMock()
    mock_embedder.embed_documents.return_value = [[0.1] * 768] * len(sample_chunks)  # 768!
    mock_embeddings_cls.return_value = mock_embedder

    # ... rest of test unchanged
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `loop.run_in_executor(None, fn)` | `asyncio.to_thread(fn, *args)` | Python 3.9 | Simpler API, same effect |
| Module-level global variable for singletons | `@lru_cache(maxsize=1)` getter function | Python 3.2+ | Thread-safe, lazy initialization, testable via cache_clear() |

---

## Open Questions

1. **Shared singleton module vs. per-module singletons**
   - What we know: Both `ingest.py` and `retrieval.py` need the same two singletons (`OllamaEmbeddings`, Supabase client). Defining them in both modules creates duplication; extracting to `src/clients.py` is cleaner but adds a file.
   - What's unclear: Scope preference — "minimal code change" (duplicate in each module) vs. "clean architecture" (shared module).
   - Recommendation: Given CLAUDE.md principle "Impact minimal code", define in each module independently. If a future phase introduces a third consumer, then extract. The planner should decide based on task scope.

2. **delete_document local-file responsibility**
   - What we know: Currently, the local-file deletion logic lives entirely in `app.py`'s `_run_delete_flow()`, while `ingest.py`'s `delete_document()` only touches Supabase. TECH-05 specifies "delete local file first, then Supabase". This could mean: (a) keep the logic in `app.py` but reorder it, or (b) move local-file deletion into `ingest.py`'s `delete_document()`.
   - What's unclear: Whether `delete_document()` should be responsible for file system operations (mixing concerns) or whether `app.py` orchestration is the right place.
   - Recommendation: Keep file deletion in `app.py` — `ingest.py`'s `delete_document()` is correctly scoped to DB operations. Only reorder the steps in `_run_delete_flow()`. This is the minimal change.

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | none detected — runs with `pytest` from project root |
| Quick run command | `pytest tests/test_ingest.py tests/test_pipeline.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TECH-01 | `embed_and_store` and `answer` do not block event loop | unit (mock asyncio.to_thread integration) | `pytest tests/test_app_async.py -x -q` | ❌ Wave 0 |
| TECH-02 | Same `OllamaEmbeddings` instance returned on repeated calls | unit | `pytest tests/test_singletons.py -x -q` | ❌ Wave 0 |
| TECH-03 | Same Supabase client instance returned on repeated calls | unit | `pytest tests/test_singletons.py -x -q` | ❌ Wave 0 |
| TECH-04 | `OllamaEmbeddings` mock works, dimension=768 | unit | `pytest tests/test_ingest.py::TestEmbedAndStore -x -q` | ✅ (needs fix) |
| TECH-05 | Delete with missing local file leaves Supabase untouched | unit | `pytest tests/test_app_delete.py -x -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_ingest.py tests/test_pipeline.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_singletons.py` — covers TECH-02 and TECH-03: verify `_get_embedder()` and `_get_supabase_client()` return the same object on repeated calls, with `cache_clear()` in teardown
- [ ] `tests/test_app_async.py` — covers TECH-01: verify that `asyncio.to_thread` is called (mock it) and that the async handlers do not block; or at minimum verify the `await` keyword is present via code inspection test
- [ ] `tests/test_app_delete.py` — covers TECH-05: verify that when local file does not exist, `delete_document` is never called
- [ ] Fix existing `tests/test_ingest.py` — TECH-04: patch target, dimension, settings mock, and `.txt` extension test

---

## Sources

### Primary (HIGH confidence)
- Direct source code inspection: `src/ingest.py`, `src/retrieval.py`, `src/pipeline.py`, `app.py`, `tests/test_ingest.py`, `tests/test_pipeline.py`, `src/config.py`
- Python stdlib docs (asyncio.to_thread available since 3.9, project uses 3.11): https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
- Python stdlib docs (functools.lru_cache thread-safe in CPython): https://docs.python.org/3/library/functools.html#functools.lru_cache

### Secondary (MEDIUM confidence)
- unittest.mock.patch targeting rules (patch where the name is used, not where defined): https://docs.python.org/3/library/unittest.mock.html#patch

---

## Metadata

**Confidence breakdown:**
- Bug identification (TECH-01 through TECH-05): HIGH — confirmed by direct code inspection, no ambiguity
- Fix patterns (asyncio.to_thread, lru_cache): HIGH — stdlib, stable since Python 3.9/3.2
- Test fix patterns: HIGH — unittest.mock behavior is well-documented and directly verifiable
- Wave 0 test file designs: MEDIUM — interface design is straightforward but exact test structure is planner's choice

**Research date:** 2026-03-16
**Valid until:** 2026-06-16 (stable stdlib patterns; no expiry risk)
