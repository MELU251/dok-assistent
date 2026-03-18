"""Unit tests fuer src/workflow.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from src.extractor import AngebotData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_angebot_data() -> AngebotData:
    return AngebotData(
        title="Kompressor-Projekt",
        summary="Beschaffung eines Industriekompressors.",
        requirements=["10 bar Druck", "ISO 9001"],
        special_requests=[],
    )


@pytest.fixture()
def sample_retrieved() -> list[Document]:
    return [
        Document(page_content="Preis: 15.000 EUR", metadata={"source": "angebot_2023.pdf", "page": 1}),
        Document(page_content="Lieferumfang: Kompressor", metadata={"source": "angebot_2022.pdf", "page": 2}),
        Document(page_content="Offene Punkte: Besichtigung", metadata={"source": "angebot_2021.pdf", "page": 1}),
    ]


_GENERATOR_RESULT = {
    "zusammenfassung": "Angebotszusammenfassung.",
    "technische_loesung": "Technische Details.",
    "lieferumfang": ["Kompressor", "Steuereinheit"],
    "offene_punkte": ["Besichtigung erforderlich"],
    "sources": ["angebot_2023.pdf", "angebot_2022.pdf", "angebot_2021.pdf"],
    "hil_hinweis": "KI-generierter Entwurf",
    "cost_eur": 0.005,
}


# ---------------------------------------------------------------------------
# create_angebotsentwurf
# ---------------------------------------------------------------------------

class TestCreateAngebotsentwurf:
    def test_returns_tuple_of_three(self, tmp_path):
        from src.workflow import create_angebotsentwurf

        with patch("src.workflow.load_document", return_value=[MagicMock()]), \
             patch("src.workflow.chunk_document", return_value=[MagicMock()]), \
             patch("src.workflow.extract_requirements", return_value=MagicMock(
                 title="T", summary="S", requirements=["R1"], special_requests=[]
             )), \
             patch("src.workflow.search", return_value=[MagicMock()]), \
             patch("src.workflow.generate_angebot", return_value=_GENERATOR_RESULT), \
             patch("src.workflow.write_docx", return_value=tmp_path / "out.docx"):
            result = create_angebotsentwurf("fake.pdf")

        assert len(result) == 3

    def test_returns_docx_path(self, tmp_path):
        from src.workflow import create_angebotsentwurf

        expected_path = tmp_path / "Angebotsentwurf_fake.docx"
        with patch("src.workflow.load_document", return_value=[MagicMock()]), \
             patch("src.workflow.chunk_document", return_value=[MagicMock()]), \
             patch("src.workflow.extract_requirements", return_value=MagicMock(
                 title="T", summary="S", requirements=["R1"], special_requests=[]
             )), \
             patch("src.workflow.search", return_value=[]), \
             patch("src.workflow.generate_angebot", return_value=_GENERATOR_RESULT), \
             patch("src.workflow.write_docx", return_value=expected_path) as mock_write:
            docx_path, _, _ = create_angebotsentwurf("fake.pdf")

        assert docx_path == expected_path

    def test_returns_angebot_data(self, tmp_path):
        from src.workflow import create_angebotsentwurf

        mock_data = AngebotData(
            title="Test-Projekt",
            summary="Test-Zusammenfassung.",
            requirements=["Anforderung 1"],
            special_requests=[],
        )
        with patch("src.workflow.load_document", return_value=[MagicMock()]), \
             patch("src.workflow.chunk_document", return_value=[MagicMock()]), \
             patch("src.workflow.extract_requirements", return_value=mock_data), \
             patch("src.workflow.search", return_value=[]), \
             patch("src.workflow.generate_angebot", return_value=_GENERATOR_RESULT), \
             patch("src.workflow.write_docx", return_value=tmp_path / "out.docx"):
            _, angebot_data, _ = create_angebotsentwurf("fake.pdf")

        assert angebot_data.title == "Test-Projekt"

    def test_output_filename_contains_source_stem(self, tmp_path):
        from src.workflow import create_angebotsentwurf

        with patch("src.workflow.load_document", return_value=[MagicMock()]), \
             patch("src.workflow.chunk_document", return_value=[MagicMock()]), \
             patch("src.workflow.extract_requirements", return_value=MagicMock(
                 title="T", summary="S", requirements=["R"], special_requests=[]
             )), \
             patch("src.workflow.search", return_value=[]), \
             patch("src.workflow.generate_angebot", return_value=_GENERATOR_RESULT), \
             patch("src.workflow.write_docx", return_value=tmp_path / "out.docx") as mock_write:
            create_angebotsentwurf("mein_lastenheft.pdf")

        # write_docx wurde mit einem Pfad aufgerufen der den Stem enthaelt
        call_args = mock_write.call_args
        output_path: Path = call_args[0][2]  # 3. positionales Argument
        assert "mein_lastenheft" in str(output_path)

    def test_rag_search_uses_summary(self, tmp_path):
        from src.workflow import create_angebotsentwurf

        mock_data = MagicMock()
        mock_data.summary = "Industriekompressor Beschaffung"
        mock_data.requirements = ["R1"]
        mock_data.special_requests = []

        with patch("src.workflow.load_document", return_value=[MagicMock()]), \
             patch("src.workflow.chunk_document", return_value=[MagicMock()]), \
             patch("src.workflow.extract_requirements", return_value=mock_data), \
             patch("src.workflow.search") as mock_search, \
             patch("src.workflow.generate_angebot", return_value=_GENERATOR_RESULT), \
             patch("src.workflow.write_docx", return_value=tmp_path / "out.docx"):
            mock_search.return_value = []
            create_angebotsentwurf("fake.pdf")

        mock_search.assert_called_once()
        assert mock_search.call_args[0][0] == "Industriekompressor Beschaffung"
