# Product Requirements Document v3 — "Recall" / "Memex"

**Conversational range, temporal recall, and web UX refinements.**

Version: 3.0
Previous versions: `PRD.md` (v1, CLI, phases 0–6) and `PRD-v2.md` (web app, phases 5–8).
Companion document: `TDD-v3.md`.
Status of phases 0–8: **COMPLETE** (code complete; some live DoD checks still pending — see `MEMORY.md`).

> **Naming note.** The product working title in the original docs is *Recall*. The
> shipped web client is branded **Memex**. They are the same product; "Memex" is the
> name a user sees in the UI.

---

## 1. Why v3 exists

Phases 0–8 delivered a working second brain: store memories in natural language,
retrieve them by meaning, get a grounded answer, on both CLI and web. But three gaps
make it feel like a demo rather than a product people use daily:

1. **It is conversationally brittle.** Say "hi" and it tries to *store* "hi" as a
   memory. Ask "what's the capital of France?" and it either stores the question or
   answers "I don't have anything saved about that." A real assistant should handle a
   greeting or a general question gracefully instead of treating everything as a note.

2. **It has no sense of time.** "What did I tell you today?" is a completely natural
   thing to ask a memory app, and it currently can't answer it — semantic search has
   no notion of *when* something was saved.

3. **The web experience has rough edges.** After a response the cursor leaves the
   input; you can't start typing your next thought while one is in flight; and the gap
   between pressing "log in" and seeing the chat feels slow and uncertain.

v3 closes these three gaps. It adds no new screens and no new third-party services.

---

## 2. Goals and non-goals

### Goals
- Handle greetings and general questions conversationally via Gemini, without polluting
  the memory store and without breaking the no-hallucination guarantee for personal facts.
- Answer time-scoped questions ("what did I tell you today / this week / yesterday").
- Make the web chat feel immediate: cursor returns to the input, you can type while a
  response streams, and login lands you in the chat quickly.

### Non-goals
- No new screens, sidebars, or settings panels (the two-screen model from v2 stands).
- No general-purpose chatbot positioning. Memex is a memory tool that is *polite and
  capable* about non-memory input — not a replacement for a general assistant.
- No multi-turn conversational memory of the chat itself (each message is still routed
  independently). A rolling context window is explicitly future scope.
- No change to the embedding model, dimension (768), or database schema beyond what
  temporal queries strictly require.

---

## 3. Feature 1 — Conversational range (the GENERAL intent)

### 3.1 Behaviour

Today every message is classified as **store** or **query**. v3 adds a third class:
**general**.

| Class     | Meaning                                                            | Handling                                              |
|-----------|--------------------------------------------------------------------|-------------------------------------------------------|
| `store`   | The user is telling Memex something to remember.                   | Embed + save (unchanged).                             |
| `query`   | The user is recalling something **personal** they told Memex.      | Embed + semantic search + grounded answer (unchanged).|
| `general` | A greeting, small talk, a general-knowledge question, or a meta question ("what can you do?"). | Answered by Gemini conversationally. **Not** grounded in the memory store and **not** saved. |

Examples:

```
"hi"                              -> general -> "Hey — tell me something and I'll remember it."
"thanks!"                         -> general -> a short acknowledgement
"what can you do?"                -> general -> a one-line description of Memex
"what's the capital of France?"   -> general -> "Paris." (general knowledge)
"buy milk tomorrow"               -> store
"where did I park?"               -> query  (personal recall — stays strict)
```

### 3.2 The strict-personal-facts rule (critical)

The Gemini fallback applies **only to messages classified `general` up front**. It does
**not** apply to personal-recall misses.

- If a `query` returns no matching memories, Memex still replies with the fixed
  "I don't have anything saved about that yet." message. It must **never** ask Gemini to
  guess at a personal fact it was never told (a wifi password, where you parked, what a
  friend said). Inventing personal facts is the one thing this product must never do.
- General knowledge ("the capital of France", "how many ml in a cup") is *not* a personal
  fact, so answering it from the model is acceptable and is clearly not presented as
  something the user previously stored.

This refines, rather than weakens, the no-hallucination rule: **never invent personal
memories; general knowledge and small talk are fine.**

### 3.3 Greetings should not touch the database

Because greetings and general questions are classified `general` before any retrieval,
they never run a semantic search and never produce a "nothing saved" dead-end. This is
cleaner than the "search first, fall back on empty" approach and keeps personal recall
strict.

### 3.4 Tone

General replies are short, warm, and stay in character as a memory assistant. No emoji
spam, no "As an AI…", no multi-paragraph essays. A greeting gets one line. A general
question gets a direct answer. The product is sparse by design (v2 §5) and that applies
to its conversation too.

---

## 4. Feature 2 — Temporal recall

### 4.1 Behaviour

Memex can answer questions scoped by time, returning what was stored in a window rather
than what is semantically similar.

