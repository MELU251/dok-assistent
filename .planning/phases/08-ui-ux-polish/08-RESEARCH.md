# Phase 8: UI/UX Polish - Research

**Researched:** 2026-03-18
**Domain:** Chainlit UI — command handling, message formatting, error handling, source citation rendering
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-01 | Beim ersten Chat-Start erscheint eine deutschsprachige Willkommensnachricht die erklärt: wie man ein Dokument hochlädt, wie man Fragen stellt, und was das System kann und nicht kann | `_build_welcome_content()` exists in `app.py` — partially implemented; content must be verified/extended to fully cover all three stated sub-points |
| UI-02 | Nutzer kann jederzeit im laufenden Chat die Liste der aktuell geladenen Dokumente abrufen (nicht nur beim Session-Start) | `/dokumente`-Befehl fehlt — `on_message()` in `app.py` muss den neuen Befehlszweig erhalten; `get_indexed_documents()` ist bereits importiert |
| UI-03 | Alle benutzersichtbaren Fehlermeldungen erscheinen auf Deutsch; keine technischen englischen Fehlertexte (RuntimeError, connection refused etc.) erreichen den Nutzer | Alle `cl.Message`-Fehlerblöcke in `app.py` sind auf Deutsch — formale Verifikation fehlt; kein systematischer Test aller Fehlerpfade |
| UI-04 | Quellenangaben werden als formatierte Karte prominent dargestellt (Dateiname + Seite visuell hervorgehoben), nicht als Fließtext am Antwortende | `sources_block` in `_run_rag_flow()` ist plain Markdown-Text — muss zu `cl.Text`/visueller Karte umgebaut werden |
</phase_requirements>

---

## Summary

Phase 8 ist eine Gap-Closure-Phase: Die vier UI-Anforderungen (UI-01 bis UI-04) wurden nie formal geplant oder verifiziert. Ein Teil davon wurde während Phase 3 inline implementiert, aber die Implementierung ist teils unvollständig (UI-02, UI-04) und teils nicht formal verifiziert (UI-01, UI-03). Die Aufgaben sind alle in `app.py` lokalisiert — eine einzige Datei — und erfordern keine neuen Bibliotheken oder Architekturentscheidungen.

Die Implementierung teilt sich in zwei Typen: (1) **Neue Logik** — `/dokumente`-Befehl in `on_message()` und visuelle Quellenangaben in `_run_rag_flow()` — und (2) **Verifikation bestehender Logik** — Willkommensnachricht und Fehlertext-Vollständigkeit. Alle vier Requirements lassen sich mit Unit-Tests absichern, die das bestehende Mocking-Pattern aus `test_app_async.py` verwenden.

**Primary recommendation:** Alles in `app.py` umsetzen, kein neues Modul nötig. Für UI-04 `cl.Text`-Elemente mit `display="inline"` nutzen, nicht reinen Markdown-Text.

---

## Standard Stack

### Core (bereits installiert)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chainlit | 2.10.0 | UI-Framework, Message/Element/Action/Step API | Bereits produktiv im Einsatz |
| pytest + pytest-asyncio | installed | Unit-Tests für async app-Flows | Bereits eingerichtet (asyncio_mode=auto) |

### Chainlit UI-Primitiven für diese Phase

| Primitive | Zweck | Wann verwenden |
|-----------|-------|----------------|
| `cl.Message(content=..., elements=[])` | Hauptnachricht mit optionalen Elementen | Jede Nutzerantwort |
| `cl.Text(name=..., content=..., display="inline")` | Visuelle Text-Karte/Block im Chat | UI-04: Quellenangaben als Karte |
| `cl.Action(name=..., label=...)` | Schaltflächen in Nachrichten | Bereits für Upload/Workflow genutzt |
| `cl.Step(name=...)` als async context manager | Fortschrittsschritte | Bereits für Upload/Delete-Flow genutzt |

### Kein zusätzliches Install nötig

```bash
# Keine neuen Pakete — alles ist bereits installiert
```

---

## Architecture Patterns

### Aktueller Zustand in app.py (relevant für Phase 8)

