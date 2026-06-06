# MEMORY.md

Living project log for the Recall CLI. Updated by the agent at the end of every working session.
Read this before touching any code. Write to it after every change.

---

## Current State

- **Phase:** 23–25 complete (Wave 3: accuracy & dates). **All planned phases complete.**
- **Last worked on:** 2026-06-06
- **Last agent action:** Wave 3 — (23) memory deep-dive via `mode:"recall"` (semantic-only, skips routing) + relevance floor `_filter_relevant` in `llm.synthesize_*` + rewritten `_SYSTEM_PROMPT`; (24) typed `due_at` column + index + backfill in `schema.sql`, `store.add_memory`/`update_metadata` keep `due_at`≡`metadata.due`, `list_due` uses column, new `list_due_in_range`, `temporal.extract_due_range`, `llm.summarize_due_window`, query path checks due-range before created_at-range, `extract_range` now word-boundary matches "today/yesterday/this week"; (25) forget defaults to single top match (bulk only on "everything/all"), `ForgetConfirm` overlay raised to `bottom-32 sm:bottom-36 z-[60]`.
- **⚠️ ACTION REQUIRED:** run the updated `supabase/schema.sql` (adds `due_at` column) **before** the new code is deployed — `add_memory` now writes `due_at` and will error if the column is missing.
- **Prior agent action:** Phase 22 — quick-capture, voice input, command palette, PWA, shared memory.

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
| 9     | Conversational range (GENERAL) | code complete | `Intent` += "general"; router greeting/meta fast-path + 3-way classifier; `llm.chat_general(_stream)`; CLI + FastAPI general branch; optional `source` field. Personal-recall miss stays strict. |
| 10    | Temporal recall             | code complete | `temporal.extract_range`, `store.list_memories_in_range`, `llm.summarize_window(_stream)`, optional `tz` on `/chat`, `memories_user_created_idx` index. |
| 11    | Web UX refinements          | code complete | refocus input after reply (desktop only); type-while-loading (send gated); optimistic chat shell + `/health` warm-up from auth page. |
| 12    | Auth & onboarding hardening | code complete | password-eye works; duplicate-signup handled; name→`user_metadata`; humane errors; resend confirmation. `web/components/auth/AuthForm.tsx`, new `web/lib/auth-helpers.ts`, `Icon.tsx` (+`visibility_off`). |
| 13    | Transitions & status states | code complete | branded splash hand-off (SplashTransition); neutral 3-dot indicator replaces "Retrieving memories…" via `pending` flag; first-token swap. `web/app/chat/page.tsx`, `MessageBubble.tsx` (+`PendingIndicator`), `MessageList.tsx` (pass `pending`), `SplashTransition.tsx` (new), `LoadingSkeleton.tsx` (new), `globals.css` (+dot-pulse/skeleton-shimmer). |
| 14    | Reliable streaming          | code complete | **root cause fixed:** `api/routers/chat.py` now JSON-encodes SSE frames via `_sse({"t"|"done"|"error"})`; `web/lib/api.ts` splits on `\n\n` event boundaries and `JSON.parse`s each frame. Tokens with newlines survive transport losslessly. |
| 15    | Personality & prompt system | code complete | `recall/prompts.py` (all prompts + `MEMEX_VOICE` + `SAVE_ACKS`); `llm.save_ack()` replaces fixed "Saved." in CLI + API. No-hallucination short-circuits unchanged. |
| 16    | Natural-language forget     | code complete | 4th intent `forget`; router heuristic + 4-way classifier; `store.delete_memories`; two-step confirm (`confirm_forget`/`forget_candidates`) in API; `fc` SSE frame captured by `postChatStream`; `ForgetConfirm.tsx`; CLI bare-text forget flow with y/N prompt. |
| 17    | Richer chat UI & theme depth | complete | remove standing "TODAY" divider (only between differing dates); welcoming empty state + suggestion chips; `RecentMemories` cards from `getMemories`; elevation/depth tokens. |
| 18    | Settings menu & dark mode   | complete | `SettingsMenu` dropdown by logout; **real dark mode = tokenise hardcoded hex** (`AuthForm` `#00236f`, `MessageBubble` `bg-white`); `data-theme` + no-flash script; `web/lib/theme.ts`. |
| 19    | Memory Library              | complete  | `/library` route; `PATCH /memories/{id}` re-embeds; `POST /memories/{id}/pin`; `GET /memories/count`; client search/filters; inline edit/delete confirm; pinned-first sort. |
| 20    | Organisation & reminders    | complete       | auto-tags (`metadata.tags`, closed label set), `temporal.extract_due` → `metadata.due`, `GET /memories/due`. Best-effort, never blocks save. |
| 21    | Data ownership & insights   | complete       | export/import (`/memories/export`, `/import` w/ de-dup), `/memories/stats`, on-demand digest. |
| 22    | Capture & reach             | complete       | quick-capture, Web Speech voice input, `Cmd/Ctrl+K` command palette, installable PWA, optional shared single memory. |
| 23    | Accurate recall             | complete       | memory deep-dive (`mode:"recall"`, semantic-only); relevance floor `_filter_relevant`; rewritten synthesis prompt. |
| 24    | Due-date recall             | complete       | typed `due_at` column + index + backfill; `extract_due_range`; `list_due_in_range`; `summarize_due_window`; due-range checked before created_at-range; `extract_range` word-boundary match. |
| 25    | Forget precision & dialog   | complete       | natural delete → single top match (bulk only on "everything/all"); `ForgetConfirm` overlay raised above input bar. |

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
| 2026-06-06 | Due dates get a typed `due_at timestamptz` column (synced with `metadata.due`), not metadata-only | User chose it; date-range filters on a typed/indexed column are robust vs ISO-string compare in jsonb. Kept `metadata.due` too so display/export and existing code paths are untouched. **Requires running the migration before deploy** (writes set `due_at`). |
| 2026-06-06 | Memory-click "deep-dive" added a `mode:"recall"` flag that skips routing + temporal parsing and does semantic-only synthesis | The old click stuffed the whole note into a routed query string — circular, noisy, and could be mis-routed to STORE or hijacked by a `due`/`task`/date word inside the note. A dedicated mode is deterministic and accurate without a new endpoint. |
| 2026-06-06 | Forget: temporal/all bulk only when "everything/all/every/each" present; else single top semantic match | User reported a plain delete offering 3 memories — caused by a stray date word triggering the temporal-range branch. Gating bulk to explicit quantifiers matches intent; the semantic path already returns the highest-similarity match. |
| 2026-06-06 | `extract_due_range` checked before `extract_range` in the query path; due-intent detected by `_DUE_INTENT_RE` | "what's due today" must read due dates, not save dates. Keyword gate keeps "what did I save today" on the created_at path. Also relaxed `extract_range` from whole-string equality to word-boundary search so natural phrasing triggers temporal recall. |
| 2026-06-06 | Synthesis: drop weak matches (`_filter_relevant`, floor 0.2 / spread 0.2) + rewrote `_SYSTEM_PROMPT` | Inaccurate answers came from passing all top-k memories regardless of similarity; an off-topic note derailed replies. Filtering tightens grounding and reinforces no-hallucination (empty after filter → "nothing saved"). |
| 2026-06-02 | Wave 2 (phases 12–22) planned into `PRD-v3.md`/`TDD-v3.md` Part II rather than new files | User asked to "add to" the existing v3 docs; phase numbers continue 12+; the requested fixes (12–18) ship before the new product surface (19–22) |
| 2026-06-02 | Streaming bug diagnosed: tokens with `\n` break `data: {token}\n\n` SSE framing; `api.ts` drops any line not starting with `data: `. Fix = JSON-encode each frame (`{t|done|error}`) and split client buffer on `\n\n` | Pinpointed from reading `chat.py` `_stream_chat` + `api.ts` `postChatStream`; JSON-encoding is the simplest lossless transport and avoids fiddly multi-`data:` rejoining |
| 2026-06-02 | New state (pin/tags/due/shared) rides existing `metadata jsonb`; name rides `user_metadata`; only optional GIN index + optional shared-RLS policy are schema changes | Keeps Wave 2 migration-light; `vector(768)`/HNSW/`match_memories` untouched |
| 2026-06-02 | Natural-language forget uses a stateless two-step confirm (`confirm_forget` ids in the request), never deletes on the first turn | Destructive + irreversible; carrying the confirm token in the request avoids server session state while guaranteeing an explicit confirm |
| 2026-06-02 | v3 fallback rule: add a 3rd `GENERAL` intent for greetings/general-knowledge (always answered by Gemini); personal-recall (`query`) misses still return the fixed "nothing saved" — Gemini never invents personal facts | User choice. Greetings/general are classified up front and never hit the DB, which keeps the no-hallucination guarantee intact for personal facts while still handling non-memory input gracefully |
| 2026-06-02 | Consolidated all spec into `PRD.md` / `TDD.md` (v1+v2+v3, phases 0–11); kept `PRD-v2/TDD-v2` + new `PRD-v3/TDD-v3` as detailed references | User asked to amend v2 + new v3 into the original docs; originals are now the single current source, version docs hold per-phase detail |
| 2026-06-02 | Temporal recall via `created_at` btree index + `list_memories_in_range`, not a new RPC/schema column; tz passed from the web client (`Intl…timeZone`) | "today" must mean the user's local day; a filtered select on an indexed column is enough, no vector change needed |
| 2026-06-02 | Docs reflect shipped reality: app branded **Memex**, Material-3/Manrope-Inter design (Stitch), not PRD-v2 §6 parchment/Lora; v3 is behavioural/UX only, no visual redesign | Implementation diverged from PRD-v2 §6 in the Phase 7 rebuild; docs should not contradict the codebase |
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

