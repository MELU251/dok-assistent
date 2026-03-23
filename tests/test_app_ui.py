"""Tests fuer UI/UX-Requirements UI-01 bis UI-04.

Wave 1 — UI-01 und UI-02 implementiert (Plan 02).
UI-03 und UI-04 noch xfail(strict=True) bis ebenfalls implementiert.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWelcomeMessage:
    """UI-01: Willkommensnachricht deckt alle drei Pflichtinhalte ab."""

    def test_welcome_contains_upload_instructions(self):
        """_build_welcome_content() nennt unterstuetzte Dateiformate fuer den Upload."""
        import app

        with patch("app.get_indexed_documents", return_value=[]):
            content = app._build_welcome_content()

        content_lower = content.lower()
        # Muss die konkreten Dateiformate nennen, damit Nutzer weiss was hochgeladen werden kann
        # (PDF, DOCX, XLSX — aktuell nicht erwaehnt im Begruessung)
        formats_mentioned = sum(
            1 for fmt in ["pdf", "docx", "xlsx", "word", "excel"]
            if fmt in content_lower
        )
        assert formats_mentioned >= 2, (
            f"Willkommensnachricht nennt keine unterstuetzten Dateiformate (PDF, DOCX, XLSX). "
            f"Gefunden: {formats_mentioned} Formate. Inhalt: {content[:400]}"
        )

    def test_welcome_contains_question_instructions(self):
        """_build_welcome_content() erklaert explizit wie man Fragen in das Eingabefeld tippt."""
        import app

        with patch("app.get_indexed_documents", return_value=[]):
            content = app._build_welcome_content()

        content_lower = content.lower()
        # Muss den Nutzer aktiv zur Texteingabe auffordern (nicht nur einen Button-Label)
        # Aktuell: "Stellen Sie einfach eine Frage" — zu vage; Nutzer braucht explizite Anweisung
        # zum Chat-Eingabefeld
        assert any(
            phrase in content_lower
            for phrase in [
                "eingabefeld",
                "chatfenster",
                "textfeld",
                "nachrichten eingeben",
                "frage eingeben",
                "direkt in",
                "unten eingeben",
                "nachrichtenfeld",
                "tippen sie ihre",
                "schreiben sie ihre frage",
            ]
        ), (
            f"Willkommensnachricht zeigt nicht explizit auf das Eingabefeld: {content[:400]}"
        )

    def test_welcome_contains_system_limits(self):
        """_build_welcome_content() informiert ueber Systemgrenzen (was das System NICHT kann)."""
        import app

        with patch("app.get_indexed_documents", return_value=[]):
            content = app._build_welcome_content()

        content_lower = content.lower()
        # Muss erklaeren, dass das System nur aus Dokumenten antwortet (Grenzen kommunizieren)
        assert any(
            phrase in content_lower
            for phrase in [
                "nur aus",
                "ausschliesslich",
                "nur auf basis",
                "nicht enthalten",
                "keine allgemeinen",
                "begrenzt auf",
                "nur die",
                "nicht beantworten",
                "ausserhalb der dokumente",
            ]
        ), (
            f"Willkommensnachricht kommuniziert keine Systemgrenzen "
            f"(was das System NICHT kann): {content[:400]}"
        )


class TestDokumenteCommand:
    """UI-02: /dokumente-Befehl liefert aktuelle Dokumentenliste."""

    async def test_dokumente_command_lists_docs(self):
        """on_message('/dokumente') sendet Nachricht mit Dateinamen aus get_indexed_documents()."""
        import app

        mock_session = MagicMock()
        mock_session.get.return_value = None

        msg = MagicMock()
        msg.content = "/dokumente"

        sent_contents: list[str] = []

        def capture_message(content="", **kwargs):
            mock_msg = MagicMock()
            sent_contents.append(content)
            mock_msg.send = AsyncMock(return_value=None)
            return mock_msg

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Message", side_effect=capture_message),
            patch("app.get_indexed_documents", return_value=["handbuch.pdf", "vertrag.docx"]),
        ):
            await app.on_message(msg)

        assert len(sent_contents) >= 1, "/dokumente hat keine Nachricht gesendet"
        combined = " ".join(sent_contents)
        assert "handbuch.pdf" in combined, (
            f"Dokumentliste enthaelt 'handbuch.pdf' nicht: {combined}"
        )
        assert "vertrag.docx" in combined, (
            f"Dokumentliste enthaelt 'vertrag.docx' nicht: {combined}"
        )

    async def test_dokumente_command_empty(self):
        """on_message('/dokumente') ohne Dokumente sendet Meldung mit 'keine' oder 'Keine'."""
        import app

        mock_session = MagicMock()
        mock_session.get.return_value = None

        msg = MagicMock()
        msg.content = "/dokumente"

        sent_contents: list[str] = []

        def capture_message(content="", **kwargs):
            mock_msg = MagicMock()
            sent_contents.append(content)
            mock_msg.send = AsyncMock(return_value=None)
            return mock_msg

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Message", side_effect=capture_message),
            patch("app.get_indexed_documents", return_value=[]),
        ):
            await app.on_message(msg)

        assert len(sent_contents) >= 1, "/dokumente hat bei leerer Liste keine Nachricht gesendet"
        combined = " ".join(sent_contents).lower()
        assert "keine" in combined, (
            f"Leere Dokumentliste enthaelt kein 'keine': {combined}"
        )


class TestGermanErrors:
    """UI-03: Alle Fehlerpfade senden deutschen Text ohne technischen Jargon."""

    async def test_rag_flow_error_no_internal_type(self):
        """_run_rag_flow-Fehlerblock sendet keine rohen Exception-Klassennamen."""
        import app

        mock_session = MagicMock()
        mock_session.get.return_value = []

        sent_contents: list[str] = []

        def capture_message(content="", **kwargs):
            mock_msg = MagicMock()
            sent_contents.append(content)
            mock_msg.send = AsyncMock(return_value=None)
            return mock_msg

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message", side_effect=capture_message),
            patch("app.asyncio.to_thread", side_effect=RuntimeError("Verbindungsfehler")),
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            await app._run_rag_flow("Was ist das?")

        assert len(sent_contents) >= 1, "Fehlerfall hat keine Nachricht gesendet"
        combined = " ".join(sent_contents)
        # Kein roher Exception-Typ im Output
        assert "RuntimeError" not in combined, (
            f"Fehlermeldung enthaelt rohen Exception-Typ 'RuntimeError': {combined}"
        )
        assert "type(exc).__name__" not in combined, (
            f"Fehlermeldung enthaelt Python-Ausdruck 'type(exc).__name__': {combined}"
        )
        # Kein "_Intern:" Marker
        assert "_Intern:" not in combined, (
            f"Fehlermeldung enthaelt internen Marker '_Intern:': {combined}"
        )

    async def test_upload_flow_error_no_internal_type(self):
        """_run_upload_flow embed_and_store-Fehlerblock sendet keine englischen Exception-Typen."""
        import app

        mock_file = MagicMock()
        mock_file.name = "test.pdf"
        mock_file.path = "/tmp/test.pdf"

        sent_contents: list[str] = []

        def capture_message(content="", **kwargs):
            mock_msg = MagicMock()
            sent_contents.append(content)
            mock_msg.send = AsyncMock(return_value=None)
            return mock_msg

        # embed_and_store wirft RuntimeError — simuliert Ollama-Fehler
        async def mock_to_thread(fn, *args, **kwargs):
            if fn.__name__ == "embed_and_store":
                raise RuntimeError("Ollama nicht erreichbar")
            return MagicMock()

        with (
            patch("app.cl.AskFileMessage") as mock_ask,
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message", side_effect=capture_message),
            patch("app.shutil.copy"),
            patch("app.load_document", return_value=[MagicMock()]),
            patch("app.chunk_document", return_value=[MagicMock()]),
            patch("app.get_indexed_documents", return_value=[]),
            patch("app.asyncio.to_thread", side_effect=mock_to_thread),
        ):
            mock_ask.return_value.send = AsyncMock(return_value=[mock_file])
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            await app._run_upload_flow()

        assert len(sent_contents) >= 1, "Fehlerfall hat keine Nachricht gesendet"
        combined = " ".join(sent_contents)
        assert "RuntimeError" not in combined, (
            f"Fehlermeldung enthaelt 'RuntimeError': {combined}"
        )
        assert "_Intern:" not in combined, (
            f"Fehlermeldung enthaelt '_Intern:': {combined}"
        )

    async def test_delete_flow_error_no_internal_type(self):
        """_run_delete_flow-Fehlerblock sendet keine Nachricht mit '_Intern:'."""
        import app

        sent_contents: list[str] = []

        def capture_message(content="", **kwargs):
            mock_msg = MagicMock()
            sent_contents.append(content)
            mock_msg.send = AsyncMock(return_value=None)
            return mock_msg

        with (
            patch("app.DOCS_DIR") as mock_dir,
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message", side_effect=capture_message),
            patch("app.asyncio.to_thread", side_effect=RuntimeError("DB-Fehler")),
        ):
            # Lokale Datei existiert (um den Loeschflow zu starten)
            mock_local = MagicMock()
            mock_local.exists.return_value = True
            mock_local.unlink.return_value = None
            mock_dir.__truediv__ = MagicMock(return_value=mock_local)

            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            await app._run_delete_flow("test.pdf")

        assert len(sent_contents) >= 1, "Fehlerfall hat keine Nachricht gesendet"
        combined = " ".join(sent_contents)
        assert "_Intern:" not in combined, (
            f"Fehlermeldung enthaelt '_Intern:': {combined}"
        )
        assert "RuntimeError" not in combined, (
            f"Fehlermeldung enthaelt 'RuntimeError': {combined}"
        )

    async def test_workflow_generation_error_no_internal_type(self):
        """_run_workflow_generation-Fehlerblock sendet keine Nachricht mit '_Intern:'."""
        import app

        sent_contents: list[str] = []

        def capture_message(content="", **kwargs):
            mock_msg = MagicMock()
            sent_contents.append(content)
            mock_msg.send = AsyncMock(return_value=None)
            return mock_msg

        mock_angebot = MagicMock()
        mock_angebot.summary = "Test-Zusammenfassung"

        with (
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message", side_effect=capture_message),
            patch("app.asyncio.to_thread", side_effect=Exception("Generierungsfehler")),
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            await app._run_workflow_generation("/tmp/test.pdf", "test.pdf", mock_angebot)

        assert len(sent_contents) >= 1, "Fehlerfall hat keine Nachricht gesendet"
        combined = " ".join(sent_contents)
        assert "_Intern:" not in combined, (
            f"Fehlermeldung enthaelt '_Intern:': {combined}"
        )
        assert "Exception" not in combined, (
            f"Fehlermeldung enthaelt 'Exception': {combined}"
        )


class TestSourceCitations:
    """UI-04: Quellenangaben als cl.Text-Element mit display='inline'."""

    async def test_rag_flow_uses_cl_text_element(self):
        """_run_rag_flow() mit vorhandenen Quellen ruft cl.Text auf (nicht nur cl.Message)."""
        import app

        mock_session = MagicMock()
        mock_session.get.return_value = []

        mock_result = {
            "answer": "Die Antwort lautet 42.",
            "sources": ["handbuch.pdf, Seite 3", "vertrag.docx, Seite 1"],
            "cost_eur": 0.001,
        }

        cl_text_calls: list = []

        def capture_text(**kwargs):
            cl_text_calls.append(kwargs)
            return MagicMock()

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message") as mock_message,
            patch("app.cl.Text", side_effect=capture_text),
            patch("app.asyncio.to_thread", AsyncMock(return_value=mock_result)),
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_message.return_value.send = AsyncMock(return_value=None)
            await app._run_rag_flow("Was ist die Antwort?")

        assert len(cl_text_calls) > 0, (
            "cl.Text wurde nicht aufgerufen — Quellen werden nicht als Text-Element uebergeben"
        )

    async def test_cl_text_display_inline(self):
        """cl.Text wird mit display='inline' aufgerufen."""
        import app

        mock_session = MagicMock()
        mock_session.get.return_value = []

        mock_result = {
            "answer": "Antwort mit Quellen.",
            "sources": ["dokument.pdf, Seite 5"],
            "cost_eur": 0.001,
        }

        cl_text_calls: list = []

        def capture_text(**kwargs):
            cl_text_calls.append(kwargs)
            return MagicMock()

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message") as mock_message,
            patch("app.cl.Text", side_effect=capture_text),
            patch("app.asyncio.to_thread", AsyncMock(return_value=mock_result)),
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_message.return_value.send = AsyncMock(return_value=None)
            await app._run_rag_flow("Wo steht das?")

        assert len(cl_text_calls) > 0, (
            "cl.Text wurde nicht aufgerufen"
        )
        displays = [call.get("display") for call in cl_text_calls]
        assert "inline" in displays, (
            f"cl.Text wurde nicht mit display='inline' aufgerufen. "
            f"Gefundene display-Werte: {displays}"
        )
