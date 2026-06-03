# Technical Design Document v3 — "Recall" / "Memex"

Companion to `PRD-v3.md`.
Builds on `TDD.md` (v1, phases 0–4) and `TDD-v2.md` (phases 5–8). Phases 0–8 are
**complete**. This document specifies phases 9–11: the GENERAL intent + Gemini
conversational fallback, temporal recall, and three web UX refinements.

> **Implementation note.** Confirm provider SDK names, model identifiers, and streaming
> APIs against current docs before writing integration code. Current confirmed values
> (from `MEMORY.md`): chat model `gemma-4-26b-a4b-it`, embedding model
> `gemini-embedding-001` at `output_dimensionality=768`. Do not hardcode model strings —
> read from config.

---

## 1. What changes, in one diagram

```
            message
               │
               ▼
        router.route(text, cfg)  ──────────────┐
               │                               │ heuristic first, LLM classifier on miss
        ┌──────┼───────────────┐               │
        ▼      ▼               ▼               │
     store   query          general   ◀── NEW third class
        │      │               │
        │      │               └──▶ llm.chat_general(text)         ◀── NEW: conversational,
        │      │                     (NOT grounded, NOT saved)         not memory-grounded
        │      │
        │      └──▶ temporal?  ──yes──▶ store.list_memories_in_range  ◀── NEW path
        │                │                 → llm.summarize_window
        │               no
        │                └──▶ embeds → store.search_memories → llm.synthesize_answer
        │                                 (empty → fixed "nothing saved", UNCHANGED)
        │
        └──▶ embed → store.add_memory   (UNCHANGED)
```

Isolation rules from v1/v2 still hold: only `store.py` knows Supabase; only
`embeddings.py` / `llm.py` know Gemini.

---

## 2. Data model — what is enough

The `general` intent needs **no schema change**: general replies are not stored.

Temporal recall needs **no new columns** — `memories.created_at` (timestamptz, already
present and indexed by default on PK only) is sufficient. To keep window listings fast as
the table grows, add a btree index:

```sql
-- new in Phase 10
create index if not exists memories_user_created_idx
  on memories (user_id, created_at desc);
```

No change to `vector(768)`, the HNSW index, or the `match_memories` RPC.

---

## 3. Phase 9 — GENERAL intent + conversational fallback

### 3.1 Intent type

```python
# recall/models.py
Intent = Literal["store", "query", "general"]
```

### 3.2 Routing (`recall/router.py`)

Add a greeting/meta fast-path **before** the existing query heuristic so trivial input
never costs an LLM call, then extend the classifier to three classes.

```python
_GREETINGS = {
    "hi", "hello", "hey", "yo", "sup", "hiya", "howdy",
    "thanks", "thank you", "thx", "ty", "ok", "okay", "cool", "nice",
    "good morning", "good evening", "good afternoon", "gm",
}
_META = {"help", "what can you do", "what can you do?", "who are you", "who are you?"}

def route(text: str, cfg: Config) -> Intent:
    normalized = text.strip().lower()

    # 0. greeting / meta fast-path → general, no LLM call
    if normalized in _GREETINGS or normalized in _META:
        return "general"

    # 1. existing query heuristic (ends with ?, query-starter word, did/do/have i …)
    #    NOTE: a bare "?" or query-starter is still treated as query; the LLM
    #    classifier disambiguates general-knowledge questions in step 2.
    ...

    # 2. ambiguous → LLM classifier (now three-way), default to store on failure
    return classify_intent(text, cfg)
```

> **Design note on questions.** The "ends with ?" heuristic currently forces `query`.
> A general-knowledge question ("what's the capital of France?") also ends with "?".
> Two acceptable options — pick one and document it:
> - **(a, recommended)** Keep the heuristic returning `query` for `?`, and let the
>   *empty-result* path stay strict ("nothing saved"). General-knowledge questions then
>   only reach Gemini if the classifier (step 2) is consulted — so relax the heuristic to
>   *not* short-circuit on `?` alone, sending genuinely ambiguous questions to the
>   three-way classifier.
> - **(b)** Always send `?`-ending input to the three-way classifier.
> Either way, the classifier is the component that separates "personal recall" from
> "general knowledge". The heuristic only handles the cheap, unambiguous cases.

### 3.3 Three-way classifier (`recall/llm.py`)

Extend the existing `classify_intent` prompt to three labels. Keep temperature 0.

```
You classify a message as STORE, QUERY, or GENERAL.
STORE   = the user is telling you something to remember (a fact, idea, task, note).
QUERY   = the user is recalling something PERSONAL they told you earlier.
GENERAL = a greeting, small talk, a general-knowledge question, or a question about
          what you are / can do — NOT something personal they previously told you.
Examples:
  "remind me to call mom tomorrow"   -> STORE
  "my friend mentioned cheap jackets"-> STORE
  "where did I park?"                -> QUERY
  "did I have any app ideas?"        -> QUERY
  "hi there"                         -> GENERAL
  "what's the capital of France?"    -> GENERAL
  "what can you do?"                 -> GENERAL
Reply with exactly one word: STORE, QUERY, or GENERAL.
```

Parsing: map the reply to one of the three; **default to `store` on any failure**
(unchanged — safer to over-save than to lose input).

### 3.4 Conversational handler (`recall/llm.py`)

```python
def chat_general(message: str, cfg: Config) -> str: ...
def chat_general_stream(message: str, cfg: Config) -> Generator[str, None, None]: ...
```

System prompt (persona — short, in character, not a general chatbot):

```
You are Memex, a personal memory assistant. The user has said something that is not a
memory to store and not a question about their saved memories — it's a greeting, small
talk, or a general question. Reply briefly and warmly. For a greeting, invite them to
tell you something to remember. For a general-knowledge question, answer directly and
concisely. Never claim something is from the user's saved memories. Keep it to a sentence
or two.
```

Temperature ~0.4 (a touch warmer than synthesis). These handlers are independent of the
memory store — they pass no memories.

### 3.5 Wiring

**CLI (`recall/cli.py`):** in the bare-text path, add a branch for `general` →
`llm.chat_general(text, cfg)` → print. Do not embed, do not store, do not search.

**API (`api/routers/chat.py`):** add the `general` branch to both the non-streaming and
streaming paths.

```python
# non-streaming
if intent == "general":
    reply = llm.chat_general(body.message, _cfg)
    return ChatResponse(intent="general", reply=reply, id=None)

# streaming (_stream_chat)
elif intent == "general":
    for token in llm.chat_general_stream(message, _cfg):
        yield f"data: {token}\n\n"
    yield "data: [DONE]\n\n"
```

