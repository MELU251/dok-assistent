"""Unit tests fuer async Event-Loop-Safety in app.py (TECH-01)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHilHinweisMessage:
    """hil_hinweis muss nach _deliver_file als cl.Message im Chat erscheinen (WORK-04)."""

    @pytest.mark.xfail(strict=True, reason="WORK-04: hil_hinweis not yet wired")
    @pytest.mark.asyncio
    async def test_hil_hinweis_message_sent(self):
        """cl.Message wird mit hil_hinweis-Inhalt gesendet, wenn der Wert vorhanden ist."""
        import app

        hil_hinweis_text = "Bitte pruefen Sie diesen Entwurf vor dem Versand."

        mock_result = {
            "zusammenfassung": "Zusammenfassung",
            "technische_loesung": "Technische Loesung",
            "lieferumfang": "Lieferumfang",
            "offene_punkte": "Offene Punkte",
            "sources": ["quelle.pdf"],
            "cost_eur": 0.01,
            "hil_hinweis": hil_hinweis_text,
        }

        mock_deliver_file = AsyncMock()
        mock_step = MagicMock()
        mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_step.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_message_instance = MagicMock()
        mock_message_instance.send = AsyncMock()

        sent_contents = []

        async def capture_send(msg_instance):
            sent_contents.append(msg_instance)

        with (
            patch("src.retrieval.search", return_value=[]),
            patch("src.generator.generate_angebot", return_value=mock_result),
            patch("src.output.write_docx", return_value="/tmp/test.docx"),
            patch("src.workflow.OUTPUT_DIR", "/tmp"),
            patch("app._deliver_file", mock_deliver_file),
            patch("app.cl.Step", mock_step),
            patch("app.asyncio.to_thread") as mock_to_thread,
            patch("chainlit.Message") as mock_cl_message,
        ):
            # Konfiguriere to_thread so, dass es die entsprechenden Ergebnisse zurueckgibt
            async def side_effect_to_thread(fn, *args, **kwargs):
                if fn.__name__ == "search":
                    return []
                if fn.__name__ == "generate_angebot":
                    return mock_result
                if fn.__name__ == "write_docx":
                    return "/tmp/test.docx"
                return MagicMock()

            mock_to_thread.side_effect = side_effect_to_thread

            mock_cl_message_instance = MagicMock()
            mock_cl_message_instance.send = AsyncMock()
            mock_cl_message.return_value = mock_cl_message_instance

            mock_angebot_data = MagicMock()
            mock_angebot_data.summary = "Test Summary"

            await app._run_workflow_generation(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                angebot_data=mock_angebot_data,
            )

        # Pruefe, dass cl.Message mit hil_hinweis-Inhalt aufgerufen wurde
        cl_message_calls = mock_cl_message.call_args_list
        hinweis_calls = [
            call for call in cl_message_calls
            if "hil_hinweis" in str(call) or "Hinweis" in str(call)
        ]
        assert len(hinweis_calls) >= 1, (
            f"cl.Message wurde nicht mit hil_hinweis aufgerufen. "
            f"Tatsaechliche Aufrufe: {cl_message_calls}"
        )


class TestUploadFlowAsync:
    """embed_and_store muss via asyncio.to_thread aufgerufen werden."""

    @pytest.mark.asyncio
    async def test_embed_and_store_uses_to_thread(self):
        import app
        mock_to_thread = AsyncMock(return_value=3)
        mock_file = MagicMock()
        mock_file.name = "test.pdf"
        mock_file.path = "/tmp/test.pdf"

        with (
            patch("app.asyncio.to_thread", mock_to_thread),
            patch("app.cl.AskFileMessage") as mock_ask,
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message") as mock_message,
            patch("app.shutil.copy"),
            patch("app.load_document", return_value=[MagicMock()]),
            patch("app.chunk_document", return_value=[MagicMock()]),
            patch("app.get_indexed_documents", return_value=[]),
        ):
            mock_ask.return_value.send = AsyncMock(return_value=[mock_file])
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_message.return_value.send = AsyncMock(return_value=None)
            await app._run_upload_flow()

        called_fns = [call.args[0] for call in mock_to_thread.call_args_list]
        from src.ingest import embed_and_store
        assert embed_and_store in called_fns, (
            "embed_and_store wurde nicht via asyncio.to_thread aufgerufen"
        )


class TestRagFlowAsync:
    """answer() muss via asyncio.to_thread aufgerufen werden."""

    @pytest.mark.asyncio
    async def test_answer_uses_to_thread(self):
        import app
        mock_result = {
            "answer": "Antwort",
            "sources": ["test.pdf, Seite 1"],
            "cost_eur": 0.001,
        }
        mock_to_thread = AsyncMock(return_value=mock_result)

        mock_session = MagicMock()
        mock_session.get.return_value = []

        with (
            patch("app.asyncio.to_thread", mock_to_thread),
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message") as mock_message,
            patch("app.cl.Text", return_value=MagicMock()),
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_message.return_value.send = AsyncMock(return_value=None)
            await app._run_rag_flow("Was ist das?")

        called_fns = [call.args[0] for call in mock_to_thread.call_args_list]
        from src.pipeline import answer
        assert answer in called_fns, (
            "answer() wurde nicht via asyncio.to_thread aufgerufen"
        )
