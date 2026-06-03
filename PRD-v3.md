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

---
---

# Part II — Wave 2 (v3.1): product, polish, and growth

> Everything above (phases 0–11) is built. Part II is the **next** body of work. It is a
> single document so a coding agent can read top-to-bottom, but it is delivered as
> independent phases (12–22), each with its own Definition of Done. Phases 12–18 are the
> user-requested fixes and polish; phases 19–22 are the new product surface that makes
> Memex valuable to everyday users *and* professionals.
>
> **Altitude.** This part says *what* and *why*. The matching *how* (files, signatures,
> exact edits) is in `TDD-v3.md` Part II, section-for-section. Phase numbers line up across
> both documents.

## 12. Wave 2 at a glance

| Phase | Name | Theme | One-line outcome |
|-------|------|-------|------------------|
| 12 | Auth & onboarding hardening | Fix | Password eye works; duplicate-signup handled; friendly errors; name captured. |
| 13 | Transitions & status states | Fix | A branded hand-off between login and chat; a neutral "working" indicator, not "retrieving". |
| 14 | Reliable streaming | Fix | Replies actually stream token-by-token without dropping multi-line content. |
| 15 | Personality & prompt system | Fix | Memex has a consistent, warm voice; confirmations vary; one prompt module. |
| 16 | Natural-language forget | Feature | "forget what I said about X / forget yesterday's notes" deletes the right memories, with confirmation. |
| 17 | Richer chat UI & theme depth | Fix | Remove the date divider; fuller empty state; recent-memory cards; the screen no longer feels empty. |
| 18 | Settings menu & dark mode | Feature | A dropdown by the logout button; working dark mode; a couple of useful toggles. |
| 19 | Memory Library | Feature | Browse, search, pin, edit, and delete memories in a dedicated panel. |
| 20 | Organisation & reminders | Feature | Auto-tags/categories, favourites, and time-based reminders surfaced at the right moment. |
| 21 | Data ownership & insights | Feature | Export / import everything; a lightweight stats + daily-digest view. |
| 22 | Capture & reach | Feature | Quick-capture, voice input, command palette, installable PWA, shareable single memory. |

Phases 12–18 should ship first and in order — they are the "make it feel finished" wave.
Phases 19–22 are additive product surface and can be reordered by priority, but each still
has a hard Definition of Done.

---

## 13. Phase 12 — Auth & onboarding hardening

**Problem.** The auth screen has a password-reveal eye that does nothing, signing up with
an already-registered email fails confusingly, the "Full Name" field is collected and
thrown away, and error copy is raw Supabase text.

**Requirements**
- **R12.1 — Working password reveal.** The eye icon toggles the password field between
  masked and plain text, and the icon reflects the current state (open eye vs. eye-off).
  Applies to every password field (login, signup, and any future confirm field).
