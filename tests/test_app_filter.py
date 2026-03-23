"""Unit-Tests fuer den /filter-Befehl in app.py (CHAT-03).

Testet, dass der /filter-Befehl in on_message den source_filter korrekt
in cl.user_session setzt bzw. zuruecksetzt.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFilterCommand:
    """Tests fuer den /filter-Befehl in on_message."""

    @pytest.mark.asyncio
    async def test_filter_with_filename_sets_source_filter_in_session(self):
        """/filter datei.pdf setzt source_filter auf 'datei.pdf' in user_session."""
        import app

        mock_session = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "/filter datei.pdf"

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Message") as mock_msg_cls,
        ):
            mock_msg_cls.return_value.send = AsyncMock()
            await app.on_message(mock_message)

        mock_session.set.assert_any_call("source_filter", "datei.pdf")

    @pytest.mark.asyncio
    async def test_filter_without_argument_resets_source_filter_to_none(self):
        """/filter ohne Argument setzt source_filter auf None in user_session."""
        import app

        mock_session = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "/filter"

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Message") as mock_msg_cls,
        ):
            mock_msg_cls.return_value.send = AsyncMock()
            await app.on_message(mock_message)

        mock_session.set.assert_any_call("source_filter", None)

    @pytest.mark.asyncio
    async def test_filter_command_returns_early_without_calling_rag(self):
        """/filter-Befehl ruft _run_rag_flow nicht auf (fruehes return)."""
        import app

        mock_session = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "/filter bericht.docx"

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.cl.Message") as mock_msg_cls,
            patch("app._run_rag_flow", new_callable=AsyncMock) as mock_rag,
        ):
            mock_msg_cls.return_value.send = AsyncMock()
            await app.on_message(mock_message)

        mock_rag.assert_not_called()