The personal-recall (`query`) empty-result behaviour in `synthesize_answer` /
`synthesize_answer_stream` is **unchanged** — it still returns the fixed `_NO_MEMORIES`
message when no memories are passed.

### 3.6 API contract delta

`/chat` `intent` field can now be `"general"`. Backward compatible. Optionally add an
explicit `source` for the frontend to label answers:

```
ChatResponse:
{ "intent": "store" | "query" | "general",
  "reply": string,
  "id": string | null,
  "source": "memory" | "general" | "none" }   // optional, additive
```

`source` = `"memory"` for grounded query answers, `"general"` for general replies,
`"none"` for the strict "nothing saved" case. The frontend may use it to render a subtle
"not from your memories" affordance; it is not required for Phase 9 to pass.

### 3.7 Phase 9 Definition of Done

- `python -m recall`: "hi" → conversational reply, **no** new Supabase row; "what's the
  capital of France?" → correct answer, not framed as a memory.
- Web: same, via `/chat`. `intent` returns `"general"`.
- A `query` with nothing stored still returns the fixed "nothing saved" string — confirm
  Gemini is **not** called to invent a personal fact.
- Storing and recalling personal memories is unchanged.

---

## 4. Phase 10 — Temporal recall

### 4.1 Time-range extraction

A query that is time-scoped needs a `(start, end)` window in the user's time zone. Use a
heuristic for the common phrases; only fall to the LLM for the harder ones.

```python
# recall/temporal.py (new)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# returns (start_utc, end_utc, label) or None if no temporal scope detected
def extract_range(text: str, tz: str = "UTC", now: datetime | None = None)
    -> tuple[datetime, datetime, str] | None: ...
```

Heuristic phrases (case-insensitive substring / regex):
- `today`                → [local midnight today, now]
- `yesterday`            → [local midnight yesterday, local midnight today]
- `this week`            → [start of local week, now]
- `last N days` / `past N days` → [now − N days, now]
- a weekday name or `YYYY-MM-DD` → that local day

Compute boundaries in the supplied `tz` (e.g. via `ZoneInfo`), then convert to UTC for the
DB query. Return `None` when no temporal phrase is present → the query falls through to
ordinary semantic search. Vague phrases ("recently", "a while ago") deliberately return
`None`.

### 4.2 Store function (`recall/store.py`)

```python
def list_memories_in_range(
    client, user_id: str, start: datetime, end: datetime
) -> list[Memory]:
    # supabase: select * from memories
    #   where user_id = ? and created_at >= start and created_at < end
    #   order by created_at asc
```

No RPC needed — a filtered `select` on the table is enough; the new
`memories_user_created_idx` keeps it fast.

### 4.3 Summarisation (`recall/llm.py`)

```python
def summarize_window(memories: list[Memory], label: str, cfg: Config) -> str: ...
def summarize_window_stream(...) -> Generator[str, None, None]: ...
```

- If `memories` is empty → return `f"Nothing saved {label}."` **without** calling Gemini.
  (This is a true statement about the user's data, parallel to the no-hallucination
  short-circuit.)
- Otherwise pass the list (with timestamps, oldest first) and ask Gemini to present it
  concisely. System prompt: "List/summarise what the user saved in this window. Use ONLY
  the items given. Be concise. Do not invent items."

### 4.4 Query-flow integration

In the `query` branch (CLI and `api/routers/chat.py`), before embedding:

```python
rng = temporal.extract_range(message, tz=client_tz)
if rng:
    start, end, label = rng
    mems = store.list_memories_in_range(db, user_id, start, end)
    reply = llm.summarize_window(mems, label, _cfg)   # or stream variant
else:
    # existing semantic path: embed → search_memories → synthesize_answer
```

### 4.5 Passing the time zone

- **Web:** `lib/api.ts` includes the browser zone from
  `Intl.DateTimeFormat().resolvedOptions().timeZone` in the chat request body
  (`{ "message": str, "tz": str }`). `ChatRequest` gains an optional `tz: str | None`.
- **CLI:** uses the machine local zone (`datetime.now().astimezone().tzinfo`); no flag
  needed.

`tz` is additive and optional → backward compatible; default `"UTC"` if absent.

### 4.6 Phase 10 Definition of Done

- Store two memories now; "what did I tell you today?" returns both, oldest first.
- "what did I tell you yesterday?" with nothing stored yesterday → "Nothing saved
  yesterday." (no invention).
- "this week" and "last 3 days" return correct windows.
- Window respects the user's local day (test with a non-UTC `tz` near midnight).
- A non-temporal query still uses semantic search unchanged.

---

## 5. Phase 11 — Web UX refinements

All three are frontend-only changes in `web/`. No backend changes.

### 5.1 Return focus to the input
In `app/chat/page.tsx`, hold a `ref` to the textarea (or lift one into `ChatInput.tsx`
via `forwardRef`). After a send settles — i.e. after the streaming generator finishes or
the non-streaming `postChat` resolves, in a `finally` — call `inputRef.current?.focus()`.
Guard for mobile: only refocus on pointer-fine / non-touch to avoid forcing the virtual
keyboard open unexpectedly (`matchMedia('(pointer: fine)')`).

### 5.2 Type while loading, gate only sending
`ChatInput.tsx` currently disables the textarea when `loading`. Change so that:
- The `<textarea>` is **never** disabled by `loading` — the user can always type.
- The send action is gated: in the Enter handler, `if (loading) return;` and the send
  button uses `disabled={loading || !input.trim()}`.
This lets the user compose the next message while a response streams, but prevents
overlapping/racing sends. Keep the existing Shift+Enter newline behaviour.

### 5.3 Faster login → chat
- **Optimistic shell:** after `signInWithPassword` / `signUp` succeeds, `router.push`
  (or `router.replace`) to `/chat` immediately. `ChatLayout` (top bar + empty message
  area + input) renders right away; do not block first paint on `GET /memories`.
- **Non-blocking data:** load any prior state into the already-rendered shell; show the
  empty state until it arrives rather than a full-page spinner.
- **Warm the backend:** fire a fire-and-forget `GET /health` from the auth screen on
  mount (and/or at submit time) so a sleeping free-tier backend is waking while the user
  authenticates. Ignore its result. *(This targets perceived latency, not cost — hosting
  scale is out of scope per the project owner.)*
- Keep the v2 auth guard (`app/chat/layout.tsx` server-side session check, `proxy.ts`
  session refresh) intact — the optimistic push must still land on a guarded route.

### 5.4 Phase 11 Definition of Done

- After a response (streamed or not), the cursor is back in the textarea without a click
  (desktop).
- While a response streams, typing in the textarea works; Enter and the send button do
  nothing until it completes.