- **[ACTION for Wave 3 / Phase 24]** Run the updated `supabase/schema.sql` in the Supabase SQL editor. It adds the `due_at timestamptz` column, the `memories_user_due_idx` index, and backfills `due_at` from existing `metadata.due`. Must happen **before** deploying the new backend — `store.add_memory` now writes `due_at`. After migrating, verify: save "submit report tomorrow", then ask "what's due today/tomorrow" and confirm the due-window listing; delete a single note by description and confirm only one candidate appears.
- **[ACTION for Phase 5 DoD]** Run updated `supabase/schema.sql` in Supabase SQL editor (RLS now enabled with owner policy). Set `SUPABASE_ANON_KEY` in `.env`. Then: `python -m recall` → sign up with an email → store some memories → `/quit` → `python -m recall` again → restored session should show previous memories. Create a second account and verify it sees none of the first account's memories.
- **[ACTION for Phase 1 DoD]** Fill in real `SUPABASE_URL` and `SUPABASE_KEY` (service_role) in `.env`, then run `supabase/schema.sql` in the Supabase SQL editor. After that, test: `/add buy milk` → id appears; `/list` shows it; `/count` correct; `/forget <id>` removes it; quit+relaunch persists.
- **[ACTION for Phase 2 DoD]** Add `GEMINI_API_KEY` and set `EMBED_MODEL=gemini-embedding-001` in `.env`. Add a few distinct memories with `/add`, then test `/search` with different wording — right notes should surface with sensible similarity scores.
- Confirm Supabase free-tier inactivity-pause behavior before relying on long-idle persistence.
- **[v3 / Phase 9 design] Decided: `?`-ending input removed from heuristic; all `?`-ending text goes to the 3-way classifier (option a from `TDD-v3.md §3.2`). Query-starter words + "did/do/have i" prefixes still short-circuit to QUERY.
- **[v3 / Phase 10] Done.** `tzdata` added to `requirements.txt`. `ZoneInfo` works with system timezone database on Windows and Linux. Railway/Render Linux images include `tzdata`; the pip package provides a fallback.

