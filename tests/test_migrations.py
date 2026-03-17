"""Integrations-Test fuer Alembic-Migrationen (ALL).

Prueft, dass 'alembic upgrade head' erfolgreich ausgefuehrt werden kann.
Nur im Integrations-Modus ausfuehren (erfordert konfigurierte Datenbank).
"""

import subprocess

import pytest

pytestmark = pytest.mark.integration


class TestMigrations:
    """Integrations-Tests fuer Alembic-Datenbankmigrationen."""

    @pytest.mark.xfail(strict=True, reason="not yet implemented")
    def test_alembic_upgrade_head_runs_clean(self):
        """alembic upgrade head wird ohne Fehler ausgefuehrt (Return Code 0)."""
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"alembic upgrade head fehlgeschlagen:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
