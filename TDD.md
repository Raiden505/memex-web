# Technical Design Document — "Recall" CLI

Companion to `PRD.md`. This document is written to be followed by a coding agent.
Phase numbers here map 1:1 to the phases in the PRD. Each phase lists the files to
touch, the work to do, and a **Definition of Done** with the exact commands to verify.

> **Implementation note for the agent:** provider SDK package names, model
> identifiers, and free-tier limits change over time. Before writing integration
> code, confirm the current values against official docs:
> - Supabase Python client and pgvector usage
> - Google Gen AI SDK (the unified `google-genai` package) and current Gemini
>   model + embedding model identifiers
> Do not hardcode a model string from memory; read it from config and verify it works.

---

## 1. Architecture overview

A thin CLI client talks to two cloud services. The CLI holds all application
logic; the cloud holds state (the database) and intelligence (the LLM/embeddings).

```
            ┌─────────────────────────── your machine ──────────────────────────┐
            │                                                                    │
   you ───▶ │  CLI (REPL)                                                        │
            │    │                                                               │
            │    ├─ router ──▶ llm.classify_intent ─┐  (Phase 4)                 │
            │    │                                   │                            │
            │    ├─ store ────────────┐              │                            │
            │    ├─ embeddings ──┐     │             │                            │
            │    └─ llm.synthesize_answer            │                            │
            │                    │     │             │                            │
            └────────────────────┼─────┼─────────────┼────────────────────────────┘
                                 │     │             │
                       ┌─────────▼─┐ ┌─▼─────────────▼─┐
                       │  Gemini   │ │    Supabase      │
                       │  API      │ │  Postgres +      │
                       │ (embed +  │ │  pgvector + Auth │
                       │  chat)    │ │                  │
                       └───────────┘ └──────────────────┘
```

**Why this shape:** keeping the database and accounts in the cloud is what makes a
future second client (phone/web) a drop-in — it just authenticates to the same
Supabase project. The CLI is deliberately a thin client so that logic is portable.

## 2. Tech stack

| Concern        | Choice                            | Rationale                                            |
|----------------|-----------------------------------|------------------------------------------------------|
| Language       | Python 3.10+                      | Best ecosystem for this; matches the CLI form factor |
| Database       | Supabase (Postgres + pgvector)   | Free tier; DB + auth + API in one; pgvector is plenty up to ~10M vectors |
| Embeddings     | Gemini embeddings (free tier)    | Free; single provider with the chat model           |
| LLM            | Gemini 2.5 Flash (free tier)     | 1,500 req/day free is ample for personal use         |
| DB client      | `supabase` (supabase-py)         | Official client, handles auth + RPC                  |
| LLM client     | `google-genai`                   | Official unified Gemini SDK                          |
| Config         | `python-dotenv` + env vars       | Simple, standard secret handling                     |
| CLI            | Python stdlib REPL loop          | Minimal deps; `rich` optional for nicer output       |

Keep dependencies minimal. `rich` is optional and only for formatting.

## 3. Project structure

```
recall/
  __init__.py
  __main__.py         # entry point: `python -m recall` -> calls cli.main()
  cli.py              # REPL loop, command parsing, dispatch
  config.py           # env loading + validation, settings constants
  store.py            # all Supabase / pgvector access (the ONLY DB-aware module)
  embeddings.py       # Gemini embedding calls
  llm.py              # Gemini chat: synthesize_answer + classify_intent
  router.py           # intent routing (heuristic + llm) [Phase 4]
  models.py           # dataclasses: Memory, SearchResult, Intent
  auth.py             # Supabase auth login/session [Phase 5]
supabase/
  schema.sql          # table, index, RPC function, RLS policies
.env.example
requirements.txt
README.md
docs/
  PRD.md
  TDD.md
```

**Isolation rule:** only `store.py` knows about Supabase, only `embeddings.py` and
`llm.py` know about Gemini. Everything else works through their function
contracts. This is what lets the backend be swapped later without touching the CLI.

## 4. Data model