---

## Session Notes

Short log of what each session did. Prepend new entries (newest at top).

### 2026-06-06 — Wave 3 (phases 23–25): accuracy & dates
- **Phase 23 — accurate recall.**
  - `recall/llm.py` — added `_filter_relevant(memories)` (keep similarity ≥ max(0.2, top−0.2)); applied at the head of `synthesize_answer` and both stream variants → empty after filter returns `_NO_MEMORIES`.
  - `recall/prompts.py` — rewrote `_SYSTEM_PROMPT` (lead with a direct answer, use only the relevant memory, never guess).
  - `api/routers/chat.py` — `ChatRequest.mode`; `mode=="recall"` forces `intent="query"` + `semantic_only=True` threaded through `_handle_query`/`_stream_chat` (skips temporal/due parsing → pure semantic synthesis).
  - `web/lib/api.ts` — `postChat`/`postChatStream` accept `{mode}`.
  - `web/app/chat/page.tsx` — `handleSend` refactored into `sendText(text, opts)`; new `handleAskMemory` sends `"Tell me about: <content>"` with `{mode:"recall"}`.
  - `web/components/chat/{EmptyState,RecentMemories}.tsx` — memory cards call `onAskMemory(content)`; dropped the old `What do I know about: …?` / `Tell me about:` query-string stuffing. `RecentMemories` prop `onSuggestion`→`onAskMemory`.
- **Phase 24 — due-date recall.**
  - `supabase/schema.sql` — `due_at timestamptz` column + `memories_user_due_idx` + backfill from `metadata->>'due'`.
  - `recall/store.py` — `add_memory` mirrors `metadata.due`→`due_at`; `update_metadata` syncs `due_at` when `"due"` in updates; `list_due` filters the `due_at` column; new `list_due_in_range(start,end)`.
  - `recall/temporal.py` — `_DUE_INTENT_RE`; new `extract_due_range` (windows: overdue/tomorrow/today/this&next week/generic "soon"); `extract_range` relaxed to word-boundary `re.search` for today/yesterday/this week.
  - `recall/prompts.py` — `_DUE_SUMMARY_SYSTEM`. `recall/llm.py` — `summarize_due_window` + `_stream_async` + `_due_lines`.
  - `api/routers/chat.py` + `recall/cli.py` — query path checks `extract_due_range` before `extract_range`; `source`/empty detection includes "Nothing due".
- **Phase 25 — forget precision & dialog.**
  - `api/routers/chat.py` `_resolve_forget_candidates` + `recall/cli.py` `_do_forget_natural` — bulk (all/temporal) only when `_FORGET_BULK_RE` matches; default = single top match (`results[0]` if sim ≥ 0.6).
  - `web/app/chat/page.tsx` — `ForgetConfirm` overlay `bottom-24 z-10` → `bottom-32 sm:bottom-36 z-[60]` (above the z-50 input bar).
- **Docs** — PRD.md §13 + phase-table rows 23–25; TDD.md §18 + `due_at` in the data model; this file.
- Python compiles; `tsc --noEmit` clean for changed files (only pre-existing stale `.next` `app/demo` validator errors remain). No automated tests exist yet (manual DoD).

### 2026-06-04 — Phase 22 implemented
- **`api/routers/memories.py`** — `POST /memories` now embeds content, extracts due date, inserts with initial metadata, and enqueues `_apply_tags_bg` background task (same pattern as chat route); added `_apply_tags_bg` helper; imports `BackgroundTasks`, `llm`, `temporal`.
- **`web/lib/api.ts`** — added `createMemory(content)` calling `POST /memories`.
- **`web/components/ui/Icon.tsx`** — added `close`, `mic`, `mic_off` SVG icons.
- **`web/components/chat/ChatInput.tsx`** — added `captureMode`/`onExitCapture` props: in capture mode shows "Save" badge + × button and changes placeholder; added voice input via Web Speech API (`window.SpeechRecognition || webkitSpeechRecognition`), feature-detected at module level; mic button hidden when unsupported; listening state drives mic/mic_off toggle + animate-pulse; `any` casts for untyped browser API.
- **`web/components/ui/CommandPalette.tsx`** (new) — modal opened by `Cmd/Ctrl+K`; four commands: Quick save, Open Library, Today's digest, Toggle theme (cycles light→dark→system); controlled `query` filter; arrow key + Enter keyboard nav; `active` index; closes on Escape/outside-click.
- **`web/components/chat/ChatLayout.tsx`** — added `"use client"` + optional `onCapture` prop threaded to `TopBar`.
- **`web/components/ui/TopBar.tsx`** — added optional `onCapture` prop; renders `add_circle` button (titled "Quick save (C)") when provided, left of SettingsMenu.
- **`web/app/chat/page.tsx`** — added `captureMode` + `paletteOpen` state; imported `createMemory` + `CommandPalette`; `SAVE_ACKS` client-side pool; `handleCapture` activates capture mode + focuses input; `handleSend` branches on `captureMode` (calls `createMemory`, shows random ack, optimistic UI); global `keydown` effect: `c` (outside input) → capture mode, `Cmd/Ctrl+K` → palette toggle, `Escape` → exit capture; `CommandPalette` rendered with `onDigest` wired to `handleSuggestion`.
- **`web/app/manifest.ts`** (new) — `MetadataRoute.Manifest`: name Memex, `start_url /chat`, `display standalone`, `theme_color #00236f`, SVG icon.
- **`web/public/icon.svg`** (new) — rounded-rect "M" brand icon (512×512, dark blue bg).
- **`web/public/sw.js`** (new) — network-first service worker; caches HTML navigation responses as visited; serves from cache when offline; cleans up old caches on activate.
- **`web/app/layout.tsx`** — SW registration script added inline alongside existing no-flash theme script.
- TypeScript check passes clean.

