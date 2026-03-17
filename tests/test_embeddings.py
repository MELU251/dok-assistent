"""Integration test: chunk a sample document and create real OpenAI embeddings.

Run with:
    pytest tests/test_embeddings.py -v -s

Requires a valid OPENAI_API_KEY in your .env file.
No Supabase connection needed.
"""

import logging

import pytest
import tiktoken
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sample document with German Umlauts to verify encoding handling
# ---------------------------------------------------------------------------

SAMPLE_TEXT = """
Geschäftsbericht 2024 – Zusammenfassung

Die Müller GmbH hat im Geschäftsjahr 2024 einen Umsatz von 4,2 Millionen Euro
erzielt, was einer Steigerung von 12 % gegenüber dem Vorjahr entspricht.

Haupttreiber des Wachstums waren:
- Die Einführung neuer Produkte im Bereich Büroausstattung
- Die Erschließung neuer Märkte in Österreich und der Schweiz
- Effizientere Prozesse durch die Digitalisierungsinitiative „Zukunft 4.0"

Personalentwicklung:
Zum 31. Dezember 2024 beschäftigte das Unternehmen 87 Mitarbeiterinnen und
Mitarbeiter (Vorjahr: 74). Die Fluktuationsrate lag bei erfreulichen 3,2 %.

Ausblick 2025:
Für das kommende Geschäftsjahr erwartet die Geschäftsführung ein weiteres
Wachstum von 8–10 %. Geplante Investitionen umfassen den Ausbau des Lagers
in München sowie die Modernisierung der IT-Infrastruktur.

Risiken:
Die unsichere makroökonomische Lage sowie steigende Energiekosten stellen
weiterhin Herausforderungen dar. Das Unternehmen begegnet diesen Risiken
durch diversifizierte Lieferketten und langfristige Energielieferverträge.
""".strip()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _count_tokens(text: str) -> int:
    """Count tokens using cl100k_base (same as text-embedding-3-small)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _estimate_cost_eur(token_count: int) -> float:
    """Estimate embedding cost in EUR ($0.00002/1K tokens, rate 0.92)."""
    return (token_count / 1000) * 0.00002 * 0.92


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEmbeddingIntegration:
    """Live integration tests – require OPENAI_API_KEY in .env."""

    def test_chunking_and_embedding(self):
        """Full flow: chunk sample text → embed → verify dimensions and log cost."""
        from src.config import get_settings
        from src.ingest import chunk_document

        settings = get_settings()

        # Wrap sample text as a Document
        doc = Document(
            page_content=SAMPLE_TEXT,
            metadata={"source": "test_sample.txt", "page": 1},
        )

        # --- Step 1: Chunk ---
        chunks = chunk_document([doc])
        assert len(chunks) >= 1, "Expected at least one chunk"

        token_counts = [_count_tokens(c.page_content) for c in chunks]
        print(f"\n{'='*55}")
        print(f"  Chunks created : {len(chunks)}")
        for i, (chunk, tokens) in enumerate(zip(chunks, token_counts), 1):
            print(f"  Chunk {i:02d}: {tokens:4d} tokens | {len(chunk.page_content):5d} chars")
        print(f"  Total tokens   : {sum(token_counts)}")

        # All chunks must respect the configured size limit
        for tokens in token_counts:
            assert tokens <= settings.chunk_size, (
                f"Chunk exceeds configured size ({tokens} > {settings.chunk_size})"
            )

        # --- Step 2: Embed ---
        from langchain_openai import OpenAIEmbeddings

        embedder = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key,
        )
        texts = [c.page_content for c in chunks]
        vectors = embedder.embed_documents(texts)

        # --- Step 3: Verify dimensions ---
        expected_dim = 1536
        assert len(vectors) == len(chunks), "One vector per chunk expected"
        for i, vec in enumerate(vectors):
            assert len(vec) == expected_dim, (
                f"Chunk {i+1}: expected {expected_dim} dimensions, got {len(vec)}"
            )

        # --- Step 4: Report costs ---
        total_tokens = sum(token_counts)
        cost_eur = _estimate_cost_eur(total_tokens)
        print(f"\n  Embedding dimensions : {expected_dim}")
        print(f"  Estimated cost       : ~{cost_eur * 100:.4f} Cent")
        print(f"{'='*55}\n")

        assert cost_eur < 0.0001, "Sanity check: sample doc should cost < 0.01 Cent"

    def test_german_umlauts_survive_chunking(self):
        """Verify that Umlauts (ä ö ü ß) are preserved through chunking."""
        from src.ingest import chunk_document

        umlaut_text = "Äpfel, Öl, Überraschung, Müsli, Straße, weiß, grüßen."
        doc = Document(
            page_content=umlaut_text,
            metadata={"source": "umlaut_test.txt", "page": 1},
        )
        chunks = chunk_document([doc])
        combined = " ".join(c.page_content for c in chunks)

        for char in ["Ä", "Ö", "Ü", "ä", "ö", "ü", "ß"]:
            assert char in combined, f"Umlaut '{char}' lost during chunking"

    def test_embedding_vector_is_normalized(self):
        """text-embedding-3-small vectors should be approximately unit length."""
        import math

        from src.config import get_settings
        from langchain_openai import OpenAIEmbeddings

        settings = get_settings()
        embedder = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key,
        )
        vectors = embedder.embed_documents(["Testtext für Normalisierung"])
        vec = vectors[0]
        magnitude = math.sqrt(sum(x * x for x in vec))
        assert abs(magnitude - 1.0) < 0.01, (
            f"Expected unit vector (magnitude≈1.0), got {magnitude:.4f}"
        )
