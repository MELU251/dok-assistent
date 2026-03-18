"""Workflow-Modul: Orchestriert den Angebotsentwurf-Erstellungsprozess.

Koordiniert den kompletten Ablauf:
  Dokument laden → Chunks → Extraktion → RAG-Retrieval → Generierung → .docx
"""

import logging
from pathlib import Path

from langchain_core.documents import Document

from src.extractor import AngebotData, extract_requirements
from src.generator import generate_angebot
from src.ingest import chunk_document, load_document
from src.output import write_docx
from src.retrieval import search

logger = logging.getLogger(__name__)

# Ausgabeverzeichnis fuer generierte Angebotsentwuerfe
OUTPUT_DIR = Path("output")


def create_angebotsentwurf(
    file_path: str,
    tenant_id: str = "default",
) -> tuple[Path, AngebotData, dict]:
    """Erstellt einen Angebotsentwurf aus einem Lastenheft.

    Fuehrt den kompletten Workflow aus:
    1. Lastenheft laden und in Chunks aufteilen
    2. Anforderungen via Claude extrahieren (AngebotData)
    3. Aehnliche historische Angebote via RAG abrufen
    4. Angebotsentwurf via Claude generieren
    5. Entwurf als .docx speichern

    Args:
        file_path: Pfad zum Lastenheft (PDF oder DOCX).
        tenant_id: Tenant-ID fuer die Vektorsuche.

    Returns:
        Tuple aus:
          - docx_path: Pfad zur erzeugten .docx-Datei
          - angebot_data: Extrahierte AngebotData (fuer Verifikationsschritt)
          - result: Dict mit dem generierten Entwurfs-Inhalt

    Raises:
        ValueError: Wenn das Dokument leer ist oder Extraktion fehlschlaegt.
        RuntimeError: Wenn ein API-Aufruf fehlschlaegt.
    """
    path = Path(file_path)
    logger.info("Starte Angebotsentwurf-Workflow fuer: %s", path.name)

    # Schritt 1: Lastenheft laden und chunken
    docs = load_document(str(path))
    chunks: list[Document] = chunk_document(docs)
    logger.info("Lastenheft geladen: %d Chunks", len(chunks))

    # Schritt 2: Anforderungen extrahieren
    angebot_data = extract_requirements(chunks)
    logger.info("Extraktion abgeschlossen: '%s'", angebot_data.title)

    # Schritt 3: Historische Angebote abrufen
    retrieved = search(angebot_data.summary, tenant_id=tenant_id)
    logger.info("RAG-Retrieval: %d Chunks aus historischen Angeboten", len(retrieved))

    # Schritt 4: Angebotsentwurf generieren
    result = generate_angebot(angebot_data, retrieved)
    logger.info("Entwurf generiert (cost: %.4f EUR)", result["cost_eur"])

    # Schritt 5: .docx schreiben
    sections = {
        "zusammenfassung": result["zusammenfassung"],
        "technische_loesung": result["technische_loesung"],
        "lieferumfang": result["lieferumfang"],
        "offene_punkte": result["offene_punkte"],
    }
    output_filename = f"Angebotsentwurf_{path.stem}.docx"
    docx_path = write_docx(sections, result["sources"], OUTPUT_DIR / output_filename)

    logger.info("Workflow abgeschlossen: %s", docx_path)
    return docx_path, angebot_data, result
