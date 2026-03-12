# Pitfalls Research

**Domain:** RAG document assistant — PoC to pilot-ready transition (Python / LangChain / Chainlit / Supabase / Ollama on VPS)
**Researched:** 2026-03-12
**Confidence:** HIGH — all pitfalls sourced from direct codebase inspection; supplemented by domain knowledge of Chainlit async model, LangChain production patterns, and Docker-on-VPS deployment.

---

## Critical Pitfalls

### Pitfall 1: Blocking Sync Code Inside Chainlit's Async Event Loop

**What goes wrong:**
`embed_and_store()` in `app.py` line 210 is called directly inside an `async def` handler without `asyncio.to_thread()` or a thread pool. This call blocks the entire Chainlit event loop for the duration of the Ollama HTTP round-trips and Supabase insertions. While blocked, the server cannot handle any other websocket messages — including keepalive pings — making the UI appear frozen. For a 50-page PDF producing ~200 chunks at 10 chunks/batch, this easily takes 20–60 seconds. If the client disconnects due to a missed heartbeat, the upload silently fails with no partial rollback.

**Why it happens:**
Chainlit handlers are `async`, which gives a false sense that all called code is safe. The event loop runs on a single thread; any synchronous I/O inside `async def` blocks the whole server, not just the current session.

**How to avoid:**
Wrap all blocking calls with `asyncio.to_thread()`:
```python
stored = await asyncio.to_thread(embed_and_store, chunks, callback=progress)
result = await asyncio.to_thread(answer, question)
```
Apply this to every call path in `app.py` that reaches Ollama, Supabase, or the Anthropic API: `embed_and_store`, `delete_document`, `load_document`, `answer`. The `_run_rag_flow` call to `answer()` on line 312 is equally blocking.

**Warning signs:**
- UI shows a spinner but stops updating mid-upload
- All concurrent users are blocked while one user uploads
- Chainlit logs show websocket ping timeouts during uploads
- `answer()` takes 3–5 seconds but the UI does not update until the entire function returns

**Phase to address:** Tech Debt phase (first milestone phase)

---

### Pitfall 2: OllamaEmbeddings Recreated Per Call — TCP Connection Exhaustion Under Load

**What goes wrong:**
`OllamaEmbeddings` is instantiated fresh in every call to `embed_and_store()` and `search()`. Each instantiation creates a new `httpx` client, which opens new TCP connections to the Ollama VPS via Tailscale. Over a multi-user session or bulk ingest, this results in TCP connection exhaustion on the VPS (which has tight resource limits on a shared Hostinger instance). Connection errors are non-deterministic and surface as `RuntimeError` from Ollama, causing mid-upload failures with no retry logic.

**Why it happens:**
Quick PoC implementation: instantiation was placed inside the function body for simplicity. The `get_settings()` singleton was correctly cached with `@lru_cache`; the same pattern was not applied to the Ollama and Supabase clients.

**How to avoid:**
Cache at module level with `functools.lru_cache` or a module-level singleton:
```python
# src/ingest.py and src/retrieval.py
from functools import lru_cache

@lru_cache(maxsize=1)
def _get_embeddings() -> OllamaEmbeddings:
    s = get_settings()
    return OllamaEmbeddings(base_url=str(s.ollama_base_url), model=s.ollama_embed_model)
```
Apply the same pattern to the Supabase client (`create_client` calls in `ingest.py` lines 184/226, `retrieval.py` lines 47/87, `app.py` line 17).

**Warning signs:**
- `httpx.ConnectTimeout` or `httpx.RemoteProtocolError` errors after several uploads in a row
- VPS netstat showing many `TIME_WAIT` TCP connections
- Embed latency increases over session lifetime (connection setup overhead accumulating)

**Phase to address:** Tech Debt phase

---

### Pitfall 3: Stale Test Mocks — False Confidence in CI

**What goes wrong:**
`test_ingest.py` patches `src.ingest.OpenAIEmbeddings` but the module imports `OllamaEmbeddings`. The patch silently targets a name that does not exist in the module, so the real `OllamaEmbeddings` is never mocked. If `OllamaEmbeddings` calls through to Ollama during tests (e.g., in an environment where Ollama is reachable), tests pass by accident; in CI where Ollama is not available, the test crashes or skips for the wrong reason. The test also asserts `vector(1536)` dimension but production uses `vector(768)`. This means CI gives a green checkmark while hiding actual integration failures.

**Why it happens:**
The codebase was originally prototyped with OpenAI embeddings. When migrated to Ollama, the mock import path was not updated. The test continued to pass because the wrong class name was silently patched as a no-op (no exception is raised when you patch a non-existent attribute on a module).

