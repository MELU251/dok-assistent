"""Unit-Tests fuer src/retrieval.py.

Testet Similarity-Search, Metadaten-Mapping und Source-Filter-Funktion.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# TestSearch — Basissuche und Metadaten-Mapping
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests fuer die grundlegende Suche und Metadaten-Zuordnung."""

    @patch("src.retrieval.get_settings")
    @patch("src.retrieval._get_supabase_client")
    @patch("src.retrieval._get_embedder")
    def test_returns_documents_with_populated_metadata(self, mock_get_embedder, mock_get_client, mock_get_settings):
        """search() gibt Dokumente mit korrekten Metadaten (source, page) zurueck."""
        from src.retrieval import search

        mock_get_settings.return_value = MagicMock(top_k_results=4)
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 768
        mock_get_embedder.return_value = mock_embedder

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [
            {
                "content": "Testinhalt",
                "source": "test.pdf",
                "page": 1,
                "tenant_id": "default",
            }
        ]
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        docs = search("Testfrage")

        assert len(docs) == 1
        assert isinstance(docs[0], Document)
        assert docs[0].metadata["source"] == "test.pdf"
        assert docs[0].metadata["page"] == 1


# ---------------------------------------------------------------------------
# TestSourceFilter — source_filter Parameter (Wave 0 xfail stubs, CHAT-03)
# ---------------------------------------------------------------------------


class TestSourceFilter:
    """Tests fuer den source_filter-Parameter in retrieval.search()."""

    @patch("src.retrieval.get_settings")
    @patch("src.retrieval._get_supabase_client")
    @patch("src.retrieval._get_embedder")
    def test_source_filter_returns_only_matching_docs(self, mock_get_embedder, mock_get_client, mock_get_settings):
        """search() mit source_filter gibt nur Dokumente der angegebenen Quelle zurueck."""
        from src.retrieval import search

        mock_get_settings.return_value = MagicMock(top_k_results=4)
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 768
        mock_get_embedder.return_value = mock_embedder

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [
            {"content": "Inhalt A", "source": "a.pdf", "page": 1, "tenant_id": "default"},
            {"content": "Inhalt B", "source": "b.pdf", "page": 2, "tenant_id": "default"},
        ]
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        docs = search("Frage", source_filter="a.pdf")

        assert all(doc.metadata["source"] == "a.pdf" for doc in docs)
        assert len(docs) == 1

    @patch("src.retrieval.get_settings")
    @patch("src.retrieval._get_supabase_client")
    @patch("src.retrieval._get_embedder")
    def test_source_filter_requests_triple_match_count(self, mock_get_embedder, mock_get_client, mock_get_settings):
        """search() mit source_filter ruft RPC mit match_count = top_k_results * 3 auf."""
        from src.retrieval import search

        mock_get_settings.return_value = MagicMock(top_k_results=4)
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 768
        mock_get_embedder.return_value = mock_embedder

        mock_client = MagicMock()
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = []
        mock_client.rpc.return_value.execute.return_value = mock_rpc_response
        mock_get_client.return_value = mock_client

        search("Frage", source_filter="a.pdf")

        rpc_call_args = mock_client.rpc.call_args
        rpc_params = rpc_call_args[0][1] if rpc_call_args[0] else rpc_call_args[1]
        match_count = rpc_params.get("match_count")
        # Default top_k_results is 4, so with source_filter it must be 12
        assert match_count == 12