### Table: `memories`

| Column      | Type           | Notes                                              |
|-------------|----------------|----------------------------------------------------|
| `id`        | `uuid`         | Primary key, default `gen_random_uuid()`           |
| `user_id`   | `uuid`         | Owner. Phases 1–4 use a fixed placeholder; Phase 5 links to `auth.users` |
| `content`   | `text`         | The memory text                                    |
| `embedding` | `vector(768)`  | Must match the embedding model's output dimension  |
| `metadata`  | `jsonb`        | Reserved for future tags; default `'{}'`           |
| `created_at`| `timestamptz`  | Default `now()`                                    |

> **Embedding dimension lock-in (critical):** the `vector(768)` size must equal
> the dimension your embedding model outputs. Configure the embedding model to 768
> dimensions and never change the model afterward without re-embedding every row —
> vectors from different models are not comparable.

### `supabase/schema.sql` (target contents)

```sql
-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Table
create table if not exists memories (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null,
  content    text not null,
  embedding  vector(768),
  metadata   jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- 3. Similarity search index (cosine)
create index if not exists memories_embedding_idx
  on memories using hnsw (embedding vector_cosine_ops);

-- 4. RPC for semantic search (called from store.search_memories)
create or replace function match_memories(
  query_embedding vector(768),
  match_user_id   uuid,
  match_count     int
)
returns table (id uuid, content text, created_at timestamptz, similarity float)
language sql stable
as $$
  select m.id, m.content, m.created_at,
         1 - (m.embedding <=> query_embedding) as similarity
  from memories m
  where m.user_id = match_user_id
  order by m.embedding <=> query_embedding   -- <=> is cosine distance
  limit match_count;
$$;

-- 5. RLS — enabled in Phase 5 (see Security section)
```

### Dataclasses (`models.py`)

```python
@dataclass
class Memory:
    id: str
    content: str
    created_at: str
    user_id: str

@dataclass
class SearchResult:
    id: str
    content: str
    created_at: str
    similarity: float   # 0..1, higher = more similar

Intent = Literal["store", "query"]
```

## 5. Module contracts (function signatures the agent should implement)

These are the stable interfaces. Implement them progressively per the phase plan.

```python
# config.py
def load_config() -> Config        # reads + validates env; friendly error if missing
# Config fields: supabase_url, supabase_key, gemini_api_key,
#   chat_model, embed_model, embed_dim=768, top_k=5, user_id (placeholder until Phase 5)

# store.py  (Phase 1 = CRUD; Phase 2 adds search)
def get_client(cfg) -> Client
def add_memory(client, content: str, embedding: list[float] | None, user_id: str) -> str
def list_memories(client, user_id: str) -> list[Memory]
def delete_memory(client, mem_id: str, user_id: str) -> bool
def count_memories(client, user_id: str) -> int
def search_memories(client, query_embedding: list[float], user_id: str, k: int) -> list[SearchResult]

# embeddings.py  (Phase 2)
def embed(text: str) -> list[float]          # returns a 768-float vector

# llm.py
def synthesize_answer(question: str, memories: list[SearchResult]) -> str   # Phase 3
def classify_intent(text: str) -> Intent                                    # Phase 4

# router.py  (Phase 4)
def route(text: str) -> Intent               # heuristic first, then classify_intent

# auth.py  (Phase 5)
def login(client, email: str, password: str) -> Session
def current_user_id(client) -> str
```

## 6. Key flows

**Store flow (auto):** input text → `router.route` returns `store` → `embeddings.embed(text)`
→ `store.add_memory(content, embedding, user_id)` → confirm with the new id.

**Query flow (auto):** input text → `router.route` returns `query` →
`embeddings.embed(text)` → `store.search_memories(vector, user_id, top_k)` →
`llm.synthesize_answer(question, results)` → print the answer.

## 7. Intent routing design (Phase 4)

A fast heuristic handles the obvious cases without an LLM call; everything else
goes to the model. Keep the heuristic conservative so genuinely ambiguous input
falls through to the model.

