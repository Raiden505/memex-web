# MEMORY.md

Living project log for the Recall CLI. Updated by the agent at the end of every working session.
Read this before touching any code. Write to it after every change.

---

## Current State

- **Phase:** 8 — Streaming + hardening complete. Build + lint clean.
- **Last worked on:** 2026-05-31
- **Last agent action:** Phase 8 implemented — SSE streaming from FastAPI to Next.js with retry fallback. Backend chat router supports `?stream=true` returning `text/event-stream`. Frontend `postChatStream()` reads `ReadableStream`, parses SSE chunks, retries once on failure. Chat page tries streaming first, falls back to non-streaming `postChat()` on error, then shows inline error as last resort. Fixed chat.py router name shadowing (renamed FastAPI router to `chat_router`).

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
| 6     | FastAPI backend             | code complete | /memories CRUD + /chat endpoint behind JWT auth; Procfile for Railway |
| 7     | Next.js web app             | code complete | chat interface + auth pages + design system; build passes, lint clean |
| 8     | Streaming + hardening       | code complete | SSE streaming in FastAPI + Next.js; retry with non-streaming fallback; inline error display |

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

### 2026-05-31 — Phase 8 implemented
- **`recall/llm.py`** — added `synthesize_answer_stream()`: uses `client.models.generate_content_stream()` to yield tokens via `Generator[str, None, None]`.
- **`api/routers/chat.py`** — renamed FastAPI router to `chat_router` (fixed shadowed `router` import from `recall.router`). Added `?stream=true` query param support: when set, returns `StreamingResponse` with `text/event-stream`. `_stream_chat()` async generator yields `data: <token>\n\n` per token, ends with `data: [DONE]\n\n`. Store intent streamed as single chunk.
- **`api/main.py`** — updated router include to `chat.chat_router`.
- **`web/lib/api.ts`** — added `postChatStream()` (async generator): calls `/chat?stream=true`, reads `ReadableStream` with `getReader()`, parses SSE `data:` lines, handles `[DONE]` termination. Retries once with 800ms backoff on failure.
- **`web/app/chat/page.tsx`** — `handleSend` now tries `postChatStream()` first. First token replaces "Retrieving memories..." loading text, subsequent tokens append. If streaming fails, falls back to `postChat()` (non-streaming). If that also fails, shows "Couldn't reach memory" error inline.
- Build + lint clean. Frontend and backend ready.

