"""Aehnlichkeitssuche und Dokumentverwaltung in Supabase pgvector."""

import logging

from langchain_core.documents import Document

from src.clients import _get_embedder, _get_supabase_client
from src.config import get_settings

logger = logging.getLogger(__name__)


def search(
    query: str,
    tenant_id: str = "default",
    source_filter: str | None = None,
) -> list[Document]:
    """Die relevantesten Dokument-Chunks fuer eine Anfrage abrufen.

    Bettet die Anfrage via Ollama ein und ruft die match_document_chunks-RPC-Funktion
    in Supabase direkt auf (umgeht langchain_community SupabaseVectorStore,
    das mit supabase-py 2.x inkompatibel ist).

    Args:
        query: Natuerlichsprachliche Frage oder Suchbegriff.
        tenant_id: Mandanten-ID zur Eingrenzung der Suche.
        source_filter: Optionaler Dateiname zur Eingrenzung der Suche auf ein Dokument.
                       Wird als Post-Filter nach dem RPC-Aufruf angewendet.

    Returns:
        Liste von bis zu TOP_K_RESULTS Document-Objekten mit Metadaten.

    Raises:
        RuntimeError: Wenn Embedding oder Vektorsuche fehlschlagen.
    """
    settings = get_settings()
    logger.debug("Searching (tenant=%s, source_filter=%s): %s", tenant_id, source_filter, query[:80])

    # Schritt 1: Query einbetten
    try:
        embedder = _get_embedder()
        query_vector = embedder.embed_query(query)
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        raise RuntimeError(f"Embedding fehlgeschlagen: {exc}") from exc

    # Schritt 2: RPC-Funktion direkt aufrufen
    # Bei source_filter mehr Kandidaten anfordern, da Post-Filterung Treffer reduziert
    match_count = settings.top_k_results * 3 if source_filter else settings.top_k_results
    try:
        client = _get_supabase_client()
        response = client.rpc(
            "match_document_chunks",
            {
                "query_embedding": query_vector,
                "match_count": match_count,
                "filter": {"tenant_id": tenant_id},
            },
        ).execute()
    except Exception as exc:
        logger.error("Supabase RPC failed: %s", exc)
        raise RuntimeError(f"Suche fehlgeschlagen: {exc}") from exc

    # Schritt 3: Zeilen in LangChain-Documents umwandeln
    # Die RPC-Funktion gibt Metadaten als JSONB-Objekt zurueck; Top-Level-Spalten als Fallback
    docs = [
        Document(
            page_content=row["content"],
            metadata={
                "source": (row.get("metadata") or {}).get("source")
                          or row.get("source", "unknown"),
                "page": (row.get("metadata") or {}).get("page")
                        or row.get("page", 0),
                "tenant_id": (row.get("metadata") or {}).get("tenant_id")
                             or row.get("tenant_id", "default"),
            },
        )
        for row in (response.data or [])
    ]

    # Schritt 4: Post-Filter nach Quelle und Ergebnis auf top_k_results begrenzen
    if source_filter:
        docs = [d for d in docs if d.metadata.get("source") == source_filter]
        docs = docs[: settings.top_k_results]

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
