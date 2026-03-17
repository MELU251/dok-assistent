"""Unit tests fuer async Event-Loop-Safety in app.py (TECH-01)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