### 2026-05-31 — Phase 7 Stitch rebuild (v2 — definitive)
Second full frontend rebuild from scratch, this time using Stitch HTML output as the **sole source of truth** (project `11872078192055407338`). PRD-v2.md / TDD-v2.md design specs explicitly ignored. Every color hex, font size, spacing value, and Tailwind class derived from the generated HTML.
- **`globals.css`** — `@theme inline` block maps all Material 3 colors verbatim from Stitch: surface (#f8f9fa), primary (#00236f), secondary (#416656), tertiary (#0d0097), outline (#757682), outline-variant (#c5c5d3), etc. Custom utilities: `.auth-bg` (radial gradients), `.glass-panel` (rgba(255,255,255,0.7) + blur(20px) + 0.5px #E5E7EB border), `.ai-glow` (0 0 40px -10px rgba(39,36,184,0.15)), `.input-pill` (shadow), `.message-enter` (200ms ease-out translateY), `.mode-toggle-transition` (0.3s cubic-bezier(0.4,0,0.2,1)).
- **`layout.tsx`** — Manrope (400-800), Inter (400-500,600), JetBrains Mono (500). Title "Memex".
- **`AuthForm.tsx`** — Exact Stitch login-desktop.html structure: glass-panel rounded-xl p-8, segmented control with sliding white pill (calc(50%-4px) width, translateX toggle), JetBrains Mono 14px labels, icon-prefixed inputs (person/mail/lock SVGs, 20px, left-3), focus:ring-2 ring-primary/20, password visibility toggle, "Continue to Memex" / "Create free account" submit button (bg-primary py-4, arrow_forward icon), "or continue with" divider (metadata style over #c5c5d3 border), Google/GitHub social grid (border-outline-variant rounded-lg py-3), TOS/Privacy footer (mt-8, metadata text, #444651).
- **`app/auth/page.tsx`** — `auth-bg` class with radial gradients (indigo 0.3 opacity + mint 0.2 opacity), fixed background blobs (bg-primary/5 blur-[80px], bg-secondary/5 blur-[100px]), centered flex layout.
- **`TopBar.tsx`** — Exact Stitch chat-desktop.html header: fixed top-0, bg-surface/70, backdrop-blur-xl, border-b-[0.5px] border-outline-variant/30, h-16, px-6, max-w-[800px] mx-auto. "Memex" in Manrope 24px/32px -0.01em weight 600 text-primary. Settings icon (SVG, not Material Symbols) + user avatar (h-8 w-8 rounded-full bg-primary-fixed border-outline-variant/30).
- **`ChatLayout.tsx`** — h-dvh flex flex-col bg-[#f8f9fa].
- **`ChatInput.tsx`** — Exact Stitch chat-desktop.html input: fixed bottom-0, gradient-to-t from-background, pb-8 pt-12. Pill: bg-surface border-outline-variant/50 rounded-full flex items-center p-2 gap-2, focus-within:ring-2 ring-primary/10. add_circle button (secondary color, hover:bg-secondary-fixed/30). Send button: p-3 bg-primary text-on-primary rounded-full, opacity-40 when disabled. Input: flex-1 bg-transparent, Inter 16px, placeholder:text-outline/70.
- **`MessageBubble.tsx`** — Exact Stitch chat-desktop.html bubbles. AI: flex flex-col gap-2 max-w-[85%]. Avatar row: w-6 h-6 rounded-lg bg-tertiary-container with sparkle icon + "Memex AI" metadata. Bubble: ai-glow, bg-white, border-outline-variant/50, p-4, rounded-2xl rounded-tl-none. User: flex flex-col gap-2 max-w-[85%] self-end items-end. Bubble: bg-primary text-on-primary p-4 rounded-2xl rounded-tr-none shadow-[0px_2px_4px_rgba(0,0,0,0.05)]. Timestamp + check_circle icon (secondary, FILL 1).
- **`DateDivider.tsx`** — Exact Stitch: flex justify-center my-8. Span: font-label-md text-outline, py-1 px-4, rounded-full, border border-outline-variant/30, bg-surface-container-low, uppercase tracking-wider.
- **`EmptyState.tsx`** — Centered: w-14 h-14 rounded-2xl bg-primary with sparkle icon + "Your extended cognitive field." (Manrope 18px) + subtitle (Inter 14px metadata, #757682).
- **`MessageList.tsx`** — max-w-[800px] mx-auto, px-6, pt-24 pb-32, flex flex-col gap-message-gap (12px). Groups messages by date, inserts DateDividers, auto-scrolls to bottom.
- **`app/chat/page.tsx`** — useState for messages, input, loading. handleSend: adds user msg → "Retrieving memories..." loading assistant msg → calls postChat → replaces loading msg with reply or error (isError: true). EmptyState shown when no messages.
- Build passes, lint clean. All 12 files rewritten. Stitch is the only design reference.

### 2026-05-31 — Phase 7 UI/UX redesign
Full visual redesign of all Phase 7 frontend files. Logic unchanged.
- `globals.css` — rewritten: `.auth-card` (responsive, bordered sm+/borderless mobile), `.auth-input` (labeled fields with focus ring), `.chat-input-wrapper` + `.chat-textarea` (integrated send button inside border, `focus-within` ring), cleaner `.bubble-user` / `.bubble-assistant`, custom scrollbar, removed stale `.chat-textarea` border/bg (now on wrapper).
- `types/index.ts` — added `isError?: boolean` to Message interface.
- `AuthForm.tsx` — labeled inputs (Email / Password labels above fields), field-level error display, signup email-confirmation notice, inline hover via JS (no Tailwind arbitrary hover for CSS vars), toggle is plain text with no underline per PRD.
- `app/auth/page.tsx` — simplified wrapper (`min-h-dvh`, padding only, no card logic — card is in `.auth-card` CSS).
- `TopBar.tsx` — added `"use client"`, content constrained to `max-w-2xl mx-auto` to align with message column.
- `ChatInput.tsx` — added `"use client"`, send button moved inside `.chat-input-wrapper` (bottom-right, always visible, disabled:opacity-25 when empty per PRD).
- `MessageBubble.tsx` — simplified; error color via inline style `color: var(--accent)`.
- `DateDivider.tsx` — inline styles for consistent CSS variable use.
- `EmptyState.tsx` — `select-none` added.
- `MessageList.tsx` — added `"use client"`, removed `errorMessage` prop (errors now in-line as messages), `max-w-2xl mx-auto` container for centered column on wide screens.
- `app/chat/page.tsx` — removed `errorMessage` state; loading dot (`·`) added immediately as assistant message, replaced with reply or error text in-place after API returns. Cleaner state flow.

### 2026-05-31 — Phase 7 implemented
- Scaffolded `web/` with `create-next-app` (Next.js 16.2.6, React 19, Tailwind v4, TypeScript). Installed `@supabase/ssr` + `@supabase/supabase-js`.
- Fixed Next.js 16 breaking change: `middleware.ts` → `proxy.ts` (deprecated convention). Same API: `export default async function proxy(request: NextRequest)`.
- `web/app/globals.css` — full design system from PRD-v2.md §6.2: CSS custom properties for light and dark (`@media (prefers-color-scheme: dark)`), Tailwind v4 `@theme inline` block referencing all color/font CSS variables, base typography (15px, 1.65 line-height), message bubble CSS classes, input area CSS, message entrance animation (200ms ease-out translateY).
- `web/app/layout.tsx` — Lora (400/600) and Plus Jakarta Sans (400/500) via `next/font/google`, CSS variables `--font-lora` / `--font-jakarta`, `min-h-dvh` body.
- `web/types/index.ts` — `Message` (id, role, content, date) and `Role` types.
- `web/lib/supabase/client.ts` — browser Supabase client via `createBrowserClient`.
- `web/lib/supabase/server.ts` — server Supabase client via `createServerClient` with cookie handling.
- `web/proxy.ts` — session refresh + route protection: redirects `/chat` → `/auth` if not authed, `/auth` → `/chat` if already authed.
- `web/lib/api.ts` — typed wrapper: `getMemories()` (GET /memories), `postChat(message)` (POST /chat). Reads JWT from browser Supabase session.
- `web/components/auth/AuthForm.tsx` — "use client": email/password form, sign-in / sign-up toggle, error text below fields, no toasts. Fonts and colors match PRD §7.1.
- `web/app/auth/page.tsx` — server component: centred AuthForm in `min-h-dvh` container.
- `web/app/page.tsx` — server component: checks session, redirects to `/chat` or `/auth`.
- `web/app/chat/layout.tsx` — server-side session check; redirects to `/auth` if absent.
- `web/components/ui/TopBar.tsx` — "sign out" button calls `supabase.auth.signOut()`.
- `web/components/chat/EmptyState.tsx` — centred "tell me something" in `text-faint`.
- `web/components/chat/MessageBubble.tsx` — user (right-aligned, dark bubble) and assistant (left-aligned, no background) variants. Error text in accent colour.
- `web/components/chat/DateDivider.tsx` — centred label ("Today"/"Yesterday"/"12 May") with thin lines.
- `web/components/chat/MessageList.tsx` — groups messages by date, inserts DateDividers, auto-scrolls to bottom via ref.
- `web/components/chat/ChatInput.tsx` — auto-expanding textarea (min 42px, max 130px), Enter sends, Shift+Enter for newline, arrow button.
- `web/components/chat/ChatLayout.tsx` — `h-dvh` flex column, TopBar + children.
- `web/app/chat/page.tsx` — "use client": owns all state (`messages`, `input`, `loading`, `errorMessage`). On send: adds user message → calls `postChat()` → adds assistant response or sets error. EmptyState shown when no messages.
- Build passes (no TypeScript errors), lint passes (no ESLint errors). Dev server ready: `cd web && npm run dev`.

### 2026-05-31 — Phase 6 implemented
- `api/__init__.py` — empty package marker.
- `api/dependencies.py` — `get_current_user` FastAPI dependency: extracts Bearer token via `HTTPBearer`, validates JWT with `supabase.auth.get_user(token)` using the service key, returns `user_id`. `get_db` provides the Supabase admin client.
- `api/routers/memories.py` — `POST /memories` (store, returns `{id, created_at}`), `GET /memories` (list all for user), `DELETE /memories/{id}` (404 if not found). All endpoints require `get_current_user` and scope operations to that user_id.
- `api/routers/chat.py` — `POST /chat`: routes message via `router.route()`, if store → embed + save, if query → embed + search + synthesize. Returns `{intent, reply, id}`.
- `api/main.py` — FastAPI app with CORS middleware (origins from `ALLOWED_ORIGINS` env), includes memories and chat routers, `/health` ping endpoint.
- `recall/store.py` — `add_memory` now returns the full row dict `{id, content, user_id, embedding, metadata, created_at}` instead of just the id string. `cli.py` updated accordingly.
- `Procfile` — `web: uvicorn api.main:app --host 0.0.0.0 --port $PORT` for Railway.

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
