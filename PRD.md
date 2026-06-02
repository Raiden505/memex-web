# Product Requirements Document — "Recall" / "Memex"

**A personal memory app: tell it things, ask it later. CLI + web.**

Version: 3.0 (consolidated — supersedes the original CLI-only v1)
This document folds in the web/multi-client scope from `PRD-v2.md` and the conversational
/ temporal / UX features from `PRD-v3.md`, so it is the single current product spec.
Companion document: `TDD.md`. Detailed v2/v3 specs remain in `PRD-v2.md` / `PRD-v3.md`.

> **Naming note.** The working title is *Recall*; the shipped web client is branded
> **Memex**. Same product.

---

## 1. Overview

Recall/Memex is a personal "second brain." You tell it things in plain language — facts,
ideas, tasks, things people told you — and it saves them. Later you ask questions in plain
language and it answers from what you told it. Under the hood it is a small RAG
(retrieval-augmented generation) system over your own notes, backed by the cloud so the
same account works from multiple devices.

It now ships as **two clients sharing one backend**:
- a **CLI** (terminal REPL), and
- a **web app** (browser chat),

both reading and writing the same Supabase account.

Example session:

```
you › my friend told me there are sick jackets in Islamabad
bot › got it, I'll remember that.

you › where did I hear about jackets?
bot › Your friend mentioned there are some great jackets in Islamabad.

you › hi
bot › Hey — tell me something and I'll remember it.

you › what did I tell you today?
bot › Today you saved: the jacket tip from your friend.
```

---

## 2. Problem statement

People constantly accumulate small pieces of information and lose them. Notes apps require
you to organise, then remember where you filed things. Recall removes the organising step:
you dump information in naturally and retrieve it by *asking*, not by searching folders.
It should also behave like a real assistant — handle a greeting or a general question
without choking — and understand time ("what did I tell you today?").

---

## 3. Goals and non-goals

### Goals
- Capture a memory from a single natural-language sentence, zero ceremony.
- Retrieve memories by asking natural-language questions.
- True multi-device: CLI at the terminal, web from any browser, same memories.
- Handle greetings and general questions conversationally without polluting the store.
- Answer time-scoped questions ("today", "this week", "yesterday").
- A web UI that looks like a considered product, not a generic AI chatbot.
- Run on a completely free stack.

### Non-goals
- No native mobile app (the web app is responsive and covers mobile).
- No multi-user product / sharing between accounts.
- No rich note organisation (folders, tags). Retrieval is by meaning or by time.
- No real-time collaboration.
- Not a general-purpose chatbot — it is a memory tool that is polite about non-memory
  input, not a replacement for a general assistant.
- No multi-turn conversational memory of the chat session itself (future scope).

---

## 4. Products

### 4.1 CLI (complete)
A terminal REPL. Plain text in, plain text out, plus slash-command overrides.

| Command          | Purpose                                          |
|------------------|--------------------------------------------------|
| `/add <text>`    | Force-store text as a memory                     |
| `/ask <text>`    | Force-treat text as a question                   |
| `/search <text>` | Show raw matching memories (no AI answer)        |
| `/list`          | Show all stored memories with their ids          |
| `/forget <id>`   | Delete a memory by id                            |
| `/count`         | How many memories are stored                     |
| `/logout`        | Sign out and clear the local session             |
| `/help`          | Show help                                        |
| `/quit`          | Exit                                             |

### 4.2 Web app
A browser-based chat. Login/signup → a single full-screen chat view. No dashboards, no
sidebars, no settings panels. No slash commands — the interface is purpose-built.

---

## 5. Interaction model

Both clients use the same intent model. Free-text input is automatically classified and
handled; the CLI additionally offers slash-command overrides.

Three intents:

| Intent    | Meaning                                                            | Result                                                |
|-----------|--------------------------------------------------------------------|-------------------------------------------------------|
| **store** | Telling Memex something to remember.                               | Embed + save.                                         |
| **query** | Recalling something **personal** you told it (optionally time-scoped). | Semantic search (or a date-window listing) + grounded answer. |
| **general** | A greeting, small talk, general-knowledge question, or "what can you do?". | Answered conversationally by Gemini; not saved, not memory-grounded. |

The web app has **two screens only**:

- **Auth.** Centred form with brand mark, email/password, sign-in/sign-up toggle.
- **Chat.** Full-screen conversation: messages fill the vertical space, input anchored at
  the bottom, a minimal sign-out link in the top corner. Nothing else.

---

## 6. Functional requirements

- **FR1 — Store.** Save a memory (text + timestamp) to durable cloud storage; survives
  restarts and machine changes.
- **FR2 — Retrieve.** Given a question, find the most semantically relevant memories and
  answer grounded only in those memories.
- **FR3 — No-hallucination (personal).** If nothing relevant is stored for a personal
  recall, say so rather than inventing. Never fabricate a personal fact.
- **FR4 — Intent routing.** Classify free-text as store / query / general and handle
  automatically; slash commands override (CLI).
- **FR5 — Manage.** List, count, and delete memories.
- **FR6 — Resilience.** External failures (LLM/DB/network) produce a clear message, never
  an unhandled crash.
