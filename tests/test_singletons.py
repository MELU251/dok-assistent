"""Unit tests fuer Singleton-Getter in src/ingest.py und src/retrieval.py (TECH-02, TECH-03)."""

from unittest.mock import MagicMock, patch

import pytest


class TestEmbedderSingleton:
    """_get_embedder() muss dieselbe Instanz bei wiederholten Aufrufen zurueckgeben."""

    def teardown_method(self):
        from src.ingest import _get_embedder
        _get_embedder.cache_clear()

    @patch("src.ingest.get_settings")
    def test_returns_same_instance(self, mock_settings):
        mock_settings.return_value = MagicMock(
            ollama_embed_model="nomic-embed-text",
            ollama_base_url="http://100.0.0.1:11434",
        )
        with patch("src.ingest.OllamaEmbeddings") as mock_cls:
            mock_cls.return_value = MagicMock()
            from src.ingest import _get_embedder
            inst1 = _get_embedder()
            inst2 = _get_embedder()
            assert inst1 is inst2
            assert mock_cls.call_count == 1


class TestSupabaseSingletonIngest:
    """_get_supabase_client() in ingest.py muss dieselbe Instanz zurueckgeben."""

    def teardown_method(self):
        from src.ingest import _get_supabase_client
        _get_supabase_client.cache_clear()

    @patch("src.ingest.get_settings")
    def test_returns_same_instance(self, mock_settings):
        mock_settings.return_value = MagicMock(
            supabase_url="https://x.supabase.co",
            supabase_service_key="key",
        )
        with patch("src.ingest.create_client") as mock_cc:
            mock_cc.return_value = MagicMock()
            from src.ingest import _get_supabase_client
            inst1 = _get_supabase_client()
            inst2 = _get_supabase_client()
            assert inst1 is inst2
            assert mock_cc.call_count == 1


class TestSupabaseSingletonRetrieval:
    """_get_supabase_client() in retrieval.py muss dieselbe Instanz zurueckgeben."""

    def teardown_method(self):
        from src.retrieval import _get_supabase_client
        _get_supabase_client.cache_clear()

    @patch("src.retrieval.get_settings")
    def test_returns_same_instance(self, mock_settings):
        mock_settings.return_value = MagicMock(
            supabase_url="https://x.supabase.co",
            supabase_service_key="key",
        )
        with patch("src.retrieval.create_client") as mock_cc:
            mock_cc.return_value = MagicMock()
            from src.retrieval import _get_supabase_client
            inst1 = _get_supabase_client()
            inst2 = _get_supabase_client()
            assert inst1 is inst2
            assert mock_cc.call_count == 1
