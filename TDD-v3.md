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
