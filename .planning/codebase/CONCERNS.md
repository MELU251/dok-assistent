# Codebase Concerns

**Analysis Date:** 2025-03-12

## Tech Debt

**Inconsistent OllamaEmbeddings instantiation:**
- Issue: `OllamaEmbeddings` client is recreated on every embedding operation (search queries, bulk embed) instead of being cached or initialized once
- Files: `src/retrieval.py` (lines 36-40), `src/ingest.py` (lines 149-152), `app.py`
- Impact: Significant performance overhead; each query/embedding operation creates a new HTTP client and potentially new TCP connections. With high query volume, this could cause resource exhaustion or slow response times.
- Fix approach: Cache `OllamaEmbeddings` instance in a singleton or module-level variable, similar to how settings are cached with `@lru_cache` in `src/config.py`

**Blocking embedding operations in chat UI:**
- Issue: `embed_and_store()` in `app.py` (lines 210) runs synchronously in async context without offloading to thread pool
- Files: `app.py` (lines 204-211)
- Impact: Blocks the Chainlit event loop during embedding creation and storage, making the UI unresponsive. For large documents with many chunks, this could timeout or cause "frozen" UI.
- Fix approach: Use `asyncio.to_thread()` or `concurrent.futures.ThreadPoolExecutor` to run CPU/I/O bound embedding work off the main event loop

**Supabase client created on every operation:**
- Issue: `create_client()` is called repeatedly in `ingest.py`, `retrieval.py`, and `app.py` instead of being cached
- Files: `src/ingest.py` (lines 184, 226), `src/retrieval.py` (lines 47, 87), `app.py` (line 17)
- Impact: Unnecessary connection overhead; potential connection pool exhaustion under load
- Fix approach: Cache Supabase client in a module-level singleton or inject it as a dependency

**Hard-coded cost estimation formulas:**
- Issue: Cost calculation uses hard-coded 2024 pricing for claude-sonnet-4-6 and static USD→EUR conversion (lines 31-32 in `pipeline.py`)
- Files: `src/pipeline.py` (lines 30-33), `ingest_cli.py` (line 15)
- Impact: Cost estimates become inaccurate as Anthropic pricing changes. No mechanism to update without code changes.
- Fix approach: Move pricing to configuration (`.env` or config.py), or fetch from Anthropic pricing API periodically

**Metadata handling assumes consistent structure:**
- Issue: Code assumes document metadata always has "source" and "page" fields, using `.get()` with defaults but not validating structure
- Files: `src/pipeline.py` (lines 47-48), `src/retrieval.py` (lines 62-65), `app.py` (lines 189-190)
- Impact: If ingestion fails to set required metadata, source attribution breaks silently in answers
- Fix approach: Implement metadata validation schema in `load_document()` to ensure all chunks have required metadata before storage

## Known Bugs

**Test mismatch with actual embeddings implementation:**
- Symptoms: `test_ingest.py` (line 132) patches `OpenAIEmbeddings` but code actually uses `OllamaEmbeddings`
- Files: `tests/test_ingest.py` (line 132)
- Trigger: Running `pytest tests/test_ingest.py::TestEmbedAndStore::test_stores_correct_number_of_chunks`
- Workaround: Test currently passes due to mocking, but doesn't validate actual Ollama integration
- Impact: False confidence in embed_and_store tests; actual Ollama failures won't be caught

**Potential race condition in document deletion:**
- Symptoms: Delete operation removes chunks from database but then immediately tries to delete local file; if file operations fail, Supabase records are already gone
- Files: `app.py` (lines 267-282)
- Trigger: Network interruption or permission error during `local_file.unlink()` after successful delete
- Workaround: None - if file deletion fails, no rollback mechanism
- Impact: Inconsistent state between Supabase (clean) and local filesystem (file still present)

**Chunk limit handling in vector search not enforced:**
- Symptoms: `retrieval.py` passes `match_count` to RPC function but no validation that result respects limit
- Files: `src/retrieval.py` (lines 48-55)
- Trigger: Edge case where Supabase RPC returns more results than requested
- Workaround: Could slice result manually
- Impact: Could feed more context than configured `TOP_K_RESULTS` to Claude, inflating token usage and costs

## Security Considerations

**API keys exposed in error messages:**
- Risk: Exception handling in multiple places logs full exceptions which could contain sensitive information if Anthropic/Supabase errors include auth details
- Files: `src/ingest.py` (lines 168, 198), `src/retrieval.py` (lines 42, 57), `src/pipeline.py` (lines 139)
- Current mitigation: Logging uses `logger.error()` which outputs to console/file, not to client
- Recommendations:
  - Sanitize exception messages before logging
  - Never include raw exception objects in user-facing messages
  - Use structured logging with separate error codes instead of full exception text

