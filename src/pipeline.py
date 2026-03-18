"""RAG pipeline: retrieve relevant chunks and generate an answer with Claude."""

import logging
import time
from typing import Any

from anthropic import Anthropic
from langchain_core.documents import Document

from src.config import get_settings
from src.retrieval import search

logger = logging.getLogger(__name__)

# Prompt-Template: Kontext geht in system, Frage in messages (CHAT-01)
_SYSTEM_PROMPT_TEMPLATE = """Du bist ein hilfreicher Assistent für das Unternehmen. Beantworte die Frage \
ausschließlich auf Basis der folgenden Dokumenten-Auszüge.

Wenn die Antwort nicht in den Dokumenten gefunden werden kann, sage klar:
"Diese Information ist in den vorliegenden Dokumenten nicht enthalten."

Nenne am Ende deiner Antwort immer die Quellen im Format:
📄 Quelle: [Dateiname], Seite [X]

Dokumente:
{context}"""

# Cost estimates for claude-sonnet-4-6 (USD per 1M tokens, 2024 pricing)
_INPUT_COST_PER_1M = 3.0
_OUTPUT_COST_PER_1M = 15.0
_USD_TO_EUR = 0.86


def _build_context(docs: list[Document]) -> str:
    """Format retrieved documents into a context string for the prompt.

    Args:
        docs: List of Document chunks from vector search.

    Returns:
        Formatted context string with source labels.
    """
    parts = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        parts.append(f"[{i}] {source} (Seite {page}):\n{doc.page_content}")
    return "\n\n".join(parts)


def _extract_sources(docs: list[Document]) -> list[str]:
    """Extract deduplicated source references from documents.

    Args:
        docs: List of Document chunks.

    Returns:
        List of unique 'filename, page X' strings.
    """
    seen: set[str] = set()
    sources: list[str] = []
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        label = f"{source}, Seite {page}"
        if label not in seen:
            seen.add(label)
            sources.append(label)
    return sources


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate query cost in EUR.

    Args:
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens generated.

    Returns:
        Estimated cost in EUR.
    """
    cost_usd = (
        (input_tokens / 1_000_000) * _INPUT_COST_PER_1M
        + (output_tokens / 1_000_000) * _OUTPUT_COST_PER_1M
    )
    return cost_usd * _USD_TO_EUR


def answer(
    question: str,
    tenant_id: str = "default",
    source_filter: str | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """Answer a question using retrieved document context via Claude.

    Retrieves relevant chunks, builds the RAG prompt, calls
    claude-sonnet-4-6, and returns the answer with sources and cost.

    Args:
        question: Natural language question from the user.
        tenant_id: Tenant identifier to scope the document search.
        source_filter: Optionaler Dateiname zur Eingrenzung der Suche auf ein Dokument.
        history: Optionale Gespraechshistorie als Liste von role/content-Dicts.
                 Maximal die letzten 6 Eintraege werden verwendet (3 Turns).

    Returns:
        Dictionary with keys:
            - answer (str): Generated answer in German.
            - sources (list[str]): Deduplicated source references.
            - cost_eur (float): Estimated cost for this query.

    Raises:
        RuntimeError: If retrieval or LLM call fails.
    """
    settings = get_settings()
    start_time = time.monotonic()

    # Schritt 1: Relevante Chunks abrufen
    logger.info("Retrieving context for question (tenant=%s)", tenant_id)
    docs = search(question, tenant_id=tenant_id, source_filter=source_filter)

    if not docs:
        logger.warning("No relevant documents found for query.")
        return {
            "answer": "Diese Information ist in den vorliegenden Dokumenten nicht enthalten.",
            "sources": [],
            "cost_eur": 0.0,
        }

    # Schritt 2: System-Prompt mit Dokumentenkontext aufbauen
    context_str = _build_context(docs)
    system_content = _SYSTEM_PROMPT_TEMPLATE.format(context=context_str)

    # Schritt 3: Nachrichtenliste aufbauen (History-Fenster + aktuelle Frage)
    # CHAT-01: Letzte 3 Turns (6 Messages) aus der History
    window = [m for m in (history or [])[-6:] if (m.get("content") or "").strip()]
    messages = window + [{"role": "user", "content": question}]

    # Schritt 4: Claude aufrufen
    logger.info("Rufe Claude claude-sonnet-4-6 auf...")
    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_content,
            messages=messages,
        )
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc)
        raise RuntimeError(f"LLM call failed: {exc}") from exc

    elapsed = time.monotonic() - start_time
    answer_text = response.content[0].text

    # Step 4: Calculate costs
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_eur = _estimate_cost(input_tokens, output_tokens)

    logger.info(
        "Answer generated in %.2fs | tokens: %d in / %d out | cost: %.4f EUR",
        elapsed,
        input_tokens,
        output_tokens,
        cost_eur,
    )

    return {
        "answer": answer_text,
        "sources": _extract_sources(docs),
        "cost_eur": cost_eur,
    }
