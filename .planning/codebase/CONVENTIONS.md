# Coding Conventions

**Analysis Date:** 2026-03-12

## Naming Patterns

**Files:**
- Lowercase with underscores for module names: `config.py`, `ingest.py`, `retrieval.py`, `pipeline.py`
- Prefix test files with `test_`: `test_connection.py`, `test_ingest.py`, `test_pipeline.py`, `test_embeddings.py`
- Private helper constants prefixed with underscore: `_EMBED_BATCH_SIZE`, `_SYSTEM_PROMPT`, `_INPUT_COST_PER_1M`

**Functions:**
- Lowercase with underscores (snake_case): `load_document()`, `chunk_document()`, `embed_and_store()`, `get_settings()`
- Private/internal functions prefixed with underscore: `_build_context()`, `_extract_sources()`, `_estimate_cost()`, `_ok()`, `_fail()`
- Public functions without leading underscore, documented with docstrings

**Variables:**
- Lowercase with underscores (snake_case): `sample_docs`, `mock_docs`, `batch_size`, `query_vector`
- Module-level constants in UPPERCASE: `DOCS_DIR`, `_ACCEPTED_TYPES`, `_MAX_SIZE_MB`
- Temporary/loop variables lowercase: `i`, `doc`, `chunk`, `row`, `exc`

**Types:**
- Classes use PascalCase: `Settings`, `Document`, `User`
- Type hints use full paths when needed: `list[Document]`, `dict[str, Any]`, `Callable[[int, int], None]`
- Type hints on function parameters and returns (enforced throughout)

## Code Style

**Formatting:**
- No explicit formatter tool (Prettier/Black) configured
- Line wrapping appears flexible, multi-line strings and long imports observed
- Indentation: 4 spaces (Python standard)
- String quotes: Double quotes preferred in most cases, single quotes in some docstrings
- Blank lines: Two lines between top-level functions/classes, one line between methods

**Linting:**
- No linter configuration file present (no `.flake8`, `pyproject.toml`, `pylintrc`)
- Code follows PEP 8 conventions implicitly (snake_case functions, docstring style, etc.)
- No automated enforcement in place

## Import Organization

**Order:**
1. Standard library imports (logging, time, uuid, pathlib, functools, typing, collections, math, shutil)
2. Third-party library imports (httpx, pydantic, langchain*, anthropic, supabase, tiktoken, unstructured, pytest)
3. Local application imports (from src.*)

**Pattern in Code:**
```python
import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import tiktoken
from langchain_community.document_loaders import TextLoader, UnstructuredFileLoader
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import create_client

from src.config import get_settings
```

**Path Aliases:**
- No path aliases configured (no `jsconfig.json`, `tsconfig.json`, or equivalent)
- Imports use relative module paths: `from src.config import get_settings`

## Error Handling

**Patterns:**
- Try/except blocks wrap all external service calls (Ollama, Supabase, Claude API)
- Caught exceptions logged with logger.error() before re-raising
- Custom RuntimeError raised with descriptive context message
- SystemExit raised from config module for startup failures
- Error messages include actionable hints:
  - "Ist Tailscale aktiv?" (Is Tailscale active?)
  - "Supabase-Tabelle muss vector(768) verwenden!" (Supabase table must use vector(768)!)
  - "Pruefen Sie URL und SERVICE_KEY in .env" (Check URL and SERVICE_KEY in .env)

**Example from `src/ingest.py`:**
```python
try:
    embedder = OllamaEmbeddings(...)
    all_embeddings: list[list[float]] = []
    for batch_start in range(0, total, _EMBED_BATCH_SIZE):
        batch_chunks = chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]
        batch_embeddings = embedder.embed_documents(batch_texts)
        all_embeddings.extend(batch_embeddings)
except Exception as exc:
    logger.error("Embedding failed: %s", exc)
    raise RuntimeError(
        f"Ollama-Embedding fehlgeschlagen: {exc}\n"
        "Ist Tailscale aktiv und der VPS erreichbar?"
    ) from exc
```

## Logging

**Framework:** Standard `logging` module (Python stdlib)