- From pressing the auth button, the chat shell is visible promptly; a cold backend does
  not produce a long blank screen after login.

---

## 6. Module contract changes (summary)

```python
# models.py
Intent = Literal["store", "query", "general"]            # + "general"

# router.py
route(text, cfg) -> Intent                               # + greeting/meta fast-path, 3-way

# llm.py
classify_intent(text, cfg) -> Intent                     # now STORE | QUERY | GENERAL
chat_general(message, cfg) -> str                        # NEW
chat_general_stream(message, cfg) -> Generator[str,…]    # NEW
summarize_window(memories, label, cfg) -> str            # NEW (Phase 10)
summarize_window_stream(memories, label, cfg) -> Gen[…]  # NEW (Phase 10)

# temporal.py (NEW, Phase 10)
extract_range(text, tz="UTC", now=None) -> tuple[datetime, datetime, str] | None

# store.py
list_memories_in_range(client, user_id, start, end) -> list[Memory]   # NEW (Phase 10)
```

```
# FastAPI
ChatRequest:  { "message": str, "tz": str | None }        # + optional tz
ChatResponse: { "intent": "store"|"query"|"general",
                "reply": str, "id": str|null,
                "source": "memory"|"general"|"none" }      # + general intent, optional source
```

---

## 7. Testing

Network-free unit tests to add:
- `router.route` greeting/meta fast-path returns `general` for the greeting set.
- `temporal.extract_range` for "today" / "yesterday" / "this week" / "last 3 days" /
  a non-temporal string (→ `None`), including a non-UTC `tz` boundary case.
- Classifier reply parsing maps STORE/QUERY/GENERAL correctly and defaults to `store`.

Integration (manual, per the Definitions of Done above) against live free-tier services.

---

## 8. Open items to confirm during build

- Gemini streaming method for the conversational and summary handlers (reuse the
  `generate_content_stream` pattern already in `synthesize_answer_stream`).
- Final choice for the `?`-heuristic (§3.2 option a vs b); document the decision in
  `MEMORY.md`.
- Whether to surface the optional `source` field in the UI in Phase 9 or defer to a later
  polish pass.
- Confirm `zoneinfo` tz database availability on the deploy target (Railway/Render); add
  `tzdata` to `requirements.txt` if the base image lacks the system zone files.

---
---

# Part II — Wave 2 (v3.1) technical design

> Companion to `PRD-v3.md` Part II. Phase numbers line up across both documents. Phases
> 0–11 are built; this part specifies phases 12–22. Read the matching PRD phase first for
> the *why* and the Definition of Done; this part is the *how* — concrete files,
> signatures, and edits.
>
> **Ground truth (verified against the current tree, do not re-derive):**
> - Intent type lives in `recall/models.py`: `Intent = Literal["store", "query", "general"]`.
> - Routing: `recall/router.py` `route(text, cfg)` — greeting/meta fast-path → query
>   heuristic → `classify_intent` (LLM).
> - LLM handlers + all prompts: `recall/llm.py` (`synthesize_answer(_stream)`,
>   `classify_intent`, `chat_general(_stream)`, `summarize_window(_stream)`, module-level
>   `_SYSTEM_PROMPT` / `_INTENT_SYSTEM` / `_PERSONA_PROMPT` / `_SUMMARY_SYSTEM`,
>   `_NO_MEMORIES`).
> - Store (only DB-aware module): `recall/store.py` — `add_memory`, `list_memories`,
>   `delete_memory`, `count_memories`, `search_memories`, `list_memories_in_range`.
> - API: `api/routers/chat.py` (`chat` + `_stream_chat`, `ChatRequest`/`ChatResponse`),
>   `api/routers/memories.py` (CRUD), `api/dependencies.py` (`get_current_user`, `get_db`).
> - Web chat owner: `web/app/chat/page.tsx`; transport: `web/lib/api.ts`
>   (`postChat`, `postChatStream`, `getMemories`); components under
>   `web/components/chat/*` and `web/components/ui/*`; icons in
>   `web/components/ui/Icon.tsx` (SVG switch — **add new names here**, there is no icon
>   font); styling/tokens in `web/app/globals.css` (`@theme inline`).
> - **`web/AGENTS.md` rule still applies: this is a modified Next.js; read
>   `node_modules/next/dist/docs/` before writing framework code.**

---

## 9. Phase 12 — Auth & onboarding hardening

All changes are in `web/components/auth/AuthForm.tsx` unless noted. No backend changes.

### 9.1 Working password reveal (R12.1)
- Add `const [showPassword, setShowPassword] = useState(false);`.
- The password `<input>` `type` becomes `{showPassword ? "text" : "password"}`.
- The existing reveal `<button>` (currently inert, line ~156) gets
  `onClick={() => setShowPassword(v => !v)}` and renders `visibility` when hidden,
  `visibility_off` when shown.
- **Icon work:** `web/components/ui/Icon.tsx` only has `visibility`. Add a `visibility_off`
  case to the `name` union and the `switch` (eye with a slash — Feather `eye-off` path:
  `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>`).

### 9.2 Duplicate-account handling (R12.2)
- Supabase `signUp` behaviour: with email-confirmation **on**, an existing email returns a
  `data.user` with an **empty `identities` array** and no error (anti-enumeration). With it
  **off**, it returns an `AuthApiError` like "User already registered". Handle **both**:
  - After `signUp`, if `error` message matches `/already registered|already exists/i`
    **or** (`data.user && (data.user.identities?.length ?? 0) === 0`), treat as duplicate.
  - On duplicate: `setMode("login")`, keep `email` in state (it already persists), and set a
    friendly notice: "Looks like you already have an account — log in instead." Focus the
    password field.
- Extract a small helper `isDuplicateSignup(error, data)` for testability.

### 9.3 Capture the name (R12.3)
- Pass the name into signup options:
  `supabase.auth.signUp({ email, password, options: { data: { full_name: name } } })`.
- `full_name` lands in `auth.users.user_metadata`; it is already in the JWT, so no DB
  column is needed. The web client can read it via
  `supabase.auth.getUser()` → `data.user.user_metadata.full_name`.
- Greeting use (chat empty state, phase 17): derive first name client-side
  (`full_name.split(" ")[0]`). For general replies addressing the user by name (optional),
  the API would need the name — defer; client-side greeting is enough for the DoD.

### 9.4 Humane errors (R12.4) + confirm clarity (R12.5)
- Add a pure `mapAuthError(message: string): string` mapping common substrings to copy:
  `invalid login credentials` → "Email or password is incorrect.";
  `email not confirmed` → "Please confirm your email first — check your inbox.";
  `rate limit` / `429` → "Too many attempts. Wait a minute and try again.";
  `network`/`fetch` → "Can't reach the server. Check your connection.";
  fallback → a generic "Something went wrong. Try again.".
