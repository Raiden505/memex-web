# MEMORY.md

Living project log for the Recall CLI. Updated by the agent at the end of every working session.
Read this before touching any code. Write to it after every change.

---

## Current State

- **Phase:** 5 — auth implemented. Code complete, needs live Supabase DoD test with RLS deployed.
- **Last worked on:** 2026-05-31
- **Last agent action:** Implemented Phase 5 auth — created `recall/auth.py`, updated `recall/cli.py` with login/signup/reconnect flow, session persists to `~/.recall/session.json`, RLS enabled in schema.sql.

---

## Phase Completion

| Phase | Name                        | Status    | Notes |
|-------|-----------------------------|-----------|-------|
| 0     | Skeleton                    | complete  | DoD verified: banner, /help, /quit, friendly missing-config message |
| 1     | Cloud storage (no AI)       | code complete — needs live Supabase DoD test | run schema.sql in Supabase dashboard first |
| 2     | Semantic search             | code complete — needs live DoD test | /add now embeds; /search queries by meaning |
| 3     | Answers (RAG complete)      | code complete — needs live DoD test | /ask: embed → search → synthesize; no-hallucination short-circuit in place |
| 4     | Auto intent                 | code complete — needs live DoD test | heuristic + LLM classifier; bare text routes to store or query automatically |
| 5     | Auth (CLI + Supabase)       | code complete — needs live Supabase DoD test | login/signup, session persist, RLS on; 2nd session sees same memories, different account sees none |
| 6     | FastAPI backend             | planned    | per PRD-v2/TDD-v2; /memories CRUD + /chat endpoint behind JWT auth |
| 7     | Next.js web app             | planned    | per PRD-v2/TDD-v2; chat interface, auth pages, design system |
| 8     | Streaming + hardening       | planned    | per PRD-v2/TDD-v2; SSE streaming, retry logic, inline error display |

---

## Confirmed Values

Fill these in once confirmed against official docs before writing integration code.

