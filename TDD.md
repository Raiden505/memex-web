# Technical Design Document — "Recall" / "Memex"

Companion to `PRD.md`.
Version: 3.0 (consolidated). Folds in the multi-client architecture from `TDD-v2.md`
(phases 5–8) and the conversational/temporal/UX design from `TDD-v3.md` (phases 9–11), so
this is the single current technical spec. Detailed v2/v3 designs remain in
`TDD-v2.md` / `TDD-v3.md`.

> **Implementation note.** Confirm provider SDK names, model identifiers, embedding output
> dimension, and streaming APIs against current official docs before writing integration
> code. Confirmed values (`MEMORY.md`): chat model `gemma-4-26b-a4b-it`, embedding model
> `gemini-embedding-001` at `output_dimensionality=768`. Read model strings from config —
> never hardcode from memory.

---

## 1. Architecture

```
  Browser / mobile ──▶  Next.js (Vercel)
                          - Auth pages (Supabase JS client)
                          - Chat UI (streaming)
                                │ HTTPS + Supabase JWT
                                ▼
  Terminal ──────────▶  FastAPI (Railway / Render)
  (direct module          - /memories  CRUD
   calls, no hop)         - /chat      route + stream
                          - validates JWT via Supabase
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
       Supabase (Postgres+pgvector+Auth)   Gemini API (embed + chat)
```

**CLI relationship.** The CLI calls `store.py`, `embeddings.py`, `llm.py`, `router.py`
directly — no network hop. FastAPI is an additional layer for the web client, not a
replacement for the CLI. Both clients share the same Supabase database and account via
Phase 5 auth.

**Isolation rules (unchanged across all phases):**
- Only `store.py` knows about Supabase.
- Only `embeddings.py` and `llm.py` know about Gemini.
- Everything else works through their function contracts, so the backend can be swapped
  without touching client logic.

---

## 2. Tech stack

| Concern         | Choice                            | Notes                                              |
|-----------------|-----------------------------------|----------------------------------------------------|
| CLI             | Python REPL (`rich` optional)     | Direct module calls.                               |
| API backend     | FastAPI (Python)                  | Thin layer over the existing modules. Async.       |
| Backend hosting | Railway (free tier) / Render      | One service to deploy.                             |
| Frontend        | Next.js 16 (App Router), TS       | Vercel hosting.                                    |
| Auth (web)      | Supabase JS + `@supabase/ssr`     | JWT issued by Supabase; validated by FastAPI.      |
| Database        | Supabase (Postgres + pgvector)    | `vector(768)` + HNSW cosine index + `match_memories` RPC. |
| Embeddings      | Gemini `gemini-embedding-001`     | `output_dimensionality=768` (MRL truncation).      |
| LLM             | Gemini chat (`gemma-4-26b-a4b-it`)| Streaming via `generate_content_stream`.           |
| Config          | `python-dotenv` + env vars        |                                                    |
| Styling         | Tailwind (v4 as shipped)          | Custom tokens via CSS variables.                   |

---

## 3. Project structure

```
recall/                         ← Python monorepo root
  recall/                       ← Python package (phases 0–4 + 9–10 additions)
    __init__.py  __main__.py
    cli.py  config.py  models.py
    store.py        ← Supabase access (ONLY DB-aware module)
    embeddings.py   ← Gemini embeddings
    llm.py          ← Gemini chat: synthesize / classify / general / summarize
    router.py       ← intent routing (heuristic + LLM, 3-way)
    auth.py         ← Supabase auth (Phase 5)
    temporal.py     ← time-range extraction (Phase 10, NEW)
  api/                          ← FastAPI (Phase 6)
    main.py  dependencies.py
    routers/ memories.py  chat.py
  supabase/ schema.sql
  requirements.txt  .env.example  Procfile

web/                            ← Next.js (Phase 7)
  app/ layout.tsx page.tsx auth/page.tsx chat/{layout,page}.tsx globals.css
  components/ auth/AuthForm.tsx chat/{ChatLayout,MessageList,MessageBubble,DateDivider,ChatInput,EmptyState}.tsx ui/{Logo,TopBar}.tsx
  lib/ supabase/{client,server}.ts  api.ts
  types/index.ts  proxy.ts  (session refresh — renamed from middleware.ts in Next 16)
  tailwind/next config  .env.local.example  package.json
```

