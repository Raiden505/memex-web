# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Protocol

Every working session must follow this order — no exceptions:

1. **Read `MEMORY.md` first.** Check the current phase, decisions log, open questions, and session notes before writing a single line of code. Never assume you know the current state.
2. **Do the work.** Implement, fix, or investigate as requested. Follow the phase order in `TDD.md`; do not start a phase until the previous one's Definition of Done passes.
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

**Recall** — a personal memory CLI ("second brain"). You tell it things in plain language; it saves them to Supabase with Gemini embeddings. Later you ask questions; it retrieves semantically relevant memories and synthesizes an answer with Gemini. A RAG system over your own notes.

Full spec in `PRD.md` (product) and `TDD.md` (technical design, including phase-by-phase implementation plan). Follow the phases in order — each phase has a Definition of Done that must pass before starting the next.

## Commands

```bash
# Run the CLI
python -m recall

# Run tests
pytest

# Run a single test file
pytest tests/test_router.py

# Install dependencies
pip install -r requirements.txt

# Copy and fill in secrets before first run
cp .env.example .env
```

## Tech Stack

| Concern     | Choice                                            |
|-------------|---------------------------------------------------|
| Language    | Python 3.10+                                      |
| Database    | Supabase (Postgres + pgvector)                    |
| Embeddings  | Gemini embeddings via `google-genai`              |
| LLM         | Gemini 2.5 Flash via `google-genai`               |
| DB client   | `supabase` (supabase-py)                          |
| Config      | `python-dotenv` + env vars                        |

> Before writing any integration code, confirm current Gemini model identifiers and embedding output dimensions from official docs. Do not hardcode model strings from memory.

## Architecture

The CLI is a thin REPL loop (`cli.py`) that dispatches to isolated service modules. Two strict isolation rules:
- **Only `store.py`** knows about Supabase
- **Only `embeddings.py` and `llm.py`** know about Gemini

Everything else works through their function contracts, enabling backend swaps without touching the CLI.

**Store flow:** `router.route(text)` → `store` → `embeddings.embed(text)` → `store.add_memory(content, embedding, user_id)` → confirm with new id

**Query flow:** `router.route(text)` → `query` → `embeddings.embed(text)` → `store.search_memories(vector, user_id, top_k)` → `llm.synthesize_answer(question, results)` → print answer

## Module Contracts

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
synthesize_answer(question, memories) -> str   # Phase 3
classify_intent(text) -> Intent                # Phase 4 — "STORE" or "QUERY"

# router.py
route(text) -> Intent            # heuristic first, then classify_intent fallback

# auth.py (Phase 5)
login(client, email, password) -> Session
current_user_id(client) -> str
```

## Intent Routing (Phase 4)

Heuristic routes to **query** if: text ends with `?`, OR first word is `what/where/when/who/why/how/which`, OR it starts with `did i`/`do i`/`have i`. Everything else → ask the LLM classifier. If the LLM call fails, default to `store`.

"remind me to call mom" → STORE. "remind me where I parked" → QUERY. Do not add "remind me" to the heuristic — the LLM disambiguates it.

## Critical Constraints

- **Embedding dimension is locked at 768.** The `vector(768)` column type and embedding model output must agree. Never change the model without re-embedding every row.
- **No-hallucination rule:** if `search_memories` returns no results, short-circuit `synthesize_answer` and return a fixed "nothing saved about that" message without calling the LLM.
- **Security phases:** Phases 1–4 use the Supabase `service_role` key + a fixed placeholder `user_id` (RLS off). Phase 5 switches to the `anon` key + real auth + RLS policies. Never commit the service role key.

## Database

Run `supabase/schema.sql` in the Supabase SQL editor to set up the table, HNSW index, and `match_memories` RPC function. The RPC is how `store.search_memories` performs cosine similarity search.

## Testing

Unit-testable without the network: the heuristic in `router.route`, config validation, command parsing in `cli.py`. Integration tests are manual per-phase via the Definitions of Done in `TDD.md`.
