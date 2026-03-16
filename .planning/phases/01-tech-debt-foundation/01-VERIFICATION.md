---
phase: 01-tech-debt-foundation
verified: 2026-03-16T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run the Chainlit app, upload a large PDF, and attempt to interact with the chat UI during the upload"
    expected: "The UI remains responsive — button clicks and text input are not frozen while embedding is in progress"
    why_human: "asyncio.to_thread offload is verified at the code level but actual Chainlit responsiveness under real upload load cannot be confirmed without running the app"
---

# Phase 1: Tech Debt Foundation — Verification Report

**Phase Goal:** Der Chainlit-Event-Loop blockiert nicht mehr; alle externen Clients werden als Singletons gecacht; Tests decken den tatsächlichen Code-Pfad ab; der Delete-Flow ist atomar korrekt
**Verified:** 2026-03-16
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1 | Dokument-Upload blockiert die UI nicht mehr — andere Nutzer-Aktionen bleiben während des Uploads ansprechbar | VERIFIED (code) / ? (runtime) | `app.py` line 211: `stored = await asyncio.to_thread(embed_and_store, chunks, callback=progress)`; `test_app_async.py` 2/2 tests green |
| 2 | Nach 20 aufeinanderfolgenden Queries keine TCP-Verbindungserschöpfung — OllamaEmbeddings- und Supabase-Client-Instanzen sind Singletons | VERIFIED | `_get_embedder()` and `_get_supabase_client()` decorated with `@lru_cache(maxsize=1)` in both `src/ingest.py` and `src/retrieval.py`; `test_singletons.py` 3/3 tests green |
| 3 | `pytest` läuft grün und testet tatsächlich `OllamaEmbeddings`; Dimension-Assertion ist 768, nicht 1536 | VERIFIED | `test_ingest.py` patches `src.ingest._get_embedder`, asserts `[[0.1] * 768]`; no reference to `OpenAIEmbeddings` or `1536` in any phase-modified test file; 15/15 tests green |
| 4 | Ein `/loeschen`-Befehl, der die lokale Datei nicht findet, hinterlässt die Supabase-Records unberührt | VERIFIED | `_run_delete_flow()` checks `local_file.exists()` first and returns immediately without calling `delete_document`; `test_app_delete.py` 2/2 tests green |

**Score:** 4/4 truths verified (automated)
**Human verification pending:** 1 item (runtime UI responsiveness — code is correct)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ingest.py` | `_get_embedder()` and `_get_supabase_client()` with `@lru_cache(maxsize=1)` | VERIFIED | Lines 25-39: both singletons present; `embed_and_store()` calls `_get_embedder()` (line 167) and `_get_supabase_client()` (line 199); `delete_document()` calls `_get_supabase_client()` (line 240) |
| `src/retrieval.py` | Same two singleton getters; `search()` and `get_indexed_documents()` use them | VERIFIED | Lines 15-29: both singletons present; `search()` calls `_get_embedder()` (line 54) and `_get_supabase_client()` (line 62); `get_indexed_documents()` calls `_get_supabase_client()` (line 101) |
| `app.py` | `import asyncio`; three `asyncio.to_thread` wrappers; corrected `_run_delete_flow()` | VERIFIED | `import asyncio` at line 11; `to_thread` at lines 211, 281, 318; `_run_delete_flow()` checks `local_file.exists()` before touching Supabase |
| `tests/test_ingest.py` | Patches `src.ingest._get_embedder` and `_get_supabase_client`; dimension 768; no OpenAI references | VERIFIED | Lines 131-133: correct patch targets; line 145: `[[0.1] * 768]`; no `OpenAIEmbeddings` or `1536` in file |
| `tests/test_singletons.py` | Tests identity of `_get_embedder()` and `_get_supabase_client()` in both modules | VERIFIED | Three test classes covering ingest embedder, ingest Supabase client, retrieval Supabase client; all pass |
| `tests/test_app_async.py` | Tests `embed_and_store` and `answer` are called via `asyncio.to_thread` | VERIFIED | Two test classes; patch targets `app.asyncio.to_thread`; asserts function identity in `call_args_list` |
| `tests/test_app_delete.py` | Tests missing-file guard and file-before-Supabase ordering | VERIFIED | Two tests; `assert_not_called()` for missing file; `check_order` side-effect asserts file is gone before `delete_document` is invoked |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py _run_upload_flow()` | `src.ingest.embed_and_store` | `await asyncio.to_thread(embed_and_store, chunks, callback=progress)` | WIRED | Line 211 confirmed |
| `app.py _run_rag_flow()` | `src.pipeline.answer` | `await asyncio.to_thread(answer, question)` | WIRED | Line 318 confirmed |
| `app.py _run_delete_flow()` | `src.ingest.delete_document` | `await asyncio.to_thread(delete_document, filename)` — only after `local_file.unlink()` | WIRED | Lines 276 (unlink) then 281 (to_thread delete) confirm correct order |
| `src/ingest.py embed_and_store()` | `_get_embedder()` | Direct call replaces inline `OllamaEmbeddings(...)` | WIRED | Line 167; no inline `OllamaEmbeddings(` in any hot path |
| `src/ingest.py delete_document()` | `_get_supabase_client()` | Direct call replaces inline `create_client(...)` | WIRED | Line 240 |
| `src/retrieval.py search()` | `_get_embedder()` and `_get_supabase_client()` | Direct calls replace inline instantiation | WIRED | Lines 54 and 62 |
| `src/retrieval.py get_indexed_documents()` | `_get_supabase_client()` | Direct call | WIRED | Line 101 |
| `tests/test_singletons.py` | `src.ingest._get_embedder` | Import with `cache_clear()` in teardown | WIRED | Lines 12-13, 23-27 |
| `tests/test_app_delete.py` | `src.ingest.delete_document` | `@patch("app.delete_document")` + `assert_not_called()` | WIRED | Lines 18, 24 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TECH-01 | 01-03-PLAN.md | `embed_and_store()` and `pipeline.answer()` run in `asyncio.to_thread()` | SATISFIED | `app.py` lines 211, 318; `test_app_async.py` 2 tests green |
| TECH-02 | 01-02-PLAN.md | `OllamaEmbeddings` instance cached as module-level singleton | SATISFIED | `_get_embedder()` `@lru_cache(maxsize=1)` in both `ingest.py` and `retrieval.py`; `test_singletons.py` 2 tests green |
| TECH-03 | 01-02-PLAN.md | Supabase client cached as singleton across all modules | SATISFIED | `_get_supabase_client()` `@lru_cache(maxsize=1)` in both modules; `test_singletons.py` TestSupabaseSingletonIngest + TestSupabaseSingletonRetrieval green |
| TECH-04 | 01-01-PLAN.md | `test_ingest.py` patches `OllamaEmbeddings` (not `OpenAIEmbeddings`); dimension 768 | SATISFIED | `test_ingest.py` patches `src.ingest._get_embedder`; dimension `768`; no `OpenAIEmbeddings` reference in modified test files |
| TECH-05 | 01-04-PLAN.md | Delete-Flow: local file deleted before Supabase; file-absent guard prevents Supabase access | SATISFIED | `_run_delete_flow()` checks `local_file.exists()` first, calls `local_file.unlink()` before `delete_document`; `test_app_delete.py` 2 tests green |