### 2026-06-04 — Phase 21 implemented
- **`recall/store.py`** — added `content_exists(client, user_id, content) -> bool` (ilike check for de-dup).
- **`api/routers/memories.py`** — added `GET /memories/export` (full memory list as JSON), `POST /memories/import` (per-item exact-match then cosine ≥ 0.97 de-dup, returns `{imported, skipped}`), `GET /memories/stats` (`total`, `added_last_30d`, `top_tags` computed in Python from list_memories). All three endpoints positioned before `/{mem_id}` routes to avoid path conflicts.
- **`web/lib/api.ts`** — added `exportMemories()`, `importMemories(items)`, `getStats()`.
- **`web/components/ui/SettingsMenu.tsx`** — "Export my data" triggers real JSON download via `Blob + URL.createObjectURL`; "Import memories" triggers hidden `<input type=file accept=.json>` ref; on file selection, parses JSON, calls `importMemories`, shows `importStatus` inline ("Imported X, skipped Y." or error); version bumped to v0.21; About section updated with explicit Supabase/Gemini free-tier privacy copy.
- **`web/app/library/page.tsx`** — added `addedLast30d` and `topTags` memos computed from existing `memories` state (no extra API call); insights bar rendered above search filters showing "X memories · Y added this month · top tags: …" (hidden when loading or empty).
- Daily digest (R21.4): handled by existing temporal chat flow ("what did I save today?" → temporal recall path). No new UI button needed.
- TypeScript check passes, Python syntax valid.

### 2026-06-04 — Phase 20 implemented
- **`recall/prompts.py`** — added `_TAG_SYSTEM` (closed-label-set tagger prompt, temperature 0).
- **`recall/temporal.py`** — added `_FUTURE_DAYS_RE`, `_MONTH_MAP`, `_MONTH_NAMES_RE`; new `extract_due(text, tz, now)` returning naive UTC datetime for first future date found. Patterns: "tomorrow", "in N days/weeks/months", "next week", "next month", "next/on [weekday]", "[Month] [Day]", ISO date. Returns None for past dates or no match.
- **`recall/llm.py`** — imported `_TAG_SYSTEM`; defined `_VALID_TAGS` frozenset; new `tag_memory(content, cfg) -> list[str]` (temp 0, filters to closed set, swallows exceptions).
- **`recall/store.py`** — `add_memory` gains optional `metadata: dict | None = None`; new `update_metadata(client, mem_id, user_id, updates)` (fetch-merge-update); new `list_due(client, user_id, before)` filtering `metadata->>due` not-null + lte.
- **`api/routers/memories.py`** — imported `datetime/timedelta/timezone`; added `GET /memories/due` returning memories due in next 7 days + overdue (positioned before `/{mem_id}` variants to avoid route conflict).
- **`api/routers/chat.py`** — imported `BackgroundTasks`; added `_apply_tags_bg` background helper; `chat` endpoint gains `background_tasks` param; both non-streaming and streaming store branches now compute `extract_due`, write initial metadata, enqueue `_apply_tags_bg`.
- **`recall/cli.py`** — `_do_store` computes `extract_due` + passes initial metadata; tags computed inline after ack, swallowed on failure.
- **`web/types/index.ts`** — extracted `MemoryMetadata` interface (pinned, tags, due); `Message` and `Memory` use it.
- **`web/lib/api.ts`** — imported `MemoryMetadata`; `getMemories` uses it; added `getDueMemories()` (`GET /memories/due`).
- **`web/app/library/page.tsx`** — rewrote: `DueRow` component with overdue/upcoming label; `Due & Upcoming` section at top of main (hidden when empty); tag filter chips row (All + 8 closed-set tags with counts, disabled when count=0); tag pills in `MemoryRow` below content; `selectedTag` filter state; `tagCounts` memo; `handleDelete` also removes from `dueMemories`.
- TypeScript check passes, Python syntax valid.

### 2026-06-03 — Phase 19 implemented
- **Backend:**
  - `recall/models.py` — added optional `metadata` field to `Memory` and `SearchResult` dataclasses.
  - `recall/store.py` — `list_memories` now selects `metadata`; added `update_memory(mem_id, user_id, content, embedding)`; added `set_pinned(mem_id, user_id, pinned)` writing to `metadata` jsonb; added `search_memories_text(user_id, query)` for server-side substring search (available, library uses client-side).
  - `api/routers/memories.py` — extended with `PATCH /memories/{id}` (re-embeds via `embeddings.embed` then `store.update_memory`), `POST /memories/{id}/pin` (`store.set_pinned`), `GET /memories/count` (`store.count_memories`). `GET /memories` now returns `metadata` in `MemoryOut`.
  - `supabase/schema.sql` — `match_memories` RPC now returns `metadata jsonb`; added optional `memories_metadata_idx` GIN index for future metadata queries.