**Plaintext secrets in .env configuration:**
- Risk: `ANTHROPIC_API_KEY`, `SUPABASE_SERVICE_KEY`, `CHAINLIT_AUTH_SECRET` stored in `.env` file
- Files: Referenced in `src/config.py`, `.env` (not readable)
- Current mitigation: `.env` listed in `.gitignore`
- Recommendations:
  - For production: migrate to environment variable injection or secret management systems (AWS Secrets Manager, HashiCorp Vault, etc.)
  - Implement rotation mechanism for API keys
  - Add audit logging for all API credential usage

**Ollama over Tailscale but no certificate validation:**
- Risk: Tailscale connection is unencrypted HTTP (not HTTPS) from code perspective
- Files: `src/config.py` (line 26), code creates client with `http://` URLs
- Current mitigation: Tailscale VPN provides encryption at network level
- Recommendations:
  - Document explicitly that Tailscale security is the only protection
  - Add TLS support if Ollama needs to operate outside Tailscale perimeter
  - Validate Tailscale IP is in expected range to catch misconfiguration

**SQL injection risk in document source filtering:**
- Risk: Document `source` field (filename) comes from user uploads and is used in SQL equality filters
- Files: `src/ingest.py` (lines 230-231), `src/retrieval.py` (line 53 filter)
- Current mitigation: Uses Supabase ORM/SDK which parameterizes queries
- Recommendations:
  - Continue using parameterized APIs; never construct SQL strings
  - Validate filename length and characters (alphanumeric + safe punctuation only)
  - Add filename whitelist/validation in `app.py` upload handler

**Password authentication uses plaintext comparison:**
- Risk: Chainlit auth callback compares plaintext passwords in memory
- Files: `app.py` (lines 55-56)
- Current mitigation: Only used for development/PoC; auth enforced at network level via Tailscale in production docs
- Recommendations:
  - For production: replace with proper OAuth2/OIDC provider
  - If using password: hash with bcrypt/argon2, never store/compare plaintext
  - Implement rate limiting on failed login attempts

## Performance Bottlenecks

**Vector search RPC function assumes optimal index configuration:**
- Problem: `match_document_chunks` RPC performance depends on Supabase IVFFlat index quality
- Files: `src/retrieval.py` (lines 48-55), Supabase migration in CLAUDE.md
- Cause: No monitoring or validation that index is correctly tuned for data size
- Improvement path:
  - Monitor query latency and index size over time
  - Adjust IVFFlat `lists` parameter based on table size (currently hardcoded to 100)
  - Consider HNSW index for larger datasets (>1M documents)

**No batch optimization for multiple queries:**
- Problem: Each user question creates a separate embedding and search operation
- Files: `src/pipeline.py` (lines 115), `app.py` (lines 310-312)
- Cause: Architecture assumes single-question-per-request pattern
- Improvement path:
  - Cache recent query embeddings to avoid re-embedding identical questions
  - Implement request queuing/batching if multi-user concurrent load occurs
  - Profile actual latency; most likely bottleneck is Ollama embedding time (not vector search)

**Chunk size approximation could be inaccurate:**
- Problem: Uses `tiktoken.get_encoding("cl100k_base")` to estimate tokens, but nomic-embed-text may tokenize differently
- Files: `src/ingest.py` (lines 90-93)
- Cause: No official token counter for nomic-embed-text; approximation chosen for performance
- Improvement path:
  - Validate token counting accuracy by periodically comparing actual embedding counts to estimates
  - If drift detected, consider using Ollama's tokenization API or switching to character-based chunking

## Fragile Areas

**Document loading depends on Unstructured library behavior:**
- Files: `src/ingest.py` (lines 57-62, 10)
- Why fragile: UnstructuredFileLoader uses different parsing strategies (fast vs hi_res) which have different accuracy/speed tradeoffs. "fast" strategy may fail on scanned PDFs or complex layouts.
- Safe modification:
  - Add strategy parameter to environment config (currently hardcoded to "fast")
  - Implement fallback strategy if one fails
  - Add document validation step post-load to warn if extracted text is suspiciously short
- Test coverage: `test_ingest.py` mocks the loader; no integration tests with real PDFs

