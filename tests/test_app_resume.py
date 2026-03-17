"""Unit-Tests fuer on_chat_resume in app.py (CHAT-02).

Testet, dass on_chat_resume die History aus einem ThreadDict
korrekt rekonstruiert und im cl.user_session speichert.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestOnChatResume:
    """Tests fuer die History-Rekonstruktion beim Fortsetzen eines Chats."""

    def test_user_message_steps_become_history_entries(self):
        """ThreadDict mit 2 user- und 2 assistant-Steps ergibt 4 History-Eintraege."""
        thread_dict = {
            "id": "test-thread-123",
            "steps": [
                {"type": "user_message", "input": "Erste Frage"},
                {"type": "assistant_message", "output": "Erste Antwort"},
                {"type": "user_message", "input": "Zweite Frage"},
                {"type": "assistant_message", "output": "Zweite Antwort"},
            ],
        }

        mock_session = MagicMock()

        with patch("chainlit.user_session", mock_session):
            from app import on_chat_resume  # noqa: PLC0415

            asyncio.run(on_chat_resume(thread_dict))

        mock_session.set.assert_called_once()
        call_args = mock_session.set.call_args
        history = call_args[0][1]
        assert len(history) == 4
        roles = [entry["role"] for entry in history]
        assert roles[0] == "user"
        assert roles[1] == "assistant"
        assert roles[2] == "user"
        assert roles[3] == "assistant"

    def test_empty_steps_sets_empty_history(self):
        """ThreadDict ohne Steps fuehrt zu leerer History."""
        thread_dict = {
            "id": "test-thread-empty",
            "steps": [],
        }

        mock_session = MagicMock()

        with patch("chainlit.user_session", mock_session):
            from app import on_chat_resume  # noqa: PLC0415

            asyncio.run(on_chat_resume(thread_dict))

        mock_session.set.assert_called_once()
        call_args = mock_session.set.call_args
        history = call_args[0][1]
        assert history == []
