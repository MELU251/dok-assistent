"""Verbindungstest fuer alle externen Dienste.

Fuehrt Live-Checks gegen Ollama, Supabase und Claude durch.
Kein Mocking - echte Verbindungen erforderlich.

Ausfuehren:
    pytest tests/test_connection.py -v -s
"""

import httpx
import pytest


def _ok(label: str, detail: str = "") -> None:
    msg = f"  [OK]    {label}"
    if detail:
        msg += f"  =>  {detail}"
    print(msg)


def _fail(label: str, reason: str = "") -> None:
    msg = f"  [FAIL]  {label}"
    if reason:
        msg += f"  =>  {reason}"
    print(msg)


# ---------------------------------------------------------------------------
# Check 1: Ollama VPS erreichbar?
# ---------------------------------------------------------------------------

class TestOllamaConnection:

    def test_vps_reachable(self):
        """GET /api/tags muss mit HTTP 200 antworten."""
        from src.config import get_settings
        settings = get_settings()
        url = f"{settings.ollama_base_url}/api/tags"

        print(f"\n[1] Ollama VPS: {url}")
        try:
            r = httpx.get(url, timeout=5.0)
            r.raise_for_status()
            _ok("VPS erreichbar", f"HTTP {r.status_code}")
        except Exception as exc:
            _fail("VPS NICHT erreichbar", str(exc))
            pytest.fail(
                f"Ollama VPS nicht erreichbar: {exc}\n"
                "=> Ist Tailscale aktiv? Laeuft 'ollama serve' auf dem VPS?"
            )

    def test_nomic_model_available(self):
        """nomic-embed-text muss in der Modellliste des VPS vorhanden sein."""
        from src.config import get_settings
        settings = get_settings()
        url = f"{settings.ollama_base_url}/api/tags"

        print(f"\n[2] Modell '{settings.ollama_embed_model}' verfuegbar?")
        try:
            r = httpx.get(url, timeout=5.0)
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            # Teilstring-Vergleich: "nomic-embed-text:latest" enthaelt "nomic-embed-text"
            match = any(settings.ollama_embed_model in m for m in models)
            if match:
                _ok("Modell gefunden", f"Verfuegbare Modelle: {models}")
            else:
                _fail("Modell NICHT gefunden", f"Verfuegbare Modelle: {models}")
                pytest.fail(
                    f"'{settings.ollama_embed_model}' nicht auf dem VPS.\n"
                    f"=> Auf VPS ausfuehren: ollama pull {settings.ollama_embed_model}"
                )
        except Exception as exc:
            pytest.fail(f"Modellliste konnte nicht abgerufen werden: {exc}")

    def test_embedding_dimension(self):
        """Einen kurzen Text einbetten und Dimension pruefen (muss 768 sein)."""
        from langchain_ollama import OllamaEmbeddings
        from src.config import get_settings
        settings = get_settings()

        print(f"\n[3] Embedding-Test mit '{settings.ollama_embed_model}'")
        try:
            embedder = OllamaEmbeddings(
                model=settings.ollama_embed_model,
                base_url=settings.ollama_base_url,
            )
            vector = embedder.embed_query("Hallo Welt")
            dim = len(vector)
            expected = 768
            status = "OK" if dim == expected else f"ERWARTET {expected}!"
            _ok("Embedding erstellt", f"Dimension: {dim} [{status}]")
            assert dim == expected, (
                f"Falsche Vektordimension: {dim} (erwartet {expected}).\n"
                "=> Supabase-Tabelle muss vector(768) verwenden!"
            )
        except Exception as exc:
            _fail("Embedding fehlgeschlagen", str(exc))
            pytest.fail(str(exc))


# ---------------------------------------------------------------------------
# Check 2: Supabase erreichbar und Tabelle vorhanden?
# ---------------------------------------------------------------------------

class TestSupabaseConnection:

    def test_table_accessible(self):
        """document_chunks-Tabelle in Supabase muss abfragbar sein."""
        from supabase import create_client
        from src.config import get_settings
        settings = get_settings()

        print(f"\n[4] Supabase: {settings.supabase_url}")
        try:
            client = create_client(settings.supabase_url, settings.supabase_service_key)
            result = client.table("document_chunks").select("id").limit(1).execute()
            count = len(result.data) if result.data else 0
            _ok(
                "Tabelle 'document_chunks' erreichbar",
                f"{count} Eintraege sichtbar (evtl. leer bei erstem Start)",
            )
        except Exception as exc:
            _fail("Supabase-Verbindung fehlgeschlagen", str(exc))
            pytest.fail(
                f"Supabase nicht erreichbar: {exc}\n"
                "=> URL und SERVICE_KEY in .env pruefen\n"
                "=> SQL-Migration in Supabase ausgefuehrt? (README.md)"
            )


# ---------------------------------------------------------------------------
# Check 3: Claude API funktionsfaehig?
# ---------------------------------------------------------------------------

class TestClaudeApi:

    def test_short_completion(self):
        """Kurze Claude-Anfrage, gibt Token-Count aus."""
        from anthropic import Anthropic
        from src.config import get_settings
        settings = get_settings()

        print("\n[5] Claude API (claude-sonnet-4-6)")
        try:
            client = Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=32,
                messages=[{"role": "user", "content": "Antworte mit genau einem Wort: Hallo"}],
            )
            text = response.content[0].text.strip()
            in_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens
            cost_eur = ((in_tok / 1_000_000) * 3.0 + (out_tok / 1_000_000) * 15.0) * 0.92
            _ok(
                "Claude API erreichbar",
                f"Antwort: '{text}' | {in_tok} In- / {out_tok} Out-Tokens | "
                f"Kosten: ~{cost_eur * 100:.4f} Cent",
            )
        except Exception as exc:
            _fail("Claude API fehlgeschlagen", str(exc))
            pytest.fail(f"Claude API nicht erreichbar: {exc}")