```
app.py
├── _build_welcome_content()    → UI-01: Willkommensnachricht (partial)
├── on_chat_start()             → ruft _build_welcome_content() auf
├── on_message()                → UI-02: fehlt /dokumente-Branch
│   ├── /filter Branch          → (fertig)
│   ├── /loeschen Branch        → (fertig)
│   └── RAG-Branch              → (fertig)
├── _run_rag_flow()             → UI-03: Fehlertext (verifizieren)
│                               → UI-04: sources_block (umbauen)
└── _run_upload_flow()          → UI-03: Fehlertext (verifizieren)
    _run_delete_flow()          → UI-03: Fehlertext (verifizieren)
    _run_workflow_flow()        → UI-03: Fehlertext (verifizieren)
    _run_workflow_generation()  → UI-03: Fehlertext (verifizieren)
```

### Pattern 1: Neuer Slash-Command in on_message()

**What:** Neuen `/dokumente`-Branch im `on_message()`-Handler einfügen, analog zum bestehenden `/filter`- und `/loeschen`-Muster.
**When to use:** Immer wenn eine neue Chat-Direktive gebraucht wird.

```python
# Einfügen VOR der regulären RAG-Anfrage, nach /loeschen-Block
if text.lower().startswith("/dokumente"):
    docs = get_indexed_documents()
    if docs:
        doc_list = "\n".join(f"  - {d}" for d in docs)
        content = f"**Aktuell indexierte Dokumente ({len(docs)}):**\n{doc_list}"
    else:
        content = "_Keine Dokumente indexiert. Laden Sie ein Dokument hoch._"
    await cl.Message(content=content).send()
    return
```

### Pattern 2: Quellenangaben als cl.Text-Element (UI-04)

**What:** Statt plaintext `sources_block` in die Message zu schreiben, ein `cl.Text`-Element mit `display="inline"` erstellen. Das rendert als visuell abgesetzter Block im Chainlit-Chat.
**When to use:** Immer wenn strukturierte Metadaten (Quellenangaben) prominent angezeigt werden sollen.

```python
# In _run_rag_flow() — ersetzt den sources_block-String-Ansatz
elements = []
if result["sources"]:
    sources_text = "\n".join(f"- {s}" for s in result["sources"])
    elements.append(
        cl.Text(
            name="Quellen",
            content=f"**Quellen:**\n{sources_text}",
            display="inline",
        )
    )

cost_cent = result["cost_eur"] * 100
cost_note = f"\n\n<sub>Kosten dieser Anfrage: ~{cost_cent:.3f} Cent</sub>"

await cl.Message(
    content=result["answer"] + cost_note,
    elements=elements,
).send()
```

### Pattern 3: Willkommensnachricht vollständig (UI-01)

**What:** `_build_welcome_content()` erweitern um explizit alle drei Punkte zu adressieren: Dokument hochladen, Fragen stellen, System-Grenzen.

```python
def _build_welcome_content() -> str:
    """Willkommensnachricht mit Dokumentliste und vollständiger Bedienungsanleitung."""
    docs = get_indexed_documents()

    if docs:
        doc_list = "\n".join(f"  - {d}" for d in docs)
        library_section = f"**Verfügbare Dokumente ({len(docs)}):**\n{doc_list}"
    else:
        library_section = (
            "_Noch keine Dokumente indexiert. "
            "Laden Sie ein Dokument hoch um zu beginnen._"
        )

    return (
        "## Willkommen beim Dokumenten-Assistenten\n\n"
        "Ich beantworte Ihre Fragen direkt aus Ihren Unterlagen — "
        "mit Quellenangabe (Dateiname + Seite).\n\n"
        f"{library_section}\n\n"
        "---\n"
        "**So funktioniert es:**\n"
        "- **Dokument hochladen:** Klicken Sie _Dokument hochladen_ — "
        "unterstützt PDF, DOCX und XLSX (max. 50 MB)\n"
        "- **Fragen stellen:** Tippen Sie einfach Ihre Frage — "
        "ich durchsuche alle indexierten Dokumente\n"
        "- **Wichtig:** Ich beantworte nur Fragen auf Basis der hochgeladenen Dokumente. "
        "Informationen die nicht in Ihren Unterlagen stehen, kann ich nicht liefern.\n\n"
        "**Befehle:**\n"
        "- `/dokumente` — aktuelle Dokumentenliste anzeigen\n"
        "- `/filter [dateiname]` — Suche auf ein bestimmtes Dokument eingrenzen\n"
        "- `/loeschen [dateiname]` — Dokument vollständig entfernen\n"
    )
```