- **Frontend:**
  - `web/types/index.ts` — added `metadata?: { pinned?: boolean } | null` to `Message`; new `Memory` interface.
  - `web/lib/api.ts` — added `getMemoryCount()`, `updateMemory(id, content)`, `deleteMemory(id)`, `setPinned(id, pinned)`. `getMemories` now passes `metadata` through.
  - `web/components/ui/Icon.tsx` — added `arrow_back`, `edit`, `pin`, `search` SVG icons.
  - `web/app/library/layout.tsx` — auth guard (same pattern as `/chat`).
  - `web/app/library/page.tsx` — full Library page: fixed header with back arrow + count badge; search bar + time-window dropdown (All time / Today / Yesterday / This week / Last 7 days / Last 30 days); client-side filtering; list of `MemoryRow` components with pin toggle, inline edit (textarea, Enter-to-save, Escape-to-cancel), inline delete confirm (Yes/No); skeleton loading states; empty state.
  - `web/components/ui/SettingsMenu.tsx` — Memory Library button now `router.push("/library")` instead of alert placeholder.
  - `web/components/chat/RecentMemories.tsx` — now sorts `pinned` memories to the top before slicing top-5.
  - `web/proxy.ts` — matcher includes `/library/:path*`; redirect unauthenticated library requests to `/auth`.
- Build passes, lint clean.

### 2026-06-03 — Phase 17 re-implemented from scratch
- Rewrote all Phase 17 files fresh (no diff reuse):
  - `MessageList.tsx` — message-based iteration with date-change-only dividers.
  - `EmptyState.tsx` — fetch-first-name from Supabase, branded icon, headline/subtitle, 4 suggestion chips, `onSuggestion` prop.
  - `RecentMemories.tsx` — fetch `getMemories`, skeleton placeholders, top-5 clickable cards, relative dates, empty-state message.
  - `TopBar.tsx` — preserved Phase 18 SettingsMenu; `auto_awesome` brand accent next to wordmark.
  - `chat/page.tsx` — preserved all Phase 16 forget + Phase 18 booting logic; `handleSuggestion` callback wired to `EmptyState`.
  - `globals.css` — preserved full Phase 18 dark-mode token map; elevation utilities rewritten fresh.
- Build passes, lint clean.

### 2026-06-03 — Phase 18 implemented
- **`web/lib/theme.tsx`** (new) — `ThemeProvider` context with `light`/`dark`/`system` support. Initializes from `localStorage` via lazy state initializer (no setState in effects). `resolved` computed via `useMemo` from `resolveTheme()`. Applies `data-theme` attribute to `<html>` in `useEffect`. Listens to `prefers-color-scheme` changes when in `system` mode. `useTheme()` hook exported.
- **`web/app/providers.tsx`** (new) — client component wrapping `ThemeProvider` around children. Imported by `layout.tsx`.
- **`web/app/layout.tsx`** — added no-flash inline `<script>` in `<head>` that reads `localStorage.theme` before paint and sets `data-theme` on `<html>` immediately. Prevents FOUC on reload.
- **`web/app/globals.css`** — added complete `[data-theme="dark"]` override block mapping every semantic color token to a dark Material-3-compatible value. Dark body uses subdued radial gradients. Dark `.glass-panel` uses `rgba(27,30,36,0.7)`. Dark elevation shadows use stronger opacity. All remaining hardcoded hex values removed (glass-panel border now uses `var(--color-outline-variant)`).
- **`web/components/ui/SettingsMenu.tsx`** (new) — dropdown popover from settings icon in `TopBar`. Contains: segmented theme toggle (Light/Dark/System), signed-in email display, "Memory Library" and "Export my data" placeholder actions (alert for now, wired in Phase 19/21), and an "About Memex" footer with version + privacy caveat. Closes on outside-click and Escape. Keyboard-navigable with `role="menu"`/`role="menuitem"`.
- **`web/components/ui/Icon.tsx`** — added `sun`, `moon`, `monitor` SVG icons for the theme toggle.
- **`web/components/ui/TopBar.tsx`** — fetches user email via `supabase.auth.getUser()` on mount. Renders `SettingsMenu` left of the logout button.
- **`web/components/auth/AuthForm.tsx`** — replaced hardcoded `color: "#00236f"` with `text-primary` Tailwind class. Replaced inline `style={{ color: ... }}` on segmented toggle buttons with conditional `className` using `text-primary` / `text-on-surface-variant`.
- **`web/components/chat/MessageBubble.tsx`** — replaced `bg-white` with `bg-surface-container-lowest`.
- **`web/components/chat/ForgetConfirm.tsx`** — replaced `bg-white` with `bg-surface-container-lowest`.
- Build passes, lint clean. Phase 18 code complete.

