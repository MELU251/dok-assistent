# Feature Research

**Domain:** Pilot-ready RAG document assistant for KMUs (Mittelstand)
**Researched:** 2026-03-12
**Confidence:** HIGH (based on project docs, codebase audit, domain knowledge of enterprise document tools)

---

## Context: What Already Exists

The PoC has a working core pipeline. The following features are already built and should NOT appear in the pilot roadmap as new work:

- File upload (PDF, DOCX, XLSX) via Chainlit UI
- Basic Q&A with source attribution (filename + page)
- Per-query cost tracking (EUR)
- Document deletion via `/loeschen` command
- Password authentication (single user)
- Docker deployment on VPS

This research focuses on what is **missing** for a customer to use the product independently.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features a new pilot customer will assume exist. Missing any one of them causes confusion, loss of trust, or inability to complete basic tasks without guidance.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multi-turn conversation context** | Every modern chat tool (WhatsApp, ChatGPT) maintains context across messages. Without it, every follow-up question is treated as a new, unrelated query. | MEDIUM | Requires passing prior messages as context to Claude. Chainlit provides `cl.chat_context` or message history in session. Cost increase ~20-30% per query from extra tokens. |
| **Persistent chat history (thread list)** | Users expect to return tomorrow and find yesterday's conversations. "Where did my question go?" is the first thing a pilot customer will ask. | MEDIUM | Chainlit supports a `data_layer` (SQLite or PostgreSQL) for thread/message persistence. Supabase or local SQLite are both viable. Requires schema additions. |
| **Onboarding / first-run guidance** | A new user opening a blank chat box with no instructions will not know what to do. KMU employees are not technical. | LOW | Welcome message with explicit instructions: "Lade zuerst ein Dokument hoch, dann stelle Fragen dazu." A simple `on_chat_start` improvement. |
| **Visible document inventory** | Users need to know which documents the system can answer questions about. Without this, they lose trust ("Does it know this file?"). | LOW | Already partially built (shows list on chat start). Needs to be persistent and accessible mid-conversation, not only at session start. |
| **Upload progress feedback** | Large files (multi-MB PDFs) take 10-30 seconds to process. Without visible progress, users assume it is broken. | LOW | Already partially built via `cl.Step`. Needs to show per-chunk progress reliably; current async-blocking issue must be fixed for this to work correctly. |
| **Stable login without errors** | User must be able to log in without encountering crashes or cryptic errors on first visit. | LOW | Blocker-level: requires async/blocking tech debt fix. If embed_and_store blocks the event loop during ingest, the UI may freeze and appear broken. |
| **Graceful "document not found" response** | When a user asks about something not in the uploaded documents, the system must say so clearly in German. | LOW | Already implemented in pipeline ("Diese Information ist in den vorliegenden Dokumenten nicht enthalten.") — verify it works reliably. |
| **Error messages in German** | KMU pilot customer is German-speaking. English error messages ("RuntimeError: connection refused") destroy trust immediately. | LOW | Partially implemented. All user-facing errors must be localized. Technical errors must be caught and translated to friendly German messages. |

### Differentiators (Competitive Advantage)

Features that turn a demo into a "wow." These are not expected by default but create sticky impressions with KMU decision-makers comparing this to basic search or ChatGPT.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Source attribution with page number** | Already built. The single biggest differentiator vs generic ChatGPT: the answer cites exactly which page to check. KMU customers care deeply about verifiability — "I need to know WHERE it says that." | LOW | Already exists. Must be visually prominent (not buried in a small footnote). Consider showing it as a formatted card, not just a line of text. |
| **Answer quality indicator / confidence signal** | When the system finds relevant chunks it should say so clearly; when it is guessing or has low similarity scores, it should indicate that. Builds trust. | MEDIUM | Retrieve cosine similarity scores from Supabase RPC. If best match < 0.6 similarity, add a warning: "Ich bin nicht sicher, ob diese Antwort korrekt ist." |
| **Document-scoped questions** | "Ask about this specific document" dropdown/filter. Prevents cross-document confusion when multiple files are uploaded (e.g., "contract 2024" vs "contract 2023"). | MEDIUM | Requires UI filter that passes `source` filter to retrieval.search(). Architecture already has source metadata. |
| **Cost transparency per conversation** | Showing the per-query cost in the UI is rare and builds trust with cost-conscious KMU customers ("This cost €0.008 — not €0.50 like I feared"). | LOW | Already implemented. Keep it visible. |
| **Async upload without blocking chat** | User can upload a document and immediately ask questions about existing documents while the new one is being processed. | HIGH | Requires fixing the blocking embed_and_store tech debt + background task queue. High value, high complexity. Consider for v1.1. |

