# AGENTS.md

Working protocol for this repo. Read before touching code. Companion to `MEMORY.md` (project state log — read it first every session).

## Commands

```bash
# CLI
python -m recall                          # run the CLI REPL
pytest                                    # run all tests
pytest tests/test_router.py               # run a single test file

# Python backend (Phase 6+)
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000  # start FastAPI dev server

# Next.js frontend (Phase 7+)
cd web && npm install                      # first time setup
cd web && npm run dev                      # start Next.js dev server
cd web && npm run build                    # production build
cd web && npm run lint                     # lint TypeScript

# Setup
cp .env.example .env                       # then fill in real secrets
cp web/.env.local.example web/.env.local   # frontend secrets (Phase 7+)
```

## Architecture

```
recall/                            ← Python monorepo root
  recall/                          ← existing Python package (phases 0–4)
    __init__.py
    __main__.py
    cli.py                         # REPL loop + command dispatch
    config.py                      # env loading; ConfigError → friendly message
    store.py                       # ONLY file that touches Supabase
    embeddings.py                  # ONLY file (with llm.py) that touches Gemini
    llm.py                         # synthesize_answer + classify_intent (+ stream in Phase 8)
    router.py                      # heuristic → LLM fallback for store vs query
    models.py                      # Memory, SearchResult, Intent dataclasses
    auth.py                        # Phase 5 — Supabase login/session management
  tests/                           # pytest tests
  api/                             # Phase 6 — FastAPI backend
    main.py                        # FastAPI app, CORS, router includes
    dependencies.py                # JWT auth dependency (get_current_user)
    routers/
      memories.py                  # POST/GET/DELETE /memories
      chat.py                      # POST /chat (non-streaming + streaming)
  supabase/
    schema.sql                     # run once in Supabase SQL editor (Phase 5: RLS on)
  requirements.txt
  .env.example

web/                               # Phase 7 — Next.js project (App Router, TypeScript)
  app/
    layout.tsx                     # root layout: fonts, CSS vars, metadata
    page.tsx                       # redirects to /chat or /auth
    auth/
      page.tsx                     # login / signup
    chat/
      layout.tsx                   # auth guard: redirect if no session
      page.tsx                     # chat interface (owns all state)
    globals.css                    # CSS custom properties + base styles
  components/
    auth/
      AuthForm.tsx
    chat/
      ChatLayout.tsx
      MessageList.tsx
      MessageBubble.tsx
      DateDivider.tsx
      ChatInput.tsx
      EmptyState.tsx
    ui/
      TopBar.tsx
  lib/
    supabase/
      client.ts                    # browser Supabase client
      server.ts                    # server Supabase client (route handlers)
    api.ts                         # typed wrapper for all FastAPI calls
  types/
    index.ts
  middleware.ts                     # Supabase session refresh + route protection
  tailwind.config.ts
  next.config.ts
  .env.local.example
  package.json
```

### Data flow

```
Browser/mobile → Next.js (Vercel)   →  FastAPI (Railway)  →  Supabase + Gemini
Terminal       → direct module calls →  Supabase + Gemini
```

**CLI:** calls `store.py`, `embeddings.py`, `llm.py` directly. **Web:** calls FastAPI over HTTPS with Supabase JWT.

### Isolation rules

| Layer        | Allowed imports                                                      |
|--------------|----------------------------------------------------------------------|
| `recall/store.py` | Only file that imports `supabase`                               |
| `recall/embeddings.py`, `recall/llm.py` | Only files that import `google.genai`                |
| `api/` routers  | Import from `recall.*` packages only; never touch Supabase/Gemini directly |
| `web/`        | Calls FastAPI via `lib/api.ts` only; never calls Supabase/Gemini directly |
| `recall/cli.py`, `recall/router.py` | Work through function contracts, not external services     |

## Critical constraints