- **R12.2 — Duplicate-account handling.** Signing up with an email that already exists must
  not dead-end. Detect it and respond with a clear message plus a one-tap switch to the
  Login tab, pre-filling the email. ("Looks like you already have an account — log in
  instead.")
- **R12.3 — Capture the name.** The Full Name entered at signup is saved to the user's
  profile and used to greet them (e.g. the empty state and general replies can address them
  by first name). If no name is given, behaviour is unchanged.
- **R12.4 — Humane errors.** Map common auth failures (wrong password, invalid email,
  unconfirmed email, rate-limited, network down) to short, friendly, specific copy. Never
  show a raw exception or HTTP status to the user.
- **R12.5 — Confirm-on-signup clarity.** When email confirmation is required, the existing
  notice stays, but it is visually a success state, and a "resend confirmation" affordance
  is offered.

**Definition of Done**
- Clicking the eye reveals/masks the password; the icon changes; tabbing and typing still
  work.
- Signing up with an existing email shows the "already have an account" message and the
  Login tab is now active with the email pre-filled — no scary error.
- Signing up with a name then reaching the chat shows a greeting that uses the first name.
- Each of: wrong password, malformed email, and an offline submit shows a distinct,
  friendly message.

---

## 14. Phase 13 — Transitions & status states

**Problem.** After pressing the auth button there is a blank, uncertain gap before the chat
appears (phase 11 made the *shell* optimistic but there is still no branded hand-off), and
while a reply is being produced the assistant bubble literally reads "Retrieving
memories…" — which is wrong when the message is actually being *saved* or is *small talk*.

**Requirements**
- **R13.1 — Branded hand-off.** Between a successful auth and an interactive chat, show a
  brief, branded transition (logo + a calm progress treatment) rather than a blank screen
  or a raw spinner. It must resolve quickly and never block longer than the data load.
- **R13.2 — Neutral working indicator.** Replace the literal "Retrieving memories…" text
  with a content-free, animated "working" indicator (e.g. a three-dot / shimmer in the
  assistant bubble). It must read correctly whether Memex is saving, recalling, summarising
  a time window, or just chatting. No words that presume the operation type.
- **R13.3 — First-token swap.** The instant the first real token arrives, the working
  indicator is replaced in place by the streaming text (no flicker, no duplicate bubble).
- **R13.4 — Memory hydration skeleton.** When prior memories/recent cards are loading into
  the freshly rendered shell, show a lightweight skeleton, not a spinner over a blank page.

**Definition of Done**
- Logging in shows a branded transition, then the chat — no blank flash.
- Sending any message (a save, a recall, a greeting) shows the same neutral indicator; none
  of them say "retrieving".
- When the reply starts, the indicator becomes the text smoothly in the same bubble.

---

## 15. Phase 14 — Reliable streaming

**Problem.** Replies do not visibly stream. The transport drops any chunk that contains a
line break, so multi-line or markdown-ish answers arrive truncated or appear to "pop in"
all at once on the non-streaming fallback.

**Requirements**
- **R14.1 — Lossless streaming transport.** Tokens that contain newlines (or any
  character) must arrive intact and in order. The end-to-end stream must reproduce the
  model output byte-for-byte.
- **R14.2 — Visible incremental render.** The user sees text grow token-by-token, not a
  single late paint. A gentle caret/typing cue while streaming is acceptable (but optional).
- **R14.3 — Graceful fallback unchanged.** If streaming genuinely fails, the existing
  retry-then-non-streaming fallback still produces the full, correct answer.
- **R14.4 — No regression to other intents.** Save confirmations and temporal summaries
  stream/settle correctly too.

**Definition of Done**
- A reply known to contain line breaks (e.g. a list of three saved items) renders in full,
  with every line present, and visibly grows as it streams.
- Killing the network mid-stream falls back and still shows the complete answer or a clean
  inline error — never a half-truncated reply with no indication.

---

## 16. Phase 15 — Personality & prompt system

**Problem.** Replies are flat. Saves always say a bare "Saved." Recalls read like a search
engine. There is no consistent voice, and prompts are scattered as string constants across
`llm.py`.

**Requirements**
- **R15.1 — A defined voice.** Memex has a short, documented persona: warm, concise,
  quietly clever, never bubbly or corporate, never "As an AI…". The voice is the same
  across saves, recalls, time summaries, and small talk.
- **R15.2 — Confirmations with character.** A successful save returns a varied, brief,
  human acknowledgement (rotating among a small set, optionally reflecting what was saved)
  instead of a fixed "Saved." It must stay one short line and must not invent detail.
- **R15.3 — Grounded answers keep their guarantees.** More character must **not** weaken
  the no-hallucination rule: personal-recall misses still return the fixed "nothing saved"
  line; general knowledge is still clearly not framed as a personal memory.
- **R15.4 — One prompt module.** All system prompts live in one place, are easy to tune,
  and are reused by CLI and API identically so both clients sound the same.
- **R15.5 — Length discipline.** The persona enforces brevity (a sentence or two) so the
  product stays sparse; character comes from word choice, not length.

**Definition of Done**
- Saving three different things yields three differently-worded one-line confirmations,
  each plainly an acknowledgement, none inventing facts.
- A recall answer reads warm and natural while still grounded only in retrieved memories.
- A `query` miss still returns exactly the fixed "nothing saved" string.
- CLI and web replies for the same input read in the same voice.

---

## 17. Phase 16 — Natural-language forget

**Problem.** Deletion only exists in the CLI as `/forget <id>`. There is no way to say
"forget that" in plain language, and the web app cannot delete at all.

**Requirements**
- **R16.1 — A fourth intent: forget.** Memex recognises deletion requests in natural
  language and routes them to a delete flow instead of storing them. ("forget that I parked
  on level 3", "delete what I said about the dentist", "forget everything from yesterday".)
- **R16.2 — Forget by detail.** "forget what I told you about X" finds the memories that
  match X (semantically) and targets them.
- **R16.3 — Forget by time.** "forget yesterday's notes / everything from last week"
  targets memories in that window (reusing the temporal engine).
- **R16.4 — Confirmation, always.** Deletion is destructive and irreversible, so Memex
  always shows exactly which memories will be removed and requires an explicit confirm
  before deleting. A "forget everything" style request requires a stronger confirm.
- **R16.5 — Honest empty case.** If nothing matches, Memex says so plainly and deletes
  nothing. It must never claim to have forgotten something it never had.
- **R16.6 — Web + CLI parity.** Both clients support the natural-language forget flow,
  including the confirmation step.

**Definition of Done**
- "forget what I said about the dentist" lists the matching memory/memories, asks to
  confirm, and on confirm they are gone (verify in Supabase).
- "forget everything from yesterday" targets exactly the right window and requires confirm.
- A forget request that matches nothing returns a plain "I don't have anything saved about
  that" and deletes nothing.
- Cancelling the confirmation leaves all memories intact.

---

## 18. Phase 17 — Richer chat UI & theme depth

**Problem.** The chat is sparse to the point of feeling empty and unfinished. There is a
persistent "TODAY" date divider pinned at the top that adds noise, the empty state is a
single line, and there is nothing that shows the user their data at a glance. The theme is
flat.

**Requirements**
- **R17.1 — Remove the standing date divider.** The "TODAY" chip at the top of the chat is
  removed. (Date separation, if kept at all, only appears *between* messages that actually
  span different days — never as a lone header on an empty/one-day conversation.)
- **R17.2 — A welcoming empty state.** The empty state becomes useful: a warm headline, a
  one-line explanation, and 3–4 tappable suggestion chips ("Remember something…", "What did
  I save today?", "What can you do?") that prefill the input.
- **R17.3 — Recent-memory cards.** When the conversation is empty (and/or in a dedicated
  area), show a small set of "recent memories" as cards — the last few things the user
  saved, with their date — so the screen demonstrates value immediately and gives a tap to
  recall. Cards are read-from `GET /memories`.
- **R17.4 — Depth and texture.** Add tasteful visual depth consistent with the existing
  Material-3/Stitch system: refined surface elevation, a subtle accent treatment on the
  brand/header, and a considered background — without violating the "no gradients hero / no
  glassy over-rounded cards" guidance from §8. The result should feel crafted, not busy.
- **R17.5 — Responsive.** All new UI works on mobile widths (cards stack, chips wrap).

**Definition of Done**
- There is no "TODAY" chip on a fresh or single-day chat.
- An empty chat shows a real welcome with working suggestion chips and recent-memory cards
  (or a friendly "nothing yet" if the account is empty).
- Tapping a recent-memory card or a suggestion chip starts the right action.
- The screen no longer reads as "empty"; it looks intentional on desktop and mobile.

---

## 19. Phase 18 — Settings menu & dark mode

**Problem.** There is only a bare logout icon. There is no dark mode despite the design
system nominally supporting one, and no place for app preferences.

**Requirements**
- **R18.1 — Settings dropdown.** A small settings menu opens from a control next to the
  logout button in the top bar. It is a lightweight dropdown/popover, not a new screen
  (keeps the two-screen model intact).
- **R18.2 — Dark mode toggle.** The menu offers Light / Dark / System. The choice is
  applied app-wide and persisted across reloads. Dark mode is a real, complete theme — no
  unreadable hardcoded-light remnants.
- **R18.3 — At least two more useful items.** The menu also includes a couple of genuinely
  useful entries — chosen from: the signed-in account/email, a link to the Memory Library
  (phase 19), "export my data" (phase 21), "clear all memories" (with strong confirm), and
  an "about Memex" line. Pick what fits; the menu should feel purposeful, not padded.
- **R18.4 — Accessible & dismissible.** Opens on click, closes on outside-click / Escape,
  keyboard-navigable, and does not trap focus.

**Definition of Done**
- A settings control sits beside logout and opens a dropdown.
- Switching to Dark restyles the entire app (auth + chat) with no light-mode leftovers, and
  the choice survives a reload; System follows the OS.
- The menu contains the theme control plus at least two other working items.

---

## 20. Phase 19 — Memory Library

> From here on, new product surface. The two-screen rule relaxes *slightly*: the Library is
> a panel/overlay reachable from settings, not a separate marketing-style dashboard. The
> chat remains the home screen.

**Why.** Both casual users and professionals eventually want to *see* and *manage* what
they have stored — not only converse with it. This is the most-requested "real app"
capability and unlocks trust (I can find and fix what's in here).

**Requirements**
- **R19.1 — Browse.** A scrollable list of all memories, newest first, each showing content
  and saved date.
- **R19.2 — Search & filter.** Filter by free text (semantic and/or substring) and by time
  window; results update as you type.
- **R19.3 — Edit.** Edit a memory's text in place; on save it is re-embedded so future
  recall reflects the edit.
- **R19.4 — Delete.** Delete a single memory with confirm (the web counterpart of CLI
  `/forget`).
- **R19.5 — Pin / favourite.** Mark memories as pinned; pinned items sort to the top and
  can power the "recent/important" cards on the chat empty state.
- **R19.6 — Counts.** Show the total memory count.

**Definition of Done**
- The Library lists every stored memory and updates immediately after add/edit/delete.
- Editing a memory changes future recall behaviour (re-embedded).
- Pinning a memory surfaces it on the chat empty-state cards.
- Search returns the expected memories for both a keyword and a time filter.

---

## 21. Phase 20 — Organisation & reminders

**Why.** As the store grows, undifferentiated memories get hard to navigate, and a lot of
what people "tell" a second brain is implicitly time-bound ("call the dentist Tuesday",
"renew passport next month"). Light structure and gentle reminders make the product sticky
for professionals managing many small commitments.

**Requirements**
- **R20.1 — Automatic tags/categories.** At save time, Memex assigns one or more lightweight
  tags/categories (e.g. idea, task, person, place, work, personal) without the user doing
  any filing. Tags are visible in the Library and usable as filters.
- **R20.2 — Reminders.** When a saved memory implies a date/time ("on Tuesday", "next
  month", "in 3 days"), Memex extracts a due date and can surface that memory as due — at
  minimum a "due / upcoming" view, and where feasible a notification (in-app and/or PWA
  push). Extraction reuses/extends the temporal engine.
- **R20.3 — Non-intrusive.** Tagging and reminders never block the core capture flow; if
  extraction is uncertain, the memory is still saved plainly with no tag/date.
- **R20.4 — No false alarms.** A reminder only fires for memories that genuinely carried a
  future date; nothing time-less is ever surfaced as "due".

**Definition of Done**
- Saving "great idea: a tea subscription box" tags it as an idea; saving "Sara's birthday
  is in June" tags it person/date.
- Saving "renew passport next month" appears in a due/upcoming view at the right time.
- A plain memory with no date never shows up as a reminder.

---

## 22. Phase 21 — Data ownership & insights

**Why.** Trust and retention. People will only pour their life into a second brain if they
can get it all back out, and a small amount of reflection (what am I capturing, how much)
makes the tool feel alive without becoming a dashboard product.

**Requirements**
- **R21.1 — Export.** Export all memories (with dates and tags) in an open, portable format
  (JSON and/or Markdown) from settings, in one action.
- **R21.2 — Import.** Re-import a previously exported file, embedding each memory on the way
  in, with sensible de-duplication so re-importing doesn't double everything.
- **R21.3 — Insights.** A small insights view: total memories, memories added over time
  (e.g. last 30 days), and a few top tags. Honest counts only — no vanity inflation.
- **R21.4 — Daily digest (optional surface).** An on-demand (and/or scheduled) "here's what
  you saved today / this week" summary, reusing the temporal summariser.
- **R21.5 — Privacy line.** A clear in-app statement of where data lives and the Gemini
  free-tier training caveat already noted in the README.

**Definition of Done**
- Export produces a file containing every memory with dates; import of that file restores
  them without duplicating existing ones.
- The insights view shows a correct total and a correct 30-day add count.
- The digest summarises the correct window using only real memories.

---

## 23. Phase 22 — Capture & reach

**Why.** A second brain is only as good as how easily you can feed it and reach it. These
remove friction for everyday users (voice, install-to-home-screen) and power users
(command palette, quick capture).

**Requirements**
- **R22.1 — Quick capture.** A fast path to drop a memory without composing a full
  message — a global "+" / shortcut that focuses capture, and optimistic UI so the user can
  keep going immediately.
- **R22.2 — Voice input.** Dictate a memory or question via the browser's speech-to-text;
  the transcript flows through the same routing. Degrades gracefully where unsupported.
- **R22.3 — Command palette / shortcuts.** Keyboard-driven access to core actions (new
  capture, search the Library, open settings, toggle theme) for power users.
- **R22.4 — Installable PWA.** The web app is installable to a phone/desktop home screen
  (manifest + icons + offline shell), so it feels like a real app and enables push for
  reminders (phase 20).
- **R22.5 — Share a memory.** Optionally produce a shareable read-only view/snippet of a
  single memory (no account-to-account sharing — that remains a non-goal).

**Definition of Done**
- A keyboard shortcut focuses quick capture and saving it requires no extra navigation.
- Dictating a sentence on a supported browser captures it as a memory.
- The command palette opens via shortcut and can run at least: new capture, open Library,
  toggle theme.
- The app can be installed to a home screen and launches as a standalone PWA.

---

## 24. Wave 2 — cross-cutting product principles

- **The chat stays home.** Every new surface (Library, settings, insights) is reachable
  *from* the chat, never replaces it. No sidebars-by-default, no marketing dashboard.
- **The no-hallucination rule is absolute and survives every feature.** Personality,
  tags, summaries, digests, and forget-confirmations are all built only from real data;
  personal-recall misses always return the fixed message.
- **Destructive actions always confirm.** Forget, clear-all, and delete require explicit
  confirmation and say exactly what they will remove.
- **Free-tier only, latency over cost.** Same stack (Vercel, Railway/Render, Supabase,
  Gemini). New work targets perceived speed and polish; infrastructure cost/scale remains
  out of scope per the project owner.
- **Sparse by design.** Added richness (cards, depth, dark mode) must keep the product
  feeling calm and considered — character through craft, not clutter.

## 25. Audience notes (who this is for)

- **Everyday users:** capture-anything, ask-later, gentle reminders, voice, install to
  phone. The win is "I never lose a small thing again," with zero filing.
- **Professionals / knowledge workers:** the Library (find/fix/organise), auto-tags,
  reminders for many small commitments, export for portability, and insights. The win is a
  trustworthy, searchable, time-aware personal record that lives alongside their tools.
