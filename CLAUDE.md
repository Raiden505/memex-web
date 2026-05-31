# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Protocol

Every working session must follow this order — no exceptions:

1. **Read `MEMORY.md` first.** Check the current phase, decisions log, open questions, and session notes before writing a single line of code. Never assume you know the current state.
2. **Do the work.** Implement, fix, or investigate as requested. Follow the phase order in `TDD-v2.md`; do not start a phase until the previous one's Definition of Done passes.
3. **Update `MEMORY.md` last.** Before ending the session, update:
   - `Current State` — current phase and what you just did
   - `Phase Completion` — mark any phase that now passes its Definition of Done
   - `Confirmed Values` — fill in any model IDs, dimensions, or URLs you verified
   - `Decisions Log` — one row per non-trivial choice made, with the reason
   - `Open Questions / Blockers` — add new blockers, remove resolved ones
   - `Session Notes` — prepend a new dated entry summarizing what changed

Skipping the MEMORY.md read risks duplicating work or contradicting a prior decision. Skipping the MEMORY.md write means the next session starts blind.

---

## Project

**Recall** — a personal "second brain" with two clients sharing one cloud backend: a CLI (phases 0–4 complete) and a web app (phases 5–8, in progress). You tell it things in plain language; it saves them to Supabase with Gemini embeddings. Later you ask questions; it retrieves semantically relevant memories and synthesises an answer with Gemini. Both clients read and write to the same account — genuinely multi-device.

Full spec in `PRD-v2.md` (product) and `TDD-v2.md` (technical design, phase-by-phase plan). Follow the phases in order — each has a Definition of Done that must pass before starting the next. Phases 0–4 are complete.

---

## Project Structure

```
recall/                         ← Python monorepo root
  recall/                       ← existing Python package (phases 0–4 complete)
    __init__.py
    __main__.py
    cli.py
    config.py
    store.py
    embeddings.py
    llm.py
    router.py
    models.py
    auth.py                     ← added in Phase 5
  api/                          ← new in Phase 6
    main.py
    dependencies.py
    routers/
      memories.py
      chat.py
  supabase/
    schema.sql
  requirements.txt
  .env.example

web/                            ← Next.js project root (Phase 7)
  app/
    layout.tsx
    page.tsx
    auth/page.tsx
    chat/
      layout.tsx
      page.tsx
    globals.css
  components/
    auth/AuthForm.tsx
    chat/
      ChatLayout.tsx
      MessageList.tsx
      MessageBubble.tsx
      DateDivider.tsx
      ChatInput.tsx
      EmptyState.tsx
    ui/
      Logo.tsx
      TopBar.tsx
  lib/
    supabase/
      client.ts
      server.ts
    api.ts
  types/index.ts
  middleware.ts
  tailwind.config.ts
  next.config.ts
  .env.local.example
  package.json
```

---

## Commands

```bash
# Run the CLI
python -m recall

# Run tests
pytest

# Run a single test file
pytest tests/test_router.py

# Install Python dependencies
pip install -r requirements.txt

# Run the FastAPI backend (Phase 6+)
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Copy and fill in secrets before first run
cp .env.example .env

# Next.js web app (Phase 7+)
cd web && npm install
cd web && npm run dev
```

---

## Tech Stack

| Concern         | Choice                        | Notes                                         |
|-----------------|-------------------------------|-----------------------------------------------|
| CLI             | Python REPL                   | Unchanged. Direct module calls.               |
| API backend     | FastAPI (Python)              | Thin layer over existing modules. Async.      |
| Backend hosting | Railway (free tier)           | Alternatively Render.                         |
| Frontend        | Next.js 14+ (App Router)      | TypeScript throughout.                        |
| Frontend host   | Vercel (free tier)            | Natural pairing with Next.js.                 |
| Auth (web)      | Supabase JS + `@supabase/ssr` | JWT issued by Supabase; validated by FastAPI. |
| Database        | Supabase (Postgres + pgvector)| Unchanged.                                    |
| Embeddings      | Gemini embeddings             | via `google-genai`. Output dimension: 768.    |
| LLM             | Gemini 2.5 Flash              | via `google-genai`. Streaming in Phase 8.     |
| DB client       | `supabase` (supabase-py)      | Unchanged.                                    |
| Styling         | Tailwind CSS v3               | Custom tokens via CSS variables.              |
| Config          | `python-dotenv` + env vars    | Unchanged.                                    |

> Before writing any integration code, confirm current Gemini model identifiers and embedding output dimensions from official docs. Do not hardcode model strings from memory.

---

## Architecture

```
Browser / mobile ──▶  Next.js (Vercel)
                        - Auth pages (Supabase JS client)
                        - Chat UI
                              │ HTTPS + Supabase JWT
                              ▼
Terminal ────────────▶  FastAPI (Railway / Render)
(direct module calls,     - /memories  CRUD
 no network hop)          - /chat      query + stream
                          - validates JWT via Supabase
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
     Supabase (Postgres+vector+Auth)    Gemini API (embed + chat)
```