**Heuristic → `query` if** the text ends with `?`, OR the first word is one of:
`what, whats, what's, where, when, who, why, how, which`, OR it starts with
`did i`, `do i`, `have i`. Otherwise → ask the model.

> Deliberately do **not** treat "remind me" / "tell me" as query in the heuristic —
> "remind me to call mom" is a *store*. Let the model disambiguate those.

**LLM classifier prompt (system):**
```
You decide whether a message is STORE or QUERY.
STORE = the user is telling you something to remember (a fact, idea, task, note).
QUERY = the user is asking a question or trying to recall something earlier.
Examples:
  "remind me to call mom tomorrow"    -> STORE
  "I had an idea for a running app"   -> STORE
  "my friend mentioned cheap jackets" -> STORE
  "what's my wifi password?"          -> QUERY
  "remind me where I parked"          -> QUERY
  "did I have any app ideas?"         -> QUERY
Reply with exactly one word: STORE or QUERY.
```
Use temperature 0. Parse the reply; if it contains "QUERY" → query, else store.
If the LLM call fails, default to `store` (safer to over-save than to lose input).

## 8. Answer synthesis design (Phase 3)

**System prompt:**
```
You are a personal memory assistant. Answer the user's question using ONLY the
memories listed below. Be concise and natural. If the memories don't contain the
answer, say you don't have anything saved about that. Never invent details.
```
**User message:** a numbered/bulleted list of the retrieved memories (each with its
date) followed by the question. Temperature ~0.2. If no memories are retrieved,
short-circuit and return "I don't have anything saved about that yet" without
calling the LLM.

## 9. Configuration & secrets

`.env` (never committed) holds:
```
SUPABASE_URL=...
SUPABASE_KEY=...           # see Security section for which key per phase
GEMINI_API_KEY=...
CHAT_MODEL=...             # confirm current Gemini Flash model id from docs
EMBED_MODEL=...            # confirm current Gemini embedding model id from docs
```
`config.load_config()` validates that all required vars are present and prints a
friendly setup message (pointing to `.env.example`) if any are missing. Provide a
complete `.env.example` with placeholder values and comments.

## 10. Security model

- **Phases 1–4 (single user, your machine only):** use the Supabase
  **service_role** key in your local `.env`, RLS off or permissive, and a fixed
  placeholder `user_id`. This is the fastest path while there is exactly one user
  on one trusted machine. **Never commit this key and never ship it in a client.**
- **Phase 5 (multi-device ready):** enable RLS on `memories`; switch the CLI to the
  Supabase **anon** key plus a real Auth login; add policies so each row is
  readable/writable only by `auth.uid()`. The `user_id` column now references the
  authenticated user. After this, any future client signing in to the same account
  is automatically scoped to the same rows.

Example Phase-5 RLS policy:
```sql
alter table memories enable row level security;
create policy "owner can do everything"
  on memories for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
```

## 11. Error handling & resilience (baseline everywhere, deepened in Phase 6)

- Wrap every external call (Supabase, Gemini) in try/except; surface a one-line
  human message, never a raw traceback, in the REPL.
- On a Gemini rate-limit / 429: in Phase 6, retry with backoff and optionally fall
  back to a second free provider (e.g. Groq) behind the same `llm`/`embeddings`
  interface. Earlier phases may simply print "rate limited, try again shortly".
- A failed embedding on store should not silently drop the memory; either retry or
  tell the user it wasn't saved.

## 12. Testing strategy

- **Unit-testable without the network:** the heuristic in `router.route`, config
  validation, command parsing in `cli.py`. Write small pytest cases for these.
- **Integration (manual, per phase):** the Definition-of-Done checks below are the
  primary acceptance tests. Run them by hand against real free-tier services.
- Keep `store.py`, `embeddings.py`, `llm.py` behind their function contracts so they
  can be stubbed for fast local testing of `cli.py`/`router.py`.

---

## 13. Phase-by-phase implementation plan

> Each phase is independently shippable and ends in a manual Definition of Done.
> Do not start a phase until the previous one passes.

