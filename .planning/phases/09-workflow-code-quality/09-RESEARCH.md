# Phase 9: Workflow Code Quality - Research

**Researched:** 2026-03-18
**Domain:** Python dead-code removal, Chainlit UI messaging, singleton consolidation
**Confidence:** HIGH

## Summary

Phase 9 closes two specific audit gaps (WORK-04, WORK-06) identified in the v1.0 milestone audit. The gaps are surgical and well-understood: the `hil_hinweis` value is generated in `src/generator.py` but never surfaced as a Chainlit chat message; `create_angebotsentwurf` is imported at the top of `app.py` but never called (the flow was reimplemented inline); and `_get_embedder`/`_get_supabase_client` singletons are duplicated verbatim in both `src/ingest.py` and `src/retrieval.py`.

All three fixes are code-level changes with no architectural decisions required. The `hil_hinweis` fix is a one-line `cl.Message` call appended to `_run_workflow_generation()`. The dead import fix requires removing one `import` line from `app.py` and verifying no other code path calls the removed function. The singleton consolidation is a refactor: extract both getters into a new `src/clients.py` (or `src/singletons.py`) module and update imports in `ingest.py` and `retrieval.py`.

**Primary recommendation:** Fix all three issues in a single plan. The dead import and `hil_hinweis` fixes are trivial; the singleton extraction is the only structural change and should be done carefully to not break existing tests that patch `src.ingest._get_embedder` and `src.retrieval._get_supabase_client` directly.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WORK-04 | Every generated draft contains a "Human-in-the-Loop" notice visible in the Chainlit chat (not only inside the downloaded .docx) | `hil_hinweis` key already exists in `generate_angebot()` return dict — needs one `cl.Message` call in `_run_workflow_generation()` |
| WORK-06 | `create_angebotsentwurf()` in `src/workflow.py` is not dead code — the module is a coherent, tested orchestration unit | Import at `app.py:24` is never used; `_run_workflow_generation()` re-implements the pipeline inline; fix = remove dead import (do NOT re-route production flow through the orchestrator, which would break the existing 3-step split UI) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chainlit | 2.10.0 | `cl.Message(...).send()` for surfacing `hil_hinweis` | Already the project UI framework |
| pytest | current (pytest.ini present) | Unit tests for changed modules | Project standard since Phase 1 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `functools.lru_cache` | stdlib | Singleton pattern via cached getter functions | Already used; consolidation reuses same pattern |
| `unittest.mock.patch` | stdlib | Patching singletons in tests | All existing tests already use this; patch targets will change if singletons move to new module |

**Installation:** No new packages needed.

## Architecture Patterns

### Recommended Project Structure (after phase)
```
src/
├── clients.py       # NEW: shared _get_embedder(), _get_supabase_client() singletons
├── config.py        # unchanged
├── ingest.py        # remove duplicate _get_embedder, _get_supabase_client; import from clients
├── retrieval.py     # remove duplicate _get_embedder, _get_supabase_client; import from clients
├── workflow.py      # unchanged (dead import removed from app.py, not here)
├── generator.py     # unchanged
├── extractor.py     # unchanged
└── output.py        # unchanged
app.py              # remove line 24 (dead import); add hil_hinweis message in _run_workflow_generation()
```

### Pattern 1: Removing a Dead Import
**What:** Delete the `from src.workflow import create_angebotsentwurf` line at `app.py:24`. The function is never called in `app.py`; `_run_workflow_generation()` performs the pipeline steps inline using local imports.
**When to use:** When a top-level import exists but grep shows zero call sites.
**Key constraint:** `OUTPUT_DIR` from `src.workflow` IS still used at `app.py:611`. The import at line 24 covers both `create_angebotsentwurf` and, implicitly, enables the `from src.workflow import OUTPUT_DIR` inside `_run_workflow_generation()`. After removing the top-level import, the local `from src.workflow import OUTPUT_DIR` inside the function body remains valid — no change needed there.

```python
# BEFORE app.py line 24:
from src.workflow import create_angebotsentwurf

# AFTER: line deleted entirely
# (from src.workflow import OUTPUT_DIR inside _run_workflow_generation() body is a separate local import — unaffected)
```

### Pattern 2: Surfacing hil_hinweis in Chainlit
**What:** After `_deliver_file()` in `_run_workflow_generation()`, send an additional `cl.Message` with the `hil_hinweis` value from the result dict.
**When to use:** When a key is computed and returned but the UI layer never renders it.

```python
# app.py — inside _run_workflow_generation(), after _deliver_file() call:
await cl.Message(
    content=f"**Hinweis:** {result['hil_hinweis']}"
).send()
```

`result["hil_hinweis"]` is already populated by `generate_angebot()` (see `src/generator.py:110`). No changes to generator or output needed.

