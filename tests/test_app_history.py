"""Unit-Tests fuer die History-Akkumulation in app.py (CHAT-01).

Testet, dass _run_rag_flow die Gespraechshistorie korrekt im
cl.user_session speichert.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAppHistory:
    """Tests fuer die History-Akkumulation in app.py."""

    @pytest.mark.asyncio
    async def test_history_accumulates_after_rag_answer(self):
        """Nach _run_rag_flow wird user_session.set('history', ...) aufgerufen.

        Erwartet: history enthaelt einen user-Eintrag und einen assistant-Eintrag.
        """
        import app

        mock_session = MagicMock()
        mock_session.get.return_value = []

        mock_result = {
            "answer": "Antwort",
            "sources": [],
            "cost_eur": 0.001,
        }

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.asyncio.to_thread", AsyncMock(return_value=mock_result)),
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message") as mock_msg,
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_msg.return_value.send = AsyncMock()

            await app._run_rag_flow("Testfrage")

        # history should have been set with a list containing user and assistant entries
        set_calls = [
            call for call in mock_session.set.call_args_list
            if call[0][0] == "history"
        ]
        assert len(set_calls) >= 1
        history = set_calls[-1][0][1]
        roles = [entry["role"] for entry in history]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_full_history_passed_to_answer(self):
        """_run_rag_flow uebergibt die vollstaendige Session-History an answer().

        Das Fenster-Slicing liegt in pipeline.answer(), nicht in _run_rag_flow.
        Erwartet: answer() erhaelt alle 8 Eintraege aus der Session.
        """
        import app

        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Nachricht {i}"}
            for i in range(8)
        ]
        mock_session = MagicMock()
        mock_session.get.side_effect = lambda key, default=None: (
            long_history if key == "history" else None
        )

        mock_result = {
            "answer": "Antwort",
            "sources": [],
            "cost_eur": 0.001,
        }

        captured_history: list = []

        async def fake_to_thread(fn, *args, **kwargs):
            # Capture a snapshot of history at call time (before append)
            history_at_call = list(kwargs.get("history", []))
            captured_history.extend([history_at_call])
            return mock_result

        with (
            patch("app.cl.user_session", mock_session),
            patch("app.asyncio.to_thread", side_effect=fake_to_thread),
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message") as mock_msg,
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_msg.return_value.send = AsyncMock()

            await app._run_rag_flow("Folgefrage")

        # _run_rag_flow passes full history; answer() is responsible for the [-6:] window
        assert len(captured_history) == 1, "to_thread should be called once"
        history_arg = captured_history[0]
        assert len(history_arg) == 8