### Phase 0 — Skeleton
**Files:** `__main__.py`, `cli.py`, `config.py`, `models.py`, `.env.example`,
`requirements.txt`, `README.md`.
**Work:** REPL loop reading input; command parser dispatching `/help` and `/quit`;
`config.load_config()` with friendly missing-var errors; print a banner and the
memory count placeholder (0 for now).
**Definition of Done:**
- `python -m recall` launches and shows a prompt.
- `/help` lists all commands; `/quit` exits cleanly.
- Removing a required var from `.env` makes startup print a clear setup message,
  not a traceback.

### Phase 1 — Cloud storage (no AI)
**Files:** `store.py`, `supabase/schema.sql`, extend `cli.py`.
**Work:** run `schema.sql` in Supabase (table + index + function; RLS off for now).
Implement `get_client`, `add_memory` (embedding=None for now), `list_memories`,
`delete_memory`, `count_memories`. Wire `/add`, `/list`, `/forget`, `/count`.
**Definition of Done:**
- `/add buy milk` returns an id; the row appears in the Supabase table editor.
- `/list` shows it; `/count` is correct; `/forget <id>` deletes it.
- Quit, relaunch — data is still there.

### Phase 2 — Semantic search
**Files:** `embeddings.py`, extend `store.py` (`search_memories` via the
`match_memories` RPC), extend `cli.py` (`/search`). Update `/add` to compute and
store the embedding.
**Work:** implement `embed(text)` against the Gemini embedding model (output 768
dims); on add, store the vector; `/search` embeds the query and calls the RPC.
**Definition of Done:**
- Add several distinct notes.
- `/search` with wording different from any stored note returns the right note(s),
  most-similar first, with similarity scores that make sense.

### Phase 3 — Answers (RAG complete)
**Files:** `llm.py` (`synthesize_answer`), extend `cli.py` (`/ask`).
**Work:** `/ask` runs embed → search → synthesize. Implement the no-hallucination
short-circuit when no memories are returned.
**Definition of Done:**
- `/ask` a question about stored content returns a natural, grounded answer.
- `/ask` about content you never stored says it has nothing saved (no invention).

### Phase 4 — Auto intent
**Files:** `router.py`, `llm.py` (`classify_intent`), refactor `cli.py` so bare
text (no leading `/`) goes through `router.route`.
**Work:** implement the heuristic + LLM classifier from §7. Bare statements →
store flow; bare questions → query flow. Slash commands remain overrides.
**Definition of Done:**
- Typing a statement stores it; typing a question answers it.
- "remind me to call mom" stores a task; "remind me where I parked" is answered as
  a question.
- All slash commands still work.

### Phase 5 — Accounts & multi-device readiness
**Files:** `auth.py`, `supabase/schema.sql` (enable RLS + policy), update `store.py`
to use the authenticated user id, update `cli.py` for a login step, switch `.env`
to the anon key.
**Work:** Supabase email/password login; persist the session locally; all store
calls scoped to `current_user_id`. Enable RLS and the owner policy.
**Definition of Done:**
- Logging in associates new and existing memories with your account.
- A fresh session logged into the same account (simulating a second device) sees
  the same memories.
- A different account sees none of your memories.

### Phase 6 — Hardening (optional)
**Files:** `llm.py`, `embeddings.py`, `store.py`, `config.py`.
**Work:** retry-with-backoff on 429/network errors; optional fallback provider
(e.g. Groq) behind the existing `llm`/`embeddings` contracts; friendlier messages.
**Definition of Done:**
- Forcing a rate limit or disconnecting the network yields a graceful message
  and/or automatic retry/fallback, never a crash.

---

## 14. Open items to confirm during build
- Current Gemini chat + embedding model identifiers and the embedding output-dim
  setting (must equal `vector(768)`).
- Current Gemini free-tier RPM/RPD so Phase 6 backoff thresholds are realistic.
- Supabase free-tier project inactivity-pause behavior (affects long idle gaps).