**How to avoid:**
Fix the patch target to `src.ingest.OllamaEmbeddings`. Add an assertion that the mock was actually called (`mock_embeddings.assert_called_once()`). Update dimension assertions from 1536 to 768 everywhere. Add a CI smoke test that verifies the patch target exists at import time using `unittest.mock.patch` with `create=False` (the default) — this will raise `AttributeError` if the attribute doesn't exist.

**Warning signs:**
- Test passes without network access but nothing was actually mocked correctly
- Adding `assert mock_embeddings.called` causes the test to fail
- `grep -r "OpenAIEmbeddings" tests/` returns any result

**Phase to address:** Tech Debt phase (fix before CI can be trusted)

---

### Pitfall 4: Race Condition in Document Delete — Irrecoverable Inconsistent State

**What goes wrong:**
`_run_delete_flow` in `app.py` calls `delete_document(filename)` (removes Supabase chunks), then immediately calls `local_file.unlink()` (removes the file from the Docker volume). If the file deletion fails (permissions, volume mount issue, Docker overlay filesystem glitch), the Supabase records are already gone but the file remains on disk. Re-uploading the same filename creates duplicate chunks in Supabase on the next upload (no deduplication guard). There is no rollback or re-try mechanism.

**Why it happens:**
The operations are treated as a single logical delete but are two separate I/O operations with no transaction semantics. The implementation assumed both would succeed or that the order was unimportant.

**How to avoid:**
Reverse the order: delete the local file first, then delete Supabase records. A missing file is recoverable (re-upload); orphaned Supabase rows with no corresponding file cause silent data inconsistency that's harder to detect. Additionally, add an upsert guard in `embed_and_store`: before inserting, delete existing chunks with the same `source` and `tenant_id` to prevent duplicate accumulation on re-upload.

**Warning signs:**
- `get_indexed_documents()` returns no file, but re-uploading the same filename doubles the chunk count
- Log shows `delete_document` succeeded but a subsequent log line shows file-not-found error
- Supabase shows 0 rows for a document but the file exists in the Docker volume

**Phase to address:** Tech Debt phase

---

### Pitfall 5: RAG Quality Degrades Silently — No Evaluation Loop

**What goes wrong:**
The PoC produces answers but there is no mechanism to know if they are correct, relevant, or hallucinated. As more documents are added, retrieval quality can degrade: cosine similarity may return chunks that match keywords but not intent. Without an evaluation dataset and automated scoring, the transition to pilot looks complete while retrieval may be returning the wrong chunks for 30–40% of real user queries. This is discovered only when the pilot customer provides negative feedback, by which point it feels like a product failure rather than a tunable parameter.

**Why it happens:**
RAG evaluation is typically deferred during PoC because it requires test data. Transitioning to pilot without addressing this is the default path unless evaluation is explicitly planned.

**How to avoid:**
Before the pilot starts, create a small golden evaluation set of 10–20 question/answer pairs covering the kinds of documents the pilot customer will use. Log every `search()` call with the returned chunks and run manual spot-checks. Add a metric: "were all source citations in the answer traceable to a returned chunk?" as a basic hallucination check. Consider adjusting `TOP_K_RESULTS` from 4 to 5–6 and chunk size from 500 to 300 tokens if answers are missing context — these are the two most impactful levers.

**Warning signs:**
- Answer says "Diese Information ist in den vorliegenden Dokumenten nicht enthalten" for a question that should be answerable
- Source citations in answers don't match the document section where the answer actually lives
- Pilot customer asks the same question multiple times in different wording and gets different answers

**Phase to address:** RAG Quality phase (dedicated milestone before pilot launch)

---

### Pitfall 6: Tailscale Dependency in CI/CD — Flaky Deploys

**What goes wrong:**
The GitHub Actions deploy pipeline establishes a Tailscale connection to reach the VPS (which is only accessible via Tailscale). The pipeline then uses native `ssh` and `scp` to the Tailscale IP. If Tailscale authentication fails, the `tailscale ip` is unreachable, or the runner's Tailscale subnet routing is slow to propagate, the `nc -zv` reachability check on line 42 will timeout and the entire deployment fails — including image push to GHCR and the deploy step. The pipeline currently has no retry logic and no rollback: if `docker compose up -d` fails mid-deploy, the container is left in an undefined state.

