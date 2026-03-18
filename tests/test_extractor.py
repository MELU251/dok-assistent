"""Unit tests fuer src/extractor.py."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_chunks() -> list[Document]:
    return [
        Document(
            page_content="Der Kompressor muss 10 bar Betriebsdruck liefern.",
            metadata={"source": "lastenheft.pdf", "page": 1},
        ),
        Document(
            page_content="Das Geraet soll ISO 9001 zertifiziert sein.",
            metadata={"source": "lastenheft.pdf", "page": 2},
        ),
    ]


def _make_mock_response(data: dict) -> MagicMock:
    """Erstellt ein Mock-Anthropic-Response-Objekt mit JSON-Inhalt."""
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(data))]
    response.usage.input_tokens = 200
    response.usage.output_tokens = 100
    return response


_VALID_DATA = {
    "title": "Kompressor-Anlage Typ A",
    "summary": "Beschaffung eines Industriekompressors fuer die Produktion.",
    "requirements": ["10 bar Betriebsdruck", "ISO 9001 Zertifizierung"],
    "special_requests": ["Wartungsvertrag gewuenscht"],
}


# ---------------------------------------------------------------------------
# extract_requirements
# ---------------------------------------------------------------------------

class TestExtractRequirements:
    def test_returns_angebot_data(self, sample_chunks):
        from src.extractor import extract_requirements, AngebotData

        mock_resp = _make_mock_response(_VALID_DATA)
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = extract_requirements(sample_chunks)

        assert isinstance(result, AngebotData)

    def test_title_and_summary_populated(self, sample_chunks):
        from src.extractor import extract_requirements

        mock_resp = _make_mock_response(_VALID_DATA)
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = extract_requirements(sample_chunks)

        assert result.title == "Kompressor-Anlage Typ A"
        assert "Industriekompressor" in result.summary

    def test_requirements_is_list(self, sample_chunks):
        from src.extractor import extract_requirements

        mock_resp = _make_mock_response(_VALID_DATA)
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = extract_requirements(sample_chunks)

        assert isinstance(result.requirements, list)
        assert len(result.requirements) == 2

    def test_special_requests_is_list(self, sample_chunks):
        from src.extractor import extract_requirements

        mock_resp = _make_mock_response(_VALID_DATA)
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = extract_requirements(sample_chunks)

        assert isinstance(result.special_requests, list)

    def test_empty_special_requests_allowed(self, sample_chunks):
        from src.extractor import extract_requirements

        data_no_specials = {**_VALID_DATA, "special_requests": []}
        mock_resp = _make_mock_response(data_no_specials)
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = extract_requirements(sample_chunks)

        assert result.special_requests == []

    def test_empty_chunks_raises_value_error(self):
        from src.extractor import extract_requirements

        with pytest.raises(ValueError, match="leer"):
            extract_requirements([])

    def test_invalid_json_raises_value_error(self, sample_chunks):
        from src.extractor import extract_requirements

        bad_resp = MagicMock()
        bad_resp.content = [MagicMock(text="Ich habe leider kein JSON.")]
        bad_resp.usage.input_tokens = 50
        bad_resp.usage.output_tokens = 10
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = bad_resp
            with pytest.raises(ValueError, match="JSON"):
                extract_requirements(sample_chunks)

    def test_logs_token_cost(self, sample_chunks, caplog):
        from src.extractor import extract_requirements

        mock_resp = _make_mock_response(_VALID_DATA)
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            with caplog.at_level(logging.INFO, logger="src.extractor"):
                extract_requirements(sample_chunks)

        assert any("cost" in record.message.lower() for record in caplog.records)

    def test_markdown_code_block_stripped(self, sample_chunks):
        from src.extractor import extract_requirements

        # Claude gibt manchmal ```json ... ``` zurueck trotz Anweisung
        wrapped = "```json\n" + json.dumps(_VALID_DATA) + "\n```"
        bad_resp = MagicMock()
        bad_resp.content = [MagicMock(text=wrapped)]
        bad_resp.usage.input_tokens = 200
        bad_resp.usage.output_tokens = 100
        with patch("src.extractor.Anthropic") as mock_cls, \
             patch("src.extractor.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = bad_resp
            result = extract_requirements(sample_chunks)

        assert result.title == "Kompressor-Anlage Typ A"
