# External Integrations

**Analysis Date:** 2026-03-12

## APIs & External Services

**LLM Provider:**
- Anthropic Claude - Answer generation from retrieved document context
  - SDK/Client: `anthropic` Python package
  - Auth: `ANTHROPIC_API_KEY` environment variable
  - Usage: `src/pipeline.py` → `pipeline.answer()` calls `Anthropic(api_key=...).messages.create()`
  - Model: `claude-sonnet-4-6`
  - Integration: Direct HTTP REST API (not via LangChain wrapper)
  - Cost tracking: Input and output tokens counted for EUR cost estimation

## Data Storage

**Databases:**
- Supabase PostgreSQL with pgvector extension
  - Connection: `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` environment variables
  - Client: `supabase-py` 2.10+ SDK
  - Table: `document_chunks` with columns:
    - `id` (UUID primary key)
    - `tenant_id` (text, default='default')
    - `source` (text, document filename)
    - `page` (int, page number)
    - `content` (text, chunk body)
    - `embedding` (vector(768), cosine similarity searchable)
    - `created_at` (timestamp)
  - Operations:
    - Insert: `src/ingest.py` → `embed_and_store()` batches inserts via `.table("document_chunks").insert()`
    - Search: `src/retrieval.py` → `search()` calls RPC function `match_document_chunks` for similarity search
    - Delete: `src/ingest.py` → `delete_document()` purges chunks by source and tenant
    - Index: IVFFlat index on embedding column with 100 lists for cosine distance

**File Storage:**
- Local filesystem (Docker volume)
  - Location: `/app/docs` (Docker) → `docs/` (local dev)
  - Mount: `docs_data` Docker volume in `docker-compose.yml`
  - Lifecycle: Files uploaded via Chainlit UI, persisted for re-download

**Caching:**
- None - Each query performs fresh embedding and search
- LRU cache on `src.config.get_settings()` (application configuration, not query cache)

## Authentication & Identity

**Auth Provider:**
- Custom password-based authentication (Chainlit built-in)
  - Implementation: Password callback in `app.py` → `auth_callback(username, password)`
  - Credentials source: `CHAINLIT_USER` and `CHAINLIT_PASSWORD` environment variables
  - Session signing: `CHAINLIT_AUTH_SECRET` (JWT secret, 64-char hex string)
  - Scope: Single user per instance (no multi-user management)
  - Storage: Environment variables only, no database persistence

**API Key Management:**
- Anthropic: Environment variable `ANTHROPIC_API_KEY`
- Supabase: Environment variable `SUPABASE_SERVICE_KEY` (service role, full DB access)
- Ollama: No authentication required (accessible only via Tailscale VPN, network-level isolation)

## Monitoring & Observability

**Error Tracking:**
- None detected - No Sentry or similar error tracking service

**Logs:**
- Python `logging` module with configurable level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- Level: Set via `LOG_LEVEL` environment variable
- Output: stdout (captured by Docker)
- Structured logging: Uses `logger.info()`, `logger.warning()`, `logger.error()` throughout
- Notable logs:
  - `src/ingest.py`: Load time, chunk count, embedding duration, storage confirmation
  - `src/retrieval.py`: Chunks retrieved count per query
  - `src/pipeline.py`: Token usage, cost estimation, response time

**Health Checks:**
- Ollama connectivity: `src/config.py` → `check_ollama_connection()` sends GET to `/api/tags` endpoint
- Docker health probe: `docker-compose.yml` checks `http://localhost:8000/health` every 30s (Chainlit provides this)
- Manual testing: `tests/test_connection.py` validates Ollama and Supabase reachability

## CI/CD & Deployment

**Hosting:**
- Hostinger VPS (Linux)
- Deployment method: Docker Compose
- Image registry: GitHub Container Registry (ghcr.io)
- Image: `ghcr.io/melu251/dok-assistent:latest`

**CI Pipeline:**
- GitHub Actions workflows in `.github/workflows/` (not examined for this analysis)
- Likely: Build Docker image, push to GHCR, deploy to Hostinger via SSH

**Build Process:**
- `Dockerfile` multi-stage build:
  1. Builder stage: Install system deps + Python packages
  2. Runtime stage: Copy dependencies only (minimal layer)
  3. Entry point: `chainlit run app.py --host 0.0.0.0 --port 8000`

**Deployment Workflow:**
- Local dev: `docker-compose up`
- Production (Hostinger): Environment variables injected at runtime (not in .env file)
- Document persistence: Docker volume `docs_data` survives restarts

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Claude API authentication (non-optional, validated on startup)
- `OLLAMA_BASE_URL` - Embedding service URL, e.g., `http://100.x.x.x:32768` (non-optional)
- `SUPABASE_URL` - Database URL, e.g., `https://xxxx.supabase.co` (non-optional)
- `SUPABASE_SERVICE_KEY` - Full-permission database API key (non-optional)
- `CHAINLIT_AUTH_SECRET` - JWT signing secret (non-optional, 64-char hex)
- `CHAINLIT_PASSWORD` - Login password (non-optional)

**Optional env vars (defaults provided):**
- `CHUNK_SIZE=500` (tokens)
- `CHUNK_OVERLAP=50` (tokens)
- `TOP_K_RESULTS=4` (chunks per query)
- `LOG_LEVEL=INFO` (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `CHAINLIT_USER=pilot` (username)
- `OLLAMA_EMBED_MODEL=nomic-embed-text` (model name)

**Secrets location:**
- Development: `.env` file (git-ignored)
- Production: Hostinger dashboard → Environment Variables panel
- Template: `.env.example` provided for reference (values are placeholders)

## Webhooks & Callbacks

**Incoming:**
- None detected - Application is a request-response chat interface
- Chainlit provides `/health` endpoint for Docker health checks (read-only)

**Outgoing:**
- None - No webhook integrations to external services
- Unidirectional communication: Claude API (request only), Supabase (RPC/query only)

## Network & VPN

**Tailscale VPN:**
- Purpose: Secure tunnel to Ollama on Hostinger VPS
- Usage: `OLLAMA_BASE_URL=http://<TAILSCALE_IP>:11434` or `http://<TAILSCALE_IP>:32768`
- Security: Private IP namespace, no exposed ports to public internet
- Client requirement: Tailscale client must be running on developer machine and Hostinger VPS
- Configuration: Tailscale IP determined via `tailscale ip -4` on VPS

## Rate Limiting & Quotas

**Anthropic API:**
- Rate limits: Depend on API tier (not configured in code)
- Cost per query: Estimated based on token usage
- Monitoring: Tokens logged per request in `src/pipeline.py`

**Supabase:**
- RPC function: `match_document_chunks` (Postgres native, no explicit rate limiting)
- Vector search: IVFFlat index handles ~1M+ vector entries efficiently

**Ollama:**
- Self-hosted on VPS, no rate limits
- Concurrent requests: Limited by VPS resource allocation

## Document Format Support

**Supported File Types:**
- PDF (.pdf) - via `UnstructuredFileLoader` with `strategy="fast"` (pdfminer backend)
- DOCX (.docx) - via `UnstructuredFileLoader`
- XLSX (.xlsx) - via `UnstructuredFileLoader`
- TXT (.txt) - via simple `TextLoader`

**Processing Details:**
- Parser: `unstructured[pdf,docx,xlsx]` library with system dependencies (poppler, tesseract)
- OCR strategy: `strategy="fast"` for text-based PDFs; can switch to `strategy="hi_res"` for scans
- Language support: German via tesseract-ocr-deu package
- Metadata extraction: Source filename and page number preserved in chunks

---

*Integration audit: 2026-03-12*
