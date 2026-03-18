"""Extraktions-Modul: Zerlegt ein Lastenheft in strukturierte Anforderungen.

Laedt einen Satz von Dokument-Chunks, baut einen Kontext-String und ruft
Claude auf, um ein strukturiertes AngebotData-Objekt zu erzeugen.
"""

import json
import logging
import time
from typing import Any

from anthropic import Anthropic
from langchain_core.documents import Document
from pydantic import BaseModel

from src.config import get_settings

logger = logging.getLogger(__name__)

# Cost estimates (identisches Muster wie pipeline.py)
_INPUT_COST_PER_1M = 3.0
_OUTPUT_COST_PER_1M = 15.0
_USD_TO_EUR = 0.86

_SYSTEM_PROMPT = """\
Du bist ein technischer Analyst. Analysiere das folgende Lastenheft und extrahiere \
die Anforderungen strukturiert als JSON.

Antworte NUR mit einem JSON-Objekt in diesem Format (kein Markdown, kein Erklaerungstext):
{
  "title": "Kurztitel des Projekts/Produkts (max. 80 Zeichen)",
  "summary": "Zusammenfassung was benoetigt wird (2-4 Saetze)",
  "requirements": ["Anforderung 1", "Anforderung 2"],
  "special_requests": ["Sonderwunsch 1"]
}

Regeln:
- requirements: Pflichtanforderungen, die erfuellt werden MUESSEN
- special_requests: Wuensche, optionale Features, Nice-to-haves (kann leere Liste sein)
- Antworte auf Deutsch
- Kein Feld darf fehlen; special_requests darf [] sein\
"""


class AngebotData(BaseModel):
    """Strukturierte Anforderungen aus einem Lastenheft.

    Attributes:
        title: Kurztitel des Projekts oder Produkts.
        summary: Zusammenfassung des Anforderungsdokuments (2-4 Saetze).
        requirements: Liste der Pflichtanforderungen.
        special_requests: Liste optionaler Wuensche / Nice-to-haves.
    """

    title: str
    summary: str
    requirements: list[str]
    special_requests: list[str]


def extract_requirements(chunks: list[Document]) -> AngebotData:
    """Extrahiert strukturierte Anforderungen aus Lastenheft-Chunks via Claude.

    Args:
        chunks: Liste von Dokument-Chunks aus dem Lastenheft.

    Returns:
        AngebotData-Objekt mit Titel, Zusammenfassung, Anforderungen und
        Sonderwuenschen.

    Raises:
        ValueError: Wenn chunks leer ist oder Claude kein gueltiges JSON
            zurueckgibt.
        RuntimeError: Wenn der Claude-API-Aufruf fehlschlaegt.
    """
    if not chunks:
        raise ValueError("Keine Chunks uebergeben — Lastenheft ist leer oder nicht lesbar.")

    context = _build_context(chunks)
    settings = get_settings()
    start_time = time.monotonic()

    logger.info("Starte Lastenheft-Extraktion (%d Chunks)", len(chunks))

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Lastenheft:\n{context}"}],
        )
    except Exception as exc:
        logger.error("Claude API-Aufruf fehlgeschlagen: %s", exc)
        raise RuntimeError(f"Extraktion fehlgeschlagen: {exc}") from exc

    elapsed = time.monotonic() - start_time
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_eur = _estimate_cost(input_tokens, output_tokens)

    logger.info(
        "Extraktion abgeschlossen in %.2fs | tokens: %d in / %d out | cost: %.4f EUR",
        elapsed,
        input_tokens,
        output_tokens,
        cost_eur,
    )

    raw_text = response.content[0].text.strip()
    return _parse_response(raw_text)


def _build_context(chunks: list[Document]) -> str:
    """Chunks zu einem Kontext-String zusammenfuehren."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.metadata.get("source", "unbekannt")
        page = chunk.metadata.get("page", "?")
        parts.append(f"[{i}] {source} (Seite {page}):\n{chunk.page_content}")
    return "\n\n".join(parts)


def _parse_response(raw: str) -> AngebotData:
    """Claude-Antwort als JSON parsen und in AngebotData umwandeln.

    Args:
        raw: Roher Antwort-String von Claude.

    Returns:
        Validiertes AngebotData-Objekt.

    Raises:
        ValueError: Wenn der Text kein gueltiges JSON oder ungueltiges Schema hat.
    """
    # Markdown-Code-Block entfernen falls vorhanden (Abweichung vom Prompt)
    text = raw
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Claude hat kein gueltiges JSON zurueckgegeben: {exc}\nAntwort: {raw[:200]}"
        ) from exc

    try:
        return AngebotData(**data)
    except Exception as exc:
        raise ValueError(f"JSON entspricht nicht dem AngebotData-Schema: {exc}") from exc


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Schaetzt die Kosten des Extraktions-Aufrufs in EUR."""
    cost_usd = (
        (input_tokens / 1_000_000) * _INPUT_COST_PER_1M
        + (output_tokens / 1_000_000) * _OUTPUT_COST_PER_1M
    )
    return cost_usd * _USD_TO_EUR