---

## 4. Data model

### Table `memories`

| Column      | Type           | Notes                                              |
|-------------|----------------|----------------------------------------------------|
| `id`        | `uuid`         | PK, default `gen_random_uuid()`                    |
| `user_id`   | `uuid`         | Owner; Phase 5+ references `auth.users`            |
| `content`   | `text`         | The memory text                                    |
| `embedding` | `vector(768)`  | Must equal the embedding model's output dimension  |
| `metadata`  | `jsonb`        | Reserved; default `'{}'`                            |
| `created_at`| `timestamptz`  | Default `now()` — used by temporal recall          |

Indexes:
```sql
-- semantic search (existing)
create index if not exists memories_embedding_idx
  on memories using hnsw (embedding vector_cosine_ops);

-- temporal recall (Phase 10, NEW)
create index if not exists memories_user_created_idx
  on memories (user_id, created_at desc);
```

`match_memories(query_embedding, match_user_id, match_count)` RPC performs cosine search
(unchanged). RLS (Phase 5): owner-only policy `auth.uid() = user_id` for all operations.

### Dataclasses (`models.py`)
```python
@dataclass
class Memory:        id; content; created_at; user_id
@dataclass
class SearchResult:  id; content; created_at; similarity   # 0..1
Intent = Literal["store", "query", "general"]               # "general" added in Phase 9
```

---

## 5. Module contracts

```python
# config.py
load_config() -> Config        # validates env; friendly error if missing
#   fields: supabase_url, supabase_anon_key, supabase_service_key, gemini_api_key,
#           chat_model, embed_model, embed_dim=768, top_k=5, user_id

# store.py
get_client(cfg) -> Client
add_memory(client, content, embedding, user_id) -> dict       # returns full row
list_memories(client, user_id) -> list[Memory]
delete_memory(client, mem_id, user_id) -> bool
count_memories(client, user_id) -> int
search_memories(client, query_embedding, user_id, k) -> list[SearchResult]
list_memories_in_range(client, user_id, start, end) -> list[Memory]   # Phase 10, NEW

# embeddings.py
embed(text, cfg, task_type) -> list[float]   # 768; RETRIEVAL_DOCUMENT on store, RETRIEVAL_QUERY on search

# llm.py
synthesize_answer(question, memories, cfg) -> str
synthesize_answer_stream(question, memories, cfg) -> Generator[str, None, None]
classify_intent(text, cfg) -> Intent                 # STORE | QUERY | GENERAL (Phase 9)
chat_general(message, cfg) -> str                    # Phase 9, NEW
chat_general_stream(message, cfg) -> Generator[...]  # Phase 9, NEW
summarize_window(memories, label, cfg) -> str        # Phase 10, NEW
summarize_window_stream(memories, label, cfg) -> Generator[...]  # Phase 10, NEW

# router.py
route(text, cfg) -> Intent     # greeting/meta fast-path → general; heuristic; LLM fallback

# temporal.py (Phase 10, NEW)
extract_range(text, tz="UTC", now=None) -> tuple[datetime, datetime, str] | None

# auth.py
sign_in / sign_up / sign_out / save_session / load_session / restore_session
current_user_id(client) -> str
```

---

## 6. Key flows

**Store:** `route` → `store` → `embed(RETRIEVAL_DOCUMENT)` → `add_memory` → confirm.

**Personal query:** `route` → `query` → if `temporal.extract_range` returns a window →
`list_memories_in_range` → `summarize_window`; else `embed(RETRIEVAL_QUERY)` →
`search_memories` → `synthesize_answer` (empty → fixed "nothing saved", **no LLM call**).