### Pattern 4: Fehlertext-Audit (UI-03)

**What:** Alle `except`-Blöcke in `app.py` prüfen — keiner darf rohe Exception-Typen oder englische Meldungen an den Nutzer senden.
**Aktuelles Muster:** `_(Intern: {type(exc).__name__})_` taucht in mehreren Blöcken auf. Das ist technischer Jargon und verletzt UI-03.
**Fix:** Den `_(Intern: ...)_`-Suffix aus Fehlermeldungen entfernen oder durch einen deutschen generischen Text ersetzen.

```python
# Vorher (verletzt UI-03):
content=f"Fehler beim Erstellen der Embeddings für '{filename}'.\n\n"
        f"_(Intern: {type(exc).__name__})_"

# Nachher (UI-03-konform):
content=(
    f"Fehler beim Erstellen der Einbettungen für '{filename}'.\n\n"
    "Mögliche Ursachen:\n"
    "- Ollama VPS nicht erreichbar (Tailscale aktiv?)\n"
    "- Supabase-Verbindung unterbrochen\n\n"
    "Bitte prüfen Sie die Verbindung und versuchen Sie es erneut."
)
```

### Recommended Project Structure (keine Änderung)

```
app.py            ← alle UI-Änderungen hier
tests/
├── test_app_ui.py   ← neue Testdatei für UI-01..04
└── (bestehende Dateien unverändert)
```

### Anti-Patterns to Avoid

- **Neues Modul für UI-Logik erstellen:** Nicht nötig — alles bleibt in `app.py`
- **cl.Text mit `display="side"`:** Rendert als Seitenleiste, nicht inline sichtbar ohne Klick — für Quellenangaben suboptimal
- **Exception-Typ in User-Message:** `type(exc).__name__` (z.B. `RuntimeError`, `ConnectionError`) ist englischer Jargon — verletzt UI-03

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Visuelle Quellenangaben | Eigenes HTML/CSS-Template | `cl.Text(display="inline")` | Chainlit rendert das nativ im Chat |
| Slash-Command-Parser | Eigener Parser mit Regex | `text.lower().startswith("/dokumente")` | Einfachstes Mittel, konsistent mit /filter und /loeschen |
| Fehler-Logging | Custom Error-Formatter | `logger.error(...)` + deutsches `cl.Message` | Bestehendes Pattern in allen Flows |

**Key insight:** Alle vier Requirements sind reine `app.py`-Änderungen. Die Infrastruktur (Chainlit, `get_indexed_documents`, Fehler-Logging) ist fertig. Es geht ausschließlich um korrekte Verwendung bestehender Primitiven.

---

## Common Pitfalls

### Pitfall 1: cl.Text display-Wert
**What goes wrong:** `cl.Text(display="side")` öffnet die Quelle als Seitenleiste — der Nutzer sieht sie erst nach einem Klick. `display="inline"` rendert direkt im Nachrichtenfluss.
**Why it happens:** Chainlit-Default ist `"side"`, der explizit überschrieben werden muss.
**How to avoid:** Immer `display="inline"` für Quellenangaben.
**Warning signs:** Quellenangaben erscheinen nicht direkt unter der Antwort.

### Pitfall 2: `_(Intern: ...)_` in Fehlertexten
**What goes wrong:** Mehrere Fehlerblöcke in `app.py` senden `type(exc).__name__` (z.B. `RuntimeError`) an den Nutzer. Das ist englischer Jargon und verletzt UI-03 explizit.
**Why it happens:** Wurde als Debug-Hilfe inline implementiert, nie formal geprüft.
**How to avoid:** Alle `except`-Blöcke auflisten und auf `_(Intern: ...)_`-Suffix prüfen, entfernen oder durch deutschen Text ersetzen.
**Warning signs:** Grep auf `type(exc).__name__` in `app.py` liefert Treffer in an den User gesendeten Messages.

