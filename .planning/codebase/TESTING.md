# TESTING.md

## Framework

- **pytest** — test runner and assertion library
- **unittest.mock** — `MagicMock`, `patch` for unit test isolation
- No pytest plugins (no pytest-cov, pytest-asyncio, etc.) in requirements

---

## Test Structure

### Two test categories

**Integration tests** (`tests/test_connection.py`)
- Require live external services (Ollama VPS, Supabase, Claude API)
- No mocking — real HTTP connections
- Run separately: `pytest tests/test_connection.py -v -s`
- Print human-readable `[OK]` / `[FAIL]` labels with `-s` flag

**Unit tests** (`tests/test_ingest.py`, `tests/test_pipeline.py`)
- Mock all external dependencies
- Fast, offline, no service dependencies
- Organized into test classes per function under test

### Test file → module mapping
| Test file | Module tested |
|---|---|
| `tests/test_connection.py` | Live: Ollama, Supabase, Claude API |
| `tests/test_ingest.py` | `src/ingest.py` |
| `tests/test_pipeline.py` | `src/pipeline.py` |
| `tests/test_embeddings.py` | `src/ingest.py` + Ollama (integration) |

---

## Test Class Pattern

Tests grouped in classes by function name:

```python
class TestFunctionName:
    def test_specific_behavior(self, fixtures...):
        from src.module import function  # local import inside test
        result = function(args)
        assert result == expected
```

Local imports inside each test method (not at module level) — avoids import-time side effects from `get_settings()`.

---

## Fixtures

Defined at module level with `@pytest.fixture()`:

```python
@pytest.fixture()
def sample_docs() -> list[Document]:
    return [
        Document(page_content="Hello world", metadata={"source": "test.pdf", "page": 1}),
        Document(page_content="Second page", metadata={"source": "test.pdf", "page": 2}),
    ]

@pytest.fixture()
def sample_chunks() -> list[Document]:
    return [Document(page_content=f"Chunk {i}", metadata={"source": "test.pdf", "page": i})
            for i in range(5)]
```

- Fixtures return minimal `Document` objects with required metadata
- `tmp_path` builtin pytest fixture used for temporary file creation

---

## Mocking Strategy

### Patching external dependencies

`@patch` decorator targets the import path in the module under test (not the source module):

```python
@patch("src.ingest.UnstructuredFileLoader")   # patches where it's used
@patch("src.ingest.get_settings")
def test_loads_pdf(self, mock_settings, mock_loader_cls, tmp_path):
    mock_settings.return_value = MagicMock(chunk_size=500, chunk_overlap=50)
    mock_loader = MagicMock()
    mock_loader.load.return_value = [Document(...)]
    mock_loader_cls.return_value = mock_loader
```

### Key mock patterns

**Settings mock:**
```python
mock_settings.return_value = MagicMock(
    chunk_size=500,
    chunk_overlap=50,
    ollama_embed_model="nomic-embed-text",
    ...
)
```

**Supabase mock:**
```python
mock_table = MagicMock()
mock_insert_result = MagicMock()
mock_insert_result.data = [{"id": str(i)} for i in range(n)]
mock_table.insert.return_value.execute.return_value = mock_insert_result
mock_supabase = MagicMock()
mock_supabase.table.return_value = mock_table
mock_create_client.return_value = mock_supabase
```

**Anthropic mock:**
```python
mock_content = MagicMock()
mock_content.text = "Answer text"
mock_response = MagicMock()
mock_response.content = [mock_content]
mock_response.usage.input_tokens = 200
mock_response.usage.output_tokens = 80
mock_client.messages.create.return_value = mock_response
```

---

## Known Test Issues

**`test_ingest.py` uses `OpenAIEmbeddings` (stale):**
```python
@patch("src.ingest.OpenAIEmbeddings")   # WRONG — module uses OllamaEmbeddings
```
This test (`TestEmbedAndStore.test_stores_correct_number_of_chunks`) will fail because `src.ingest` imports `OllamaEmbeddings`, not `OpenAIEmbeddings`. The patch target is incorrect and the mock settings reference `openai_api_key` which doesn't exist in `Settings`.

Also expects `vector(1536)` embeddings but production uses `vector(768)` for nomic-embed-text.

---

## Running Tests

```bash
# All unit tests (no external services needed)
pytest tests/test_ingest.py tests/test_pipeline.py -v

# Live connectivity checks (requires Tailscale + real credentials)
pytest tests/test_connection.py -v -s

# All tests
pytest -v

# Specific test class
pytest tests/test_pipeline.py::TestAnswer -v
```

---

## Coverage Gaps

- No tests for `src/retrieval.py` (`search`, `get_indexed_documents`)
- No tests for `src/config.py` validators
- No tests for `app.py` UI flows (no async test setup)
- No tests for `ingest_cli.py`
- No tests for `delete_document()`
- No concurrent upload tests
- No malformed file tests (corrupted PDF, empty XLSX)
- No tenant isolation tests