```
"what did I tell you today?"
"what have I told you this week?"
"what did I save yesterday?"
"anything from the last 3 days?"
```

The reply is a concise summary or list of the memories created in that window, oldest to
newest. If nothing was stored in the window, Memex says so plainly ("Nothing saved
today.") — this is a true statement about the user's own data, not a hallucination guard.

### 4.2 Scope of phrases supported

Phase 10 supports the common, unambiguous cases: **today, yesterday, this week, last N
days**, and **a named weekday or explicit date** where feasible. Open-ended or vague
ranges ("a while ago", "recently") fall through to ordinary semantic search rather than
guessing a window.

### 4.3 Time zone

"Today" means the user's local day, not UTC. The web client resolves the user's time
zone and sends it with the request so the window is computed correctly. The CLI uses the
machine's local time zone.

### 4.4 Relationship to semantic search

A temporal listing is a different operation from semantic similarity: it filters by
`created_at` and returns everything in range, then asks Gemini to summarise it. A question
that is *both* topical and time-scoped ("what did I note about work this week?") may
combine a date filter with semantic ranking; Phase 10 treats this as a stretch case and
the pure-window case as the must-have.

---

## 5. Feature 3 — Web UX refinements

These are small, high-impact changes to the existing chat screen. No visual redesign.

### 5.1 Return the cursor to the input
After a response finishes (streamed or not), focus returns to the message textarea
automatically so the user can keep typing without reaching for the mouse.

### 5.2 Type while a response is in flight
The textarea stays **editable** while a response is loading or streaming. The user can
compose their next message immediately. **Sending** is what's gated: Enter and the send
button are disabled until the current response completes, so messages can't overlap or
race. (Today the whole textarea is disabled during loading — that changes.)

### 5.3 Faster, clearer login → chat
The wait between pressing the auth button and seeing the chat must feel short and
intentional:
- Navigate to the chat shell immediately on successful auth; render the layout (top bar,
  empty message area, input) right away rather than blocking on data.
- Load prior memories / session state into that shell without blocking first paint.
- Warm the API up front (a lightweight health ping from the auth screen) so a cold
  backend isn't discovered only after login. *(Latency, not cost — per the project owner,
  hosting cost/scale is explicitly out of scope for this work.)*

---

## 6. No-hallucination rule (restated for v3)

> Memex must never invent a **personal memory**. A personal-recall (`query`) with no
> matching results returns the fixed "nothing saved" message — no model guess.
> Messages classified `general` (greetings, small talk, general-knowledge questions) are
> answered by Gemini and are never presented as something the user previously stored.
> Temporal answers are built only from memories actually found in the requested window.

This supersedes the two-line rule in v1/v2 wherever they conflict.

---

## 7. Phased delivery plan

Phases 0–8 are **complete**. v3 adds three phases. Each ends in a manual Definition of
Done; do not start one until the previous passes.

### Phase 9 — Conversational range (GENERAL intent)
Add the third intent and the Gemini conversational handler; keep personal recall strict.

- **Acceptance:**
  - "hi", "thanks", "what can you do?" get a short conversational reply and are **not**
    saved as memories (verify in Supabase: no new row).
  - "what's the capital of France?" returns a correct general answer, clearly not framed
    as a stored memory.
  - A personal question with nothing stored ("where did I park?") still returns the fixed
    "nothing saved" message — Gemini does **not** invent an answer.
  - Storing and recalling personal memories still works exactly as before.

### Phase 10 — Temporal recall
Answer time-scoped questions from the user's own stored memories.

- **Acceptance:**
  - Store two memories, then ask "what did I tell you today?" — both come back,
    summarised, oldest first.
  - "what did I tell you yesterday?" with nothing stored yesterday returns "Nothing saved
    yesterday." (no invention).
  - "this week" and "last N days" return the correct windows.
  - The window respects the user's local day, not UTC (test near midnight or with a
    non-UTC time zone).

### Phase 11 — Web UX refinements
The three chat-screen improvements from §5.

- **Acceptance:**
  - After a response, the cursor is back in the input without clicking.
  - While a response streams, the user can type the next message but cannot send it until
    the response completes.
  - From pressing the auth button, the chat shell appears promptly (layout visible before
    data finishes loading); a cold backend does not produce a long, blank wait.

---

## 8. Constraints

- Same free-tier stack as v1/v2 (Vercel, Railway/Render, Supabase, Gemini). Per the
  project owner, **hosting cost and scale are out of scope for v3** — UX latency is in
  scope, infrastructure cost is not.
- No new third-party services and no new screens.
- Embedding model and the `vector(768)` dimension are unchanged.

---

## 9. Future scope (still out)

- Multi-turn conversational context (referring back to earlier messages in the session).
- Topical + temporal combined queries as a first-class, fully reliable feature.
- Memory management UI (browse/edit/delete from the web), dedup of near-identical
  memories, and source attribution in answers.