### Anti-Features (Deliberately NOT Build for Pilot)

These seem like good ideas but introduce scope creep, complexity, or maintenance burden that is not justified for a single-customer pilot.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Multi-user account management (admin UI)** | "What if multiple employees use it?" | The pilot is one customer, likely 1-3 users. Building a full user management UI adds weeks of work. The existing single-password auth + Tailscale is sufficient for the pilot duration. | Use environment variable credentials. If the pilot succeeds, add OAuth in the SaaS phase. |
| **Role-based access control (RBAC)** | "Some users should only see certain documents." | No evidence the pilot customer needs this. RBAC requires schema changes, UI controls, and policy enforcement — significant complexity. | Scope the pilot to a single shared workspace. Document it as a future feature. |
| **Document versioning** | "What if I re-upload an updated contract?" | True versioning requires tracking lineage, a version UI, and query routing logic. Overwriting the current chunks with re-upload is sufficient for pilot. | Instruct the pilot customer to use distinct filenames for different versions (e.g., "Vertrag_2024_v2.pdf"). |
| **Email notifications / webhooks** | "Notify me when a document is processed." | Adds infrastructure (SMTP, async job tracking) with no pilot-critical value. | Show processing status in the chat UI itself (progress steps). |
| **Analytics dashboard** | "How is the tool being used?" | Requires a separate frontend, aggregation queries, and significant work. | Log cost + token usage per query to Supabase. This is enough for pilot feedback. Raw Supabase data is readable by the developer. |
| **OCR for scanned PDFs (hi_res strategy)** | "Our PDFs are scans." | Switching from `strategy="fast"` to `strategy="hi_res"` increases ingest time 5-10x and requires Tesseract to work correctly. High failure rate on complex layouts. | Verify pilot customer documents are text-based (not scanned). If they have scans, treat as a separate known limitation. |
| **GDPR compliance features** | "We need data deletion on request." | The `/loeschen` command already provides document deletion. Full GDPR compliance (audit logs, data export, DPA) is not pilot scope. | Document existing deletion command. Note GDPR as a post-pilot requirement. |
| **Streaming responses** | "ChatGPT streams answers word by word." | Chainlit supports streaming but the current `pipeline.answer()` returns complete responses. Streaming requires refactoring the pipeline. Nice to have, not blocking. | Non-streaming responses at <8s feel acceptable. Consider streaming only if user feedback flags latency as a problem. |

---

## Feature Dependencies

```
[Stable login (async fix)]
    └──required by──> [Upload progress feedback works correctly]
    └──required by──> [Multi-turn conversation context]
    └──required by──> [Persistent chat history]

[Persistent chat history (data layer)]
    └──required by──> [Thread list / return to previous chats]

[Document inventory (mid-conversation)]
    └──enhances──> [Document-scoped questions]

[Source attribution (already built)]
    └──enhances──> [Answer quality indicator]

[Cost tracking (already built)]
    └──requires no change]

[Onboarding]
    └──independent, can ship first]
```

### Dependency Notes

- **Stable login requires async fix:** The blocking `embed_and_store()` in the Chainlit event loop must be resolved first. Without this, upload + progress + session handling are all unreliable. This is the single most important prerequisite for everything else working.
- **Persistent chat history requires a Chainlit data layer:** Chainlit provides a `CustomDataLayer` interface. This must be implemented (storing threads/messages in Supabase or SQLite) before chat history is available. This is a moderate implementation effort: 1-2 days.
- **Multi-turn context is independent of persistence:** Context within a single session can be added by passing `cl.chat_context` to the pipeline even before persistence is implemented. These are separate features.
- **Document-scoped questions enhances but does not require inventory:** The inventory can exist without filtering. Filtering requires inventory to be visible so the user knows what to filter on.

---

## MVP Definition

### Launch With — Pilot-Ready v1

The minimum set for a KMU employee to successfully use the product without handholding on day one.

- [ ] **Async fix (embed_and_store non-blocking)** — Without this, the UI is unreliable. Every other feature depends on a stable event loop.
- [ ] **Onboarding message** — First-time user knows exactly what to do. One-hour implementation. Highest ROI per unit of effort.
- [ ] **Multi-turn conversation context** — Without this, the AI feels broken. Users will immediately try "what was my previous question?" and expect it to know.
- [ ] **Persistent chat history (thread list)** — Users expect to return and find their previous conversations. Without this, the product feels like a toy, not a tool.
- [ ] **Document inventory accessible mid-conversation** — User can check what documents are loaded at any time, not only at session start.
- [ ] **All user-facing errors in German** — Any English error message in a German-language product destroys pilot trust.

