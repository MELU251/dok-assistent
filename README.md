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

## Deployment via Hostinger

Hostinger liest `docker-compose.yml` direkt aus GitHub und deployt automatisch.
Secrets kommen **nicht** aus einer `.env`-Datei – sie werden in Hostinger als
Environment Variables eingetragen und zur Laufzeit injiziert.

### Schritt 1: GitHub Repository

```bash
# Privates Repository auf github.com anlegen, dann:
git init
git remote add origin git@github.com:USERNAME/dok-assistent.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

> `.env` wird **niemals** committet – steht in `.gitignore`.

### Schritt 2: Hostinger Setup

1. **VPS Panel** → Docker → "New Stack" (oder "Deploy from GitHub")
2. GitHub-Repository verknuepfen oder URL der `docker-compose.yml` eingeben:
   ```
   https://raw.githubusercontent.com/USERNAME/dok-assistent/main/docker-compose.yml
   ```
3. **Environment Variables** eintragen – alle Werte aus `.env.example`:

| Variable | Wert / Quelle |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `OLLAMA_BASE_URL` | `http://100.103.54.4:32768` |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` |
| `SUPABASE_URL` | Supabase Dashboard → Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase Dashboard → API → service_role |
| `CHAINLIT_AUTH_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CHAINLIT_USER` | z. B. `pilot` |
| `CHAINLIT_PASSWORD` | sicheres Passwort waehlen |
| `CHUNK_SIZE` | `500` |
| `CHUNK_OVERLAP` | `50` |
| `TOP_K_RESULTS` | `4` |
| `LOG_LEVEL` | `INFO` |

### Schritt 3: Tailscale

```bash
# Tailscale-IP des VPS pruefen (auf VPS ausfuehren):
tailscale ip -4
# => 100.103.54.4

# App ist erreichbar unter:
# http://100.103.54.4:8000
```

Pilot-Kunde benoetigt: **Tailscale-Client** installiert + Einladung angenommen.

### Dokument hochladen (nach Deployment)

Direkt im Chainlit-Chat ueber den **"Dokument hochladen"**-Button –
kein SSH, kein `docker cp` noetig.

### Update deployen (nach Code-Aenderung)

```bash
git push
# Hostinger erkennt Aenderung automatisch via Webhook
# oder: Hostinger Panel → Stack → "Redeploy" klicken
```

### Logs pruefen

```bash
# Option 1: Hostinger VPS Panel → Container Logs
# Option 2: per SSH
ssh root@100.103.54.4
docker logs -f dok-assistent
```

### Manuelles CLI-Ingesting (Fallback via SSH)

```bash
ssh root@100.103.54.4
cd ~/dok-assistent
docker compose --profile tools run --rm ingest --file /app/docs/datei.pdf
```

---

## Kosten

| Schritt | Dienst | Kosten |
|---|---|---|
| Embeddings (beliebig viele Docs) | Ollama auf eigenem VPS | **0 €** |
| Query-Antwort | Claude claude-sonnet-4-6 | ~0,3–1,5 Cent |
| Supabase (bis 500 MB) | Supabase Free Tier | **0 €** |
