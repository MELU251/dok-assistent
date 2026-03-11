"""CLI script for ingesting documents into the vector store."""

import argparse
import logging
import sys

from src.config import get_settings
from src.ingest import chunk_document, embed_and_store, load_document

# Initialise logging early so config errors are readable
logging.basicConfig(level="INFO", format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Approximate cost per chunk for display
_EMBEDDING_COST_EUR_PER_CHUNK = 0.000009  # ~$0.00001 * 0.92


def main() -> None:
    """Parse arguments and run the full ingestion pipeline."""
    parser = argparse.ArgumentParser(
        description="Ingest a document into the KI-Dokumenten-Assistent vector store."
    )
    parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help="Path to the document (.pdf, .docx, or .xlsx)",
    )
    parser.add_argument(
        "--tenant",
        default="default",
        metavar="TENANT_ID",
        help="Tenant identifier (default: 'default')",
    )
    args = parser.parse_args()

    # Validate config first (exits with readable error if .env is missing)
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)

    print(f"\n[1/3] Lade Dokument: {args.file}")
    try:
        docs = load_document(args.file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[FEHLER] {exc}")
        sys.exit(1)
    print(f"      {len(docs)} Seiten/Elemente geladen.")

    print("[2/3] Erstelle Chunks...")
    chunks = chunk_document(docs)
    print(f"      {len(chunks)} Chunks erstellt.")

    print("[3/3] Erstelle Embeddings und speichere Vektoren...")
    try:
        stored = embed_and_store(chunks, tenant_id=args.tenant)
    except RuntimeError as exc:
        print(f"[FEHLER] {exc}")
        sys.exit(1)

    print(f"\n[FERTIG] {stored} Chunks gespeichert. Embeddings: 0,00 EUR (selbst gehostet)\n")


if __name__ == "__main__":
    main()
