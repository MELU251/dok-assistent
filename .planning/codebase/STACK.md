# Technology Stack

**Analysis Date:** 2026-03-12

## Languages

**Primary:**
- Python 3.11 - Core application, RAG pipeline, CLI ingestion tool
- SQL - Supabase pgvector extension for vector storage and RPC functions

**Secondary:**
- TOML - Configuration (`chainlit.toml`)
- Markdown - Documentation

## Runtime

**Environment:**
- Python 3.11-slim (Docker base image)

**Package Manager:**
- pip - Python dependency management
- Lockfile: `requirements.txt` (manual, not automatically generated)

## Frameworks

**Core:**
- LangChain 0.3+ - RAG orchestration, document loading, embeddings, text splitting
- LangChain-Ollama 0.2+ - Integration with local Ollama embedding service
- LangChain-Anthropic 0.3+ - Claude API integration
- Anthropic SDK 0.40+ - Direct LLM calls for answer generation
- Chainlit 2.0+ - Chat UI with authentication and file upload

**Testing:**
- pytest 8.0+ - Unit and integration test framework
- pytest-mock 3.14+ - Mocking library for tests

**Build/Dev:**
- Docker - Multi-stage containerization (builder + runtime)
- Docker Compose - Local development and deployment orchestration

## Key Dependencies

**Critical:**
- `langchain-core` - LangChain base abstractions (Document, BaseEmbeddings)
- `langchain-community` - UnstructuredFileLoader for PDF/DOCX/XLSX parsing
- `langchain-text-splitters` - RecursiveCharacterTextSplitter for chunking
- `supabase` 2.10+ - Python client for Supabase (pgvector operations via RPC)
- `anthropic` 0.40+ - Official Anthropic client for Claude API calls

**Infrastructure:**
- `unstructured[pdf,docx,xlsx]` 0.16+ - Document parsing with format detection
- `tiktoken` 0.8+ - Token counting for chunk sizing (cl100k_base encoding)
- `httpx` 0.27+ - HTTP client for Ollama health checks (async-capable)
- `python-dotenv` 1.0+ - .env file loading for local development
- `pydantic-settings` 2.0+ - Configuration management with validation

**System-Level (Docker):**
- `libmagic1` - File type detection (required by unstructured)
- `poppler-utils` - PDF text extraction (pdfminer backend)
- `tesseract-ocr` - OCR for scanned PDFs
- `tesseract-ocr-deu` - German language OCR support (for `strategy="hi_res"`)
- `curl` - HTTP client for health checks in Docker health probe

## Configuration

**Environment:**
- Configuration source: `.env` file (local) or environment variables (Docker)
- Management: Pydantic `BaseSettings` with validation (`src/config.py`)
- Required variables validated at startup; placeholder values (e.g., `sk-ant-...`) rejected

**Key Configs:**
- `ANTHROPIC_API_KEY` - Anthropic API authentication
- `OLLAMA_BASE_URL` - Ollama service endpoint (e.g., `http://100.x.x.x:32768` via Tailscale VPN)
- `OLLAMA_EMBED_MODEL` - Model name (`nomic-embed-text` for 768-dim vectors)
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` - Service role API key (full permissions)
- `CHUNK_SIZE` - Token count per document chunk (default: 500)
- `CHUNK_OVERLAP` - Token overlap between chunks (default: 50)
- `TOP_K_RESULTS` - Chunks retrieved per query (default: 4)
- `LOG_LEVEL` - Python logging level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
- `CHAINLIT_AUTH_SECRET` - JWT secret for session signing
- `CHAINLIT_USER` - Login username
- `CHAINLIT_PASSWORD` - Login password

**Build:**
- `Dockerfile` - Multi-stage build (builder installs deps, runtime layer minimal)
- `docker-compose.yml` - Service orchestration (chainlit app + ingest tool profiles)
- Environment variable injection via docker-compose services section

## Platform Requirements

**Development:**
- Python 3.11+
- Docker and Docker Compose (for full stack)
- Tailscale VPN client (to reach Ollama on remote VPS via encrypted tunnel)
- Access to Anthropic API (requires valid API key)

**Production:**
- Deployment target: Docker container on Hostinger VPS
- Host OS: Linux (Ubuntu/Debian)
- Networking: Tailscale VPN for Ollama connectivity (no exposed ports)
- Database: Supabase cloud-hosted PostgreSQL with pgvector extension
- Storage: Docker volume (`docs_data`) for uploaded documents
- Entry point: `chainlit run app.py --host 0.0.0.0 --port 8000`

## Performance & Resource Notes

**Embeddings:**
- Service: Ollama (self-hosted on VPS via Tailscale)
- Model: `nomic-embed-text` (768-dimensional vectors)
- Cost: €0.00 (self-hosted)
- Batch processing: 10 chunks per embedding request (`_EMBED_BATCH_SIZE`)

**LLM Calls:**
- Model: `claude-sonnet-4-6`
- Max tokens per response: 1024
- Cost estimation: Input €3.0/1M tokens, Output €15.0/1M tokens (converted from USD)
- Target: < €0.02 per query

**Response Time:**
- Target: < 8 seconds per query (end-to-end)
- Components: Embedding (~3s) + Search (~0.5s) + LLM (~2-3s)

**Chunk Processing:**
- Token counting uses `tiktoken.get_encoding("cl100k_base")` (OpenAI encoding, matches claude models)
- Chunk size calculated in tokens (not characters) for consistent split quality
- Overlap ensures context preservation across chunk boundaries

---

*Stack analysis: 2026-03-12*
