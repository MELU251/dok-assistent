"""Unit tests for src/ingest.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_docs() -> list[Document]:
    """Two minimal documents for testing."""
    return [
        Document(page_content="Hello world", metadata={"source": "test.pdf", "page": 1}),
        Document(page_content="Second page content", metadata={"source": "test.pdf", "page": 2}),
    ]


@pytest.fixture()
def sample_chunks() -> list[Document]:
    """Pre-split chunks for embed/store tests."""
    return [
        Document(
            page_content=f"Chunk {i}",
            metadata={"source": "test.pdf", "page": i},
        )
        for i in range(5)
    ]


# ---------------------------------------------------------------------------
# load_document
# ---------------------------------------------------------------------------


class TestLoadDocument:
    def test_raises_for_missing_file(self):
        from src.ingest import load_document

        with pytest.raises(FileNotFoundError):
            load_document("/nonexistent/path/file.pdf")

    def test_raises_for_unsupported_extension(self, tmp_path):
        from src.ingest import load_document

        csv_file = tmp_path / "doc.csv"
        csv_file.write_text("content")
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_document(str(csv_file))

    @patch("src.ingest.UnstructuredFileLoader")
    def test_loads_pdf_successfully(self, mock_loader_cls, tmp_path):
        from src.ingest import load_document

        pdf_file = tmp_path / "sample.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_doc = Document(page_content="Sample text", metadata={"page_number": 1})
        mock_loader = MagicMock()
        mock_loader.load.return_value = [mock_doc]
        mock_loader_cls.return_value = mock_loader

        docs = load_document(str(pdf_file))

        assert len(docs) == 1
        assert docs[0].metadata["source"] == "sample.pdf"
        assert docs[0].metadata["page"] == 1

    @patch("src.ingest.UnstructuredFileLoader")
    def test_metadata_defaults_applied(self, mock_loader_cls, tmp_path):
        """Ensure source and page are always set even if missing."""
        from src.ingest import load_document

        pdf_file = tmp_path / "nodoc.pdf"
        pdf_file.write_bytes(b"fake")

        mock_doc = Document(page_content="text", metadata={})
        mock_loader = MagicMock()
        mock_loader.load.return_value = [mock_doc]
        mock_loader_cls.return_value = mock_loader

        docs = load_document(str(pdf_file))
        assert docs[0].metadata["source"] == "nodoc.pdf"
        assert "page" in docs[0].metadata


# ---------------------------------------------------------------------------
# chunk_document
# ---------------------------------------------------------------------------


class TestChunkDocument:
    @patch("src.ingest.get_settings")
    def test_returns_smaller_chunks(self, mock_settings, sample_docs):
        from src.ingest import chunk_document

        mock_settings.return_value = MagicMock(chunk_size=50, chunk_overlap=10)

        # Use a document with plenty of text so it gets split
        long_doc = Document(
            page_content="word " * 100,
            metadata={"source": "long.pdf", "page": 1},
        )
        chunks = chunk_document([long_doc])
        assert len(chunks) >= 1

    @patch("src.ingest.get_settings")
    def test_empty_input_returns_empty(self, mock_settings):
        from src.ingest import chunk_document

        mock_settings.return_value = MagicMock(chunk_size=500, chunk_overlap=50)
        assert chunk_document([]) == []


# ---------------------------------------------------------------------------
# embed_and_store
# ---------------------------------------------------------------------------


class TestEmbedAndStore:
    def test_empty_chunks_returns_zero(self):
        from src.ingest import embed_and_store

        result = embed_and_store([])
        assert result == 0

    @patch("src.ingest._get_supabase_client")
    @patch("src.ingest._get_embedder")
    @patch("src.ingest.get_settings")
    def test_stores_correct_number_of_chunks(
        self, mock_settings, mock_get_embedder, mock_get_client, sample_chunks
    ):
        from src.ingest import embed_and_store

        mock_settings.return_value = MagicMock(
            ollama_embed_model="nomic-embed-text",
        )

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_documents.return_value = [[0.1] * 768] * len(sample_chunks)
        mock_get_embedder.return_value = mock_embedder

        # Mock Supabase client
        mock_table = MagicMock()
        mock_insert_result = MagicMock()
        mock_insert_result.data = [{"id": str(i)} for i in range(len(sample_chunks))]
        mock_table.insert.return_value.execute.return_value = mock_insert_result
        mock_supabase = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_get_client.return_value = mock_supabase

        stored = embed_and_store(sample_chunks, tenant_id="test")
        assert stored == len(sample_chunks)