### Pitfall 3: on_message-Branch-Reihenfolge
**What goes wrong:** Wenn `/dokumente`-Branch nach `/loeschen` eingefügt wird aber VOR dem `return`-Statement liegt, fallen nachfolgende Befehle durch.
**Why it happens:** Jeder Branch muss mit `return` abschließen.
**How to avoid:** Neuen `/dokumente`-Block analog zu `/filter`-Block einbauen — mit eigenem `return`.

### Pitfall 4: Willkommensnachricht-Test schlägt fehl wenn Supabase live ist
**What goes wrong:** `get_indexed_documents()` macht einen echten Supabase-RPC-Call. Im Unit-Test muss er gemockt werden.
**Why it happens:** `app.py` importiert `get_indexed_documents` direkt aus `src.retrieval`.
**How to avoid:** `patch("app.get_indexed_documents", return_value=[...])` im Test.

### Pitfall 5: pytest-asyncio-Modus ist auto
**What goes wrong:** Wenn man `@pytest.mark.asyncio` vergisst, läuft der Test trotzdem — wegen `asyncio_mode = auto` in `pytest.ini`. Kein Fehler, aber das kann bei Fehlerbehebung verwirren.
**Why it happens:** `asyncio_mode = auto` macht alle `async def`-Tests automatisch zu asyncio-Tests.
**How to avoid:** Weiter so — aber wissen dass der Marker optional ist.

---

## Code Examples

### Vollständiges Mocking-Pattern für app.py-Tests

```python
# Source: tests/test_app_async.py (bestehendes Pattern)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestDokumenteCommand:
    """UI-02: /dokumente-Befehl zeigt aktuelle Dokumentenliste."""

    async def test_dokumente_command_with_docs(self):
        import app

        mock_session = MagicMock()
        mock_session.get.return_value = None  # kein source_filter

        with (
            patch("app.get_indexed_documents", return_value=["handbuch.pdf", "vertrag.docx"]),
            patch("app.cl.Message") as mock_message,
        ):
            mock_message.return_value.send = AsyncMock(return_value=None)
            msg = MagicMock()
            msg.content = "/dokumente"
            await app.on_message(msg)

        mock_message.assert_called_once()
        content = mock_message.call_args[1]["content"] if mock_message.call_args[1] else mock_message.call_args[0][0]
        assert "handbuch.pdf" in content
        assert "vertrag.docx" in content

    async def test_dokumente_command_no_docs(self):
        import app

        with (
            patch("app.get_indexed_documents", return_value=[]),
            patch("app.cl.Message") as mock_message,
        ):
            mock_message.return_value.send = AsyncMock(return_value=None)
            msg = MagicMock()
            msg.content = "/dokumente"
            await app.on_message(msg)

        content = mock_message.call_args[1].get("content", "") or mock_message.call_args[0][0]
        assert "keine" in content.lower() or "Keine" in content
```

### cl.Text für Quellenangaben

