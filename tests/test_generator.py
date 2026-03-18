"""Unit tests fuer src/generator.py."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from src.extractor import AngebotData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_data() -> AngebotData:
    return AngebotData(
        title="Kompressor-Anlage Typ A",
        summary="Beschaffung eines Industriekompressors fuer die Produktion.",
        requirements=["10 bar Betriebsdruck", "ISO 9001 Zertifizierung"],
        special_requests=["Wartungsvertrag gewuenscht"],
    )


@pytest.fixture()
def sample_chunks() -> list[Document]:
    return [
        Document(
            page_content="Angebot fuer Kompressor 12 bar: Preis 15.000 EUR.",
            metadata={"source": "angebot_2023.pdf", "page": 1},
        ),
        Document(
            page_content="Lieferumfang: Kompressor, Steuereinheit, Wartungskit.",
            metadata={"source": "angebot_2022.pdf", "page": 3},
        ),
        Document(
            page_content="Offener Punkt: Installationsort muss besichtigt werden.",
            metadata={"source": "angebot_2021.pdf", "page": 2},
        ),
    ]


_VALID_RESPONSE = {
    "zusammenfassung": "Angebot fuer einen Industriekompressor gemaess Lastenheft.",
    "technische_loesung": "Schraubenkompressor 12 bar, drehzahlgeregelt.",
    "lieferumfang": ["Kompressor-Einheit", "Steuereinheit", "Wartungskit"],
    "offene_punkte": ["Installationsort benoetigt Besichtigung"],
}


def _make_mock_response(data: dict) -> MagicMock:
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(data))]
    response.usage.input_tokens = 500
    response.usage.output_tokens = 300
    return response


# ---------------------------------------------------------------------------
# generate_angebot
# ---------------------------------------------------------------------------

class TestGenerateAngebot:
    def test_returns_dict_with_required_keys(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, sample_chunks)

        for key in ("zusammenfassung", "technische_loesung", "lieferumfang", "offene_punkte"):
            assert key in result

    def test_zusammenfassung_is_string(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, sample_chunks)

        assert isinstance(result["zusammenfassung"], str)
        assert len(result["zusammenfassung"]) > 0

    def test_lieferumfang_is_list(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, sample_chunks)

        assert isinstance(result["lieferumfang"], list)

    def test_offene_punkte_is_list(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, sample_chunks)

        assert isinstance(result["offene_punkte"], list)

    def test_sources_contains_chunk_filenames(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, sample_chunks)

        assert "angebot_2023.pdf" in result["sources"]
        assert "angebot_2022.pdf" in result["sources"]
        assert "angebot_2021.pdf" in result["sources"]

    def test_sources_deduplicated(self, sample_data):
        from src.generator import generate_angebot

        # Zwei Chunks aus derselben Quelle
        chunks = [
            Document(page_content="A", metadata={"source": "angebot.pdf", "page": 1}),
            Document(page_content="B", metadata={"source": "angebot.pdf", "page": 2}),
        ]
        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, chunks)

        assert result["sources"].count("angebot.pdf") == 1

    def test_hil_hinweis_present(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, sample_chunks)

        assert "hil_hinweis" in result
        assert "KI-generierter Entwurf" in result["hil_hinweis"]

    def test_cost_eur_returned(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, sample_chunks)

        assert "cost_eur" in result
        assert result["cost_eur"] > 0

    def test_empty_chunks_handled_gracefully(self, sample_data):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = generate_angebot(sample_data, [])

        # Kein Fehler; sources-Liste ist leer
        assert result["sources"] == []

    def test_invalid_json_raises_value_error(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        bad_resp = MagicMock()
        bad_resp.content = [MagicMock(text="Kein JSON hier.")]
        bad_resp.usage.input_tokens = 100
        bad_resp.usage.output_tokens = 20
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = bad_resp
            with pytest.raises(ValueError, match="JSON"):
                generate_angebot(sample_data, sample_chunks)

    def test_missing_key_raises_value_error(self, sample_data, sample_chunks):
        from src.generator import generate_angebot

        incomplete = {k: v for k, v in _VALID_RESPONSE.items() if k != "lieferumfang"}
        mock_resp = _make_mock_response(incomplete)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            with pytest.raises(ValueError, match="lieferumfang"):
                generate_angebot(sample_data, sample_chunks)

    def test_logs_token_cost(self, sample_data, sample_chunks, caplog):
        from src.generator import generate_angebot

        mock_resp = _make_mock_response(_VALID_RESPONSE)
        with patch("src.generator.Anthropic") as mock_cls, \
             patch("src.generator.get_settings", return_value=MagicMock(anthropic_api_key="test")):
            mock_cls.return_value.messages.create.return_value = mock_resp
            with caplog.at_level(logging.INFO, logger="src.generator"):
                generate_angebot(sample_data, sample_chunks)

        assert any("cost" in r.message.lower() for r in caplog.records)