**Patterns:**
- Logger initialized per module: `logger = logging.getLogger(__name__)`
- Log levels used consistently:
  - `logger.debug()` for verbose details (e.g., query parameters)
  - `logger.info()` for normal operations (file loading, chunks created, API calls)
  - `logger.warning()` for recoverable issues (connection checks, retries)
  - `logger.error()` for exceptions before raising
- Log messages include context variables: `logger.info("Loading document: %s", path.name)`
- German language in log messages matching the project's German comments/docstrings

**Example:**
```python
logger.info(
    "Created %d embeddings in %.1fs (cost: 0.00 EUR - self-hosted)",
    len(all_embeddings),
    duration,
)
```

## Comments

**When to Comment:**
- Module docstring at top of every file explaining purpose (triple-quoted)
- Inline comments for non-obvious decisions (e.g., "strategy='fast' uses pdfminer for text-based PDFs")
- Comments in German to match codebase language
- No over-commenting obvious code

**Google-Style Docstrings:**
- Present on all public functions and methods
- Sections: Description, Args, Returns, Raises
- Used consistently across all modules:
  - `src/config.py`: Settings class and all public methods documented
  - `src/ingest.py`: load_document(), chunk_document(), embed_and_store(), delete_document()
  - `src/pipeline.py`: answer() and all helper functions
  - `src/retrieval.py`: search(), get_indexed_documents()

**Example from `src/pipeline.py`:**
```python
def answer(question: str, tenant_id: str = "default") -> dict[str, Any]:
    """Answer a question using retrieved document context via Claude.

    Retrieves relevant chunks, builds the RAG prompt, calls
    claude-sonnet-4-6, and returns the answer with sources and cost.

    Args:
        question: Natural language question from the user.
        tenant_id: Tenant identifier to scope the document search.

    Returns:
        Dictionary with keys:
            - answer (str): Generated answer in German.
            - sources (list[str]): Deduplicated source references.
            - cost_eur (float): Estimated cost for this query.

    Raises:
        RuntimeError: If retrieval or LLM call fails.
    """
```

## Function Design

**Size:**
- Kept concise, typically 10-30 lines
- Single responsibility principle: each function does one thing
- Examples: `_build_context()` only formats documents, `_extract_sources()` only deduplicates, `_estimate_cost()` only calculates

**Parameters:**
- Type hints always included: `def answer(question: str, tenant_id: str = "default") -> dict[str, Any]:`
- Default values provided for optional parameters: `tenant_id: str = "default"`
- Callback parameters use union syntax: `callback: Callable[[int, int], None] | None = None`
- Maximum ~3-4 parameters per function; larger configurations use settings object

**Return Values:**
- Always type-hinted
- Return dictionaries with string keys for complex returns: `dict[str, Any]`
- Return empty collections (not None) for "no results": `return []`, `return {}`
- Return tuples for fixed multi-value returns, dicts for variable-key returns

**Example:**
```python
def _build_context(docs: list[Document]) -> str:
    """Format retrieved documents into a context string for the prompt."""
    parts = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        parts.append(f"[{i}] {source} (Seite {page}):\n{doc.page_content}")
    return "\n\n".join(parts)
```

## Module Design

**Exports:**
- No `__all__` defined in any module
- All non-private functions (not prefixed with `_`) are implicitly exported
- Private functions (prefixed with `_`) used internally within module

**Barrel Files:**
- No barrel file pattern (`__init__.py` used only for package initialization)
- `src/__init__.py` exists but is empty
- Each module imported directly: `from src.config import get_settings`

## Special Conventions

**Configuration Management:**
- Pydantic `BaseSettings` pattern in `src/config.py`
- Single `get_settings()` function cached with `@lru_cache(maxsize=1)`
- Settings validated at startup with field_validator decorators
- Returns `Settings` object with all env vars typed and documented

**Tenant Isolation:**
- Multi-tenant support built in but optional
- Default tenant_id = "default" used throughout
- Metadata includes `tenant_id` for scoping searches and deletions

**Cost Tracking:**
- Claude costs estimated and logged after every query
- Costs calculated in EUR (not USD) with exchange rate: `_USD_TO_EUR = 0.92`
- Constants defined for pricing: `_INPUT_COST_PER_1M`, `_OUTPUT_COST_PER_1M`

---

*Convention analysis: 2026-03-12*