```python
# In _run_rag_flow() — Quellenangaben als inline Element
elements = []
if result["sources"]:
    sources_text = "\n".join(f"- {s}" for s in result["sources"])
    elements.append(
        cl.Text(
            name="Quellen",
            content=f"**Quellen:**\n{sources_text}",
            display="inline",
        )
    )

cost_cent = result["cost_eur"] * 100
cost_note = f"\n\n<sub>Kosten dieser Anfrage: ~{cost_cent:.3f} Cent</sub>"

await cl.Message(
    content=result["answer"] + cost_note,
    elements=elements,
).send()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Quellenangaben als Markdown-Text in `content` | `cl.Text(display="inline")` als Element | Chainlit 1.x → 2.x | Visuelle Abgrenzung, klarer erkennbar |
| `cl.Text(display="side")` Standard | `display="inline"` explizit setzen | Chainlit 2.x | Inline-Render ohne Klick |

**Kein Deprecated-Pattern relevant:** Die genutzten Chainlit-Primitiven (`cl.Message`, `cl.Text`, `cl.Action`, `cl.Step`) sind stabil in Chainlit 2.10.0.

---

## Open Questions

1. **cl.Text content-Rendering in Chainlit 2.10.0**
   - What we know: `cl.Text(display="inline")` existiert und rendert inline laut Chainlit-Dokumentation
   - What's unclear: Ob Markdown innerhalb des `content`-Felds (Fettschrift, Listen) vollständig gerendert wird oder als Plaintext erscheint
   - Recommendation: Nach Implementierung im laufenden Chainlit manuell verifizieren; Fallback: Quellen als Markdown-Section in `content` der Message direkt (aktuelles Verhalten), aber mit `---`-Trennlinie und Emoji-Icon als visuelle Hervorhebung

2. **UI-01 Inhalt: "was das System nicht kann"**
   - What we know: Die aktuelle Willkommensnachricht erklärt Upload und Fragen stellen
   - What's unclear: Welche Grenzen explizit genannt werden sollen (kein Web-Zugriff? keine Sprachen außer Deutsch? keine Bilder in PDFs?)
   - Recommendation: Standard-Set dokumentieren: "Ich beantworte nur Fragen auf Basis der hochgeladenen Dokumente" — kein Internetzugriff, keine externen Quellen

---

## Validation Architecture

> nyquist_validation ist in .planning/config.json aktiv (true) — Abschnitt ist erforderlich.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` (asyncio_mode = auto) |
| Quick run command | `pytest tests/test_app_ui.py -v` |
| Full suite command | `pytest tests/ -v -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Willkommensnachricht enthält alle drei Pflichtinhalte (Upload-Erklärung, Fragen-Erklärung, Systemgrenzen) | unit | `pytest tests/test_app_ui.py::TestWelcomeMessage -v` | ❌ Wave 0 |
| UI-02 | `/dokumente`-Befehl antwortet mit aktueller Dokumentenliste (mit und ohne Dokumente) | unit | `pytest tests/test_app_ui.py::TestDokumenteCommand -v` | ❌ Wave 0 |
| UI-03 | Alle Fehler-Branches senden deutschen Text ohne `type(exc).__name__` | unit | `pytest tests/test_app_ui.py::TestGermanErrors -v` | ❌ Wave 0 |
| UI-04 | `_run_rag_flow()` erzeugt `cl.Text`-Element mit `display="inline"` für Quellenangaben | unit | `pytest tests/test_app_ui.py::TestSourceCitations -v` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_app_ui.py -v`
- **Per wave merge:** `pytest tests/ -v -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_app_ui.py` — deckt UI-01, UI-02, UI-03, UI-04 ab (alle vier Requirements)
- Kein neues Framework-Install nötig — pytest + pytest-asyncio bereits installiert und konfiguriert

---

## Sources

### Primary (HIGH confidence)

- Direktes Code-Review: `app.py` (vollständig gelesen) — aktueller Stand aller UI-Flows
- `.planning/v1.0-MILESTONE-AUDIT.md` — Audit-Evidenz für UI-01..04, exakte Gap-Beschreibungen
- `.planning/milestones/v1.0-REQUIREMENTS.md` — verbindliche Requirement-Texte
- `.planning/codebase/TESTING.md` + `tests/test_app_async.py` — bestehende Mocking-Pattern

### Secondary (MEDIUM confidence)

- Chainlit 2.10.0 `cl.Text(display="inline")` — aus vorherigen Phasen bekannt und in Produktionsumgebung aktiv; spezifisches Rendering-Verhalten von Markdown in `cl.Text.content` nicht unabhängig verifiziert

### Tertiary (LOW confidence)

- Keine LOW-confidence-Quellen. Alle Findings basieren direkt auf dem bestehenden Projektcode und der Audit-Dokumentation.

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — Chainlit 2.10.0 bereits installiert und produktiv
- Architecture: HIGH — alle Änderungen in einer Datei (`app.py`), bestehende Pattern klar dokumentiert
- Pitfalls: HIGH — aus Audit-Evidenz und direkter Code-Inspektion abgeleitet

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (Chainlit-API ist stabil; keine schnellen Breaking Changes erwartet)