- **FR7 — Multi-device.** Every memory is tied to an account; any client signed into the
  same account sees the same memories.
- **FR8 — Conversational range.** Greetings and general questions get a short, in-character
  Gemini reply; they are not stored and never claim to be from saved memories.
- **FR9 — Temporal recall.** Answer time-scoped questions ("today", "yesterday", "this
  week", "last N days") from memories created in that window, in the user's local day.
- **FR10 — Web responsiveness.** After a reply the cursor returns to the input; the user
  can type while a reply is in flight (but not send); login lands in the chat quickly.

---

## 7. No-hallucination rule (authoritative)

> Memex must never invent a **personal memory**. A personal-recall (`query`) with no
> matching results returns the fixed "nothing saved" message — no model guess. Messages
> classified `general` (greetings, small talk, general-knowledge questions) are answered
> by Gemini and are never presented as something the user previously stored. Temporal
> answers are built only from memories actually found in the requested window.

---

## 8. Design philosophy (web)

A tool that feels like a well-made physical object — sparse, typographically considered,
warm, fast and direct. Avoid the ChatGPT/Claude aesthetic, gradient hero sections, glassy
over-rounded cards, typing-indicator animations, assistant avatars, and over-animated
transitions.

> The detailed visual spec lives in `PRD-v2.md §6` (the original parchment/Lora system).
> **As shipped, the web client is branded "Memex" and uses a Material-3-derived design**
> (Manrope / Inter type, generated from a Stitch reference — see `MEMORY.md`). Where the
> implementation and `PRD-v2.md §6` differ, the implementation is the current truth; v3
> introduces no visual redesign, only behavioural/UX changes (§ FR10).

---

## 9. Phased delivery plan

Each phase ends in a manual Definition of Done; do not start one until the previous passes.
**Phases 0–8 are complete** (code complete; some live DoD checks pending — see `MEMORY.md`).

| Phase | Name | Status | Acceptance (summary) |
|-------|------|--------|----------------------|
| 0 | Skeleton | ✅ | `python -m recall` launches; `/help`, `/quit`; friendly missing-config message. |
| 1 | Cloud storage (no AI) | ✅ | `/add` saves; `/list`/`/count`/`/forget` work; persists across restarts. |
| 2 | Semantic search | ✅ | `/search` with different wording surfaces the right notes, ranked. |
| 3 | Answers (RAG) | ✅ | `/ask` gives a grounded answer; unknown → "nothing saved", no invention. |
| 4 | Auto intent | ✅ | Bare statements store, bare questions answer; "remind me to call mom" stores, "remind me where I parked" queries. |
| 5 | Accounts & multi-device | ✅ | Login ties memories to an account; a second session sees them; another account sees none. |
| 6 | FastAPI backend | ✅ | Authenticated `/memories` CRUD + `/chat` over HTTP with a real Supabase JWT; CLI unchanged. |
| 7 | Next.js web app | ✅ | Sign in, store from the web, ask and get a correct answer incl. CLI-stored memories; works desktop + mobile. |
| 8 | Streaming + hardening | ✅ | Responses stream in; network drop / rate limit shows an inline error, not a crash. |
| 9 | Conversational range (GENERAL) | ▶ next | Greetings/general questions get a short reply and are **not** saved; personal-recall misses still say "nothing saved". |
| 10 | Temporal recall | ⬜ | "what did I tell you today/this week/yesterday" returns the right window in the user's local day. |
| 11 | Web UX refinements | ⬜ | Cursor returns to input; type-while-loading (no send); fast login → chat. |

Full per-phase Definitions of Done: phases 0–4 in `TDD.md`, 5–8 in `TDD-v2.md`, 9–11 in
`TDD-v3.md`.

---

## 10. Constraints

- **Free tier only:** Vercel (Next.js), Railway/Render (FastAPI), Supabase, Gemini. No
  paid plans. *(For v3 work, hosting cost/scale is explicitly out of scope per the project
  owner — UX latency is in scope, infrastructure cost is not.)*
- **Embedding dimension locked at 768.** The model output and the `vector(768)` column
  must agree; never change the model without re-embedding every row.
- **Privacy caveat.** The Gemini free tier may use prompts for training — acceptable for
  personal use, noted in the README.
- Free-tier rate limits and model identifiers must be confirmed against current docs at
  build time.

---

## 11. Success metrics

- A natural-language question about stored content returns the correct, grounded answer
  the large majority of the time.
- Capturing a memory takes one line of typing and no decisions.
- Greetings and general questions feel natural, never produce a "nothing saved" dead-end,
  and never invent a personal fact.
- The app runs for a month of personal use at $0.

---

## 12. Future scope

- Manual dark/light toggle.
- Memory management view (browse, edit, search, delete from the web UI).
- Dedup of near-identical memories; source attribution in answers.
- Multi-turn conversational context within a session.
- Topical + temporal combined queries as a first-class feature.
- Native mobile app using the same FastAPI backend.
- A privacy mode that keeps stored text out of third-party training data.