- Replace the raw `setEmailError(msg)` / `setPasswordError(msg)` assignments with
  `mapAuthError`. Route the message to the field it concerns (email vs password) as today,
  else show it in the existing `notice` slot.
- For the confirmation notice, style as a success state (e.g. `text-secondary`) and add a
  "Resend confirmation" text button that calls
  `supabase.auth.resend({ type: "signup", email })`.

### 9.5 Tests (network-free where possible)
- Unit-test `isDuplicateSignup` and `mapAuthError` (pure functions — extract to a small
  `web/lib/auth-helpers.ts` so they are importable without React).

**DoD:** PRD §13.

---

## 10. Phase 13 — Transitions & status states

Frontend-only. Files: `web/app/chat/page.tsx`, a new transition/skeleton component,
`web/components/chat/MessageBubble.tsx`, and `web/app/auth/page.tsx` /
`web/components/auth/AuthForm.tsx`.

### 10.1 Neutral working indicator (R13.2, R13.3) — replaces "Retrieving memories…"
- In `web/app/chat/page.tsx` (line ~26) the loading bubble content is the literal string
  `"Retrieving memories..."`. Stop using text. Add a flag to the message model instead:
  - `web/types/index.ts`: add `pending?: boolean` to `Message`.
  - Create the loading assistant message with `content: ""`, `pending: true`.
  - In `MessageBubble.tsx`, when `pending && !content`, render an animated three-dot /
    shimmer indicator (a small `<span>` with three pulsing dots) instead of `<p>{content}`.
  - On first streamed token, set `pending: false` and write the token — the existing
    `replaceLoading`/append logic stays, just also clear `pending`.
- Add the dots animation to `globals.css` (keyframes `dot-pulse`, three spans with
  staggered `animation-delay`). Keep it subtle, consistent with the 200ms-ease aesthetic
  (PRD §8: no typing-indicator *avatars*, but a minimal working dot in the bubble is the
  neutral signal we want — keep it understated).

### 10.2 Branded hand-off (R13.1) + hydration skeleton (R13.4)
- New component `web/components/ui/SplashTransition.tsx`: centered `Memex` wordmark +
  `auto_awesome`/`psychology` mark + a calm progress treatment (a slim indeterminate bar or
  the existing `progress_activity` spinner), on the same `auth-bg`/surface background.
- Trigger: phase 11 already does optimistic `router.push("/chat")`. Add a short-lived
  "booting" state in the chat shell:
  - `web/app/chat/page.tsx`: add `const [booting, setBooting] = useState(true)` and a
    `useEffect` that loads recent memories (phase 17 `getMemories`) then `setBooting(false)`;
    also clear `booting` on a max-timeout (~600ms) so it never blocks longer than the data.
  - While `booting`, render `<SplashTransition/>` over the message area only (top bar +
    input shell still mount instantly — keep first paint fast).
- Hydration skeleton: while recent-memory cards (phase 17) load, render 2–3 skeleton card
  placeholders (`animate-pulse` surfaces) rather than a spinner.

**DoD:** PRD §14.

---

## 11. Phase 14 — Reliable streaming (root cause + fix)

### 11.1 Root cause (confirmed)
`api/routers/chat.py` emits each model chunk as `yield f"data: {token}\n\n"`. Model chunks
frequently **contain newlines** (lists, sentences, markdown). On the wire that becomes:

```
data: line one
line two

```

`web/lib/api.ts` `postChatStream` splits the buffer on `"\n"` and **discards any line that
doesn't start with `"data: "`** (line ~98). So `line two` is dropped. Multi-line content is
silently truncated, which reads as "streaming doesn't work." (The non-streaming fallback in
`postChat` returns the full text, which is why answers sometimes appear correct but never
*stream*.)

This is an SSE-framing bug: a literal newline inside a `data:` value is illegal unless it is
sent as a *second* `data:` line belonging to the same event, and the client must rejoin
multi-`data:` events on `\n` and split **events** on `\n\n`.

### 11.2 Fix — encode the payload (recommended, simplest & robust)
Stop putting raw model text in the SSE field. JSON-encode each chunk so it can never contain
a bare newline or break framing.

- **Backend** (`api/routers/chat.py`, all four `yield f"data: {token}\n\n"` sites in
  `_stream_chat`, plus the `Saved.` and `Error:` emissions): replace with a single helper:
  ```python
  import json
  def _sse(payload: dict) -> str:
      return f"data: {json.dumps(payload)}\n\n"
  ```
  Emit `_sse({"t": token})` for text chunks, `_sse({"done": True})` to terminate, and
  `_sse({"error": str(exc)})` for errors. `json.dumps` escapes newlines as `\n`, so every
  event is exactly one line.
- **Frontend** (`web/lib/api.ts` `postChatStream`): split the buffer on `"\n\n"` (event
  boundaries), strip the leading `data: `, `JSON.parse` the remainder, then:
  `obj.done` → `return`; `obj.error` → `throw new Error(obj.error)`; else `yield obj.t`.
  Keep the trailing-partial-buffer handling (`buffer = parts.pop()`), the one-retry, and the
  `postChat` fallback exactly as they are.
- **Backward compat:** this changes the wire format; backend and `api.ts` must ship
  together. The `[DONE]` sentinel is replaced by `{"done":true}` — update both ends.

> Alternative considered: keep plain text but have the backend split tokens on `\n` and emit
> a `data:` line per physical line, and have the client rejoin multi-`data:` events. Works,
> but is fiddlier than JSON-encoding and easy to regress. Use the JSON approach.

### 11.3 Render (R14.2)
The current `page.tsx` append loop is fine once the transport is lossless. Optionally add a
blinking caret while `loading` by appending a `▍` to the last assistant message's rendered
content (strip it on settle). Keep it optional.

### 11.4 Tests
- Unit-test the SSE parse in `api.ts` (extract the buffer→events parser into a pure
  function `parseSseEvents(buffer): {events: string[], rest: string}` and test it with a
  payload whose token contains `\n`).
- Manual: save three items, ask "what did I tell you today?", confirm all three lines render
  and the text visibly grows.

**DoD:** PRD §15.

---

## 12. Phase 15 — Personality & prompt system

### 12.1 Centralise prompts (R15.4)
- New module `recall/prompts.py` holding every system prompt as a named constant plus the
  persona block. Move `_SYSTEM_PROMPT`, `_INTENT_SYSTEM`, `_PERSONA_PROMPT`,
  `_SUMMARY_SYSTEM`, and `_NO_MEMORIES` out of `recall/llm.py` and import them back
  (`from recall.prompts import ...`) so existing call sites are unchanged. CLI and API both
  import `llm`, so both get the same voice for free.