### Add After Validation — v1.1

Features to add once the pilot customer has used v1 for 1-2 weeks and provided initial feedback.

- [ ] **Answer quality indicator** — Add once users are comfortable with the core flow. Complexity: MEDIUM, value: HIGH for trust-building.
- [ ] **Document-scoped questions** — Add if pilot customer has multiple documents and expresses confusion about cross-document answers.
- [ ] **Streaming responses** — Add if pilot feedback cites response latency as a frustration. Easy win if the pipeline is already stable.

### Future Consideration — v2+ (SaaS Phase)

Features to defer until pilot is complete and SaaS path is validated.

- [ ] **Multi-user account management** — Only relevant when moving from single-customer pilot to multi-tenant SaaS.
- [ ] **RBAC / document access control** — Only needed if pilot customer has internal confidentiality requirements.
- [ ] **GDPR data export / audit log** — Required for regulated industries or multi-tenant SaaS; not pilot scope.
- [ ] **Email notifications** — Nice to have for production; not pilot scope.
- [ ] **Analytics dashboard** — Useful for product iteration post-pilot; raw Supabase logs suffice for now.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Async fix (embed_and_store) | HIGH (foundation) | MEDIUM (2-3 days) | P1 |
| Onboarding message | HIGH | LOW (2-4 hours) | P1 |
| Multi-turn conversation context | HIGH | MEDIUM (1-2 days) | P1 |
| Persistent chat history (data layer) | HIGH | MEDIUM (2-3 days) | P1 |
| Document inventory mid-conversation | MEDIUM | LOW (2-4 hours) | P1 |
| German error messages (all paths) | HIGH | LOW (1 day audit) | P1 |
| Answer quality indicator | HIGH | MEDIUM (1-2 days) | P2 |
| Document-scoped questions | MEDIUM | MEDIUM (1-2 days) | P2 |
| Streaming responses | LOW-MEDIUM | MEDIUM (1-2 days) | P2 |
| Async upload (background job) | MEDIUM | HIGH (3-5 days) | P3 |
| Multi-user management | LOW (pilot) | HIGH (1-2 weeks) | P3 |
| GDPR compliance features | LOW (pilot) | HIGH (1-2 weeks) | P3 |

**Priority key:**
- P1: Must have for pilot launch
- P2: Should have — add based on pilot feedback
- P3: Future consideration — not pilot scope

---

## Competitor Feature Analysis

Products the pilot customer may compare against: plain ChatGPT (most common reference), Notion AI, Microsoft Copilot for Word/SharePoint.

| Feature | Plain ChatGPT | Microsoft Copilot | Our Approach |
|---------|---------------|-------------------|--------------|
| Document upload | Yes (file chat) | Yes (SharePoint integrated) | Yes (PDF/DOCX/XLSX) |
| Source attribution | Vague / partial | Page references | Explicit filename + page number — our strongest differentiator |
| Private document handling | Sends to OpenAI | Stays in Microsoft tenant | Stays in customer's environment (Supabase + VPS) — key trust point for KMUs |
| Chat history | Yes | Yes | Missing — must fix for pilot |
| Multi-turn context | Yes | Yes | Missing — must fix for pilot |
| Cost per query | Not shown | Bundled in M365 license | Shown transparently — differentiator for cost-conscious KMUs |
| German language | Good | Good | Explicit German-language prompting and responses |
| Onboarding | Self-explanatory | Integrated into Office | Currently missing — must add |

**Key insight:** The comparison with ChatGPT is the one every pilot customer will make. ChatGPT has chat history and multi-turn context by default. If our product lacks these, the pilot customer will say "ChatGPT can already do this." These two features are non-negotiable for the pilot to feel like a step forward, not backward.

---

## Sources

- Project documentation: `.planning/PROJECT.md` (HIGH confidence — authoritative project scope)
- Codebase audit: `.planning/codebase/CONCERNS.md` (HIGH confidence — directly identifies missing features)
- Codebase audit: `.planning/codebase/ARCHITECTURE.md` (HIGH confidence — confirms what is built)
- Domain knowledge: RAG/document assistant product patterns (MEDIUM confidence — training knowledge, no external verification available in this session due to tool restrictions)
- Competitor analysis: ChatGPT, Microsoft Copilot feature sets (MEDIUM confidence — well-known products, features verified against training knowledge up to August 2025)

---

*Feature research for: Pilot-ready RAG document assistant (KMU)*
*Researched: 2026-03-12*
