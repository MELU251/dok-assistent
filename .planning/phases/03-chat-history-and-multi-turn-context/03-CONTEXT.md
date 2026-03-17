# Phase 3: Chat History and Multi-Turn Context - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning
**Source:** Conversation context (user decisions)

<domain>
## Phase Boundary

Phase 3 liefert:
1. Vollständige Alembic-Migrationsstrategie für alle Tabellen (Baseline + neue Chat-Tabellen)
2. SQLAlchemy-Models für alle Tabellen
3. Persistente Chat-Sessions und Multi-Turn-Kontext
4. Dokument-Filter für gezielte Fragen

Was Phase 3 NICHT macht:
- UI/UX-Polish (Phase 4)
- Refactoring des bestehenden pgvector/Supabase-Query-Codes

</domain>

<decisions>
## Implementation Decisions

### ORM & Migration-Stack (LOCKED)
- **Alembic + SQLAlchemy** als Migration- und ORM-Stack
- Kein Prisma (Python-Client noch Beta), kein Liquibase (Java-Overhead)
- Ziel: `alembic upgrade head` auf neuer DB → vollständiges Schema, kein manuelles SQL

### Migrations-Scope (LOCKED)
- **Baseline-Migration** für bestehendes `document_chunks`-Schema (inkl. pgvector-Extension und ivfflat-Index) — alle zukünftigen DBs/Testsysteme starten mit korrektem Schema
- **Neue Migration** für `chat_sessions`-Tabelle
- **Neue Migration** für `chat_messages`-Tabelle
- Alle Tabellen durch Alembic versioniert — keine manuellen SQL-Skripte mehr

### Scope-Grenze für bestehenden Code (LOCKED)
- Bestehender Supabase-Python-Client-Code für Vektorsuche (ingest.py, retrieval.py) bleibt **unangetastet**
- SQLAlchemy nur für neue Chat-Tabellen als Query-Layer verwenden
- Keine Umstellung des pgvector-Retrieval auf SQLAlchemy — zu viel Scope-Risiko

### Chat-Persistenz (LOCKED)
- Chat-Sessions und Nachrichten in Supabase persistieren (gleiche DB wie Vektoren)
- Chainlit-Session-Lifecycle als Trigger für Session-Erstellung

### Multi-Turn-Kontext (Claude's Discretion für Implementierungsdetails)
- Conversation History wird in die RAG-Pipeline eingebaut
- Vorherige Turns fließen als Kontext in den LLM-Call
- Konkrete Implementierung (LangChain Memory-Klasse vs. manuell) → Claude's Discretion

### Dokument-Filter (Claude's Discretion für Implementierungsdetails)
- Nutzer kann Frage auf ein spezifisches Dokument eingrenzen
- Chainlit-UI-Mechanismus (Dropdown, `/`-Befehl, etc.) → Claude's Discretion

</decisions>

<specifics>
## Specific Ideas

- `alembic upgrade head` soll als einziger Setup-Schritt für neue Testsysteme reichen
- Tailscale/VPS-Infrastruktur bleibt unverändert
- Authentifizierung/Multi-Tenant bleibt PoC-Level (tenant_id = 'default')

</specifics>

<deferred>
## Deferred Ideas

- Multi-Tenant-Session-Isolation (Phase 4+ oder SaaS-Milestone)
- Volltextsuche über Chat-Historie
- Chat-Export-Funktion

</deferred>

---

*Phase: 03-chat-history-and-multi-turn-context*
*Context gathered: 2026-03-17 via conversation*
