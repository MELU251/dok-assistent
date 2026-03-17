"""Unit-Tests fuer die SQLAlchemyDataLayer-Registrierung in app.py (CHAT-02).

Testet, dass die get_data_layer-Funktion eine SQLAlchemyDataLayer-Instanz zurueckgibt.
"""

from unittest.mock import MagicMock

import pytest


class TestDataLayer:
    """Tests fuer die Registrierung des Chainlit Data Layers."""

    @pytest.mark.xfail(strict=True, reason="not yet implemented")
    def test_get_data_layer_returns_sql_alchemy_instance(self):
        """get_data_layer gibt eine SQLAlchemyDataLayer-Instanz zurueck."""
        from chainlit.data.sql_alchemy import SQLAlchemyDataLayer  # noqa: PLC0415

        from app import get_data_layer  # noqa: PLC0415

        mock_settings = MagicMock()
        mock_settings.database_url = "sqlite+aiosqlite:///./test.db"

        result = get_data_layer(mock_settings)

        assert isinstance(result, SQLAlchemyDataLayer)