- Add one shared `MEMEX_VOICE` preamble string and prepend it to the synthesize / general /
  summary prompts so tone is consistent. Keep the **constraints** of each prompt intact
  (synthesis: only listed memories; summary: only listed items; general: never claim a
  saved memory).

### 12.2 The voice (R15.1, R15.5)
`MEMEX_VOICE` (documented, tunable):
```
You are Memex, the user's second brain. Voice: warm, concise, quietly clever. Speak in
one or two short sentences. Plain language, a touch of personality, no corporate filler,
no emoji spam, never "As an AI". You are calm and trustworthy, not chatty.
```
This is appended to `_PERSONA_PROMPT`, `_SYSTEM_PROMPT` (synthesis), and `_SUMMARY_SYSTEM`.
Leave `_INTENT_SYSTEM` (the classifier) untouched — it must stay terse and deterministic.

### 12.3 Confirmations with character (R15.2)
Today `api/routers/chat.py` and the CLI return a fixed `"Saved."`. Replace with a small,
local, **non-LLM** rotation so saves stay instant and free:
- New `recall/prompts.py`: `SAVE_ACKS = ["Got it — saved.", "Noted.", "Locked in.",
  "Saved that.", "Filed away.", "I'll remember that.", ...]`.
- New `recall/llm.py` helper `save_ack(content: str | None = None) -> str` that returns
  `random.choice(SAVE_ACKS)`. (Keep it deterministic-testable by allowing an injected
  `rng`.) Do **not** call Gemini for confirmations — latency/cost not worth it, and it must
  never echo invented detail.
- Update both `api/routers/chat.py` store branches (non-streaming `reply="Saved."` line ~62
  and streaming `yield f"data: Saved.\n\n"` line ~79 → `_sse({"t": llm.save_ack()})`) and
  the CLI store path to use `save_ack()`.

### 12.4 Guarantees preserved (R15.3)
- `_NO_MEMORIES` short-circuit in `synthesize_answer(_stream)` is **unchanged** — it returns
  the fixed string with no LLM call. Persona text is only added to the *grounded* prompt,
  not to the miss path.
- `summarize_window` empty case (`"Nothing saved {label}."`) is unchanged.

### 12.5 Tests
- `save_ack` returns a member of `SAVE_ACKS` (inject a seeded rng).
- Prompt-module import smoke test (constants exist, non-empty).

**DoD:** PRD §16.

---

## 13. Phase 16 — Natural-language forget (the FORGET intent)

This adds a 4th intent and a **two-step confirm** flow. The flow is the only stateful piece
of chat, so the confirmation token is carried in the request/response, not on the server.

### 13.1 Intent type & routing
- `recall/models.py`: `Intent = Literal["store", "query", "general", "forget"]`.
- `recall/router.py`: add a cheap forget heuristic **before** `classify_intent`: if the
  normalized text starts with `forget `, `delete `, `remove `, or contains
  `forget what i`/`forget everything`/`delete the memory` → return `"forget"`. Anything
  ambiguous still falls to `classify_intent`.
- `recall/llm.py` `_INTENT_SYSTEM` (the classifier prompt): add a 4th label
  `FORGET = the user wants you to delete/forget something they saved.` with 2 examples
  (`"forget what I said about the dentist" -> FORGET`,
  `"delete everything from yesterday" -> FORGET`). Update the parser to map `FORGET`.
  Keep default `store` on failure.

### 13.2 Resolving what to forget (`recall/llm.py` + `recall/temporal.py` + `recall/store.py`)
A forget request resolves to a **candidate set**:
- **By time:** run `temporal.extract_range(message, tz)`. If it returns a window →
  candidates = `store.list_memories_in_range(...)`.