**Metadata extraction from documents is lossy:**
- Files: `src/ingest.py` (lines 69-71)
- Why fragile: Only preserves "source" (filename) and "page". Loses document title, author, creation date, which could be useful for filtering or context
- Safe modification:
  - Expand metadata schema in Supabase (add author, doc_type, created_at)
  - Update ingest flow to extract and preserve additional metadata
  - Migrate existing document_chunks records
- Test coverage: Tests verify source/page are set but don't validate metadata richness

**RAG prompt template is not versioned or swappable:**
- Files: `src/pipeline.py` (lines 15-28)
- Why fragile: Hard-coded system prompt makes experimentation difficult; changing prompt requires code change and re-deployment
- Safe modification:
  - Move prompt template to a separate file or config
  - Implement prompt versioning (e.g., "de_rag_v1", "de_rag_v2") with fallback chain
  - Add A/B testing capability for prompt variants
- Test coverage: `test_pipeline.py` tests prompt building but doesn't test different prompts

**Cost estimation not validated against actual charges:**
- Files: `src/pipeline.py` (lines 74-88), `ingest_cli.py` (lines 15)
- Why fragile: Estimates are approximations; actual Anthropic charges depend on exact tokenization. No reconciliation between estimates and real charges.
- Safe modification:
  - Store actual token counts and estimated costs in database for all queries
  - Monthly reconciliation script comparing estimates to Anthropic API usage reports
  - Alert if divergence exceeds threshold (e.g., >10%)
- Test coverage: No tests verify cost calculation accuracy

## Scaling Limits

**Single Supabase instance for all tenants:**
- Current capacity: Database designed for multi-tenant (tenant_id column) but no row-level security (RLS) policies visible
- Limit: Without RLS, a compromised API key or bug could expose all tenants' documents
- Scaling path:
  - Implement Supabase RLS policies to enforce tenant isolation at database level
  - Consider separate Supabase projects per tenant for higher isolation
  - Add multi-tenancy compliance audit (SOC2/ISO27001 requirement)

**Chainlit UI not designed for multi-user concurrent access:**
- Current capacity: Single session per user; no mention of concurrent session limits
- Limit: Chainlit's memory/state management may not handle >10-20 concurrent users
- Scaling path:
  - Benchmark Chainlit under load (use `locust` or `wrk`)
  - If needed, migrate to custom FastAPI + WebSocket UI with explicit session management
  - Implement rate limiting per user/tenant

**Ollama VPS resource constraints:**
- Current capacity: Single nomic-embed-text model on shared VPS; embedding throughput limited by GPU/CPU
- Limit: With multiple users, embedding requests will queue. Latency degrades rapidly above ~5 concurrent embeddings
- Scaling path:
  - Monitor Ollama response times and queue depth
  - Implement async embedding queue with celery/RabbitMQ
  - Add second embedding model replica on separate VPS or Kubernetes pod
  - Consider batch embedding endpoint instead of single-query at a time

**Supabase pgvector index not tuned for scale:**
- Current capacity: IVFFlat index with lists=100 designed for small datasets (<100K documents)
- Limit: Index effectiveness degrades significantly above 1M chunks; query latency will increase
- Scaling path:
  - Monitor index bloat with `SELECT pg_size_pretty(pg_total_relation_size('document_chunks'))`
  - Tune lists parameter: lists = sqrt(number_of_rows/probe_recall_accuracy)
  - Implement document TTL/archival to prevent unbounded growth
  - Consider partitioning by tenant_id if single table grows too large

## Dependencies at Risk

**langchain-community and langchain-ollama version coupling:**
- Risk: Code imports from both `langchain_community` (TextLoader, UnstructuredFileLoader) and `langchain_ollama`. These packages may have breaking changes in minor versions.
- Impact: Dependencies on ">=0.3.0" are loose; could pull incompatible minor versions
- Migration plan:
  - Pin exact versions in requirements.txt (e.g., `langchain-ollama==0.2.1`)
  - Run integration tests in CI on dependency updates
  - Keep separate minor version pins for each langchain-* package to enforce compatibility

**Unstructured[pdf,docx,xlsx] dependency chain:**
- Risk: Unstructured pulls heavy dependencies: pdf parsing (pdfminer.six), DOCX parsing (python-docx), XLSX parsing (openpyxl). Any of these could have CVEs.
- Impact: Large attack surface; supply chain risk if malicious code injected into any transitive dependency
- Migration plan:
  - Monitor security advisories for all transitive dependencies (`pip-audit` or Dependabot)
  - Consider splitting document type support (optional extras) if not all users need all formats
  - Evaluate alternatives (e.g., pypdf for PDF-only support)

