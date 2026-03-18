"""Chainlit Chat-UI fuer den KI-Dokumenten-Assistenten.

Features:
  - Passwort-Authentifizierung (CHAINLIT_AUTH_SECRET + Umgebungsvariablen)
  - Datei-Upload direkt im Chat (PDF, DOCX, XLSX, max. 50 MB)
  - Automatische Indexierung nach Upload
  - RAG-basierte Fragen und Antworten mit Quellenangabe
  - Dokument-Loeschung via /loeschen [dateiname]
"""

import asyncio
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
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import ThreadDict

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
# Datenpersistenz
# ---------------------------------------------------------------

@cl.data_layer
def get_data_layer() -> SQLAlchemyDataLayer:
    """Chainlit-Datenpersistenz via SQLAlchemy (Supabase PostgreSQL).

    Returns:
        SQLAlchemyDataLayer-Instanz fuer Thread- und Nachrichten-Persistenz.
    """
    settings = get_settings()
    # asyncpg kennt pgbouncer=true nicht – Parameter aus der URL entfernen
    conninfo = settings.async_database_url
    conninfo = conninfo.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
    return SQLAlchemyDataLayer(
        conninfo=conninfo,
        ssl_require=True,
        show_logger=False,
    )


# ---------------------------------------------------------------
# Datenbank-Migration
# ---------------------------------------------------------------

_CHAINLIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    "id"         UUID PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata"   JSONB NOT NULL DEFAULT '{}',
    "createdAt"  TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    "id"             TEXT PRIMARY KEY,
    "createdAt"      TEXT,
    "name"           TEXT,
    "userId"         UUID REFERENCES users("id") ON DELETE SET NULL,
    "userIdentifier" TEXT,
    "tags"           TEXT[],
    "metadata"       JSONB
);

CREATE TABLE IF NOT EXISTS steps (
    "id"           TEXT PRIMARY KEY,
    "name"         TEXT NOT NULL,
    "type"         TEXT NOT NULL,
    "threadId"     TEXT NOT NULL REFERENCES threads("id") ON DELETE CASCADE,
    "parentId"     TEXT,
    "command"      TEXT,
    "streaming"    BOOLEAN NOT NULL DEFAULT FALSE,
    "waitForAnswer" BOOLEAN,
    "isError"      BOOLEAN,
    "metadata"     JSONB,
    "tags"         TEXT[],
    "input"        TEXT,
    "output"       TEXT,
    "createdAt"    TEXT,
    "start"        TEXT,
    "end"          TEXT,
    "generation"   JSONB,
    "showInput"    TEXT,
    "defaultOpen"  BOOLEAN,
    "autoCollapse" BOOLEAN,
    "language"     TEXT
);