**General:** `route` → `general` → `chat_general` (no embed, no store, no search). Never
framed as a saved memory.

---

## 7. Intent routing

Fast heuristic first; LLM classifier for the rest.

1. **Greeting / meta fast-path → `general`** (no LLM call): bare "hi/hello/hey/thanks/ok",
   "good morning", "help", "what can you do".
2. **Query heuristic → `query`:** ends with `?`, OR first word in
   {what, whats, what's, where, when, who, why, how, which}, OR starts with
   "did i" / "do i" / "have i". *(See `TDD-v3.md §3.2` for handling general-knowledge
   questions that also end in "?"; the LLM classifier is what separates personal recall
   from general knowledge.)*
3. **Ambiguous → `classify_intent`** (3-way: STORE | QUERY | GENERAL, temperature 0).
   Default to `store` on any failure — safer to over-save than lose input.

Deliberately do **not** treat "remind me" / "tell me" as query in the heuristic — the
model disambiguates ("remind me to call mom" = store; "remind me where I parked" = query).

---

## 8. Answer synthesis & conversational handling

**Synthesis (query):** system prompt restricts the answer to the listed memories; if no
memories are passed, short-circuit to the fixed "I don't have anything saved about that
yet." with **no** model call. Temperature ~0.2.

**General:** persona prompt — "You are Memex, a personal memory assistant… reply briefly
and warmly… never claim something is from the user's saved memories." Temperature ~0.4,
no memories passed. (Full prompt in `TDD-v3.md §3.4`.)

**Temporal summary:** present the listed window items concisely, oldest first, using only
the items given; empty window short-circuits to `"Nothing saved {label}."` with no model
call. (Details in `TDD-v3.md §4`.)

---

## 9. FastAPI — API contract

All endpoints require `Authorization: Bearer <supabase-jwt>`; `get_current_user`
validates via the Supabase service key and returns `user_id`. All data is scoped to it.

```
POST   /memories      { "content": str }                → 201 { "id", "created_at" }
GET    /memories                                        → 200 [{ "id","content","created_at" }]
DELETE /memories/{id}                                   → 200 { "deleted": true } | 404

POST   /chat   { "message": str, "tz": str|null }       # tz optional (Phase 10)
  Non-streaming → 200 { "intent":"store"|"query"|"general",
                        "reply": str, "id": str|null,
                        "source":"memory"|"general"|"none" }   # source optional/additive
  Streaming (?stream=true) → text/event-stream, "data: <chunk>\n\n", ends "data: [DONE]\n\n"

GET    /health                                          → 200 (used to warm a cold backend)
Errors: { "detail": str }, HTTP 401 / 404 / 422 / 500
```

`/chat` branches by intent: `store` → embed+save; `query` → temporal-window or
semantic search + synthesize; `general` → `chat_general`. Streaming mirrors the same
branches (store/general emit a single or few chunks; query streams synthesis/summary).

---

## 10. Authentication

- **Phases 1–4:** service_role key + placeholder `user_id`, RLS off — single trusted
  machine only. Never ship that key in a client.
- **Phase 5+:** anon key + Supabase email/password auth + RLS owner policy
  (`auth.uid() = user_id`). CLI persists the session to `~/.recall/session.json`.
- **Web:** `supabase.auth.signInWithPassword` / `signUp` in the browser; `@supabase/ssr`
  cookie; `proxy.ts` refreshes the session and guards `/chat`; `lib/api.ts` attaches the
  JWT to every FastAPI call. The service key never appears in the Next.js project.

---

## 11. Streaming (Phase 8)

FastAPI returns `StreamingResponse(media_type="text/event-stream")`; the generator yields
`data: <token>\n\n` per token and ends with `data: [DONE]\n\n`. `llm.synthesize_answer_stream`
(and the Phase 9/10 `*_stream` handlers) use `client.models.generate_content_stream`.

Next.js `lib/api.ts` `postChatStream()` reads the `ReadableStream`, splits on `\n\n`,
strips the `data: ` prefix, stops on `[DONE]`, and appends each chunk to the last
assistant message. It retries once with backoff, then falls back to non-streaming
`postChat()`, then to an inline error.

---

## 12. Web UX behaviour (Phase 11)

- **Refocus:** after a send settles (in a `finally`), focus the textarea; guard with
  `matchMedia('(pointer: fine)')` so mobile keyboards aren't forced open.
- **Type-while-loading:** the textarea is never disabled by `loading`; only the send
  action is gated (`if (loading) return;` in the Enter handler; `disabled={loading ||
  !input.trim()}` on the button).
- **Fast login → chat:** optimistic `router.push('/chat')` on auth success; render the
  `ChatLayout` shell before data loads; fire a fire-and-forget `GET /health` from the auth
  screen to warm a cold backend. Keep the server-side auth guard intact.

Full detail in `TDD-v3.md §5`.

---

## 13. Error handling & resilience

Wrap every external call (Supabase, Gemini) in try/except; surface a one-line human
message, never a raw traceback. On Gemini 429/network errors: retry with backoff (3
attempts, 500ms start) and a friendly message. A failed embedding on store must not
silently drop the memory — retry or tell the user it wasn't saved.

---

## 14. Configuration & secrets

```
# Python backend (.env)
SUPABASE_URL=...
SUPABASE_ANON_KEY=...            # CLI + web auth
SUPABASE_SERVICE_KEY=...         # FastAPI JWT validation only
GEMINI_API_KEY=...
CHAT_MODEL=gemma-4-26b-a4b-it
EMBED_MODEL=gemini-embedding-001
ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000

# Next.js (web/.env.local)
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...   # safe to expose — RLS enforces security
NEXT_PUBLIC_API_URL=https://your-api.railway.app
```

The service key must never appear in the Next.js project. `config.load_config()` validates
required vars and prints a friendly setup message (pointing to `.env.example`) if any are
missing.

---

## 15. Testing

Network-free unit tests: `router.route` heuristics incl. the greeting/meta fast-path;
`temporal.extract_range` (today/yesterday/this week/last N days/non-temporal → None, plus
a non-UTC tz boundary); classifier reply parsing (STORE/QUERY/GENERAL, default store);
config validation; CLI command parsing. Integration tests are the manual Definitions of
Done per phase.

---

## 16. Phase-by-phase plan

Phases 0–4: see this document's history and `MEMORY.md` (all complete).
Phases 5–8: detailed in `TDD-v2.md §10` (all complete).
Phases 9–11: detailed in `TDD-v3.md §3–§5`. Summary:

- **Phase 9 — GENERAL intent + conversational fallback.** `Intent` gains `"general"`;
  router greeting/meta fast-path + 3-way classifier; `llm.chat_general(_stream)`; CLI and
  `/chat` branches. Personal-recall miss stays strict. *DoD:* greetings/general questions
  reply conversationally and are not stored; personal miss still says "nothing saved".
- **Phase 10 — Temporal recall.** `temporal.extract_range`,
  `store.list_memories_in_range`, `llm.summarize_window(_stream)`, optional `tz` on
  `/chat`, new btree index, `tzdata` if needed. *DoD:* "today/yesterday/this week/last N
  days" return correct windows in the user's local day; empty window says "Nothing saved
  …".
- **Phase 11 — Web UX refinements.** Refocus input after reply; type-while-loading (send
  gated); optimistic chat shell + `/health` warm-up. *DoD:* cursor returns to input; can
  type but not send during a reply; fast, non-blank login → chat.

---

## 17. Open items to confirm during build

- Gemini streaming method for the v3 handlers (reuse the existing `generate_content_stream`
  pattern).
- `?`-heuristic decision for general-knowledge questions (`TDD-v3.md §3.2`); record in
  `MEMORY.md`.
- `zoneinfo`/tz database availability on the deploy target; add `tzdata` to
  `requirements.txt` if missing.
- Supabase free-tier inactivity-pause behaviour for long idle gaps.
- Whether to surface the optional `source` field in the UI now or later.
