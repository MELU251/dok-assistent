"""Unit-Tests fuer die SQLAlchemyDataLayer-Registrierung in app.py (CHAT-02).

Testet, dass die get_data_layer-Funktion eine SQLAlchemyDataLayer-Instanz zurueckgibt.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestDataLayer:
    """Tests fuer die Registrierung des Chainlit Data Layers."""

    def test_get_data_layer_returns_sql_alchemy_instance(self):
        """get_data_layer gibt eine SQLAlchemyDataLayer-Instanz zurueck.

        Die Funktion nimmt keine Parameter; sie liest die DB-URL intern via get_settings().
        get_data_layer ist mit @cl.data_layer dekoriert, daher wird die Fabrikfunktion direkt
        aufgerufen ohne Parameter. SQLAlchemyDataLayer wird gemockt, da asyncpg lokal nicht
        installiert ist (nur auf dem VPS verfuegbar).
        """
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://user:pass@localhost:5432/testdb"

        mock_layer_instance = MagicMock()
        mock_layer_cls = MagicMock(return_value=mock_layer_instance)

        with (
            patch("app.get_settings", return_value=mock_settings),
            patch("app.SQLAlchemyDataLayer", mock_layer_cls),
        ):
            from app import get_data_layer  # noqa: PLC0415
            result = get_data_layer()

        # Verify the data layer factory was called with the correct async conninfo
        mock_layer_cls.assert_called_once()
        call_kwargs = mock_layer_cls.call_args[1]
        assert "conninfo" in call_kwargs
        assert "postgresql+asyncpg://" in call_kwargs["conninfo"]
        assert call_kwargs.get("ssl_require") is True
        assert result is mock_layer_instance
