"""Unit-Tests fuer die History-Akkumulation in app.py (CHAT-01).

Testet, dass _run_rag_flow die Gespraechshistorie korrekt im
cl.user_session speichert und das History-Fenster begrenzt wird.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestAppHistory:
    """Tests fuer die History-Akkumulation in app.py."""

    @pytest.mark.xfail(strict=True, reason="not yet implemented")
    def test_history_accumulates_after_rag_answer(self):
        """Nach _run_rag_flow wird user_session.set zweimal aufgerufen.

        Erwartet: einmal mit Rolle 'user', einmal mit Rolle 'assistant'.
        """
        mock_session = MagicMock()
        mock_session.get.return_value = []

        with patch("chainlit.user_session", mock_session):
            from app import _run_rag_flow  # noqa: PLC0415

            _run_rag_flow("Testfrage")

        assert mock_session.set.call_count == 2
        calls = mock_session.set.call_args_list
        roles = [call[0][0] for call in calls]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.xfail(strict=True, reason="not yet implemented")
    def test_history_window_passed_to_answer(self):
        """Wenn user_session 8 Nachrichten enthaelt, werden nur die letzten 6 an answer() uebergeben."""
        mock_session = MagicMock()
        mock_session.get.return_value = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Nachricht {i}"}
            for i in range(8)
        ]

        with (
            patch("chainlit.user_session", mock_session),
            patch("app.answer") as mock_answer,
        ):
            mock_answer.return_value = {
                "answer": "Antwort",
                "sources": [],
                "cost_eur": 0.001,
            }
            from app import _run_rag_flow  # noqa: PLC0415

            _run_rag_flow("Folgefrage")

        mock_answer.assert_called_once()
        call_kwargs = mock_answer.call_args
        history_arg = call_kwargs[1].get("history") or call_kwargs[0][1]
        assert len(history_arg) == 6