- **Chat model ID:** `gemma-4-26b-a4b-it` (user preference — Gemma 4 26B MoE, available via Gemini API on AI Studio)
- **Gemini embedding model ID:** `gemini-embedding-001` (confirmed — `text-embedding-004` shut down Jan 2026)
- **Embedding output dimension:** 768 (confirmed — model default is 3072, truncated to 768 via `output_dimensionality` param, no quality loss per MRL)
- **Gemini free-tier RPM/RPD:** — (check https://ai.google.dev/gemini-api/docs/rate-limits before Phase 6)
- **Supabase project URL:** — (user-specific)

---

## Decisions Log

| Date       | Decision | Reason |
|------------|----------|--------|
| 2026-05-31 | Phase 5: `cfg.user_id` mutated after login in `main()` | Cleanest way to thread the authenticated UUID through all existing store calls without changing any function signatures |
| 2026-05-31 | Session saved to `~/.recall/session.json` (not inside the project dir) | Keeps credentials out of the repo entirely; works cross-platform via `Path.home()` |
| 2026-05-31 | Adopted PRD-v2/TDD-v2 multi-client plan | CLI + web app sharing one backend; phases 5-8 re-activated from deferred state |
| 2026-05-30 | `RECALL_USER_ID` env var overrides the default placeholder `user_id` in `Config` | Lets the user set a stable UUID without editing code; the placeholder stays as the default so Phase 1 works out-of-the-box |
| 2026-05-30 | Config validation exits with `sys.exit(1)` via `ConfigError` caught in `main()`, not a top-level exception | Keeps the REPL loop clean; the error is a setup problem, not a runtime fault |
| 2026-05-30 | `pytest` added to `requirements.txt` | Unit tests for router heuristic / config / CLI parsing are required per TDD §12 |
| 2026-05-30 | `ALTER TABLE memories DISABLE ROW LEVEL SECURITY` added explicitly to schema.sql (Phase 5+: re-enabled with owner policy) | Supabase enables RLS by default on all new tables; Phases 1-4 needed it off for service_role key access |
| 2026-05-30 | `task_type="RETRIEVAL_DOCUMENT"` on store, `task_type="RETRIEVAL_QUERY"` on search | Without task types, all memories score ~0.59 regardless of relevance — the model compresses scores into a narrow band. Task types restore meaningful ranking separation. |
| 2026-05-30 | Chat model changed from `gemini-2.5-flash` to `gemma-4-26b-a4b-it` | User preference. Model is a 26B MoE (4B active params) available via Gemini API. No code changes — model ID is read from `CHAT_MODEL` env var. |

---

## Open Questions / Blockers

- **[ACTION for Phase 5 DoD]** Run updated `supabase/schema.sql` in Supabase SQL editor (RLS now enabled with owner policy). Set `SUPABASE_ANON_KEY` in `.env`. Then: `python -m recall` → sign up with an email → store some memories → `/quit` → `python -m recall` again → restored session should show previous memories. Create a second account and verify it sees none of the first account's memories.
- **[ACTION for Phase 1 DoD]** Fill in real `SUPABASE_URL` and `SUPABASE_KEY` (service_role) in `.env`, then run `supabase/schema.sql` in the Supabase SQL editor. After that, test: `/add buy milk` → id appears; `/list` shows it; `/count` correct; `/forget <id>` removes it; quit+relaunch persists.
- **[ACTION for Phase 2 DoD]** Add `GEMINI_API_KEY` and set `EMBED_MODEL=gemini-embedding-001` in `.env`. Add a few distinct memories with `/add`, then test `/search` with different wording — right notes should surface with sensible similarity scores.
- Confirm Supabase free-tier inactivity-pause behavior before relying on long-idle persistence.

---

## Session Notes

Short log of what each session did. Prepend new entries (newest at top).

### 2026-05-31 — Phase 5 implemented
- `recall/auth.py` — new; `save_session`, `load_session`, `clear_session`, `restore_session`, `sign_in`, `sign_up`, `sign_out`. Session saved to `~/.recall/session.json`. `restore_session` sets JWT on client, refreshes token, and saves updated tokens.
- `recall/cli.py` — `_auth_flow()` added: tries session restore first, falls back to 1/2/q prompt for sign-in/sign-up. `cfg.user_id` mutated to authenticated UUID after login. `/logout` command added (signs out + clears local session). Help text updated.
- `recall/config.py` — `supabase_service_key` field added to Config dataclass (for FastAPI Phase 6). Env check now requires `SUPABASE_ANON_KEY` (with `SUPABASE_KEY` fallback for legacy .env files).
- `supabase/schema.sql` — RLS enabled with `owner can do everything` policy (`auth.uid() = user_id`).

DoD needs live test: run updated schema.sql in Supabase, set `SUPABASE_ANON_KEY` in .env, then `python -m recall` → login/signup → store some memories → quit → relaunch → same memories visible from restored session.

### 2026-05-31 — v2 plan adoption
- Adopted `PRD-v2.md` and `TDD-v2.md` as the new plan. Reversed the "Phase 5+ deferred indefinitely" decision. Phase 5 (Auth) is now up next.
- `AGENTS.md` — rewritten for multi-client architecture: new commands (FastAPI dev server, Next.js dev server), expanded directory structure (api/, web/), new isolation rules for api/ and web/ layers, FastAPI conventions, frontend conventions, updated critical constraints (RLS, JWT, CORS, streaming).
- `requirements.txt` — added `fastapi`, `uvicorn[standard]`, `python-jose[cryptography]` for Phase 6.
- `.env.example` — added `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `ALLOWED_ORIGINS` for multi-client auth.
- `supabase/schema.sql` — Phase 5 RLS policy lines uncommented; added `supabase_auth.users` auth table creation.
- `MEMORY.md` — updated phase table with v2 phases 5-8, updated current state.

### 2026-05-30 — Polish pass
- `recall/cli.py` — replaced plain `print()` with rich (Console, Table, Panel, status spinner). Help displayed in Panel, list/search in Tables, save/query show spinners during API calls, all output color-coded.
- `recall/config.py` — removed stale Phase 5 placeholder comment.
- `AGENTS.md` created for future OpenCode sessions.
- Phase 5/6 marked as "deferred" — treat Phase 4 as the terminal state for now.

### 2026-05-30 — Phase 5 (reverted)
Phase 5 was implemented then reverted at user request. All changes undone:
- `recall/auth.py` deleted
- `supabase/schema.sql` back to `DISABLE ROW LEVEL SECURITY`
- `recall/cli.py` login step removed
- `.env.example` back to service_role key + RECALL_USER_ID option restored

### 2026-05-30 — Phase 4
Files created/modified:
- `recall/router.py` — new; `route(text, cfg)`: heuristic handles ends-with-?, query-starter words, "did/do/have i" prefixes; ambiguous input falls through to `classify_intent`
- `recall/llm.py` — added `classify_intent(text, cfg)`: calls chat model at temp 0 with a few-shot STORE/QUERY system prompt; defaults to "store" on any exception
- `recall/cli.py` — bare text now routes through `router.route`; extracted `_do_store` and `_do_query` helpers shared by slash commands and auto-routing; removed `_NOT_YET` stub

DoD: test "remind me to call mom" (→ STORE) and "remind me where I parked" (→ QUERY). All slash commands still work.

### 2026-05-30 — Phase 3
Files created/modified:
- `recall/llm.py` — new; `synthesize_answer(question, memories, cfg)` calls `gemini-2.5-flash` at temperature 0.2 with a strict no-hallucination system prompt; short-circuits to a fixed message if no memories are passed (no LLM call)
- `recall/cli.py` — `/ask` wired: embed (RETRIEVAL_QUERY) → search_memories → synthesize_answer → print

Confirmed: `gemini-2.5-flash` is on free tier (10 RPM, ~250 RPD).
DoD status: code complete, imports verified. Test with `/ask` on stored content and on unstored content.

### 2026-05-30 — Phase 2
Files created/modified:
- `recall/embeddings.py` — new; `embed(text, cfg)` calls `gemini-embedding-001` with `output_dimensionality=768`
- `recall/cli.py` — `/add` now embeds before storing; `/search` wired (embed → search_memories → ranked results with similarity scores); `/ask` still a stub
- `.env.example` — updated `EMBED_MODEL` from dead `text-embedding-004` to `gemini-embedding-001`

Key finding: `text-embedding-004` was shut down Jan 14 2026. Use `gemini-embedding-001` (free tier, 768-dim output via MRL truncation).
DoD status: code complete, imports verified. Needs live Gemini API key to test.

### 2026-05-30 — Phase 1
Files created/modified:
- `supabase/schema.sql` — table, HNSW index, `match_memories` RPC (RLS off)
- `recall/store.py` — `get_client`, `add_memory`, `list_memories`, `delete_memory`, `count_memories`, `search_memories` (search_memories is a Phase 2 stub, included to complete the contract)
- `recall/cli.py` — wired `/add`, `/list`, `/count`, `/forget`; banner now shows live count from DB; `/ask` and `/search` still print not-yet stub

DoD status: code complete, imports verified. Needs real Supabase credentials + schema applied to run the live acceptance tests.

### 2026-05-30 — Phase 0
Files created:
- `recall/__init__.py`, `recall/__main__.py`, `recall/cli.py`, `recall/config.py`, `recall/models.py`
- `requirements.txt`, `.env.example`, `README.md`

DoD verified manually:
- `python -m recall` → banner + prompt shown
- `/help` → lists all 8 commands; `/quit` → clean exit
- Missing `.env` vars → prints friendly setup message with list of missing vars, no traceback

### 2026-05-30 — Init
- Initialized repository documentation: created `CLAUDE.md` and `MEMORY.md`.
- No source files existed yet. Project was at pre-Phase-0.
