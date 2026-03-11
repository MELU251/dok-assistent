"""Chainlit Chat-UI fuer den KI-Dokumenten-Assistenten.

Features:
  - Passwort-Authentifizierung (CHAINLIT_AUTH_SECRET + Umgebungsvariablen)
  - Datei-Upload direkt im Chat (PDF, DOCX, XLSX, max. 50 MB)
  - Automatische Indexierung nach Upload
  - RAG-basierte Fragen und Antworten mit Quellenangabe
  - Dokument-Loeschung via /loeschen [dateiname]
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

import chainlit as cl
from supabase import create_client

from src.config import get_settings
from src.ingest import chunk_document, delete_document, embed_and_store, load_document
from src.pipeline import answer
from src.retrieval import get_indexed_documents

logger = logging.getLogger(__name__)

# Verzeichnis fuer hochgeladene Dokumente (im Docker-Container: /app/docs als Volume)
DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Unterstuetzte MIME-Typen fuer den Datei-Upload
_ACCEPTED_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]
_MAX_SIZE_MB = 50


# ---------------------------------------------------------------
# Authentifizierung
# Aktiv wenn CHAINLIT_AUTH_SECRET in .env gesetzt ist.
# ---------------------------------------------------------------

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Benutzername und Passwort gegen .env-Werte pruefen.

    Args:
        username: Eingegebener Benutzername.
        password: Eingegebenes Passwort.

    Returns:
        cl.User bei Erfolg, None bei falschen Zugangsdaten.
    """
    settings = get_settings()
    if username == settings.chainlit_user and password == settings.chainlit_password:
        return cl.User(identifier=username, metadata={"role": "user"})
    return None


# ---------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------

def _build_welcome_content() -> str:
    """Willkommensnachricht mit Liste indexierter Dokumente aufbauen."""
    docs = get_indexed_documents()

    if docs:
        doc_list = "\n".join(f"  - {d}" for d in docs)
        library_section = (
            f"**Verfuegbare Dokumente ({len(docs)}):**\n{doc_list}"
        )
    else:
        library_section = (
            "_Noch keine Dokumente indexiert. "
            "Laden Sie ein Dokument hoch um zu beginnen._"
        )

    return (
        "## Willkommen beim Dokumenten-Assistenten\n\n"
        "Ich beantworte Ihre Fragen direkt aus Ihren Unterlagen.\n\n"
        f"{library_section}\n\n"
        "---\n"
        "**Aktionen:**\n"
        "- Klicken Sie **Dokument hochladen** um eine neue Datei zu indexieren\n"
        "- Stellen Sie einfach eine Frage um die Dokumente zu durchsuchen\n"
        "- Tippen Sie `/loeschen [dateiname]` um ein Dokument zu entfernen"
    )


# ---------------------------------------------------------------
# Chat-Hooks
# ---------------------------------------------------------------

@cl.on_chat_start
async def on_chat_start() -> None:
    """Willkommensnachricht mit Dokumentliste und Upload-Button anzeigen."""
    await cl.Message(
        content=_build_welcome_content(),
        actions=[
            cl.Action(
                name="start_upload",
                label="Dokument hochladen",
                payload={"action": "upload"},
            )
        ],
    ).send()