CREATE TABLE IF NOT EXISTS elements (
    "id"           TEXT PRIMARY KEY,
    "threadId"     TEXT,
    "type"         TEXT,
    "chainlitKey"  TEXT,
    "path"         TEXT,
    "url"          TEXT,
    "objectKey"    TEXT,
    "name"         TEXT NOT NULL,
    "display"      TEXT,
    "size"         TEXT,
    "language"     TEXT,
    "page"         INT,
    "props"        JSONB,
    "autoPlay"     BOOLEAN,
    "playerConfig" JSONB,
    "forId"        TEXT,
    "mime"         TEXT
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id"       TEXT PRIMARY KEY,
    "forId"    TEXT NOT NULL,
    "threadId" TEXT NOT NULL REFERENCES threads("id") ON DELETE CASCADE,
    "value"    FLOAT NOT NULL,
    "comment"  TEXT
);
"""


@cl.on_app_startup
async def on_app_startup() -> None:
    """Chainlit-Datenbanktabellen anlegen falls sie noch nicht existieren.

    Wird einmalig beim App-Start ausgefuehrt. Idempotent durch IF NOT EXISTS.
    """
    import ssl as _ssl
    import asyncpg

    settings = get_settings()
    conninfo = settings.async_database_url
    conninfo = conninfo.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
    # asyncpg erwartet postgresql:// – SQLAlchemy-Dialekt-Prefix entfernen
    conninfo = conninfo.replace("postgresql+asyncpg://", "postgresql://")

    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE

    try:
        conn = await asyncpg.connect(dsn=conninfo, ssl=ctx)
        try:
            await conn.execute(_CHAINLIT_SCHEMA_SQL)
            logger.info("Datenbank-Migration erfolgreich abgeschlossen.")
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("Datenbank-Migration fehlgeschlagen: %s", exc)


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

async def _deliver_file(path: Path, display_name: str, message: str) -> None:
    """Datei als Download-Element an den Nutzer schicken.

    Args:
        path: Absoluter Pfad zur erzeugten Datei.
        display_name: Angezeigter Dateiname im Chat.
        message: Begleittext zur Download-Nachricht.
    """
    file_elem = cl.File(name=display_name, path=str(path), display="inline")
    await cl.Message(content=message, elements=[file_elem]).send()


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
        "- Klicken Sie **Angebotsentwurf erstellen** um aus einem Lastenheft einen Entwurf zu erzeugen\n"
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
            ),
            cl.Action(
                name="start_workflow",
                label="Angebotsentwurf erstellen",
                payload={"action": "workflow"},
            ),
        ],
    ).send()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    """Gespraechsverlauf beim Wiederoeffnen eines alten Chats wiederherstellen.

    Rekonstruiert die in-memory History aus den Steps des Threads damit
    Multi-Turn-Kontext (CHAT-01) auch in fortgesetzten Sessions funktioniert.

    Args:
        thread: Chainlit ThreadDict mit id, name und steps (Nachrichten-Historie).
    """
    history: list[dict] = []
    for step in thread.get("steps", []):
        if step.get("type") == "user_message":
            history.append({"role": "user", "content": step.get("input", "")})
        elif step.get("type") == "assistant_message":
            history.append({"role": "assistant", "content": step.get("output", "")})
    cl.user_session.set("history", history)
    logger.info(
        "Chat wieder aufgenommen: %d Nachrichten aus History wiederhergestellt",
        len(history),
    )


@cl.action_callback("start_upload")
async def on_upload_action(action: cl.Action) -> None:
    """Upload-Dialog oeffnen wenn der Nutzer den Upload-Button klickt."""
    await _run_upload_flow()


@cl.action_callback("start_workflow")
async def on_workflow_action(action: cl.Action) -> None:
    """Angebotsentwurf-Workflow starten wenn der Nutzer den Workflow-Button klickt."""
    await _run_workflow_flow()


@cl.action_callback("confirm_workflow")
async def on_workflow_confirm(action: cl.Action) -> None:
    """Angebotsentwurf-Generierung bestaetigen nach Verifikationsschritt."""
    pending = cl.user_session.get("pending_workflow")
    if not pending:
        await cl.Message(content="Kein ausstehender Workflow gefunden.").send()
        return
    cl.user_session.set("pending_workflow", None)
    await _run_workflow_generation(
        pending["file_path"],
        pending["filename"],
        pending["angebot_data"],
    )


@cl.action_callback("cancel_workflow")
async def on_workflow_cancel(action: cl.Action) -> None:
    """Angebotsentwurf-Workflow abbrechen."""
    cl.user_session.set("pending_workflow", None)
    await cl.Message(content="Workflow abgebrochen.").send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Textnachricht verarbeiten: Loeschbefehl oder RAG-Anfrage.

    Args:
        message: Nachricht des Benutzers.
    """
    text = message.content.strip()
    if not text:
        return

    # Filterbefehl: /filter [dateiname] oder /filter (ohne Argument zum Zuruecksetzen)
    if text.lower().startswith("/filter"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            cl.user_session.set("source_filter", None)
            await cl.Message(content="Filter zurueckgesetzt. Alle Dokumente werden durchsucht.").send()
        else:
            filename = parts[1].strip()
            cl.user_session.set("source_filter", filename)
            await cl.Message(
                content=f"Filter aktiv: Fragen werden nur in **{filename}** gesucht.\n"
                        "Tippen Sie `/filter` (ohne Argument) um den Filter zurueckzusetzen."
            ).send()
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

            stored = await asyncio.to_thread(embed_and_store, chunks, callback=progress)
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

    Reihenfolge (atomar-sicher):
    1. Lokale Datei pruefen — wenn nicht vorhanden, Supabase NICHT anfassen.
    2. Lokale Datei zuerst loeschen.
    3. Supabase-Records danach loeschen.

    Args:
        filename: Dateiname des zu loeschenden Dokuments.
    """
    local_file = DOCS_DIR / filename

    # Schritt 1: Lokale Datei pruefen — wenn nicht vorhanden, Supabase NICHT anfassen
    if not local_file.exists():
        await cl.Message(
            content=(
                f"Lokale Datei '{filename}' nicht gefunden.\n"
                "Supabase-Eintraege wurden nicht veraendert."
            )
        ).send()
        return

    async with cl.Step(name=f"Loesche '{filename}'...") as step:
        # Schritt 2: Lokale Datei ZUERST loeschen
        local_file.unlink()
        step.output = f"Datei '{filename}' aus /docs entfernt"

        # Schritt 3: Supabase-Records loeschen
        try:
            deleted_chunks = await asyncio.to_thread(delete_document, filename)
            step.output += f" | {deleted_chunks} Chunks aus Datenbank entfernt"
        except RuntimeError as exc:
            logger.error("Delete DB failed for '%s': %s", filename, exc)
            await cl.Message(
                content=f"Datei wurde geloescht, aber Datenbankfehler: {type(exc).__name__}"
            ).send()
            return

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
    """Frage per RAG-Pipeline beantworten (mit Multi-Turn-Kontext und optionalem Source-Filter).

    Liest die aktive Gespraechshistorie und den Source-Filter aus der User-Session,
    ruft pipeline.answer() auf und aktualisiert die History nach der Antwort.

    Args:
        question: Natuerlichsprachliche Frage des Nutzers.
    """
    history: list[dict] = cl.user_session.get("history") or []
    source_filter: str | None = cl.user_session.get("source_filter")

    async with cl.Step(name="Durchsuche Dokumente und erstelle Antwort ...") as step:
        try:
            result = await asyncio.to_thread(
                answer, question, source_filter=source_filter, history=history
            )
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

    # CHAT-01: History aktualisieren
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": result["answer"]})
    cl.user_session.set("history", history)

    sources_block = ""
    if result["sources"]:
        source_lines = "\n".join(f"- {s}" for s in result["sources"])
        sources_block = f"\n\n---\n**Quellen:**\n{source_lines}"

    cost_cent = result["cost_eur"] * 100
    cost_note = f"\n\n<sub>Kosten dieser Anfrage: ~{cost_cent:.3f} Cent</sub>"

    await cl.Message(
        content=result["answer"] + sources_block + cost_note
    ).send()


# ---------------------------------------------------------------
# Workflow-Flow (Angebotsentwurf)
# ---------------------------------------------------------------

_WORKFLOW_ACCEPTED_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


async def _run_workflow_flow() -> None:
    """Workflow-Einstieg: Lastenheft anfordern und Anforderungen extrahieren.

    Schritt 1 von 3: Lastenheft hochladen.
    Schritt 2 von 3: Extraktion und Verifikation.
    Schritt 3 von 3 (nach Bestaetigung): Generierung und Download.
    """
    await cl.Message(
        content=(
            "**Angebotsentwurf erstellen — Schritt 1/3**\n\n"
            "Bitte laden Sie das Lastenheft hoch (PDF oder DOCX):"
        )
    ).send()

    response = await cl.AskFileMessage(
        content="Lastenheft hochladen (PDF oder DOCX, max. 50 MB):",
        accept=_WORKFLOW_ACCEPTED_TYPES,
        max_size_mb=_MAX_SIZE_MB,
        timeout=300,
    ).send()

    if not response:
        return

    uploaded = response[0] if isinstance(response, list) else response
    filename = uploaded.name
    suffix = Path(filename).suffix.lower()

    if suffix not in (".pdf", ".docx"):
        await cl.Message(
            content=(
                f"Nicht unterstuetztes Dateiformat: '{suffix}'.\n"
                "Bitte laden Sie eine PDF- oder DOCX-Datei hoch."
            )
        ).send()
        return

    # Datei temporaer in DOCS_DIR speichern fuer den Workflow
    dest_path = DOCS_DIR / filename
    try:
        shutil.copy(uploaded.path, dest_path)
    except Exception as exc:
        logger.error("Fehler beim Speichern des Lastenhefts: %s", exc)
        await cl.Message(content=f"Fehler beim Speichern der Datei: {type(exc).__name__}").send()
        return

    # Extraktion starten
    async with cl.Step(name="Schritt 2/3: Anforderungen werden extrahiert...") as step:
        try:
            from src.ingest import chunk_document, load_document
            from src.extractor import extract_requirements

            docs = await asyncio.to_thread(load_document, str(dest_path))
            chunks = chunk_document(docs)
            angebot_data = await asyncio.to_thread(extract_requirements, chunks)
            step.output = f"Extraktion abgeschlossen: '{angebot_data.title}'"
        except ValueError as exc:
            await cl.Message(
                content=f"Fehler bei der Extraktion: {exc}"
            ).send()
            return
        except RuntimeError as exc:
            logger.error("Extraktion fehlgeschlagen: %s", exc)
            await cl.Message(
                content=(
                    "Die Anforderungsextraktion ist fehlgeschlagen.\n"
                    "Bitte pruefen Sie die Verbindung und versuchen Sie es erneut.\n"
                    f"_(Intern: {type(exc).__name__})_"
                )
            ).send()
            return

    # Verifikations-Schritt: Extrahierte Anforderungen anzeigen
    reqs_text = "\n".join(f"  - {r}" for r in angebot_data.requirements)
    specials_text = (
        "\n".join(f"  - {s}" for s in angebot_data.special_requests)
        if angebot_data.special_requests
        else "  _(keine)_"
    )

    # Pending-State speichern fuer Bestaetigung
    cl.user_session.set("pending_workflow", {
        "file_path": str(dest_path),
        "filename": filename,
        "angebot_data": angebot_data,
    })

    await cl.Message(
        content=(
            f"**Erkannte Anforderungen aus '{filename}':**\n\n"
            f"**Titel:** {angebot_data.title}\n\n"
            f"**Zusammenfassung:** {angebot_data.summary}\n\n"
            f"**Pflichtanforderungen:**\n{reqs_text}\n\n"
            f"**Sonderwuensche:**\n{specials_text}\n\n"
            "---\n"
            "Stimmen die Anforderungen? Klicken Sie **Angebot generieren** um fortzufahren."
        ),
        actions=[
            cl.Action(
                name="confirm_workflow",
                label="Angebot generieren",
                payload={"action": "confirm"},
            ),
            cl.Action(
                name="cancel_workflow",
                label="Abbrechen",
                payload={"action": "cancel"},
            ),
        ],
    ).send()


async def _run_workflow_generation(
    file_path: str,
    filename: str,
    angebot_data,
) -> None:
    """Schritt 3/3: Angebotsentwurf generieren und als .docx liefern.

    Args:
        file_path: Pfad zum gespeicherten Lastenheft.
        filename: Originalname des Lastenhefts.
        angebot_data: Bereits extrahiertes AngebotData-Objekt.
    """
    async with cl.Step(name="Schritt 3/3: Angebotsentwurf wird generiert...") as step:
        try:
            from src.retrieval import search
            from src.generator import generate_angebot
            from src.output import write_docx
            from src.workflow import OUTPUT_DIR

            retrieved = await asyncio.to_thread(search, angebot_data.summary)
            result = await asyncio.to_thread(generate_angebot, angebot_data, retrieved)

            sections = {
                "zusammenfassung": result["zusammenfassung"],
                "technische_loesung": result["technische_loesung"],
                "lieferumfang": result["lieferumfang"],
                "offene_punkte": result["offene_punkte"],
            }
            output_filename = f"Angebotsentwurf_{Path(filename).stem}.docx"
            docx_path = await asyncio.to_thread(
                write_docx, sections, result["sources"], OUTPUT_DIR / output_filename
            )
            step.output = f"Entwurf erstellt: {output_filename}"
        except Exception as exc:
            logger.error("Workflow-Generierung fehlgeschlagen: %s", exc)
            await cl.Message(
                content=(
                    "Fehler bei der Entwurfs-Generierung.\n"
                    "Bitte pruefen Sie die Verbindung und versuchen Sie es erneut.\n"
                    f"_(Intern: {type(exc).__name__})_"
                )
            ).send()
            return

    sources_note = ""
    if result["sources"]:
        src_list = ", ".join(result["sources"])
        sources_note = f"\n\n**Verwendete Quellen:** {src_list}"

    cost_cent = result["cost_eur"] * 100
    cost_note = f"\n\n<sub>Generierungskosten: ~{cost_cent:.3f} Cent</sub>"

    await _deliver_file(
        path=docx_path,
        display_name=output_filename,
        message=(
            f"**Angebotsentwurf fertig!**\n\n"
            f"Ihr Entwurf basiert auf {len(retrieved)} historischen Abschnitten."
            f"{sources_note}{cost_note}\n\n"
            "_Bitte pruefen Sie den Entwurf sorgfaeltig vor dem Versand._"
        ),
    )