All 5 requirements: SATISFIED. No orphaned requirements — REQUIREMENTS.md Traceability table maps TECH-01 through TECH-05 exclusively to Phase 1, all accounted for.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Checked: `src/ingest.py`, `src/retrieval.py`, `app.py`, `tests/test_ingest.py`, `tests/test_singletons.py`, `tests/test_app_async.py`, `tests/test_app_delete.py`

No TODO/FIXME/placeholder comments, no empty implementations, no console.log-only stubs, no `return null` / `return {}` shells found in any phase-modified file.

Note: `tests/test_embeddings.py` contains references to `OpenAIEmbeddings` and `1536`, but this is a pre-existing integration test file not modified by Phase 1 and not in any plan's `files_modified` list. It is out of scope.

---

### Human Verification Required

#### 1. Chainlit UI Responsiveness Under Upload Load

**Test:** Start the Chainlit app (`chainlit run app.py`), authenticate, then upload a moderately large PDF (>1 MB). While the embedding step is running, click the "Dokument hochladen" button or type a message.
**Expected:** The UI accepts input and displays responses (even if queued) during the upload — the browser tab does not freeze, the Chainlit event loop continues servicing requests.
**Why human:** The `asyncio.to_thread` wrapping is verified at the code level. Whether Chainlit itself handles concurrency correctly end-to-end under real network conditions to the Tailscale VPS requires a live runtime test.

---

### Summary

All four observable truths from the ROADMAP.md Success Criteria are satisfied at the code level:

1. **TECH-01 (async fix):** `embed_and_store`, `answer`, and `delete_document` are all wrapped with `asyncio.to_thread` in `app.py`. The test suite confirms the wiring with mock-patched `asyncio.to_thread`.

2. **TECH-02 / TECH-03 (singletons):** Both `_get_embedder()` and `_get_supabase_client()` are present with `@lru_cache(maxsize=1)` in `src/ingest.py` and `src/retrieval.py`. All four hot-path functions (`embed_and_store`, `delete_document`, `search`, `get_indexed_documents`) use the getters — no inline instantiation remains. Three singleton identity tests pass.

3. **TECH-04 (correct test mock):** `test_ingest.py` now patches `src.ingest._get_embedder` (the lru_cache-safe target) and asserts 768-dimensional vectors. No reference to `OpenAIEmbeddings` or `1536` exists in any phase-modified test file.

4. **TECH-05 (atomic delete):** `_run_delete_flow()` guards on `local_file.exists()` first, calls `local_file.unlink()` before `asyncio.to_thread(delete_document, ...)`. Two tests confirm both the guard case (Supabase never called) and the ordering case (file gone before DB delete).

**Test suite result:** 15/15 tests pass in 2.71 seconds.

The phase goal is fully achieved at the code level. One human verification item exists for runtime UI responsiveness confirmation, which does not block the goal assessment.

---

_Verified: 2026-03-16_
_Verifier: Claude (gsd-verifier)_