- **Embedding dimension locked at 768.** `vector(768)` in schema.sql must match `output_dimensionality=768` in embeddings.py. Never change the model without re-embedding every row.
- **Task types matter.** Store uses `task_type="RETRIEVAL_DOCUMENT"`, search uses `task_type="RETRIEVAL_QUERY"`. Without task types, all scores collapse to ~0.59 regardless of relevance.
- **No-hallucination rule.** If `search_memories` returns zero results, `synthesize_answer` returns a fixed message without calling the LLM.
- **Router heuristic is deliberately conservative.** Does NOT handle "remind me" — "remind me to call mom" → STORE, "remind me where I parked" → QUERY. Only obvious cases (ends with `?`, query starter words, "did/do/have i") skip the LLM. LLM classifier failure defaults to `store` (safer to over-save).
- **Auth: RLS on, anon key everywhere except FastAPI.** Phase 5 enables RLS with an owner policy. The CLI and Next.js browser use the Supabase anon key. FastAPI validates JWTs with the service key but never exposes it. The service key must never appear in the Next.js project.
- **JWT validation in FastAPI.** `api/dependencies.py` verifies Supabase JWTs using the service key. All `api/routers/` endpoints require `get_current_user` and scope operations to that user_id.
- **CORS.** FastAPI allows only `ALLOWED_ORIGINS` from env (comma-separated). Never use `allow_origins=["*"]` in production.
- **Env var naming.** `NEXT_PUBLIC_*` variables are exposed to the browser. The anon key is safe in `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The service key is `SUPABASE_SERVICE_KEY` in the backend `.env` only.
- **Streaming (Phase 8).** FastAPI uses `text/event-stream`; Next.js reads via `ReadableStream` reader. Each chunk is `data: <text>\n\n`; final chunk is `data: [DONE]\n\n`.

## Current phase

**Phase 4** — complete. Adopted `PRD-v2.md` / `TDD-v2.md` plan. Phase 5 (Auth) is up next, followed by Phase 6 (FastAPI), Phase 7 (Next.js), Phase 8 (Streaming + hardening).

## CLI output

Uses `rich` (Console, Table, Panel, status spinner) for all output. Do not use raw `print()` in cli.py — use `console.print()` with rich markup. API calls (store, query, search) show a `console.status()` spinner while the network call is in flight.

## FastAPI conventions (Phase 6+)

- All endpoints return JSON. Error responses use `{ "detail": string }` format.
- HTTP codes: 401 (no/bad token), 404 (not found), 422 (validation), 500 (upstream).
- Use async endpoint functions (`async def`) throughout.
- The `get_current_user` dependency reads the `Authorization: Bearer <token>` header and returns the Supabase `user_id`.
- `POST /chat` detects `?stream=true` query param for streaming (Phase 8); returns plain JSON otherwise.

## Frontend conventions (Phase 7+)

- **Design fidelity is critical.** Implement `PRD-v2.md §6` (design system) and `TDD-v2.md §8` (implementation) exactly. Do not substitute fonts, colours, spacing values, or animation timings.
- **Next.js App Router only.** No `pages/` directory. All routes under `app/`.
- **TypeScript throughout.** No `.js` files in `web/`. Define shared types in `types/index.ts`.
- **State management.** Chat page uses `useState` locally. No Redux, Zustand, or React Context needed at this scale.
- **Auth flow.** Supabase JS sets cookies via `@supabase/ssr`. `middleware.ts` refreshes sessions. `chat/layout.tsx` does a server-side session check to prevent UI flash.
- **Streaming (Phase 8).** Use Fetch API `ReadableStream` reader to consume SSE. Append chunks to the last assistant message in state; do not create a new message per chunk.
- **CSS.** Tailwind for layout/utilities; custom properties from `PRD-v2.md §6.2` for the palette. `globals.css` holds the `:root` and `[data-theme="dark"]` blocks verbatim.
- **Mobile.** Test on real devices, not just Chrome DevTools. The `100dvh` layout must account for the virtual keyboard.

## Model config

All model IDs come from env vars, never hardcoded:
- `CHAT_MODEL=` — user preference (currently `gemma-4-26b-a4b-it`)
- `EMBED_MODEL=` — `gemini-embedding-001` (768-dim output via `output_dimensionality` param; `text-embedding-004` was shut down Jan 2026)

## Error handling

- Every external call (Supabase, Gemini) in the CLI is wrapped in try/except in cli.py; prints a one-line message, never a traceback.
- Missing env vars: `load_config()` raises `ConfigError`, caught by `main()` → prints setup message and exits.
- LLM classify_intent failure → defaults to `store`.
- FastAPI: all routers catch exceptions and return appropriate HTTP error responses with `detail` string.
- Next.js: errors from FastAPI show inline in the chat (accent-coloured text, no toasts/modals).