- **By detail:** else embed the message (strip the leading verb — "forget what I said about
  the dentist" → "the dentist") and `store.search_memories(...)`, then keep only candidates
  above a similarity floor (e.g. `>= 0.6`) so a vague forget doesn't nuke unrelated rows.
- **"forget everything":** if the message matches `/forget (everything|all|it all)/` with no
  qualifier → candidates = all (`store.list_memories`), and require the *stronger* confirm.
- Helper `recall/llm.py` `extract_forget_target(message, cfg) -> str` can clean the phrase
  for embedding (or do it with a small regex in `router`/`chat` — keep it simple, no LLM
  call needed for the common cases).

### 13.3 Store delete-by-set
- `recall/store.py`: add `delete_memories(client, ids: list[str], user_id) -> int` (a single
  `.delete().in_("id", ids).eq("user_id", user_id)` returning the deleted count). Reuse the
  existing single `delete_memory` under the hood is fine, but the batch form is cleaner.

### 13.4 Two-step confirm protocol (API)
Extend `ChatRequest`/`ChatResponse` in `api/routers/chat.py`:
```python
class ChatRequest(BaseModel):
    message: str
    tz: str | None = None
    confirm_forget: list[str] | None = None   # ids the user confirmed deleting

class ChatResponse(BaseModel):
    intent: str
    reply: str
    id: str | None = None
    source: str | None = None
    forget_candidates: list[dict] | None = None   # [{id, content, created_at}] pending confirm
```
Flow:
1. **First message** routes to `forget`. The server resolves candidates (13.2) but **does
   not delete**. It returns `intent="forget"`, `forget_candidates=[…]`, and a `reply` like
   "I found 2 memories about the dentist. Delete them?" (or the empty-case plain message if
   none). For "forget everything", set a flag in the reply copy so the client asks for the
   stronger confirm.
2. **Client** shows the candidates (a small confirm card with the list + Confirm/Cancel —
   see 13.6). On Confirm it re-POSTs `/chat` with the **same** message and
   `confirm_forget=[ids]`.
3. **Second message:** when `confirm_forget` is present, the server skips routing, calls
   `store.delete_memories(ids, user_id)`, and returns `reply` = a `save_ack`-style "Forgotten
   — removed N." with `source="none"`.
- Streaming: the forget *resolution* and *confirmation* are short single-shot replies; emit
  them as a single `_sse({"t": reply})` + done. No token streaming needed for forget.

### 13.5 Empty / safety cases (R16.5, R16.4)
- No candidates → `reply = "I don't have anything saved about that."`, `forget_candidates`
  omitted, nothing deleted.
- Never delete on the first turn. `confirm_forget` ids are re-checked against `user_id` in
  `delete_memories` (RLS + explicit `.eq("user_id", ...)`), so a stale/foreign id is a no-op.

### 13.6 Web UI
- `web/lib/api.ts`: `postChat` gains optional `confirmForget?: string[]` → body
  `confirm_forget`. Return type gains `forget_candidates`.
- `web/app/chat/page.tsx`: when a response has `forget_candidates`, render a
  `web/components/chat/ForgetConfirm.tsx` card (list of candidate contents + dates, Confirm
  / Cancel buttons). Confirm calls `postChat(originalText, { confirmForget: ids })` and
  replaces the card with the result line; Cancel drops the card and writes "Okay, kept
  them." Add a `delete`/`trash` icon to `Icon.tsx`.
- Because forget is a single-shot reply, route it through `postChat` (non-streaming), not
  `postChatStream`, to keep the confirm handshake simple.

### 13.7 CLI
- `recall/cli.py`: the bare-text `forget` branch lists candidates and prompts
  `Delete these N? [y/N]` inline; on `y`, `store.delete_memories`. `/forget <id>` stays.

### 13.8 Tests
- Router returns `forget` for the heuristic phrases; classifier parser maps `FORGET`.
- `delete_memories` count semantics (mock client).
- Confirm protocol: first call returns candidates + deletes nothing; second call with
  `confirm_forget` deletes (integration / mocked).

**DoD:** PRD §17.

---

## 14. Phase 17 — Richer chat UI & theme depth

Frontend-only. Files across `web/components/chat/*`, `web/components/ui/*`,
`web/app/chat/page.tsx`, `web/app/globals.css`.

### 14.1 Remove the standing date divider (R17.1)
- `web/components/chat/MessageList.tsx` groups by date and inserts `DateDivider`s. Change the
  logic so a divider is emitted **only between two messages whose dates differ** — never
  before the first group. Net effect on a same-day session: zero dividers, so the "TODAY"
  chip disappears. Keep `DateDivider.tsx` itself for genuine multi-day history.

### 14.2 Welcoming empty state + suggestion chips (R17.2)
- Rework `web/components/chat/EmptyState.tsx`: headline (optionally "Welcome back,
  {firstName}." using `user_metadata.full_name` via `supabase.auth.getUser()`), one-line
  subtitle, and a wrapped row of 3–4 chips. Each chip is a button that calls a new
  `onSuggestion(text)` prop → `web/app/chat/page.tsx` sets the input (and optionally
  auto-sends). Suggested chips: "Remember something for me", "What did I save today?",
  "What can you do?", "Show my recent notes".

### 14.3 Recent-memory cards (R17.3)
- New `web/components/chat/RecentMemories.tsx`: fetches via `getMemories()` (already in
  `api.ts`, returns newest-first), takes the top ~5, renders compact cards (content
  truncated to ~2 lines + relative date). Tapping a card prefills the input with
  "What do I know about: <snippet>?" (a recall) via the same `onSuggestion` path.
- Render it inside `EmptyState` (or just below it) when `messages.length === 0`. Show the
  phase-13 skeleton while loading; show a friendly "Nothing saved yet — tell me something"
  when the account is empty.
- `getMemories` already exists; no backend change. (Pinned-first ordering arrives with phase
  19; until then newest-first is fine.)

### 14.4 Depth & texture (R17.4)
- In `globals.css`: introduce elevation tokens (e.g. `--elevation-1/-2` box-shadows) and
  apply subtly to cards, the input pill, and the top bar; refine the existing radial-gradient
  body wash; add a thin accent rule or a small `auto_awesome` glyph to the `Memex` wordmark
  in `TopBar.tsx`. Stay within PRD §8 (no hero gradients, no glassy over-rounded cards) —
  this is *restraint with depth*, not a redesign.
- Keep the 200ms `message-enter` motion contract; new elements may fade/translate in the
  same way and nothing else animates.

### 14.5 Responsive (R17.5)
- Cards: CSS grid `repeat(auto-fill, minmax(220px, 1fr))` so they stack on mobile; chips
  `flex-wrap`. Verify at 375px width.

**DoD:** PRD §18.

---

## 15. Phase 18 — Settings menu & dark mode

### 15.1 Settings dropdown (R18.1, R18.4)
- New `web/components/ui/SettingsMenu.tsx`: a button (the existing `settings` icon, already
  in `Icon.tsx`) placed in `TopBar.tsx` **left of** the logout button, opening a popover.
  Use a small headless pattern: `useState(open)`, close on outside-click (a `useEffect`
  document listener) and on `Escape`; render items as a `<ul role="menu">`. No new library
  needed; if one is desired, confirm against `web/AGENTS.md`/Next docs first.

### 15.2 Dark mode — the real work (R18.2)
The current theme is **light-only with hardcoded hex** in components
(`AuthForm.tsx` uses `#00236f`/`#444651`; `MessageBubble.tsx` uses `bg-white`; `globals.css`
body color is `#f8f9fa`). Dark mode requires **tokenising** these:
- In `globals.css`, the `@theme inline` block already defines semantic color tokens. Add a
  dark override block:
  ```css
  :root[data-theme="dark"] {
    --color-surface: #14161a; --color-background: #14161a;
    --color-surface-container-lowest: #1b1e24; /* …full dark ramp… */
    --color-on-surface: #e3e3e6; --color-on-surface-variant: #c2c4cc;
    --color-outline: #8c8f99; --color-outline-variant: #3a3d45;
    --color-primary: #b6c4ff; --color-on-primary: #002a78; /* invert primary pair */
    /* map every token used in the UI to a dark value */
  }
  ```
  Drive it with a `data-theme` attribute on `<html>` (not `prefers-color-scheme` alone, so
  the manual toggle wins). Keep a `[data-theme="system"]` path that falls back to a
  `@media (prefers-color-scheme: dark)` block.
- **Replace hardcoded hex with tokens** in `AuthForm.tsx` (`#00236f`→`text-primary` /
  `var(--color-primary)`, `#444651`→`text-on-surface-variant`) and `MessageBubble.tsx`
  (`bg-white`→`bg-surface-container-lowest`), and the `body` color in `globals.css`
  (→ `var(--color-background)`). Audit for any other literal hex with Grep.
- Apply theme early to avoid flash: set `data-theme` in a tiny inline script in
  `web/app/layout.tsx` `<head>` that reads `localStorage.theme` before paint (the standard
  no-flash pattern). Persist the choice to `localStorage` and a React context.
- New `web/lib/theme.ts` (or a `ThemeProvider` context under `web/components/ui/`) exposing
  `theme`, `setTheme("light"|"dark"|"system")`; `SettingsMenu` calls it.

### 15.3 Other menu items (R18.3)
Include at least two of: the signed-in email (read from `getUser`); "Memory Library" (opens
phase 19); "Export data" (phase 21); "Clear all memories" (calls a new
`DELETE /memories` all-route or loops deletes, behind a typed-confirm modal); "About Memex"
(version + the privacy/Gemini caveat line). Ship the email + at least one action now;
wire Library/Export when those phases land.

### 15.4 Tests
- Theme reducer/util is a pure function (light/dark/system → resolved theme given an OS
  preference) — unit-test it.

**DoD:** PRD §19.

---

## 16. Phase 19 — Memory Library

### 16.1 Surface
- New route `web/app/library/page.tsx` (guarded the same way as `/chat` via the server
  session check + `proxy.ts`), reached from `SettingsMenu`. It is a panel/list, not a
  marketing dashboard — chat stays home.

### 16.2 Backend (extend `api/routers/memories.py` + `recall/store.py`)
Current: `POST /memories`, `GET /memories`, `DELETE /memories/{id}`. Add:
- `PATCH /memories/{id} { content }` → re-embed and update. New
  `store.update_memory(client, mem_id, user_id, content, embedding) -> dict` doing an
  `.update({content, embedding}).eq("id").eq("user_id")`. The PATCH handler calls
  `embeddings.embed(content, cfg, "RETRIEVAL_DOCUMENT")` then `store.update_memory`.
- Pin: simplest is to use the existing **`metadata jsonb`** column (already in the schema,
  default `{}` — no migration). `store.set_pinned(client, mem_id, user_id, pinned: bool)`
  writes `metadata = {..., "pinned": true}`. `GET /memories` returns `metadata` so the
  client can sort pinned-first. (Optionally add `?pinned=true` filter later.)
- `GET /memories` already lists all newest-first; add an optional `?q=` (substring,
  server-side `ilike` via a new `store.search_memories_text`) **or** do client-side filter
  for the keyword case and reuse `/chat` semantic recall for meaning — keep phase-19 search
  client-side substring + the existing time filter to stay simple.

### 16.3 Web
- `web/lib/api.ts`: add `updateMemory(id, content)`, `deleteMemory(id)`, `setPinned(id,
  pinned)`. `getMemories` already exists.
- Library UI: list of `MemoryRow` components (content, date, pin toggle, edit (inline
  textarea), delete (confirm)). Search box filters client-side; a time-window dropdown
  filters by `created_at`. Show `count_memories` total (expose via `GET /memories` length or
  a `/memories/count` route).
- Pinned memories feed phase 17's `RecentMemories` cards (sort pinned-first there).

### 16.4 Tests
- `store.update_memory` / `set_pinned` shape (mock client). Re-embed path: PATCH triggers an
  `embeddings.embed` call (assert via mock).

**DoD:** PRD §20.

---

## 17. Phase 20 — Organisation & reminders

### 17.1 Auto-tags (R20.1)
- At store time, classify the memory into a small fixed taxonomy. Cheapest reliable path:
  one extra Gemini call at save (temperature 0) returning a comma-separated subset of a
  closed label set `{idea, task, person, place, work, personal, date, misc}`. New
  `recall/llm.py` `tag_memory(content, cfg) -> list[str]` with a strict prompt ("Reply only
  with labels from this list, comma-separated.").
- Persist tags into the existing `metadata` jsonb (`metadata.tags = [...]`) — **no schema
  change**. `store.add_memory` already accepts the row; extend it (or the chat store branch)
  to write `metadata`. To avoid adding latency to the user's confirmation, compute the tag
  **after** sending the ack (fire-and-forget) or accept the extra call — document the
  trade-off; for free-tier RPM, prefer computing it inline only if within limits, else defer.
- Library (phase 19) shows tags and filters by them (`metadata.tags` contains).

### 17.2 Reminders (R20.2)
- Extend `recall/temporal.py` with `extract_due(text, tz, now) -> datetime | None` that
  detects **future** dates in a *stored* sentence ("on Tuesday", "next month", "in 3 days",
  explicit dates). Reuses the same parsing primitives as `extract_range` but returns a single
  point in time, only when it is in the future.
- On store, if `extract_due` returns a datetime, write `metadata.due = <iso>`.
- New `store.list_due(client, user_id, before: datetime) -> list[Memory]` selecting rows
  where `metadata->>due` is non-null and `<= before` (a `.lte` on the jsonb text cast; or
  `.not_.is_("metadata->>due", "null")`). Add `GET /memories/due` returning upcoming/overdue.
- Web: a "Due / upcoming" section (in Library and/or a chat affordance) listing those
  memories. Push notifications are **phase 22** (PWA) — until then, in-app surfacing only.
- **No false alarms (R20.4):** only memories with a real `metadata.due` ever appear; time-less
  memories never do.

### 17.3 Non-intrusive (R20.3)
- Tagging/due-extraction failures are swallowed — the memory is still saved plainly. Never
  block or fail the core store on these enhancements.

### 17.4 Tests
- `extract_due` future-only behaviour (past date → None; "in 3 days" → correct point; no
  date → None), including a non-UTC tz.
- `tag_memory` parser keeps only labels in the closed set.

**DoD:** PRD §21.

---

## 18. Phase 21 — Data ownership & insights

### 18.1 Export (R21.1)
- `GET /memories/export` → returns all memories (content, created_at, metadata/tags/due) as
  JSON; the client can also render Markdown locally. Reuse `store.list_memories`. The web
  triggers a file download (`Blob` + `URL.createObjectURL`). Add to `SettingsMenu`.

### 18.2 Import (R21.2)
- `POST /memories/import { items: [{content, created_at?}] }`: for each item, embed and
  insert. **De-dup:** skip an item whose `content` exactly matches an existing memory for
  that user (cheap `ilike`/equality check), or whose embedding cosine ≥ 0.97 to an existing
  one (reuse `match_memories`). Return `{imported, skipped}`.
- Web: file picker → parse → `POST /memories/import` → toast the counts.

### 18.3 Insights (R21.3)
- `GET /memories/stats` → `{ total, added_last_30d, top_tags: [{tag, count}] }`. `total` via
  `count_memories`; `added_last_30d` via `list_memories_in_range(now-30d, now)` length;
  `top_tags` by counting `metadata.tags` (small N, count in Python). A simple insights card
  in settings/Library renders these — no chart library required (a few numbers + bars).

### 18.4 Daily digest (R21.4)
- Reuse `temporal.extract_range` + `llm.summarize_window`. An on-demand "Today's digest"
  button (or the existing "what did I save today?" path) is enough for the DoD; a scheduled
  push digest depends on phase 22 PWA push and is optional.

### 18.5 Privacy line (R21.5)
- Static copy in "About Memex" (SettingsMenu) restating where data lives + the Gemini
  free-tier training caveat from the README.

### 18.6 Tests
- De-dup logic (exact-match path) unit-tested with a mock store.
- `stats` aggregation (counts from a fixed memory list).

**DoD:** PRD §22.

---

## 19. Phase 22 — Capture & reach

Mostly frontend (`web/`), no model changes.

### 19.1 Quick capture (R22.1)
- A global "+" button (top bar) and a shortcut (e.g. `c`) that focuses the input in a
  "capture" mode where Enter always **stores** (route is forced to `store` by sending to a
  thin client flag, or simply by prefixing intent server-side — simplest: a dedicated
  `POST /memories` call, which already exists and always stores). Optimistic UI: show the
  card immediately, reconcile on response.

### 19.2 Voice input (R22.2)
- Use the Web Speech API (`window.SpeechRecognition || webkitSpeechRecognition`) behind a mic
  button in `ChatInput.tsx`. Append the transcript to the input; the user reviews then sends
  through the normal route. Feature-detect and hide the mic where unsupported. No backend
  change.

### 19.3 Command palette / shortcuts (R22.3)
- `web/components/ui/CommandPalette.tsx` opened by `Cmd/Ctrl+K`: a filterable list running
  actions — New capture, Open Library, Open settings, Toggle theme, "What did I save
  today?". Implement as a controlled modal with keyboard nav; reuse existing handlers.
  Confirm modal/portal patterns against `web/AGENTS.md`/Next docs.

### 19.4 PWA (R22.4)
- Add `web/app/manifest.ts` (Next metadata manifest), icons under `web/public/`, and a
  service worker for an offline app shell (use the Next-recommended approach for this
  version — **read `node_modules/next/dist/docs/` first** per `web/AGENTS.md`). PWA install
  unlocks push for phase-20 reminders.

### 19.5 Share a memory (R22.5)
- Optional: a read-only `web/app/m/[id]/page.tsx` that renders a single memory if the owner
  enabled sharing (store `metadata.shared = true`; a public-read RLS policy scoped to
  `metadata->>shared = 'true'`). Keep account-to-account sharing out (non-goal). Lowest
  priority in the wave.

**DoD:** PRD §23.

---

## 20. Wave 2 — data model & schema deltas (summary)

No `vector(768)` / HNSW / `match_memories` changes. All new state rides the existing
`metadata jsonb` column (default `{}`), so **most phases need no migration**:

| Need | Where | Migration? |
|------|-------|------------|
| name at signup | `auth.users.user_metadata.full_name` | none (JWT) |
| pinned | `memories.metadata.pinned` | none |
| tags | `memories.metadata.tags` | none |
| due date | `memories.metadata.due` | none |
| shared flag | `memories.metadata.shared` + read RLS policy | small RLS policy (phase 22, optional) |
| due/tag query speed | optional `gin (metadata)` index in `supabase/schema.sql` | optional, add if slow |

Add the GIN index only if `metadata` filters get slow:
```sql
create index if not exists memories_metadata_idx on memories using gin (metadata);
```

## 21. Wave 2 — module & API contract deltas (summary)

```python
# models.py
Intent = Literal["store", "query", "general", "forget"]          # + forget (phase 16)

# router.py
route(text, cfg) -> Intent                                       # + forget heuristic

# llm.py
classify_intent(...) -> Intent                                   # now 4-way (+FORGET)
save_ack(content=None, rng=None) -> str                          # phase 15
tag_memory(content, cfg) -> list[str]                            # phase 20
extract_forget_target(message, cfg) -> str                       # phase 16 (may be regex)
# all prompts moved to recall/prompts.py (phase 15)

# temporal.py
extract_due(text, tz="UTC", now=None) -> datetime | None         # phase 20

# store.py
delete_memories(client, ids, user_id) -> int                     # phase 16
update_memory(client, id, user_id, content, embedding) -> dict   # phase 19
set_pinned(client, id, user_id, pinned) -> dict                  # phase 19
list_due(client, user_id, before) -> list[Memory]               # phase 20
```

```
# FastAPI
POST  /chat        + confirm_forget: list[str]|null (req); + forget_candidates (resp)  # 16
PATCH /memories/{id}            { content }                                             # 19
GET   /memories/due                                                                    # 20
GET   /memories/export                                                                  # 21
POST  /memories/import          { items: [...] }                                        # 21
GET   /memories/stats                                                                   # 21
GET   /m/[id] (web, optional)   shared read                                             # 22
```

```
# web/lib/api.ts additions
postChat(message, { confirmForget? })            # phase 16
updateMemory(id, content) / deleteMemory(id) / setPinned(id, pinned)   # phase 19
getDue() / exportData() / importData(file) / getStats()                # phases 20–21
# postChatStream: new JSON SSE frames {t|done|error}                   # phase 14
```

## 22. Wave 2 — testing summary (network-free unit tests)

- **12:** `isDuplicateSignup`, `mapAuthError` (pure, in `web/lib/auth-helpers.ts`).
- **14:** `parseSseEvents(buffer)` handles a token containing `\n`; `_sse` round-trips.
- **15:** `save_ack` returns a member of `SAVE_ACKS`; prompts module imports.
- **16:** router returns `forget`; classifier maps `FORGET`; `delete_memories` count; confirm
  protocol deletes only on second call.
- **17:** `MessageList` emits a divider only between differing dates (pure grouping fn).
- **18:** theme resolver (light/dark/system + OS pref) pure function.
- **20:** `extract_due` future-only + non-UTC tz; `tag_memory` parser stays in the closed set.
- **21:** import de-dup (exact match) and `stats` aggregation over a fixed list.

Integration tests remain the manual Definitions of Done per phase (PRD §§13–23) against the
live free-tier stack.

## 23. Wave 2 — sequencing & risk notes

- **Ship 12→18 in order first** (the "feels finished" wave); 14 (streaming) and 16 (forget)
  are the two with backend protocol changes — land their backend + frontend together.
- **Dark mode (18) is bigger than it looks** because of hardcoded hex; budget time for the
  tokenisation audit (Grep for `#` literals and `bg-white` in `web/`).
- **Extra Gemini calls (auto-tags, due-extraction in 20)** add load on the free tier; make
  them best-effort/deferred so they never slow or fail a save.
- **Forget (16) is destructive** — the two-step confirm is non-negotiable; never delete on
  the first turn, always re-scope by `user_id` in the delete.
- **PWA/manifest/service-worker (22)** must follow this repo's modified Next.js — read
  `node_modules/next/dist/docs/` per `web/AGENTS.md` before writing any of it.
