"""Geteilte externe Client-Singletons: Embedder und Supabase."""

from functools import lru_cache

from langchain_ollama import OllamaEmbeddings
from supabase import create_client

from src.config import get_settings


@lru_cache(maxsize=1)
def _get_embedder() -> OllamaEmbeddings:
    """OllamaEmbeddings-Singleton – wird einmal erstellt und wiederverwendet."""
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


@lru_cache(maxsize=1)
def _get_supabase_client():
    """Supabase-Client-Singleton – wird einmal erstellt und wiederverwendet."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
