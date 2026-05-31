# Product Requirements Document v2 — "Recall" (working title)

**A personal memory app: CLI and web.**

Version: 2.0  
Previous version: `PRD.md` (CLI-only, phases 0–6)  
Companion document: `TDD-v2.md`  
Status of phases 0–4: **COMPLETE**. This document supersedes the original.

---

## 1. Overview

Recall is a personal "second brain." You tell it things in natural language and
retrieve them by asking questions. It now ships as two clients sharing one
cloud backend: a CLI (complete) and a web app (new). Both read and write to the
same account, making it genuinely multi-device.

---

## 2. Goals and non-goals

### Goals
- A web interface that feels as natural as the CLI — just a conversation.
- True multi-device: CLI at the terminal, web from any browser, same memories.
- Completely free to run on the current stack.
- A web UI that looks like a considered product, not a generic AI chatbot.

### Non-goals
- No native mobile app (the web app is responsive and covers mobile).
- No multi-user product / sharing between accounts.
- No rich note organisation (folders, tags). Retrieval is always by meaning.
- No real-time collaboration.

---

## 3. Products

### 3.1 CLI (complete)
A terminal REPL. Plain text in, plain text out. Phases 0–4 are shipped.

### 3.2 Web app (new)
A browser-based chat interface. Login/signup → a single full-screen chat view.
No dashboards, no sidebars, no settings panels. Just the conversation.

---

## 4. Interaction model — web

The web experience has two screens only:

**Screen 1 — Auth.** A centred page with the brand mark, an email/password
form, and a toggle between sign-in and sign-up. Nothing else.

**Screen 2 — Chat.** The full screen is the conversation. Messages fill the
vertical space; the input is anchored to the bottom. No navigation. No menu.
The user can leave by closing the tab or hitting a minimal log-out action (a
small, unobtrusive link — not a button — in the top corner).

The web app follows the same intent model as the CLI: plain statements are
stored, plain questions are answered. The web app does not expose slash commands
— it does not need to, because it is a purpose-built interface.

---

## 5. Design philosophy

The goal is a tool that feels like a well-made physical object — a notebook with
a good spine, a pen that writes the right weight. Not a product demo, not an
AI assistant, not a "platform."

Specific things to avoid:
- The ChatGPT/Claude aesthetic (dark sidebar, small input at bottom-centre,
  avatar next to each message, "How can I help you today?")
- Purple or blue gradient hero sections
- Glassy cards, heavy shadows, rounded-everything
- Typing indicator animations (three bouncing dots)
- Any assistant avatar or icon
- Over-animated page transitions

What it should feel like instead:
- Sparse. Generous whitespace. Nothing on screen that does not need to be there.
- Typographically considered. The text is the product.
- Warm, not cold. The palette has paper and ink in it, not plasma and chrome.
- Fast and direct. A message appears; a response appears. No ceremony.

---

## 6. Visual design system

This section is the authoritative design spec. The frontend agent must implement
it exactly. Do not substitute fonts, colours, or spacing values arbitrarily.

### 6.1 Typography

| Role         | Font                  | Weight   | Notes                                         |
|--------------|-----------------------|----------|-----------------------------------------------|
| Brand mark   | Lora (Google Fonts)   | 600      | Used only for the app name in auth + top bar  |
| UI / body    | Plus Jakarta Sans     | 400/500  | All other text                                |
| User input   | Lora                  | 400      | Input field text only — creates a journaling feel |
| Monospace    | —                     | —        | Not used                                      |

Import both fonts via `next/font/google`. Base body size: 15px. Line height: 1.65.

### 6.2 Colour palette

Define all colours as CSS custom properties on `:root` and `[data-theme="dark"]`.

```css
:root {
  --bg:              #F5F0E8;   /* warm parchment */
  --bg-subtle:       #EDE8DF;   /* input area, message container */
  --bg-hover:        #E5DFD5;
  --text:            #1C1814;   /* warm near-black */
  --text-muted:      #7A7166;   /* placeholders, timestamps, metadata */
  --text-faint:      #B0A89E;   /* very low emphasis */
  --accent:          #9B6B4A;   /* terracotta — used sparingly */
  --accent-hover:    #7D5439;
  --user-bubble-bg:  #1C1814;
  --user-bubble-text:#F5F0E8;
  --border:          #DDD8CF;
  --border-subtle:   #EAE5DC;
  --input-bg:        #FFFFFF;
  --shadow:          0 1px 3px rgba(28, 24, 20, 0.08);
  --radius:          10px;
  --radius-bubble:   18px;
  --radius-input:    14px;
}

[data-theme="dark"] {
  --bg:              #181512;
  --bg-subtle:       #211E1B;
  --bg-hover:        #2A2622;
  --text:            #EDE8DF;
  --text-muted:      #8A8278;
  --text-faint:      #524E4A;
  --accent:          #C4885E;
  --accent-hover:    #D99A70;
  --user-bubble-bg:  #EDE8DF;
  --user-bubble-text:#181512;
  --border:          #2E2B27;
  --border-subtle:   #252220;
  --input-bg:        #211E1B;
  --shadow:          0 1px 3px rgba(0, 0, 0, 0.25);
}
```

Theme is determined by `prefers-color-scheme` by default. A manual toggle is
out of scope for this build (add later if desired).

### 6.3 Spacing scale

Use a 4px base unit. Common values: 4, 8, 12, 16, 20, 24, 32, 48, 64.
Do not introduce intermediate values without a clear reason.

### 6.4 Breakpoints

| Name    | Min width | Target device          |
|---------|-----------|------------------------|
| mobile  | 0px       | Phone portrait          |
| tablet  | 640px     | Phone landscape / tablet |
| desktop | 1024px    | Laptop and above        |

