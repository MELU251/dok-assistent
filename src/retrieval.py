"""Aehnlichkeitssuche und Dokumentverwaltung in Supabase pgvector."""

import logging
from functools import lru_cache

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from supabase import create_client

from src.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_embedder() -> OllamaEmbeddings:
    """OllamaEmbeddings-Singleton – wird einmal erstellt und wiederverwendet."""
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


@lru_cache(maxsize=1)
def _get_supabase_client():
    """Supabase-Client-Singleton – wird einmal erstellt und wiederverwendet."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def search(query: str, tenant_id: str = "default") -> list[Document]:
    """Die relevantesten Dokument-Chunks fuer eine Anfrage abrufen.

    Bettet die Anfrage via Ollama ein und ruft die match_document_chunks-RPC-Funktion
    in Supabase direkt auf (umgeht langchain_community SupabaseVectorStore,
    das mit supabase-py 2.x inkompatibel ist).

    Args:
        query: Natuerlichsprachliche Frage oder Suchbegriff.
        tenant_id: Mandanten-ID zur Eingrenzung der Suche.

    Returns:
        Liste von bis zu TOP_K_RESULTS Document-Objekten mit Metadaten.

    Raises:
        RuntimeError: Wenn Embedding oder Vektorsuche fehlschlagen.
    """
    settings = get_settings()
    logger.debug("Searching (tenant=%s): %s", tenant_id, query[:80])

    # Schritt 1: Query einbetten
    try:
        embedder = _get_embedder()
        query_vector = embedder.embed_query(query)
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        raise RuntimeError(f"Embedding fehlgeschlagen: {exc}") from exc

    # Schritt 2: RPC-Funktion direkt aufrufen
    try:
        client = _get_supabase_client()
        response = client.rpc(
            "match_document_chunks",
            {
                "query_embedding": query_vector,
                "match_count": settings.top_k_results,
                "filter": {"tenant_id": tenant_id},
            },
        ).execute()
    except Exception as exc:
        logger.error("Supabase RPC failed: %s", exc)
        raise RuntimeError(f"Suche fehlgeschlagen: {exc}") from exc

    # Schritt 3: Zeilen in LangChain-Documents umwandeln
    docs = [
        Document(
            page_content=row["content"],
            metadata=row.get("metadata", {}),
        )
        for row in (response.data or [])
    ]

    logger.info("Retrieved %d chunks (tenant=%s)", len(docs), tenant_id)
    return docs


def get_indexed_documents(tenant_id: str = "default") -> list[str]:
    """Liste aller indexierten Dokument-Dateinamen abrufen.

    Gibt jeden Dateinamen nur einmal zurueck, sortiert alphabetisch.

    Args:
        tenant_id: Mandanten-ID zur Filterung.

    Returns:
        Sortierte Liste eindeutiger Dateinamen, z. B. ["handbuch.pdf", "wartung.docx"].
        Leere Liste bei Fehler oder wenn keine Dokumente vorhanden.
    """
    try:
        client = _get_supabase_client()
        result = (
            client.table("document_chunks")
            .select("source")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        sources = sorted({row["source"] for row in (result.data or [])})
        return sources
    except Exception as exc:
        logger.warning("Indexed documents could not be retrieved: %s", exc)
        return []