**Anthropic API client version 0.40.0:**
- Risk: Loose constraint "anthropic>=0.40.0"; new versions could change API client behavior or deprecate functions
- Impact: Code assumes `client.messages.create()` interface which could change in major version
- Migration plan:
  - Pin to 0.40.x range (e.g., `anthropic>=0.40.0,<0.41.0`)
  - Subscribe to Anthropic SDK changelog and plan upgrades quarterly
  - Test new versions in staging before production deployment

**Python 3.11 end-of-life approaching (Oct 2027):**
- Risk: Code explicitly requires Python 3.11; support ends in 2027
- Impact: Will need migration to Python 3.12+ in production before EOL
- Migration plan:
  - Update CI to test against Python 3.12 and 3.13
  - Test and fix any compatibility issues proactively
  - Plan Python 3.12 upgrade for late 2026

## Missing Critical Features

**No authentication/authorization beyond single-user password:**
- Problem: Chainlit auth only validates one hardcoded username/password. No multi-user, role-based access, or audit trail.
- Blocks: Cannot deploy to production with multiple users; no compliance with audit requirements
- Recommendation: Implement proper authentication (OAuth2 via external provider) and role-based access control (admin, analyst, viewer)

**No data export/backup mechanism:**
- Problem: Users cannot export conversation history, chunked documents, or query logs
- Blocks: GDPR data subject access requests; no disaster recovery capability
- Recommendation: Implement document export (PDF/ZIP), conversation history export, and automated backups to S3

**No query audit logging or compliance tracking:**
- Problem: No structured logging of who queried what documents when; required for HIPAA/GDPR compliance
- Blocks: Cannot audit access to sensitive documents; regulatory non-compliance
- Recommendation: Add audit_log table tracking user_id, query, results, timestamp, tenant_id with immutable records

**No rate limiting or cost control:**
- Problem: Users can submit unlimited queries with no cost cap. Uncontrolled Claude API spending.
- Blocks: Prevents production use; cost runaway risk if used with large documents
- Recommendation: Implement per-tenant query quota, cost budget alerts, and automatic query rejection when limits exceeded

**No document version control or history:**
- Problem: If a document is re-uploaded with same filename, old version is silently overwritten in Supabase
- Blocks: Cannot maintain document lineage; audit trail is lost
- Recommendation: Implement versioning (version field in document_chunks) with ability to query against specific document version

## Test Coverage Gaps

**No integration tests for full RAG pipeline:**
- What's not tested: End-to-end flow from document upload → embedding → search → Claude response with actual services
- Files: Integration tests missing; `test_connection.py` only health-checks, doesn't test pipeline
- Risk: Potential failures in service coordination, data flow, or error handling only discovered in production
- Priority: High - core business logic should have integration tests

**No tests for Chainlit UI flows:**
- What's not tested: Upload flow, delete flow, RAG query flow with file operations and async steps
- Files: `app.py` entirely untested
- Risk: UI regressions, error handling issues, or performance problems only caught in manual testing
- Priority: High - UI is user-facing; issues directly impact usability

**No load/stress tests:**
- What's not tested: Behavior under concurrent users, large documents, or high query volume
- Files: No load test suite exists
- Risk: Latency, timeouts, or crashes under realistic load only discovered after production deployment
- Priority: Medium - important before scaling beyond pilot phase

**No tests for multi-tenant isolation:**
- What's not tested: Tenant-id filtering in search, delete, and ingestion; cannot confirm documents from tenant A don't leak to tenant B
- Files: Retrieval and ingest functions have tenant_id parameter but no tests verify isolation
- Risk: Data leakage between tenants in production; critical security issue
- Priority: Critical - must test before multi-tenant deployment

**No tests for embedding dimension validation:**
- What's not tested: Code assumes nomic-embed-text always returns 768-dimensional vectors; no validation
- Files: `src/ingest.py` (line 160) doesn't validate vector dimensionality matches schema
- Risk: If Ollama model changes or embedding dims misconfigured, bulk insert will fail silently or create invalid data
- Priority: Medium - safeguard for operational issues

**Cost estimation accuracy not tested:**
- What's not tested: Cost calculation against real Anthropic pricing; estimates may diverge from actual charges
- Files: `src/pipeline.py` cost functions have no tests against real pricing data
- Risk: Cost estimates presented to users are inaccurate; impacts SaaS pricing/UX
- Priority: Medium - important for accurate cost tracking

---

*Concerns audit: 2025-03-12*
