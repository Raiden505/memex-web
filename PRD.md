# Product Requirements Document — "Recall" (working title)

**A personal memory CLI: tell it things, ask it later.**

Version: 1.0
Scope of this document: CLI client only. No web or mobile apps in this build.
Companion document: `TDD.md` (technical design).

---

## 1. Overview

Recall is a command-line app that acts as a personal "second brain." You tell it
things in plain language — facts, ideas, tasks, things people told you — and it
saves them. Later you ask it questions in plain language and it answers using
what you told it. Under the hood it is a small RAG (retrieval-augmented
generation) system over your own notes.

Example session:

```
you › my friend told me there are sick jackets in Islamabad
bot › got it, I'll remember that.

you › where did I hear about jackets?
bot › Your friend mentioned there are some great jackets in Islamabad.
```

## 2. Problem statement

People constantly accumulate small pieces of information — ideas, reminders,
things they were told — and lose them. Notes apps require you to organize and
then remember where you filed things. Recall removes the organizing step: you
dump information in naturally and retrieve it by *asking*, not by searching folders.

## 3. Goals and non-goals

### Goals
- Capture a memory from a single natural-language sentence, with zero ceremony.
- Retrieve memories by asking natural-language questions.
- Run on a completely free stack (free-tier cloud services, no paid plans required).
- Be architected so it can later sync across multiple devices **without a rewrite**,
  even though only a CLI ships now.

### Non-goals (for this build)
- No web app, no mobile app, no GUI. CLI only.
- No multi-user product launch. The architecture is multi-user *ready*, but the
  shipped CLI is for a single owner.
- No rich note organization (folders, manual tags). Retrieval is by meaning.
- No real-time collaboration or sharing between people.

## 4. Target user

The builder (you), for personal use, on your own machine. Single account.
Everything is designed so "add a phone app later, signed into the same account"
is a future feature, not a redesign.

## 5. The interaction model

Two ways to interact, both available at all times:

1. **Natural language (the default magic).** You just type. The app decides
   whether you are *storing* something or *asking* something and acts accordingly.
2. **Explicit slash commands (the manual override).** For when you want precise
   control or the auto-detection guesses wrong.

| Command          | Purpose                                          |
|------------------|--------------------------------------------------|
| `/add <text>`    | Force-store text as a memory                     |
| `/ask <text>`    | Force-treat text as a question                   |
| `/search <text>` | Show raw matching memories (no AI answer)        |
| `/list`          | Show all stored memories with their ids          |
| `/forget <id>`   | Delete a memory by id                            |
| `/count`         | How many memories are stored                     |
| `/help`          | Show help                                        |
| `/quit`          | Exit                                             |

## 6. Functional requirements

- **FR1** — Store: the app saves a memory (its text + a timestamp) to durable
  cloud storage. Memories survive restarts and machine changes.
- **FR2** — Retrieve: given a question, the app finds the most semantically
  relevant stored memories and produces a natural-language answer grounded only
  in those memories.
- **FR3** — No-hallucination rule: if nothing relevant is stored, the app says so
  rather than inventing an answer.
- **FR4** — Intent routing: free-text input is classified as *store* or *query*
  and handled automatically, with slash commands as an override.
- **FR5** — Manage: the user can list, count, and delete memories.
- **FR6** — Resilience: external service failures (LLM/DB/network) produce a clear
  message, never an unhandled crash.
- **FR7** — Multi-device readiness: every memory is associated with an account so
  a future second client signed into the same account sees the same memories.

## 7. Constraints

- **Free tier only.** LLM and embeddings via Google Gemini's free tier; database
  via Supabase's free tier. No service requires a paid plan to run this build.
- **Free-tier rate limits exist.** The Gemini free tier is generous for personal
  use (well over a thousand requests/day) but is not unlimited; the app must
  degrade gracefully when limited.
- **Privacy caveat.** On the Gemini free tier, prompts may be used by the provider
  for training. This is acceptable for this build but should be surfaced to the
  user in the README. (A future privacy mode could self-host embeddings.)
- **Free-tier quotas change over time.** Exact limits and model names must be
  confirmed against current provider docs during implementation, not assumed.

## 8. Phased delivery plan (product view)

Development is split into phases. **Each phase ends in something you can test by
hand.** The acceptance check is what *you* run to confirm the phase is done.
Technical tasks for each phase live in `TDD.md` under the matching phase number.

### Phase 0 — Skeleton
The app exists and runs, but does nothing intelligent yet.
- **Acceptance:** `python -m recall` launches to a prompt; `/help` lists the
  commands; `/quit` exits cleanly; running it with missing configuration prints a
  clear, friendly "here's what to set up" message instead of a stack trace.

### Phase 1 — Cloud storage (no AI yet)
Memories are saved to and read from the cloud database using explicit commands.
- **Acceptance:** `/add buy milk` saves a note; the row is visibly present in the
  Supabase dashboard; `/list` shows it with an id; `/count` reports the right
  number; `/forget <id>` removes it; everything persists after quitting and
  relaunching.

### Phase 2 — Semantic search
The app can find memories by meaning, not exact words.
- **Acceptance:** after adding several different notes, `/search` with *different
  wording* than the original note still surfaces the right note(s), ranked with
  the most relevant first.

### Phase 3 — Answers (RAG complete)
The app turns retrieved memories into a natural answer.
- **Acceptance:** `/ask where did I hear about jackets` returns a coherent
  sentence built from your stored notes; `/ask` about something you never stored
  replies that it has nothing saved, rather than making something up.

### Phase 4 — Auto intent (the magic)
No more needing `/add` vs `/ask` — plain text just works.
- **Acceptance:** typing a statement stores it; typing a question answers it; the
  tricky cases route correctly, e.g. "remind me to call mom" is *stored* as a task
  while "remind me where I parked" is treated as a *question*. Slash commands still
  work as overrides.

### Phase 5 — Accounts & multi-device readiness (still CLI)
Memories are tied to a login, proving the multi-device foundation.
- **Acceptance:** you log in; your notes are tied to your account and persist; a
  fresh login session (simulating a second device) signed into the same account
  sees the same notes; a different account sees none of yours.

### Phase 6 — Hardening (optional polish)
Graceful behavior under failure.
- **Acceptance:** simulating a rate limit or a network drop produces a friendly
  message and/or an automatic retry or fallback, never a crash.

## 9. Success metrics

- A natural-language question about something you stored returns the correct,
  grounded answer the large majority of the time.
- Capturing a memory takes one line of typing and no decisions.
- The app runs for a month of personal use at $0.

## 10. Future scope (explicitly out of this build)

- A web client and a mobile client signed into the same account (the reason the
  architecture is cloud-backed and account-scoped from the start).
- LLM-extracted tags/categories and filtering by them.
- Parsing relative dates ("later today", "tomorrow") into real reminder dates.
- A privacy mode that keeps stored text out of any third-party training data.