@cl.action_callback("start_upload")
async def on_upload_action(action: cl.Action) -> None:
    """Upload-Dialog oeffnen wenn der Nutzer den Upload-Button klickt."""
    await _run_upload_flow()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Textnachricht verarbeiten: Loeschbefehl oder RAG-Anfrage.

    Args:
        message: Nachricht des Benutzers.
    """
    text = message.content.strip()
    if not text:
        return

    # Loeschbefehl: /loeschen [dateiname]
    if text.lower().startswith("/loeschen"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await cl.Message(
                content=(
                    "Bitte den Dateinamen angeben:\n"
                    "`/loeschen kompressor_handbuch.pdf`"
                )
            ).send()
            return
        await _run_delete_flow(parts[1].strip())
        return

    # Regulaere RAG-Anfrage
    await _run_rag_flow(text)


# ---------------------------------------------------------------
# Upload-Flow
# ---------------------------------------------------------------

async def _run_upload_flow() -> None:
    """Upload-Dialog anzeigen, Datei speichern und indexieren."""
    # Datei vom Nutzer anfordern
    response = await cl.AskFileMessage(
        content=(
            "Bitte laden Sie eine Datei hoch (PDF, DOCX oder XLSX, max. 50 MB):"
        ),
        accept=_ACCEPTED_TYPES,
        max_size_mb=_MAX_SIZE_MB,
        timeout=300,
    ).send()

    # Timeout oder Abbruch
    if not response:
        return

    uploaded = response[0] if isinstance(response, list) else response
    filename = uploaded.name
    dest_path = DOCS_DIR / filename

    # Schritt 1: Datei speichern
    async with cl.Step(name="Dokument wird gespeichert...") as step:
        try:
            shutil.copy(uploaded.path, dest_path)
            step.output = f"{filename} gespeichert ({dest_path})"
        except Exception as exc:
            logger.error("Failed to save uploaded file: %s", exc)
            await cl.Message(
                content=f"Fehler beim Speichern der Datei: {exc}"
            ).send()
            return

    # Schritt 2: Dokument laden
    async with cl.Step(name="Dokument wird geladen...") as step:
        try:
            docs = load_document(str(dest_path))
            step.output = f"{len(docs)} Seiten/Elemente erkannt"
        except Exception as exc:
            logger.error("Failed to load document '%s': %s", filename, exc)
            await cl.Message(
                content=(
                    f"Das Dokument '{filename}' konnte nicht gelesen werden.\n"
                    "Bitte pruefen Sie ob die Datei beschaedigt ist."
                )
            ).send()
            dest_path.unlink(missing_ok=True)
            return

    # Schritt 3: Chunking
    async with cl.Step(name="Erstelle Chunks...") as step:
        chunks = chunk_document(docs)
        step.output = f"{len(chunks)} Chunks erstellt"

    # Schritt 4: Embeddings erstellen und speichern
    async with cl.Step(name="Erstelle Embeddings via Ollama...") as step:
        try:
            # Callback aktualisiert den Step-Output waehrend der Verarbeitung
            def progress(current: int, total: int) -> None:
                pass  # Chainlit Steps sind nicht live-aktualisierbar; Logging genuegt

            stored = embed_and_store(chunks, callback=progress)
            step.output = f"{stored} Vektoren in Supabase gespeichert"
        except RuntimeError as exc:
            logger.error("embed_and_store failed: %s", exc)
            await cl.Message(
                content=(
                    f"Fehler beim Erstellen der Embeddings fuer '{filename}'.\n\n"
                    "Moegliche Ursachen:\n"
                    "- Ollama VPS nicht erreichbar (Tailscale aktiv?)\n"
                    "- Supabase-Verbindung unterbrochen\n\n"
                    f"Details (intern): {type(exc).__name__}"
                )
            ).send()
            return

    # Erfolgsmeldung mit aktualisierter Dokumentliste
    updated_docs = get_indexed_documents()
    doc_list = "\n".join(f"  - {d}" for d in updated_docs)

    await cl.Message(
        content=(
            f"**'{filename}' wurde erfolgreich indexiert.**\n"
            f"{stored} Chunks gespeichert.\n\n"
            f"**Verfuegbare Dokumente ({len(updated_docs)}):**\n{doc_list}\n\n"
            "Du kannst jetzt Fragen zu diesem Dokument stellen."
        ),
        actions=[
            cl.Action(
                name="start_upload",
                label="Weiteres Dokument hochladen",
                payload={"action": "upload"},
            )
        ],
    ).send()


# ---------------------------------------------------------------
# Loeschflow
# ---------------------------------------------------------------

async def _run_delete_flow(filename: str) -> None:
    """Alle Chunks eines Dokuments aus Supabase loeschen und Datei entfernen.

    Args:
        filename: Dateiname des zu loeschenden Dokuments.
    """
    # Pruefen ob das Dokument ueberhaupt indexiert ist
    indexed = get_indexed_documents()
    if filename not in indexed:
        await cl.Message(
            content=(
                f"'{filename}' wurde nicht gefunden.\n\n"
                f"Indexierte Dokumente: {', '.join(indexed) if indexed else '(keine)'}"
            )
        ).send()
        return

    async with cl.Step(name=f"Loesche '{filename}'...") as step:
        try:
            deleted_chunks = delete_document(filename)
            step.output = f"{deleted_chunks} Chunks aus Datenbank entfernt"
        except RuntimeError as exc:
            logger.error("Delete failed for '%s': %s", filename, exc)
            await cl.Message(
                content=f"Fehler beim Loeschen aus der Datenbank: {type(exc).__name__}"
            ).send()
            return

        # Originaldatei loeschen falls vorhanden
        local_file = DOCS_DIR / filename
        if local_file.exists():
            local_file.unlink()
            step.output += f" | Datei '{filename}' aus /docs entfernt"

    updated_docs = get_indexed_documents()
    remaining = (
        "\n".join(f"  - {d}" for d in updated_docs)
        if updated_docs
        else "  _(keine Dokumente mehr vorhanden)_"
    )

    await cl.Message(
        content=(
            f"**'{filename}' wurde vollstaendig geloescht.**\n"
            f"{deleted_chunks} Chunks entfernt.\n\n"
            f"**Verbleibende Dokumente ({len(updated_docs)}):**\n{remaining}"
        )
    ).send()


# ---------------------------------------------------------------
# RAG-Flow
# ---------------------------------------------------------------

async def _run_rag_flow(question: str) -> None:
    """Frage per RAG-Pipeline beantworten.

    Args:
        question: Natuerlichsprachliche Frage des Nutzers.
    """
    async with cl.Step(name="Durchsuche Dokumente und erstelle Antwort ...") as step:
        try:
            result = answer(question)
        except Exception as exc:
            logger.error("Pipeline error: %s", exc)
            await cl.Message(
                content=(
                    "Bei der Verarbeitung ist ein Fehler aufgetreten.\n\n"
                    "Bitte pruefen Sie die Verbindung und versuchen Sie es erneut.\n"
                    f"_(Intern: {type(exc).__name__})_"
                )
            ).send()
            return

        found = len(result["sources"])
        step.output = (
            f"{found} relevante Abschnitte gefunden."
            if found > 0
            else "Keine passenden Abschnitte gefunden."
        )

    sources_block = ""
    if result["sources"]:
        source_lines = "\n".join(f"- {s}" for s in result["sources"])
        sources_block = f"\n\n---\n**Quellen:**\n{source_lines}"

    cost_cent = result["cost_eur"] * 100
    cost_note = f"\n\n<sub>Kosten dieser Anfrage: ~{cost_cent:.3f} Cent</sub>"

    await cl.Message(
        content=result["answer"] + sources_block + cost_note
    ).send()