### 6.5 Motion

- Message entrance: `opacity 0 → 1` + `transform: translateY(6px) → 0` over
  200ms with `ease-out`. No bouncing, no spring.
- Input focus ring: `box-shadow` transition, 150ms.
- Button press: `scale(0.97)`, 100ms.
- Page load: single fade-in of the entire chat area, 300ms. No staggered
  reveals.
- Nothing else animates. Restraint is the point.

---

## 7. Screen and component specifications

### 7.1 Auth screen

- Vertically and horizontally centred content block, max-width 360px.
- Brand mark (Lora, 24px, --text) at the top of the block.
- A single-line tagline below in --text-muted (optional, can be empty).
- Email input, password input, primary action button.
- A plain text toggle: "Don't have an account? Sign up" / "Already have an
  account? Sign in" — in --text-muted, no button styling.
- No logo image, no illustration, no decorative elements.
- Background is --bg (the parchment tone). The content block has a subtle
  border (--border) and --shadow, or is borderless on mobile.
- Error messages appear as small red text directly below the relevant field.
  No toasts, no alert dialogs.

### 7.2 Chat screen — layout

```
┌───────────────────────────────────────────┐
│  [brand mark]                [sign out]   │  ← top bar, 48px tall, minimal
├───────────────────────────────────────────┤
│                                           │
│   messages scroll here                    │  ← flex-grow, overflow-y scroll
│                                           │
│                                           │
├───────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐  │  ← input area, auto-height
│  │  type something…          [↑ send]  │  │
│  └─────────────────────────────────────┘  │
└───────────────────────────────────────────┘
```

The top bar and input area stay fixed; the message area scrolls. On mobile,
the input area must account for the virtual keyboard (use
`dvh` units or `window.visualViewport` adjustments as appropriate).

### 7.3 Top bar

Height: 48px. Contains brand mark (left, Lora 16px) and a "sign out" text link
(right, Plus Jakarta Sans, 13px, --text-muted). No other elements. A very subtle
bottom border (--border-subtle) separates it from the message area.

### 7.4 Message bubbles

**User messages:**
- Right-aligned.
- Background: --user-bubble-bg. Text: --user-bubble-text.
- Border radius: --radius-bubble.
- Max-width: 72% on desktop, 85% on mobile.
- Padding: 10px 14px.
- Font: Plus Jakarta Sans 15px (input was Lora, but once sent, display in
  the body font for consistency).
- No avatar, no name label, no timestamp by default.

**App responses:**
- Left-aligned.
- No background, no border. Text colour: --text.
- Same max-width and padding rules.
- A very subtle left padding (8px) to visually separate from the edge.
- If the response streams in, render characters as they arrive. No "..." 
  placeholder before text starts.

**Date dividers:**
- A centred line of --text-faint text ("Today", "Yesterday", "12 May") with
  a thin --border-subtle line extending left and right.
- Appears between messages when the date changes.
- Height: 32px total, vertically centred text.

**Empty state:**
- When there are no messages, show a single centred line in --text-faint:
  "tell me something" — lowercase, no punctuation.
- This disappears as soon as the first message is sent.

### 7.5 Input area

- Background: --bg-subtle. Top border: --border.
- A textarea (not `<input>`) that starts at one line height and grows to a
  maximum of 5 lines before scrolling internally.
- Font: Lora, 15px. Placeholder: "tell me something…" in --text-faint.
- Pressing Enter sends. Shift+Enter inserts a newline.
- A small send icon button (↑ or a simple arrow SVG) to the right inside the
  input. Visible at all times (not hidden until text is entered — the input
  should not feel conditional or reactive).
- On mobile: the input area sits above the keyboard when it opens. The
  messages area shrinks to fill remaining space. Test this on a real device.

### 7.6 Loading and error states

- While waiting for a response (if not streaming), show a single "·" (middle
  dot, --text-faint) as a message in the response position. It does not
  animate. Replace it with the real response when it arrives.
- If the request fails, show the error inline where the response would be, in
  --accent colour, small text: "couldn't reach memory — try again".
- No toast notifications, no modals, no banners.

---

## 8. Phased delivery plan

Phases 0–4 are **complete**. All remaining phases build on that foundation.

### Phase 5 — Auth (CLI + Supabase)
*Unchanged from original PRD. Complete this before anything web-related.*
- **Acceptance:** login associates memories with an account; a second session
  sees the same memories; a different account sees none of yours.

### Phase 6 — FastAPI backend
A Python API layer that exposes the existing logic over HTTP.
- **Acceptance:** using a tool like `curl` or Bruno/Insomnia, you can store a
  memory, list memories, search memories, and get an answer — all authenticated
  with a real Supabase JWT. The CLI continues to work unchanged alongside this.

### Phase 7 — Next.js web app
The browser client.
- **Acceptance:** you can open the app in a browser, sign in with the same
  account used in the CLI, send a message that stores a memory, and ask a
  question that returns a correct answer — including memories you previously
  stored from the CLI. It works on both a desktop browser and a mobile browser.
  The design matches this spec.

### Phase 8 — Hardening
Graceful failure, rate-limit handling, streaming responses.
- **Acceptance:** the response streams in character-by-character; a network
  drop or rate limit produces the inline error message from §7.6 rather than
  a crash or silent failure.

---

## 9. Constraints

- Free tier only: Vercel (Next.js), Railway or Render (FastAPI), Supabase,
  Gemini. No paid services.
- The Gemini free tier may use prompts for training. This is acceptable for
  personal use but should be noted in the README.
- Free-tier rate limits and model names must be confirmed against current docs
  at build time.

---

## 10. Future scope

- Manual dark/light toggle.
- Memory management view (browse, search, delete from the web UI).
- Native mobile app using the same FastAPI backend.