**Why it happens:**
Tailscale is the correct security choice for a small pilot, but it introduces a transient network dependency in CI that does not exist in traditional deployments. The pipeline was recently migrated from appleboy actions (which ran inside Docker and couldn't access Tailscale) to native ssh; this was the right fix but adds a new failure mode.

**How to avoid:**
Add a `retry` wrapper around the Tailscale connect step (the GitHub Action supports `--timeout` flags). Add a `--wait` for Tailscale to reach the peer before proceeding. Use `docker compose pull && docker compose up -d` with `|| docker compose up -d` (pull failure should not abort deploy if the old image is still runnable). Capture `docker compose ps` after deploy and fail the job if any service is not healthy. Consider adding a rollback step: if the health check fails after deploy, restart the previous container.

**Warning signs:**
- CI logs show "connection refused" or timeout on port 22 reachability check
- Pipeline passes the build step but fails the deploy step intermittently (not on every run)
- VPS container is `Exiting` after a deploy that appeared to succeed

**Phase to address:** CI/CD Stabilization phase

---

### Pitfall 7: Unstructured "fast" Strategy Silently Fails on Real-World Documents

**What goes wrong:**
`UnstructuredFileLoader(strategy="fast")` uses pdfminer for text extraction. It works well on digitally-created PDFs but silently returns near-empty documents for scanned PDFs, image-heavy PDFs, or PDFs with unusual fonts. `load_document()` returns a list with very short `page_content` strings and no warning is raised. These empty or near-empty chunks are embedded and stored, producing low-quality vectors that never match any query. The user sees no error but their document is effectively invisible to the RAG system.

**Why it happens:**
The "fast" strategy was chosen for performance and simplicity during PoC. Document quality validation was not added because all test documents were digitally-created text PDFs.

**How to avoid:**
Add post-load validation in `load_document()`: if the total extracted text is under a threshold (e.g., fewer than 200 characters per page on average), emit a `logger.warning()` and include a user-facing caution in the upload success message. For pilot, pre-screen customer documents manually. Document that scanned PDFs require `strategy="hi_res"` (which requires Tesseract and is significantly slower). Make the strategy configurable via `UNSTRUCTURED_STRATEGY` env var with `"fast"` as default but `"hi_res"` as documented fallback.

**Warning signs:**
- Uploaded document produces fewer chunks than expected (e.g., 5 chunks for a 50-page PDF)
- Average `page_content` length in chunks is under 100 characters
- RAG answers "not found" for questions that are clearly in the document

**Phase to address:** RAG Quality phase

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `embed_and_store()` called synchronously in async handler | Simpler code, no threading | UI freezes during upload; users experience timeouts for large files | Never — must fix before pilot |
| `OllamaEmbeddings` instantiated per call | Zero setup code | TCP connection exhaustion under any real load; unpredictable latency | Never — module-level singleton is a 5-line fix |
| `create_client()` (Supabase) called per operation | No shared state to manage | Connection overhead on every DB operation; fragile under concurrent requests | Never — same singleton pattern as Ollama fix |
| Plaintext password comparison in auth callback | Simple to implement | Unsuitable if password ever logged; cannot add rate-limiting | Only for single-user pilot where Tailscale provides perimeter security |
| Hard-coded `tenant_id="default"` throughout UI | No multi-tenancy complexity | Any future multi-user pilot requires UI changes and re-test | Acceptable for single-customer pilot |
| `strategy="fast"` for all document types | Fast, no OCR dependency | Silently drops scanned PDF content | Acceptable only if customer document set is pre-validated as digital text |
| Loose version pins in `requirements.txt` | Easier initial install | Breaks silently when LangChain or Chainlit release breaking minor versions | Never in production; pin exact versions before pilot |
| Cost calculations with hard-coded pricing | Quick to implement | Estimates diverge from actual charges as Anthropic pricing changes | Acceptable for PoC cost monitoring; revisit before billing customers |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Chainlit `cl.Step` | Assuming `step.output =` during async execution updates the UI live | Steps only render their output when the `async with` block exits; live progress requires `cl.Message` updates or streaming |
| Chainlit `cl.AskFileMessage` | Treating returned value as always a list | Returns a list when `max_files > 1`, a single object when `max_files=1` — current code handles both but is fragile |
| Supabase RPC `match_document_chunks` | Calling without `tenant_id` filter in tests | Tests that omit the filter will match across all tenants; any test data bleeds into result sets |
| Supabase `insert()` | Not checking `.data` on the response before asserting success | `execute()` returns an object even on failure if RLS isn't configured; check `.data is not None and len(.data) > 0` |
| Ollama `embed_documents()` | Passing more than ~50 chunks in a single batch | Ollama has no hard limit but large batches cause request timeouts on the VPS; 10-chunk batches are the right default |
| Anthropic `messages.create()` | Not handling rate limit errors (`anthropic.RateLimitError`) | Must wrap with retry logic or surface a clear user message; silent failure causes "frozen" UI during rate limit window |
| Docker volume `docs_data` | Assuming volume is empty after `docker compose down` | Named volumes persist across `down`; documents accumulate. `docker compose down -v` destroys them. Document this for VPS ops. |
| GitHub Actions + Tailscale | Using appleboy SSH/SCP actions (run inside Docker on runner) | Tailscale tun interface is on the runner host, not inside the action's Docker container; must use native ssh/scp on the runner |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous `embed_and_store()` blocking event loop | All users frozen while one user uploads | `asyncio.to_thread()` for all blocking calls in async handlers | Immediately with any concurrent user |
| Fresh `OllamaEmbeddings` instance per call | Increasing latency per request; TCP `TIME_WAIT` buildup on VPS | Module-level singleton with `@lru_cache` | After ~10–20 requests in a session |
| Fresh `create_client()` per Supabase operation | Increased latency; connection pool warnings in logs | Module-level Supabase singleton | After ~50 DB operations |
| IVFFlat index with `lists=100` | Vector search latency grows from <100ms to >2s | Tune `lists` parameter as table grows; monitor with `EXPLAIN ANALYZE` | Above ~50,000 document chunks |
| No query result caching | Identical questions re-embed and re-query every time | Cache recent (question, embedding) pairs with TTL | Noticeable at >5 queries/minute from same user |
| `tiktoken cl100k_base` for nomic-embed-text sizing | Chunks slightly over/under the 512-token limit for the model | Validate empirically; nomic-embed-text silently truncates input above its context length | When documents have long dense paragraphs |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `SUPABASE_SERVICE_KEY` used everywhere | Service key has full DB access — a key leak exposes all document data | For pilot: acceptable. For SaaS: use anon key + Row Level Security policies |
| No input validation on uploaded filenames | A filename like `../../../etc/passwd` passed to `DOCS_DIR / filename` could traverse directories on some platforms | Sanitize filenames before constructing `dest_path`: strip path components with `Path(filename).name` only |
| `.env` written to VPS filesystem by deploy script | `.env` file with all secrets written to `/opt/dok-assistent/.env` is readable by any process running as the deploy user | Use environment injection only (as documented in `docker-compose.yml`); the CI script correctly writes then immediately uses it, but the file persists — add `chmod 600` and consider `rm .env` after `docker compose up` |
| Plaintext password in Chainlit auth | Passwords stored as environment variable, compared in plain text | Acceptable for single-user pilot behind Tailscale; unacceptable for multi-user or internet-exposed deployment |
| Exception details exposed in error messages | `f"_(Intern: {type(exc).__name__})_"` leaks implementation details; full exception could include stack traces with file paths | Keep internal error details in logs only; surface only a generic "error occurred" message to users |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback during embedding (UI appears frozen for 30+ seconds) | Pilot user thinks the app crashed and refreshes, restarting the upload | Use `asyncio.to_thread()` so the event loop stays live; update the Step output periodically |
| No conversation history between sessions | Pilot customer cannot re-read yesterday's analysis; every session starts blank | Implement session persistence (Chainlit's built-in `data_layer` or a simple Supabase `conversations` table) |
| No multi-turn context in a single conversation | Follow-up questions ("what about section 3?") don't work; every query is stateless | Pass last N messages as context to `pipeline.answer()`; this is the most-requested RAG pilot feature |
| `/loeschen` command as document management | Non-technical pilot users won't discover or remember CLI-style commands | Replace with a document management panel (list of documents with a delete button per row) |
| Generic error message on Ollama timeout | User sees "error occurred" with no action they can take | Surface "Embedding service unavailable — check VPN connection (Tailscale)" to match the German-language error conventions already in the code |
| Welcome screen re-ingestion prompt | No indication of what questions the documents can answer | After upload, show example questions generated from the document's first page |

