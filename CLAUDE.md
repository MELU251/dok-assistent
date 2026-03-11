# KI-Dokumenten-Assistent – PoC

## Projektbeschreibung
Lokaler Proof-of-Concept für einen KI-gestützten Dokumenten-Assistenten für KMUs.
Nutzer können PDFs, Word- und Excel-Dateien hochladen und in natürlicher Sprache
Fragen dazu stellen. Antworten werden immer mit Quellenangabe (Dateiname + Seite) geliefert.

## Ziel dieses PoC
- RAG-Pipeline lokal zum Laufen bringen
- Antwortqualität und Kosten pro Query messen
- Basis für späteres Multi-Tenant SaaS

---

## Tech Stack

| Layer        | Technologie                                      |
|--------------|--------------------------------------------------|
| Sprache      | Python 3.11                                      |
| RAG          | LangChain 0.3+                                   |
| LLM          | Anthropic Claude (claude-sonnet-4-6) via API     |
| Embeddings   | nomic-embed-text via Ollama (Remote-VPS)         |
| Ollama-Host  | Hostinger VPS, erreichbar via Tailscale-IP       |
| Vektoren     | Supabase + pgvector                              |
| Dokumente    | Unstructured.io (PDF, DOCX, XLSX)                |
| Demo-UI      | Chainlit                                         |
| Env-Mgmt     | python-dotenv                                    |

### Wichtig: Kein OpenAI-Account nötig
Embeddings laufen über das selbst gehostete Ollama auf dem VPS.
Einzige externe bezahlte API: Anthropic (Claude) für die Antwortgenerierung.

---

## Infrastruktur: Ollama auf VPS via Tailscale

```
[Lokaler Rechner / Dev]
        |
   Tailscale VPN (verschlüsselt, kein offener Port im Internet)
        |
[Hostinger VPS]
  └── ollama serve  →  0.0.0.0:11434
  └── Modell: nomic-embed-text (768 Dimensionen)
```

- Ollama lauscht auf dem VPS auf `0.0.0.0:11434`
- Zugriff NUR über Tailscale-IP (z.B. `100.x.x.x`) → sicher, kein offener Port
- Im Code: `OLLAMA_BASE_URL=http://<TAILSCALE_IP>:11434`
- Kein API-Key für Ollama nötig

---

## Projektstruktur

```
dok-assistent/
├── CLAUDE.md                  ← diese Datei
├── .env                       ← Secrets (nie committen!)
├── .env.example               ← Vorlage
├── .gitignore
├── requirements.txt
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── config.py              ← Alle Env-Variablen via Pydantic BaseSettings
│   ├── ingest.py              ← Dokumente laden, chunken, embedden, speichern
│   ├── retrieval.py           ← Similarity Search in pgvector
│   └── pipeline.py            ← RAG-Pipeline: Frage → Kontext → Claude → Antwort
│
├── app.py                     ← Chainlit Chat-UI
├── ingest_cli.py              ← CLI: python ingest_cli.py --file pfad.pdf
│
├── docs/                      ← Test-Dokumente (nicht committen)
│   └── .gitkeep
│
└── tests/
    ├── test_connection.py     ← Ollama + Supabase Verbindung prüfen
    ├── test_ingest.py
    └── test_pipeline.py
```

---

## Kernprinzipien & Coding-Regeln

### Allgemein
- **Sprache**: Kommentare, Docstrings, Log-Ausgaben auf **Deutsch**
- **Antworten**: Claude antwortet auf Deutsch mit Quellenangabe
- **Fehlerbehandlung**: Alle externen Calls (Claude API, Supabase, Ollama) mit try/except
- **Logging**: `logging` statt `print()`, Level INFO für normale Ops
- **Secrets**: Niemals IPs oder Keys im Code – immer `.env`

### Python-Stil
- Type Hints überall
- Pydantic `BaseSettings` für `config.py`
- Max. ~30 Zeilen pro Funktion, eine Aufgabe pro Funktion
- Google-Style Docstrings für alle öffentlichen Funktionen

### Ollama / Embedding
- Modell: `nomic-embed-text` → erzeugt Vektoren mit **768 Dimensionen**
- Supabase-Tabelle muss `vector(768)` verwenden (nicht 1536!)
- Verbindung immer aus `OLLAMA_BASE_URL` lesen
- Beim Start: Health-Check auf `{OLLAMA_BASE_URL}/api/tags`
- Bei Fehler: sprechende Meldung ausgeben:
  `"Ollama VPS nicht erreichbar – ist Tailscale aktiv?"`

### RAG
- Chunk-Größe: **500 Tokens**, Overlap: **50 Tokens**
- **k=4** Chunks pro Query
- Metadaten: `source`, `page`, `tenant_id`
- LLM antwortet nur auf Basis der gefundenen Chunks

### Kosten
- Embeddings: 0 € (Ollama auf eigenem VPS)
- Nur Claude API kostet → Input+Output-Tokens nach jeder Query loggen
- Ziel: unter **0,02 € pro Query**

---

## Umgebungsvariablen (.env.example)

```env
# Anthropic – LLM für Antworten
ANTHROPIC_API_KEY=sk-ant-...

# Ollama auf Hostinger VPS via Tailscale
# Tailscale-IP des VPS ermitteln: auf VPS "tailscale ip -4" ausführen
OLLAMA_BASE_URL=http://100.x.x.x:11434
OLLAMA_EMBED_MODEL=nomic-embed-text

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# App
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RESULTS=4
LOG_LEVEL=INFO
```

---

## Supabase SQL-Migration (einmalig ausführen)

**ACHTUNG:** `nomic-embed-text` → `vector(768)` – nicht 1536 wie OpenAI!

```sql
create extension if not exists vector;

create table document_chunks (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   text not null default 'default',
  source      text not null,
  page        int,
  content     text not null,
  embedding   vector(768),        -- nomic-embed-text = 768 Dimensionen
  created_at  timestamptz default now()
);

create index on document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);
```

---

## Antwort-Prompt Template

```
Du bist ein hilfreicher Assistent. Beantworte die Frage ausschließlich auf
Basis der folgenden Dokumenten-Auszüge. Antworte auf Deutsch.

Falls die Antwort nicht in den Dokumenten enthalten ist, sage:
"Diese Information ist in den vorliegenden Dokumenten nicht enthalten."

Nenne immer die Quellen:
📄 Quelle: [Dateiname], Seite [X]

Dokumente:
{context}

Frage: {question}
```

---

## Erfolgskriterien

- [ ] Health-Check: Ollama VPS via Tailscale erreichbar
- [ ] `nomic-embed-text` auf VPS verfügbar (`ollama list`)
- [ ] PDF, DOCX, XLSX werden korrekt geladen und gechunkt
- [ ] Embeddings werden remote erstellt und in Supabase gespeichert
- [ ] Antworten enthalten korrekte Quellenangaben
- [ ] Kosten pro Query unter 0,02 € (nur Claude)
- [ ] Antwortzeit unter 8 Sekunden gesamt
- [ ] Chainlit-Demo läuft stabil 30 Minuten