**CLI relationship:** The CLI calls `store.py`, `embeddings.py`, and `llm.py` directly — no network hop. FastAPI is an additional layer for the web client only, not a replacement for the CLI. Both share the same Supabase database and account via Phase 5 auth.

**CLI isolation rules:**
- **Only `store.py`** knows about Supabase
- **Only `embeddings.py` and `llm.py`** know about Gemini

**Store flow:** `router.route(text)` → embed → `store.add_memory(content, embedding, user_id)` → confirm  
**Query flow:** `router.route(text)` → embed → `store.search_memories(vector, user_id, top_k)` → `llm.synthesize_answer(question, results)` → answer

---

## Module Contracts

### Python (CLI + FastAPI)

```python
# config.py
load_config() -> Config          # validates env; friendly error if vars missing

# store.py
add_memory(client, content, embedding, user_id) -> str
list_memories(client, user_id) -> list[Memory]
delete_memory(client, mem_id, user_id) -> bool
count_memories(client, user_id) -> int
search_memories(client, query_embedding, user_id, k) -> list[SearchResult]

# embeddings.py
embed(text) -> list[float]       # 768-float vector — must match vector(768) in DB

# llm.py
synthesize_answer(question, memories) -> str
classify_intent(text) -> Intent                # "STORE" or "QUERY"
stream_answer(question, memories)              # async generator — Phase 8

# router.py
route(text) -> Intent            # heuristic first, then classify_intent fallback

# auth.py (Phase 5)
login(client, email, password) -> Session
current_user_id(client) -> str
```

### FastAPI endpoints (Phase 6+)

All endpoints require `Authorization: Bearer <supabase-jwt>`. All data is scoped to the authenticated `user_id`.

```
POST   /memories          { "content": string }         → 201 { "id", "created_at" }
GET    /memories                                        → 200 [{ "id", "content", "created_at" }]
DELETE /memories/{id}                                   → 200 { "deleted": true } | 404

POST   /chat              { "message": string }
  Non-streaming → 200 { "intent": "store"|"query", "reply": string, "id": string|null }
  Streaming     → text/event-stream, chunks as "data: <text>\n\n", ends "data: [DONE]\n\n"

Errors: { "detail": string }, HTTP 401 / 404 / 422 / 500
```

---

## Intent Routing (Phase 4)

Heuristic routes to **query** if: text ends with `?`, OR first word is `what/where/when/who/why/how/which`, OR it starts with `did i`/`do i`/`have i`. Everything else → ask the LLM classifier. If the LLM call fails, default to `store`.

"remind me to call mom" → STORE. "remind me where I parked" → QUERY. Do not add "remind me" to the heuristic — the LLM disambiguates it.

---

## Environment Variables

### Python backend (`.env`)
```
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...        # service key for JWT validation in FastAPI
GEMINI_API_KEY=...
CHAT_MODEL=...
EMBED_MODEL=...
ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

### Next.js (`web/.env.local`)
```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=https://your-api.railway.app
```

`NEXT_PUBLIC_` vars are exposed to the browser. The anon key is safe to expose — RLS enforces security. The service key must never appear in the Next.js project.

---

## Design System (Phase 7)

The web app follows a precise design spec in `PRD-v2.md §6`. Key points:
- **Fonts:** Lora (brand mark, textarea input) + Plus Jakarta Sans (all other UI) via `next/font/google`.
- **Palette:** warm parchment (`#F5F0E8`) light mode; deep warm dark (`#181512`) dark mode. Full CSS custom properties in `PRD-v2.md §6.2` — copy verbatim, do not substitute colours.
- **Theme:** `prefers-color-scheme` only; no manual toggle in this build.
- **Motion:** message entrance `opacity+translateY` 200ms ease-out only. No bouncing, no springs, nothing else animates.
- **Two screens only:** Auth (centred form, 360px max-width) and Chat (full-screen, no sidebars, no dashboards).
- Avoid: ChatGPT/Claude aesthetic, gradients, glassy cards, typing indicators, avatars, over-animation.

---

## Critical Constraints

- **Embedding dimension is locked at 768.** The `vector(768)` column and embedding model output must agree. Never change the model without re-embedding every row.
- **No-hallucination rule:** if `search_memories` returns no results, short-circuit `synthesize_answer` and return a fixed "nothing saved about that" message without calling the LLM.
- **Security phases:** Phases 1–4 used `service_role` key + placeholder `user_id` (RLS off). Phase 5+ uses `anon` key + real auth + RLS. The service key is only used server-side in FastAPI (`dependencies.py`) for JWT validation — never in Next.js.
- **Free tier only:** Vercel, Railway/Render, Supabase, Gemini. No paid services.

---

## Database

Run `supabase/schema.sql` in the Supabase SQL editor to set up the table, HNSW index, and `match_memories` RPC function. The RPC is how `store.search_memories` performs cosine similarity search. Phase 5 adds RLS policies to this schema.

---

## Testing

Unit-testable without the network: the heuristic in `router.route`, config validation, command parsing in `cli.py`. Integration tests are manual per-phase via the Definitions of Done in `TDD-v2.md`.