### 2026-06-03 — Phase 17 implemented
- **`web/components/chat/MessageList.tsx`** — rewrote from group-based to message-based iteration. `DateDivider` now only renders when the date label changes from the previous message (`i > 0 && formatDate(msg.date) !== formatDate(messages[i-1].date)`). No more standing "TODAY" chip on single-day sessions.
- **`web/components/chat/EmptyState.tsx`** — complete redesign (now "use client"). Fetches `firstName` from `supabase.auth.getUser().user_metadata.full_name` on mount. Renders: branded icon (psychology in primary circle), warm headline (`Welcome back, {firstName}.` or fallback), one-line subtitle, and 4 tappable suggestion chips in a `flex-wrap` row. All chips call `onSuggestion(text)` → auto-prefills input and sends.
- **`web/components/chat/RecentMemories.tsx`** (new) — self-contained component fetching `getMemories()` on mount. Shows `skeleton-pulse` placeholders (3 cards) while loading. Renders top 5 memories as clickable cards in a responsive CSS grid (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`). Each card shows content (line-clamp-2) + relative date (`Just now` / `5m ago` / `2h ago` / `3d ago`). Click prefills input with `What do I know about: <content>?`. Empty state shows friendly "Nothing saved yet — tell me something to remember."
- **`web/app/globals.css`** — added `.elevation-1`, `.elevation-2`, `.elevation-3` box-shadow utilities. Applied `elevation-1` to recent-memory cards and the welcome icon container.
- **`web/components/ui/TopBar.tsx`** — added a small `auto_awesome` icon (tertiary color) next to the "Memex" wordmark for a subtle brand accent.
- **`web/app/chat/page.tsx`** — added `handleSuggestion` callback (sets input, defers `handleSend()` via setTimeout to flush DOM). Passed to `<EmptyState onSuggestion={handleSuggestion} />`.
- Build passes, lint clean. Phase 17 code complete.

### 2026-06-03 — Phase 16 implemented
- **`recall/models.py`** — `Intent` extended to `Literal["store", "query", "general", "forget"]`.
- **`recall/prompts.py`** — `_INTENT_SYSTEM` updated to 4-way classifier; FORGET label + 2 examples added.
- **`recall/llm.py`** — `classify_intent` parser maps `"FORGET"` → `"forget"`.
- **`recall/router.py`** — forget heuristic (starts with `forget `/`delete `/`remove ` or contains `forget what i`/`forget everything` etc.) inserted before query heuristic.
- **`recall/store.py`** — `delete_memories(client, ids, user_id) -> int` batch-deletes by id list, scoped to user_id.
- **`api/routers/chat.py`** — `ChatRequest` gains `confirm_forget: list[str] | None`; `ChatResponse` gains `forget_candidates: list[dict] | None`. `_resolve_forget_candidates` resolves by "forget all" → list_memories, temporal range → list_memories_in_range, or semantic search (similarity ≥ 0.6). Non-streaming and streaming paths both handle forget (step 1: return candidates; step 2 via `confirm_forget`: delete). Streaming emits `_sse({"fc": candidates})` frame for client capture. Confirm-delete short-circuits routing.
- **`recall/cli.py`** — `_do_forget_natural` resolves candidates (all / temporal / semantic), prints a table, prompts `y/N`, calls `store.delete_memories` on confirm. Wired into bare-text dispatch.
- **`web/types/index.ts`** — `ForgetCandidate` interface; `Message.forgetCandidates` field.
- **`web/lib/api.ts`** — `postChat` accepts `opts.confirmForget`; `postChatStream` accepts `onForgetCandidates` callback; `fc` SSE frames call the callback.
- **`web/components/ui/Icon.tsx`** — `delete` (trash) icon added.
- **`web/components/chat/ForgetConfirm.tsx`** (new) — confirm card with candidate list, Delete (red) and Keep buttons.
- **`web/app/chat/page.tsx`** — `pendingForget` state captures candidates from stream `fc` frame; `handleForgetConfirm` POSTs confirm step; `handleForgetCancel` appends "Okay, kept them." `ForgetConfirm` rendered as fixed overlay above the input when `pendingForget` is set.
- TypeScript check passes clean. Never deletes on first turn; all deletes scoped by `user_id`.

### 2026-06-03 — Phase 15 implemented
- **`recall/prompts.py`** (new) — single source of truth for all LLM prompts. Contains `MEMEX_VOICE` preamble (warm, concise, quietly clever), `_NO_MEMORIES`, `_SYSTEM_PROMPT` (synthesis + voice appended), `_INTENT_SYSTEM` (classifier — voice deliberately excluded, must stay deterministic), `_PERSONA_PROMPT` (general handler + voice appended), `_SUMMARY_SYSTEM` (temporal window + voice appended), and `SAVE_ACKS` (10-item rotation list).
- **`recall/llm.py`** — removed all inline prompt constants; imports them from `recall.prompts`. Added `save_ack(content=None, rng=None) -> str` returning a random member of `SAVE_ACKS` (injectable rng for deterministic tests).
- **`api/routers/chat.py`** — store branches (streaming + non-streaming) now call `llm.save_ack()` instead of returning a fixed `"Saved."` string.
- **`recall/cli.py`** — `_do_store` now prints `llm.save_ack()` instead of `"Saved."`.
- All no-hallucination short-circuits (`_NO_MEMORIES`, `"Nothing saved {label}."`) are unchanged — persona text only appears on the grounded/general prompts.

### 2026-06-03 — Streaming async fix (post-phase-14)
- **Root cause identified:** `_stream_chat` in `chat.py` used synchronous `for token in llm.chat_general_stream(...)` etc. These sync generators call `client.models.generate_content_stream` (blocking I/O), which freezes the asyncio event loop. Uvicorn queues the write after each `yield` but the event loop can't flush until the sync generator exhausts — so all tokens arrive at once.
- **`recall/llm.py`** — Added three async generator functions using `client.aio.models.generate_content_stream` (non-blocking): `synthesize_answer_stream_async`, `chat_general_stream_async`, `summarize_window_stream_async`. Sync variants kept for CLI use.
- **`api/routers/chat.py`** — `_stream_chat` updated to use `async for` with the three new async generators. Added `X-Accel-Buffering: no` to `StreamingResponse` headers to prevent nginx proxy buffering on Railway.

### 2026-06-03 — Phase 14 implemented
- **Root cause fixed:** tokens containing `\n` were breaking raw `data: {token}\n\n` SSE framing — the frontend splits on `\n` and discarded lines not starting with `data: `, silently dropping multi-line content.
- **`api/routers/chat.py`** — added `_sse(payload: dict) -> str` helper that JSON-encodes each frame: `f"data: {json.dumps(payload)}\n\n"`. All `yield f"data: {token}\n\n"` → `yield _sse({"t": token})`. `[DONE]` → `_sse({"done": True})`. Error → `_sse({"error": str(exc)})`. `json.dumps` escapes newlines as `\n`, so every event is exactly one line.
- **`web/lib/api.ts`** — `postChatStream` buffer now splits on `"\n\n"` (SSE event boundaries) instead of `"\n"`. Each event is `JSON.parse`d: `obj.done` → return, `obj.error` → throw, `obj.t` → yield. JSON parse errors (partial buffers) are skipped. Trailing partial buffer handling preserved. One-retry + non-streaming fallback unchanged.
- Manual verification: save 3 items, ask "what did I tell you today?" — all lines render and text visibly grows token-by-token.
- Build + lint clean. Phase 14 code complete.

### 2026-06-03 — Phase 13 implemented
- **`web/types/index.ts`** — added `pending?: boolean` to `Message` interface.
- **`web/app/globals.css`** — added `dot-pulse` keyframe animation (3 staggered spans, 1.2s cycle) for the neutral working indicator. Added `skeleton-shimmer` keyframe for hydration skeleton placeholders.
- **`web/components/chat/MessageBubble.tsx`** — added `pending` prop. When `pending && !content`, renders a `<PendingIndicator/>` (three pulsing dots) instead of text content. On first token arrival, `pending: false` is set and the content renders in place — smooth swap with no flicker.
- **`web/components/chat/MessageList.tsx`** — passes `pending={msg.pending}` through to `MessageBubble`.
- **`web/components/ui/SplashTransition.tsx`** (new) — branded hand-off between auth and chat: centered "Memex" wordmark + `psychology` icon + a slim indeterminate progress bar. Renders on the same surface background, resolved within ~600ms max.
- **`web/components/ui/LoadingSkeleton.tsx`** (new) — reusable skeleton card placeholders (`skeleton-pulse` shimmer) for hydration while data loads.
- **`web/app/chat/page.tsx`** — replaced the hardcoded `"Retrieving memories..."` loading message with `content: ""`, `pending: true`. On first streamed token, `replaceLoading` now clears `pending: false` alongside setting content, so the working indicator swaps to real text in the same bubble. Added `booting` state with a 600ms max timeout; while booting, `<SplashTransition/>` renders in the message area (top bar + input shell mount instantly — fast first paint).
- Build + lint clean. Phase 13 code complete.

### 2026-06-03 — Phase 12 implemented
- **`web/components/ui/Icon.tsx`** — added `visibility_off` case (Feather eye-off path: eye with slash icon).
- **`web/lib/auth-helpers.ts`** (new) — `isDuplicateSignup(error, data)`: checks `AuthApiError` message for "already registered/exists/been registered" OR `data.user.identities` length of 0 (email-confirmation-on case). `mapAuthError(message)`: maps common auth failures (invalid credentials, email not confirmed, rate limit, network errors, weak password) to short, friendly copy. Both are pure functions importable without React.
- **`web/components/auth/AuthForm.tsx`** — R12.1: `showPassword` state toggles input type + eye icon (`visibility`↔`visibility_off`). R12.2: duplicate-signup detection calls `isDuplicateSignup`; on match → switches to login mode, keeps email, shows friendly notice, auto-focuses password field. R12.3: name passed via `options: { data: { full_name: name } }` on signup. R12.4: all errors routed through `mapAuthError`; login errors use original message for field routing (email vs password). R12.5: confirmation notice styled with `text-secondary` (success state); "Resend confirmation email" text button calls `supabase.auth.resend({ type: "signup", email })` with disable-once-sent UX.
- Build + lint clean. Phase 12 code complete.

### 2026-06-02 — Wave 2 (v3.1) planning (docs only, no code)
- Re-read `PRD.md`/`TDD.md`/`PRD-v3.md`/`TDD-v3.md` and the live code (`AuthForm.tsx`, `chat/page.tsx`, `lib/api.ts`, `ChatInput.tsx`, `TopBar.tsx`, `MessageBubble.tsx`, `DateDivider.tsx`, `EmptyState.tsx`, `Icon.tsx`, `globals.css`, `api/routers/chat.py`, `recall/llm.py`, `recall/router.py`, `recall/store.py`, `recall/models.py`) to ground the plan.
- **Appended Part II to `PRD-v3.md`** — Wave 2 product spec, phases 12–22, each with requirements + Definition of Done: (12) auth/onboarding hardening, (13) transitions/status, (14) reliable streaming, (15) personality/prompt system, (16) natural-language forget, (17) richer UI/theme depth, (18) settings menu + dark mode, (19) Memory Library, (20) organisation/reminders, (21) data ownership/insights, (22) capture/reach. Plus cross-cutting principles + audience notes.
- **Appended Part II to `TDD-v3.md`** — file-level how for each phase: exact files/signatures/edits, the streaming root-cause + JSON-SSE fix, prompt-module refactor, 4th `forget` intent + two-step confirm protocol, dark-mode tokenisation audit, `metadata`-jsonb-only schema strategy, contract/API deltas, schema deltas table, network-free test list, sequencing/risk notes.
- Diagnosed the streaming bug (see Decisions Log). Identified dark mode as larger than it looks (hardcoded hex in components needs tokenising).
- No source files changed. Next implementation step: **Phase 12**.

### 2026-06-02 — Phase 11 implemented
- **`web/components/chat/ChatInput.tsx`** — converted to `forwardRef` with `useImperativeHandle` exposing `focus()`. Removed `disabled` from the `<input>` element entirely — user can always type. Enter handler gates on `loading`: `if (!loading && value.trim()) onSend()`. Send button uses `disabled={!hasText || loading}`. Changed `disabled` prop to `loading`.
- **`web/app/chat/page.tsx`** — holds `inputRef` via `useRef<ChatInputHandle>`. In `handleSend`'s `finally` block, after `setLoading(false)`, refocuses input via `inputRef.current?.focus()` guarded by `matchMedia('(pointer: fine)').matches` to avoid forcing mobile keyboards open. Passes `loading` prop instead of `disabled` to ChatInput.
- **`web/components/auth/AuthForm.tsx`** — added `useEffect` on mount that fires a fire-and-forget `fetch('${API_URL}/health', { mode: 'no-cors' })` to warm a sleeping free-tier backend while the user is authenticating. No other changes to auth flow.
- Build + lint clean. Phase 11 code complete.

### 2026-06-02 — Phase 10 implemented
- **`recall/temporal.py`** (new) — `extract_range(text, tz, now)`: heuristic-based time-range extraction. Supports "today" (midnight→now), "yesterday" (midnight yesterday→midnight today), "this week" (Monday→now), "last N days"/"past N days", ISO dates `YYYY-MM-DD`, and weekday names ("Monday"/"mon"). All boundaries computed in the supplied `tz` then converted to UTC for DB queries. Vague phrases ("recently") → `None`. Testable via the `now` parameter.
- **`recall/store.py`** — `list_memories_in_range(client, user_id, start, end)` → `list[Memory]`: selects memories where `user_id` matches and `created_at >= start` and `< end`, ordered ascending by `created_at`.
- **`recall/llm.py`** — `summarize_window(memories, label, cfg)` and `summarize_window_stream(...)`: empty list → `f"Nothing saved {label}."` (no LLM call). Otherwise passes timestamped items with a system prompt to list/summarize using only the items given. Temperature 0.2.
- **`recall/cli.py`** — `_do_query` now tries `temporal.extract_range` first (using machine local tz). If range found → `list_memories_in_range` → `summarize_window`. Otherwise falls through to existing semantic search path.
- **`api/routers/chat.py`** — `ChatRequest` gains optional `tz: str | None`. Extracted `_handle_query` helper for the non-streaming path. Both streaming and non-streaming query branches check temporal range before falling through to semantic search. `source` now also detects "Nothing saved" prefix for temporal empty results.
- **`web/lib/api.ts`** — `postChat` and `postChatStream` now include `tz: Intl.DateTimeFormat().resolvedOptions().timeZone` in the request body.
- **`supabase/schema.sql`** — new `memories_user_created_idx` btree index on `(user_id, created_at desc)`.
- **`requirements.txt`** — added `tzdata>=2024.1` for Linux deploy targets.
- Build + lint clean. `extract_range` verified with quick test. Phase 10 code complete.

### 2026-06-02 — Phase 9 implemented
- **`recall/models.py`** — `Intent` now `Literal["store", "query", "general"]`.
- **`recall/router.py`** — greeting/meta fast-path (bare "hi"/"hello"/"thanks"/"help" etc.) returns `"general"` with no LLM call. Removed `?`-ending heuristic — option (a) from `TDD-v3.md §3.2`: `?`-ending input now goes to the 3-way classifier which separates personal-recall from general-knowledge questions. Query-starter words and "did/do/have i" prefixes still short-circuit to `"query"`. All other ambiguous input → 3-way `classify_intent`; default to `"store"` on failure.
- **`recall/llm.py`** — `classify_intent` prompt extended to 3 classes (STORE/QUERY/GENERAL). Parsing maps reply → one of three; defaults to `"store"` on any failure. Added `chat_general(message, cfg)` (temperature 0.4, persona prompt) and `chat_general_stream(message, cfg)`.
- **`recall/cli.py`** — bare-text dispatch now handles `"general"` intent: calls `llm.chat_general(text, cfg)` with spinner; does not embed, store, or search.
- **`api/routers/chat.py`** — `ChatResponse` gains optional `source` field (`"memory"` / `"general"` / `"none"`). Both streaming and non-streaming paths branch on `"general"` intent. Query path now sets `source` explicitly.
- **`web/lib/api.ts`** — `postChat` return type updated to include `source: string | null`.
- **Design decision recorded:** `?`-heuristic removed. "what's the capital of France?" → 3-way classifier → GENERAL → answered by Gemini. "where did I park?" → query-starter heuristic → QUERY → semantic search. Personal-recall empty-result short-circuit in `synthesize_answer` is unchanged.
- Build + lint clean. Phase 9 code complete.

### 2026-06-02 — v3 planning (docs only, no code)
- Analysed `PRD.md`/`PRD-v2.md`/`TDD.md`/`TDD-v2.md` and current code (`router.py`, `llm.py`, `api/routers/chat.py`, `models.py`) to ground the v3 design in how the app actually works (two-way `Intent`, strict `_NO_MEMORIES` short-circuit).
- **Created `PRD-v3.md`** — product spec for three features: (1) conversational range via a new `general` intent answered by Gemini, with personal-recall staying strict; (2) temporal recall ("what did I tell you today/this week/yesterday"); (3) web UX refinements (refocus input, type-while-loading, fast login→chat). Phases 9–11 with DoDs.
- **Created `TDD-v3.md`** — technical design: 3-way intent + greeting/meta fast-path in `router.py`, extended 3-class classifier prompt, `llm.chat_general(_stream)` persona handler; `recall/temporal.py` `extract_range`, `store.list_memories_in_range`, `llm.summarize_window(_stream)`, optional `tz` on `/chat`, new `memories_user_created_idx`; frontend changes for the three UX items. Module + API contract deltas, tests, open items.
- **Rewrote `PRD.md` and `TDD.md`** as consolidated current docs (v1+v2+v3, phases 0–11) — the originals now fold in the web/multi-client architecture and the v3 features; `PRD-v2/TDD-v2/PRD-v3/TDD-v3` retained as detailed references.
- Noted the design-vs-implementation divergence: docs now state the shipped app is branded **Memex** with the Material-3/Stitch design, and that v3 adds no visual redesign.
- No source files changed. Next implementation step: Phase 9.

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