### Pattern 3: Singleton Consolidation into src/clients.py
**What:** Create `src/clients.py` containing both `_get_embedder()` and `_get_supabase_client()` with `@lru_cache(maxsize=1)`. Both `ingest.py` and `retrieval.py` import from `clients.py` instead of defining their own copies.
**When to use:** When the same private function body is duplicated verbatim across two modules.

```python
# src/clients.py (new file)
from functools import lru_cache
from langchain_ollama import OllamaEmbeddings
from supabase import create_client
from src.config import get_settings

@lru_cache(maxsize=1)
def _get_embedder() -> OllamaEmbeddings:
    """OllamaEmbeddings-Singleton — wird einmal erstellt und wiederverwendet."""
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )

@lru_cache(maxsize=1)
def _get_supabase_client():
    """Supabase-Client-Singleton — wird einmal erstellt und wiederverwendet."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
```

```python
# src/ingest.py — replace local definitions with:
from src.clients import _get_embedder, _get_supabase_client

# src/retrieval.py — replace local definitions with:
from src.clients import _get_embedder, _get_supabase_client
```

### Anti-Patterns to Avoid
- **Re-routing `_run_workflow_generation()` through `create_angebotsentwurf()`:** The inline 3-step split (extract separately, store pending state, confirm) is intentional UI design. Collapsing it into a single `create_angebotsentwurf()` call would break the user-facing verification step (WORK-07 is already satisfied). Do not do this.
- **Keeping module-level re-exports:** Do not add `_get_embedder = clients._get_embedder` aliases in `ingest.py`/`retrieval.py`. This defeats the consolidation and breaks patch targets. Update tests to patch `src.clients._get_embedder` instead.
- **Moving the singleton module to `src/utils.py`:** Vague naming. `src/clients.py` is precise — it holds external service client factories.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Process-wide singleton | Custom `__init__` class-level registry | `@lru_cache(maxsize=1)` on getter function | Already the project pattern; thread-safe for CPython; cache_clear() works in tests |
| Human review notice | Custom notification system | Simple `cl.Message(...).send()` | Chainlit already renders text messages inline |

**Key insight:** All three fixes are one-liners or small file reshuffles. There is no complex logic to implement.

## Common Pitfalls

### Pitfall 1: Broken Patch Targets After Singleton Move
**What goes wrong:** `test_singletons.py`, `test_ingest.py`, and `test_retrieval.py` patch `src.ingest._get_embedder`, `src.ingest._get_supabase_client`, `src.retrieval._get_embedder`, and `src.retrieval._get_supabase_client`. After moving to `src.clients`, these patch targets no longer resolve — tests silently pass through to real singletons.
**Why it happens:** `unittest.mock.patch` resolves the dotted name at the time of patching. If the attribute no longer lives in the module being patched, the patch has no effect.
**How to avoid:** Update ALL patch targets to `src.clients._get_embedder` and `src.clients._get_supabase_client`. Run `grep -rn "_get_embedder\|_get_supabase_client" tests/` before and after to confirm all patch strings are updated.
**Warning signs:** Tests pass but `mock_cls.call_count == 1` assertion suddenly fails, or `mock_cls.return_value` is not what is returned by the function under test.

### Pitfall 2: OUTPUT_DIR Import Confusion
**What goes wrong:** Removing the top-level `from src.workflow import create_angebotsentwurf` might tempt a developer to also clean up `from src.workflow import OUTPUT_DIR` — but that import lives inside the function body of `_run_workflow_generation()` (line 611) and IS still needed.
**Why it happens:** Two different import styles for the same module in the same file.
**How to avoid:** Only remove the top-level line 24. Leave the local imports inside the function body intact. Run `python -c "import app"` after the change to verify no `ImportError`.

### Pitfall 3: hil_hinweis Key Missing if Result Dict Changes
**What goes wrong:** `result["hil_hinweis"]` will raise `KeyError` if `generate_angebot()` ever returns without the key (e.g., in a future refactor or test mock that uses an incomplete dict).
**Why it happens:** Direct dict key access without `.get()`.
**How to avoid:** Use `result.get("hil_hinweis", "")` in the UI layer. Check `test_workflow.py`'s `_GENERATOR_RESULT` fixture already includes `hil_hinweis` — if it does not, add it.

### Pitfall 4: lru_cache Cross-Test Contamination
**What goes wrong:** If tests in `test_singletons.py` call `_get_embedder()` from `src.clients` (after consolidation) but `teardown_method` still calls `src.ingest._get_embedder.cache_clear()`, the cache in `src.clients` is never cleared. Subsequent tests see a cached real instance.
**Why it happens:** The `lru_cache` object is per-function; after moving the function to `clients.py`, `ingest._get_embedder` is an alias — calling `cache_clear()` on it clears the same underlying `lru_cache` object only if the import is a reference (which it is in Python). This is actually safe, but must be verified.
**How to avoid:** In `teardown_method`, clear via `from src.clients import _get_embedder; _get_embedder.cache_clear()` — or keep clearing via `src.ingest._get_embedder.cache_clear()` since it references the same object after the import.