---

## "Looks Done But Isn't" Checklist

- [ ] **Async safety:** `embed_and_store` and `answer` are wrapped in `asyncio.to_thread()` — verify no `async def` handler calls sync I/O directly
- [ ] **Test mock accuracy:** `patch("src.ingest.OllamaEmbeddings")` (not OpenAIEmbeddings) — run `pytest tests/test_ingest.py -v` and confirm mocks are actually intercepting calls
- [ ] **Embedding dimensions:** Supabase `document_chunks.embedding` is `vector(768)` — run `SELECT atttypmod FROM pg_attribute WHERE attrelid='document_chunks'::regclass AND attname='embedding'`
- [ ] **Delete idempotency:** Re-uploading a deleted document produces exactly the same chunk count as the first upload — verify by uploading, deleting, uploading again and checking Supabase row count
- [ ] **Tailscale in CI:** CI pipeline completes deploy without Tailscale timeout on 3 consecutive runs — confirm in Actions run history
- [ ] **Blocking confirmed fixed:** Upload a 20-page PDF and simultaneously submit a chat question — verify the question responds during the upload
- [ ] **Document quality check:** Upload a scanned PDF and verify the app warns the user rather than silently indexing empty chunks
- [ ] **Version pins:** `pip install -r requirements.txt` in a fresh venv produces identical library versions — verify with `pip freeze | diff requirements.txt -`

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Blocking event loop discovered in production | MEDIUM | Deploy `asyncio.to_thread()` fix; no data migration needed; users simply restart their upload |
| Duplicate chunks from failed delete + re-upload | LOW | `DELETE FROM document_chunks WHERE source = '<filename>' AND tenant_id = 'default'` in Supabase SQL editor; re-upload document |
| OllamaEmbeddings TCP exhaustion on VPS | LOW | Restart Docker container (`docker compose restart chainlit`); fix singleton before next deploy |
| Wrong embedding dimensions in Supabase (1536 vs 768) | HIGH | Drop and recreate `document_chunks` table with correct `vector(768)` schema; re-ingest all documents |
| Tailscale auth key expires mid-CI | LOW | Rotate `TAILSCALE_AUTH_KEY` secret in GitHub → Settings → Secrets; re-run failed workflow |
| Document silently not searchable (empty chunks from scanned PDF) | MEDIUM | Delete document from Supabase; re-ingest with `strategy="hi_res"` via CLI (`python ingest_cli.py --file ...`) |
| Stale test mocks give false CI confidence | LOW | Fix patch targets; no production impact, but CI trust is restored |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Blocking async event loop | Phase 1: Tech Debt Fixes | Upload 20-page PDF while sending chat message; both complete without blocking |
| OllamaEmbeddings recreated per call | Phase 1: Tech Debt Fixes | `grep -n "OllamaEmbeddings()" src/` returns zero results |
| Supabase client recreated per call | Phase 1: Tech Debt Fixes | `grep -n "create_client(" src/ app.py` shows only module-level calls |
| Stale OpenAIEmbeddings mock | Phase 1: Tech Debt Fixes | `pytest tests/test_ingest.py -v` passes with `create=False` patch assertions |
| Delete race condition | Phase 1: Tech Debt Fixes | Delete + re-upload produces identical chunk count in Supabase |
| Tailscale flaky CI deploys | Phase 2: CI/CD Stabilization | 5 consecutive master-branch pushes deploy successfully with no manual intervention |
| Unstructured silent empty extraction | Phase 3: RAG Quality | Upload of known scanned PDF triggers warning message in UI |
| RAG answer quality — no evaluation | Phase 3: RAG Quality | Golden set of 15 Q/A pairs scores >80% retrieval accuracy |
| No conversation history | Phase 4: Chat History | Reloading the browser restores the last 3 conversations |
| No multi-turn context | Phase 4: Chat History | Follow-up question "was steht in Abschnitt 3?" correctly uses prior answer context |
| `/loeschen` UX not pilot-ready | Phase 5: UI/UX Polish | Pilot customer can manage documents without reading documentation |

---

## Sources

- Direct codebase inspection: `app.py`, `src/ingest.py`, `src/retrieval.py`, `src/pipeline.py` (2026-03-12)
- `.planning/codebase/CONCERNS.md` — full tech debt, bug, and fragility audit
- `.planning/codebase/TESTING.md` — known test coverage gaps and stale mock documentation
- `.planning/codebase/ARCHITECTURE.md` — data flow and layer structure
- `.github/workflows/deploy.yml` — CI/CD pipeline inspection (Tailscale + native SSH pattern)
- `Dockerfile` + `docker-compose.yml` — deployment configuration inspection
- Domain knowledge: Chainlit async model (asyncio single-threaded event loop, `asyncio.to_thread` requirement for sync I/O), LangChain production patterns (singleton embeddings clients), RAG quality evaluation practices (golden set, retrieval accuracy), Docker volume persistence behavior

---

*Pitfalls research for: RAG document assistant — PoC to pilot-ready transition*
*Researched: 2026-03-12*
