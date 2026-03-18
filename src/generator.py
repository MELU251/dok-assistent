"""Generator-Modul: Erstellt einen Angebotsentwurf aus AngebotData und RAG-Kontext.

Nimmt ein strukturiertes AngebotData-Objekt und relevante Chunks aus historischen
Angeboten entgegen und ruft Claude auf, um einen vollstaendigen 4-Abschnitt-Entwurf
zu generieren.
"""

import logging
import time

from anthropic import Anthropic
from langchain_core.documents import Document

from src.config import get_settings
from src.extractor import AngebotData

logger = logging.getLogger(__name__)

# Cost estimates (identisches Muster wie pipeline.py und extractor.py)
_INPUT_COST_PER_1M = 3.0
_OUTPUT_COST_PER_1M = 15.0
_USD_TO_EUR = 0.86

_HIL_HINWEIS = (
    "KI-generierter Entwurf — Pflichtpruefung durch Vertriebsingenieur "
    "erforderlich vor Versand an Kunden."
)

_SYSTEM_PROMPT = """\
Du bist ein erfahrener Vertriebsingenieur. Erstelle auf Basis des folgenden \
Lastenhefts und der historischen Angebote einen professionellen Angebotsentwurf.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in diesem Format \
(kein Markdown, kein Erklaerungstext):
{
  "zusammenfassung": "Kurze Zusammenfassung des Angebots (3-5 Saetze)",
  "technische_loesung": "Beschreibung der vorgeschlagenen technischen Loesung",
  "lieferumfang": ["Position 1", "Position 2", "..."],
  "offene_punkte": ["Offener Punkt 1", "Offener Punkt 2", "..."]
}

Regeln:
- Basiere den Entwurf auf den historischen Angeboten und dem Lastenheft
- lieferumfang und offene_punkte sind Listen von Strings
- Antworte auf Deutsch
- Kein Feld darf fehlen\
"""


def generate_angebot(
    data: AngebotData,
    retrieved_chunks: list[Document],
) -> dict:
    """Generiert einen strukturierten Angebotsentwurf.

    Args:
        data: Strukturierte Anforderungen aus dem Lastenheft.
        retrieved_chunks: Relevante Chunks aus historischen Angeboten (RAG).

    Returns:
        Dict mit Keys: zusammenfassung, technische_loesung, lieferumfang,
        offene_punkte, sources, hil_hinweis, cost_eur.

    Raises:
        RuntimeError: Wenn der Claude-API-Aufruf fehlschlaegt.
        ValueError: Wenn Claude kein gueltiges JSON zurueckgibt.
    """
    context = _build_rag_context(retrieved_chunks)
    sources = _extract_source_names(retrieved_chunks)
    user_content = _build_user_message(data, context)

    settings = get_settings()
    start_time = time.monotonic()

    logger.info(
        "Starte Angebotsentwurf-Generierung (Anforderungen: %d, Chunks: %d)",
        len(data.requirements),
        len(retrieved_chunks),
    )

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as exc:
        logger.error("Claude API-Aufruf fehlgeschlagen: %s", exc)
        raise RuntimeError(f"Generierung fehlgeschlagen: {exc}") from exc

    elapsed = time.monotonic() - start_time
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_eur = _estimate_cost(input_tokens, output_tokens)

    logger.info(
        "Entwurf generiert in %.2fs | tokens: %d in / %d out | cost: %.4f EUR",
        elapsed,
        input_tokens,
        output_tokens,
        cost_eur,
    )

    sections = _parse_response(response.content[0].text.strip())
    return {
        **sections,
        "sources": sources,
        "hil_hinweis": _HIL_HINWEIS,
        "cost_eur": cost_eur,
    }


def _build_rag_context(chunks: list[Document]) -> str:
    """Historische Angebots-Chunks zu Kontext-String zusammenfuehren."""
    if not chunks:
        return "Keine historischen Angebote verfuegbar."
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.metadata.get("source", "unbekannt")
        page = chunk.metadata.get("page", "?")
        parts.append(f"[{i}] {source} (Seite {page}):\n{chunk.page_content}")
    return "\n\n".join(parts)


def _extract_source_names(chunks: list[Document]) -> list[str]:
    """Deduplizierte Quelldateinamen aus Chunks extrahieren."""
    seen: set[str] = set()
    sources: list[str] = []
    for chunk in chunks:
        src = chunk.metadata.get("source", "unbekannt")
        if src not in seen:
            seen.add(src)
            sources.append(src)
    return sources


def _build_user_message(data: AngebotData, rag_context: str) -> str:
    """User-Nachricht aus AngebotData und RAG-Kontext aufbauen."""
    reqs = "\n".join(f"- {r}" for r in data.requirements)
    specials = (
        "\n".join(f"- {s}" for s in data.special_requests)
        if data.special_requests
        else "Keine"
    )
    return (
        f"Lastenheft-Zusammenfassung: {data.summary}\n\n"
        f"Pflichtanforderungen:\n{reqs}\n\n"
        f"Sonderwuensche:\n{specials}\n\n"
        f"Historische Angebote (Referenz):\n{rag_context}"
    )


def _parse_response(raw: str) -> dict:
    """Claude-Antwort als JSON parsen und Pflicht-Keys pruefen.

    Args:
        raw: Roher Antwort-String von Claude.

    Returns:
        Dict mit den 4 Pflicht-Keys.

    Raises:
        ValueError: Wenn kein gueltiges JSON oder fehlende Keys.
    """
    import json

    text = raw
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.startswith("```")).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Claude hat kein gueltiges JSON zurueckgegeben: {exc}\nAntwort: {raw[:200]}"
        ) from exc

    required = {"zusammenfassung", "technische_loesung", "lieferumfang", "offene_punkte"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Fehlende Pflicht-Keys im generierten Entwurf: {missing}")

    return data


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Schaetzt die Kosten des Generierungs-Aufrufs in EUR."""
    cost_usd = (
        (input_tokens / 1_000_000) * _INPUT_COST_PER_1M
        + (output_tokens / 1_000_000) * _OUTPUT_COST_PER_1M
    )
    return cost_usd * _USD_TO_EUR
