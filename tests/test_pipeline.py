"""Unit tests for src/pipeline.py."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_docs() -> list[Document]:
    return [
        Document(
            page_content="Das Budget für 2024 beträgt 100.000 Euro.",
            metadata={"source": "budget.pdf", "page": 3},
        ),
        Document(
            page_content="Die Personalkosten stiegen um 5%.",
            metadata={"source": "budget.pdf", "page": 5},
        ),
    ]


# ---------------------------------------------------------------------------
# _build_context
# ---------------------------------------------------------------------------


class TestBuildContext:
    def test_includes_source_and_page(self, mock_docs):
        from src.pipeline import _build_context

        context = _build_context(mock_docs)
        assert "budget.pdf" in context
        assert "Seite 3" in context
        assert "100.000 Euro" in context

    def test_empty_docs_returns_empty_string(self):
        from src.pipeline import _build_context

        assert _build_context([]) == ""


# ---------------------------------------------------------------------------
# _extract_sources
# ---------------------------------------------------------------------------


class TestExtractSources:
    def test_deduplicates_same_source_page(self):
        from src.pipeline import _extract_sources

        docs = [
            Document(page_content="a", metadata={"source": "file.pdf", "page": 1}),
            Document(page_content="b", metadata={"source": "file.pdf", "page": 1}),
        ]
        sources = _extract_sources(docs)
        assert len(sources) == 1

    def test_preserves_distinct_sources(self, mock_docs):
        from src.pipeline import _extract_sources

        sources = _extract_sources(mock_docs)
        assert len(sources) == 2


# ---------------------------------------------------------------------------
# answer
# ---------------------------------------------------------------------------


class TestAnswer:
    @patch("src.pipeline.get_settings")
    @patch("src.pipeline.search")
    def test_returns_no_document_message_when_no_results(self, mock_search, mock_get_settings):
        from src.pipeline import answer

        mock_search.return_value = []
        result = answer("Was ist das Budget?")

        assert "nicht enthalten" in result["answer"]
        assert result["sources"] == []
        assert result["cost_eur"] == 0.0

    @patch("src.pipeline.Anthropic")
    @patch("src.pipeline.search")
    @patch("src.pipeline.get_settings")
    def test_returns_answer_with_sources(
        self, mock_settings, mock_search, mock_anthropic_cls, mock_docs
    ):
        from src.pipeline import answer

        mock_settings.return_value = MagicMock(anthropic_api_key="sk-ant-test")
        mock_search.return_value = mock_docs

        # Mock Anthropic response
        mock_content = MagicMock()
        mock_content.text = "Das Budget beträgt 100.000 Euro. 📄 Quelle: budget.pdf, Seite 3"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 80

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        result = answer("Was ist das Budget?")

        assert "answer" in result
        assert len(result["sources"]) == 2
        assert result["cost_eur"] > 0

    @patch("src.pipeline.Anthropic")
    @patch("src.pipeline.search")
    @patch("src.pipeline.get_settings")
    def test_raises_runtime_error_on_api_failure(
        self, mock_settings, mock_search, mock_anthropic_cls, mock_docs
    ):
        from src.pipeline import answer

        mock_settings.return_value = MagicMock(anthropic_api_key="sk-ant-test")
        mock_search.return_value = mock_docs

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API timeout")
        mock_anthropic_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="LLM call failed"):
            answer("Was kostet das?")
