"""Anwendungskonfiguration aus Umgebungsvariablen."""

import logging
from functools import lru_cache

import httpx
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Alle Anwendungseinstellungen, beim Start validiert."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic – LLM für Antwortgenerierung
    anthropic_api_key: str = Field(..., description="Anthropic API-Key")

    # Ollama – selbst gehostete Embeddings auf VPS via Tailscale
    ollama_base_url: str = Field(..., description="Ollama-Basis-URL, z.B. http://100.x.x.x:11434")
    ollama_embed_model: str = Field("nomic-embed-text", description="Ollama-Embedding-Modell")

    # Supabase
    supabase_url: str = Field(..., description="Supabase Projekt-URL")
    supabase_service_key: str = Field(..., description="Supabase Service-Role-Key")

    # Datenbank-Verbindungen fuer Alembic und Chainlit
    # Fuer Alembic (sync): postgresql://postgres:[PWD]@db.[REF].supabase.co:5432/postgres
    # Fuer Chainlit (async): postgresql+asyncpg://postgres:[PWD]@db.[REF].supabase.co:5432/postgres
    database_url: str = Field(..., description="Sync PostgreSQL-URL fuer Alembic-Migrationen")
    async_database_url: str = Field(
        ..., description="Async PostgreSQL-URL (postgresql+asyncpg://) fuer Chainlit SQLAlchemyDataLayer"
    )

    # RAG-Parameter
    chunk_size: int = Field(500, description="Chunk-Größe in Tokens")
    chunk_overlap: int = Field(50, description="Überlappung zwischen Chunks in Tokens")
    top_k_results: int = Field(4, description="Anzahl zurückgegebener Chunks pro Query")

    # Chainlit-Authentifizierung
    # CHAINLIT_AUTH_SECRET generieren: python -c "import secrets; print(secrets.token_hex(32))"
    chainlit_auth_secret: str = Field(..., description="Zufälliger Secret für JWT-Signing")
    chainlit_user: str = Field("pilot", description="Login-Benutzername")
    chainlit_password: str = Field(..., description="Login-Passwort")

    # App
    log_level: str = Field("INFO", description="Logging-Level")

    @field_validator(
        "anthropic_api_key",
        "supabase_url",
        "supabase_service_key",
        "ollama_base_url",
        "database_url",
        "async_database_url",
    )
    @classmethod
    def must_not_be_placeholder(cls, v: str, info) -> str:
        """Platzhalter-Werte aus .env.example ablehnen."""
        placeholders = {
            "sk-ant-...",
            "https://xxxx.supabase.co",
            "eyJ...",
            "http://100.x.x.x:11434",
            "postgresql://postgres:your-password@db.xxxx.supabase.co:5432/postgres",
            "postgresql+asyncpg://postgres:your-password@db.xxxx.supabase.co:5432/postgres",
        }
        if v in placeholders:
            raise ValueError(
                f"'{info.field_name}' enthält einen Platzhalter-Wert. "
                "Bitte echten Wert in .env eintragen."
            )
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Sicherstellen, dass ein gültiger Python-Logging-Level angegeben ist."""
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level muss einer von {valid} sein, erhalten: '{v}'")
        return upper

    def check_ollama_connection(self) -> bool:
        """Prüfen ob der Ollama-VPS via Tailscale erreichbar ist.

        Sendet einen HTTP GET auf {ollama_base_url}/api/tags mit kurzem Timeout.

        Returns:
            True wenn erreichbar, False bei Fehler.
        """
        url = f"{self.ollama_base_url}/api/tags"
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.warning(
                "Ollama VPS nicht erreichbar – ist Tailscale aktiv? (%s)", exc
            )
            return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Gecachte Anwendungseinstellungen zurückgeben.

    Raises:
        SystemExit: Wenn eine Pflicht-Variable fehlt oder ungültig ist.
    """
    try:
        settings = Settings()
        logging.basicConfig(level=settings.log_level)
        return settings
    except Exception as exc:
        raise SystemExit(
            f"\n[KONFIGURATIONSFEHLER] Einstellungen konnten nicht geladen werden:\n{exc}\n"
            "Tipp: .env.example nach .env kopieren und Werte eintragen."
        ) from exc
