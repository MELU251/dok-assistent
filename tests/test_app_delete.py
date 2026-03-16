"""Unit tests fuer atomischen Delete-Flow in app.py (TECH-05)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDeleteFlowAtomicity:
    """delete_document darf Supabase NICHT anfassen wenn lokale Datei fehlt."""

    @pytest.mark.asyncio
    async def test_missing_local_file_does_not_touch_supabase(self, tmp_path):
        import app
        # DOCS_DIR auf tmp_path umlenken – dort existiert "ghost.pdf" nicht
        with (
            patch("app.DOCS_DIR", tmp_path),
            patch("app.delete_document") as mock_delete,
            patch("app.cl.Message") as mock_msg,
        ):
            mock_msg.return_value.send = AsyncMock()
            await app._run_delete_flow("ghost.pdf")

        mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_existing_local_file_deletes_file_before_supabase(self, tmp_path):
        import app
        # Datei anlegen damit sie existiert
        local_file = tmp_path / "real.pdf"
        local_file.write_bytes(b"fake pdf")

        deletion_order = []

        def track_unlink():
            deletion_order.append("file")

        with (
            patch("app.DOCS_DIR", tmp_path),
            patch("app.delete_document") as mock_delete,
            patch("app.cl.Step") as mock_step,
            patch("app.cl.Message"),
            patch("app.get_indexed_documents", return_value=[]),
        ):
            mock_step.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_step.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_delete.return_value = 5
            # Track that file is gone before delete_document is called
            original_delete = mock_delete.side_effect
            def check_order(*a, **kw):
                # By the time delete_document is called, local file must not exist
                assert not local_file.exists(), (
                    "Lokale Datei noch vorhanden als delete_document aufgerufen wurde — "
                    "falsche Reihenfolge!"
                )
                return 5
            mock_delete.side_effect = check_order
            await app._run_delete_flow("real.pdf")

        mock_delete.assert_called_once_with("real.pdf")
