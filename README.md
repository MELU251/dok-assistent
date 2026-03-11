# KI-Dokumenten-Assistent – PoC

Lokaler Proof-of-Concept für einen KI-gestützten Dokumenten-Assistenten.
Unterstützt PDF, DOCX und XLSX. Antworten immer mit Quellenangabe.

**Stack:** Claude (Antworten) + Ollama/nomic-embed-text auf eigenem VPS (Embeddings, kostenlos) + Supabase pgvector

---

## Setup (5 Schritte)

**1. Virtuelle Umgebung erstellen**
```bash
py -3.11 -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

**2. Abhängigkeiten installieren**
```bash
pip install -r requirements.txt
```

**3. Umgebungsvariablen konfigurieren**
```bash
cp .env.example .env
# .env öffnen und Werte eintragen (Tailscale-IP, Supabase, Anthropic Key)
```

**4. Supabase vorbereiten** (SQL unten, einmalig)

**5. Verbindung testen, dann Demo starten**
```bash
pytest tests/test_connection.py -v -s   # alle Dienste prüfen
python ingest_cli.py --file docs/beispiel_handbuch.txt
chainlit run app.py
```

---

## Supabase SQL-Migration (einmalig ausführen)

Öffne den **SQL Editor** in deinem Supabase-Projekt und führe aus:

> ⚠️ **Wichtig:** `nomic-embed-text` erzeugt **768 Dimensionen** – nicht 1536 wie OpenAI!
> Die Tabelle muss `vector(768)` verwenden, sonst schlägt jeder Insert fehl.

```sql
-- pgvector Extension aktivieren
create extension if not exists vector;

-- Tabelle für Dokument-Chunks
-- ACHTUNG: vector(768) für nomic-embed-text (nicht 1536!)
create table document_chunks (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   text not null default 'default',
  source      text not null,
  page        int,
  content     text not null,
  embedding   vector(768),        -- nomic-embed-text = 768 Dimensionen
  created_at  timestamptz default now()
);

-- Index für schnelle Vektorsuche
create index on document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);
```

Zusätzlich die **RPC-Funktion** für LangChain (ebenfalls im SQL Editor):

```sql
create or replace function match_document_chunks(
  query_embedding vector(768),       -- 768, nicht 1536!
  match_count     int default 4,
  filter          jsonb default '{}'
)
returns table (id uuid, content text, metadata jsonb, similarity float)
language plpgsql as $$
begin
  return query
  select
    dc.id,
    dc.content,
    jsonb_build_object(
      'source',    dc.source,
      'page',      dc.page,
      'tenant_id', dc.tenant_id
    ) as metadata,
    1 - (dc.embedding <=> query_embedding) as similarity
  from document_chunks dc
  where dc.tenant_id = (filter->>'tenant_id')
  order by dc.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

---

## Verbindungstest

```bash
pytest tests/test_connection.py -v -s
```

Prüft der Reihe nach:
1. Ollama VPS via Tailscale erreichbar?
2. `nomic-embed-text` auf VPS installiert?
3. Embedding-Dimension korrekt (768)?
4. Supabase Tabelle `document_chunks` vorhanden?
5. Claude API antwortet?

---

## Beispiel-Queries für die Demo

```
Wie oft muss das Öl gewechselt werden und welche Ölsorte ist vorgeschrieben?
Wie läuft ein Ölwechsel ab? Ich brauche die genauen Schritte.
Der Motorschutzschalter hat ausgelöst – was soll ich jetzt tun?
Was sind die Garantiebedingungen und was muss ich für die Wartung dokumentieren?
Ich brauche einen neuen Luftfilter. Was kostet der und wie bestelle ich ihn?
```

---

## Tests ausführen

```bash
pytest tests/ -v                          # alle Unit-Tests
pytest tests/test_connection.py -v -s     # Live-Verbindungstest
```

---

## Projektstruktur

```
├── src/
│   ├── config.py      # Env-Variablen, Validierung, Ollama-Health-Check
│   ├── ingest.py      # Dokumente laden, chunken, via Ollama einbetten
│   ├── retrieval.py   # Similarity Search in pgvector
│   └── pipeline.py    # RAG-Pipeline: Frage → Kontext → Claude → Antwort
├── app.py             # Chainlit Chat-UI
├── ingest_cli.py      # CLI zum Indexieren
└── tests/
    ├── test_connection.py   # Live-Verbindungstest aller Dienste
    ├── test_ingest.py
    └── test_pipeline.py
```

## Deployment auf VPS (Docker)

Voraussetzung: Docker + Docker Compose auf dem VPS, Tailscale aktiv.
Ollama läuft bereits als separater Stack – kein gemeinsames Compose-File nötig.

### Erstes Deployment

```bash
# Code auf VPS bringen (eine der beiden Optionen):
git clone <repo-url> dok-assistent && cd dok-assistent
# oder: scp -r . user@vps:~/dok-assistent && ssh user@vps "cd dok-assistent"

# .env befüllen
cp .env.example .env
nano .env   # Alle Felder ausfüllen, besonders:
            # CHAINLIT_AUTH_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
            # CHAINLIT_USER=pilot
            # CHAINLIT_PASSWORD=<sicheres-passwort>

# Deployen
chmod +x deploy.sh && ./deploy.sh
```

### Dokument hochladen und indexieren

```bash
# 1. Datei in das persistente Volume kopieren
docker cp dokument.pdf dok-assistent:/app/docs/

# 2. Indexieren (startet einmalig, beendet sich danach)
docker compose --profile tools run --rm ingest --file /app/docs/dokument.pdf
```

### Update deployen (nach Code-Änderung)

```bash
git pull
docker compose build && docker compose up -d chainlit
```

### Logs prüfen

```bash
docker compose logs -f chainlit
```

### Pilot-Kunden onboarden

1. **Tailscale**: Admin-Console → Geräte → Einladen → E-Mail des Kunden
2. **Link senden**: `http://100.103.54.4:8000`
3. **Zugangsdaten**: `CHAINLIT_USER` / `CHAINLIT_PASSWORD` aus `.env`
4. Kunde braucht: Tailscale-Client installiert + eingeloggt

---

## Kosten

| Schritt | Dienst | Kosten |
|---|---|---|
| Embeddings (beliebig viele Docs) | Ollama auf eigenem VPS | **0 €** |
| Query-Antwort | Claude claude-sonnet-4-6 | ~0,3–1,5 Cent |
| Supabase (bis 500 MB) | Supabase Free Tier | **0 €** |
