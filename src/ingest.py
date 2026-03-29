"""Dokument-Ingestion: laden, chunken, einbetten und in Supabase pgvector speichern."""

import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import tiktoken
from langchain_community.document_loaders import TextLoader, UnstructuredFileLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.clients import _get_embedder, _get_supabase_client
from src.config import get_settings

logger = logging.getLogger(__name__)

# Anzahl Chunks pro Embedding-Batch – Balance zwischen Geschwindigkeit und Fortschrittsgranularität
_EMBED_BATCH_SIZE = 10


def load_document(file_path: str) -> list[Document]:
    """Dokument von der Festplatte laden.

    Unterstuetzt .pdf, .docx, .xlsx und .txt via UnstructuredFileLoader bzw. TextLoader.

    Args:
        file_path: Absoluter oder relativer Pfad zum Dokument.

    Returns:
        Liste von LangChain-Document-Objekten, eines pro Seite/Element.

    Raises:
        ValueError: Wenn die Dateiendung nicht unterstuetzt wird.
        FileNotFoundError: Wenn die Datei nicht existiert.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    supported = {".pdf", ".docx", ".xlsx", ".txt"}
    if path.suffix.lower() not in supported:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. Supported: {supported}"
        )

    logger.info("Loading document: %s", path.name)
    try:
        if path.suffix.lower() == ".txt":
            # Einfacher TextLoader fuer Plaintext – kein Unstructured noetig
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            # strategy="fast" nutzt pdfminer fuer textbasierte PDFs (korrekte Umlaut-Behandlung).
            # Fuer gescannte PDFs: strategy="hi_res" + Tesseract OCR.
            loader = UnstructuredFileLoader(
                str(path),
                mode="elements",
                strategy="fast",
                encoding="utf-8",
            )
        docs = loader.load()
    except Exception as exc:
        logger.error("Failed to load '%s': %s", file_path, exc)
        raise

    # Metadaten normalisieren: source und page immer setzen
    for doc in docs:
        doc.metadata.setdefault("source", path.name)
        doc.metadata.setdefault("page", doc.metadata.get("page_number", 0))

    logger.info("Loaded %d elements from '%s'", len(docs), path.name)
    return docs


def chunk_document(docs: list[Document]) -> list[Document]:
    """Dokumente in ueberlappende Chunks aufteilen.

    Nutzt tiktoken (cl100k_base) als Token-Zaehl-Naeherung fuer nomic-embed-text.

    Args:
        docs: Liste von Document-Objekten.

    Returns:
        Liste kleinerer Document-Chunks mit erhaltenen Metadaten.
    """
    settings = get_settings()

    _tokenizer = tiktoken.get_encoding("cl100k_base")

    def _token_len(text: str) -> int:
        return len(_tokenizer.encode(text))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=_token_len,
    )
    chunks = splitter.split_documents(docs)
    logger.info(
        "Split %d docs into %d chunks (size=%d, overlap=%d)",
        len(docs),
        len(chunks),
        settings.chunk_size,
        settings.chunk_overlap,
    )
    return chunks


def embed_and_store(
    chunks: list[Document],
    tenant_id: str = "default",
    callback: Callable[[int, int], None] | None = None,
) -> int:
    """Chunks via Ollama einbetten und in Supabase pgvector speichern.

    Verarbeitet Chunks in Batches von _EMBED_BATCH_SIZE. Nach jedem Batch wird
    optional callback(current, total) aufgerufen – nuetzlich fuer Fortschrittsanzeige.

    Args:
        chunks: Liste von Document-Chunks.
        tenant_id: Mandanten-ID fuer Isolation.
        callback: Optionale Funktion (current: int, total: int) -> None,
                  wird nach jedem Embedding-Batch aufgerufen.

    Returns:
        Anzahl erfolgreich gespeicherter Chunks.

    Raises:
        RuntimeError: Wenn Ollama oder Supabase nicht erreichbar sind.
    """
    if not chunks:
        logger.warning("No chunks to store.")
        return 0

    settings = get_settings()
    total = len(chunks)

    # Embeddings via Ollama (selbst gehostet, 0 EUR)
    logger.info(
        "Creating embeddings for %d chunks via Ollama (%s)...",
        total,
        settings.ollama_embed_model,
    )
    t_start = time.monotonic()

    try:
        embedder = _get_embedder()

        all_embeddings: list[list[float]] = []

        # Batch-weise einbetten und Fortschritt melden
        for batch_start in range(0, total, _EMBED_BATCH_SIZE):
            batch_chunks = chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]
            batch_texts = [c.page_content for c in batch_chunks]
            batch_embeddings = embedder.embed_documents(batch_texts)
            all_embeddings.extend(batch_embeddings)

            if callback:
                current = min(batch_start + _EMBED_BATCH_SIZE, total)
                callback(current, total)

    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        raise RuntimeError(
            f"Ollama-Embedding fehlgeschlagen: {exc}\n"
            "Ist Tailscale aktiv und der VPS erreichbar?"
        ) from exc

    duration = time.monotonic() - t_start
    logger.info(
        "Created %d embeddings in %.1fs (cost: 0.00 EUR - self-hosted)",
        len(all_embeddings),
        duration,
    )

    # In Supabase speichern
    logger.info("Storing %d chunks in Supabase...", total)
    try:
        client = _get_supabase_client()
        rows = [
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "source": chunk.metadata.get("source", "unknown"),
                "page": int(chunk.metadata.get("page", 0)),
                "content": chunk.page_content,
                "embedding": embedding,
            }
            for chunk, embedding in zip(chunks, all_embeddings)
        ]
        result = client.table("document_chunks").insert(rows).execute()
    except Exception as exc:
        logger.error("Supabase insert failed: %s", exc)
        raise RuntimeError(f"Chunks konnten nicht gespeichert werden: {exc}") from exc

    stored = len(result.data) if result.data else len(rows)
    logger.info("Stored %d chunks.", stored)
    return stored


def delete_document(source: str, tenant_id: str = "default") -> int:
    """Alle Chunks eines Dokuments aus Supabase loeschen.

    Wird fuer DSGVO-konforme Loeschung verwendet. Loescht alle Eintraege
    mit dem angegebenen Dateinamen und Mandanten.

    Args:
        source: Dateiname (z. B. "kompressor_handbuch.pdf").
        tenant_id: Mandanten-ID.

    Returns:
        Anzahl geloeschter Chunks.

    Raises:
        RuntimeError: Bei Datenbankfehler.
    """
    logger.info("Deleting document '%s' (tenant=%s)...", source, tenant_id)

    try:
        client = _get_supabase_client()
        result = (
            client.table("document_chunks")
            .delete()
            .eq("source", source)
            .eq("tenant_id", tenant_id)
            .execute()
        )
    except Exception as exc:
        logger.error("Delete failed for '%s': %s", source, exc)
        raise RuntimeError(f"Loeschen fehlgeschlagen: {exc}") from exc

    deleted = len(result.data) if result.data else 0
    logger.info("Deleted %d chunks for '%s'.", deleted, source)
    return deleted