## Code Examples

### Verifying Dead Import (no call sites)
```bash
# Run before removing the import — should return zero results
grep -n "create_angebotsentwurf" app.py
# Expected: only line 24 (the import itself), no call sites
```

### Test Patch Target Update Pattern
```python
# BEFORE (test_singletons.py):
with patch("src.ingest.OllamaEmbeddings") as mock_cls:
    ...

# AFTER (both ingest and retrieval tests):
with patch("src.clients.OllamaEmbeddings") as mock_cls:
    ...
```

### Minimal hil_hinweis Chainlit Message
```python
# In _run_workflow_generation(), after _deliver_file() call:
hil_hinweis = result.get("hil_hinweis", "")
if hil_hinweis:
    await cl.Message(content=f"**Hinweis:** {hil_hinweis}").send()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Duplicated singleton definitions per module | Single shared `src/clients.py` module | Phase 9 | One cache per singleton process-wide; simpler test patching |
| `hil_hinweis` only in downloaded .docx | `hil_hinweis` also shown as `cl.Message` in chat | Phase 9 | WORK-04 satisfied |

**Dead code status:**
- `create_angebotsentwurf` in `app.py:24`: confirmed dead import — remove
- `create_angebotsentwurf` in `src/workflow.py`: keep — it is the documented orchestration function and is tested by `test_workflow.py`; the audit gap is that `app.py` imported but never called it. The resolution is to remove the dead import, not the function.

## Open Questions

1. **Should `src/clients.py` also export `get_settings` from `src/config.py`?**
   - What we know: `get_settings` is already a shared singleton in `src/config.py` with its own `lru_cache`. It is imported directly by all modules that need it.
   - What's unclear: There is no duplication of `get_settings` — the consolidation goal applies only to `_get_embedder` and `_get_supabase_client`.
   - Recommendation: Do not move `get_settings`. Only consolidate the two singletons that are duplicated.

2. **Should `test_singletons.py` be updated in place or a new `test_clients.py` created?**
   - What we know: `test_singletons.py` currently tests both `src.ingest` and `src.retrieval` singleton behaviour separately.
   - Recommendation: Update `test_singletons.py` to test `src.clients` directly. Remove the per-module singleton tests since the singletons no longer live there. This is cleaner and avoids double-testing.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini present, asyncio_mode=auto) |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/test_singletons.py tests/test_workflow.py -x -q` |
| Full suite command | `pytest -m "not integration" -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WORK-04 | `hil_hinweis` message sent in `_run_workflow_generation()` | unit | `pytest tests/test_app_async.py -k hil_hinweis -x` | Check existing; add test if missing |
| WORK-06 | `create_angebotsentwurf` not imported at module level in `app.py` | unit (import check) | `pytest tests/test_workflow.py -x -q` | ✅ (existing workflow tests cover the function itself) |
| Singleton | Single `lru_cache` in `src/clients.py` shared by both modules | unit | `pytest tests/test_singletons.py -x -q` | ✅ (needs patch target update) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_singletons.py tests/test_workflow.py -x -q`
- **Per wave merge:** `pytest -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_app_async.py` — needs a test asserting `hil_hinweis` is sent as `cl.Message` in `_run_workflow_generation()` (covers WORK-04). Check if this test already exists in `test_app_async.py`; if not, add it.
- [ ] `tests/test_singletons.py` — patch targets must be updated from `src.ingest.*` / `src.retrieval.*` to `src.clients.*` after singleton move.

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `app.py`, `src/generator.py`, `src/workflow.py`, `src/ingest.py`, `src/retrieval.py`, `src/config.py`
- Direct test inspection: `tests/test_singletons.py`, `tests/test_workflow.py`, `tests/test_generator.py`
- `.planning/v1.0-MILESTONE-AUDIT.md` — authoritative audit findings for WORK-04 and WORK-06

### Secondary (MEDIUM confidence)
- `.planning/milestones/v2-workflow-engine/REQUIREMENTS.md` — WORK-04, WORK-06 requirement text
- `.planning/ROADMAP.md` — phase goal statement

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all changes are in existing Python/Chainlit code
- Architecture: HIGH — all three changes are directly observable in the source files; no speculative API research required
- Pitfalls: HIGH — patch-target breakage pattern is well-known and verified against actual test files

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable codebase; no fast-moving dependencies involved)
