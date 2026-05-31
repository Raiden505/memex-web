# Technical Design Document v2 — "Recall"

Companion to `PRD-v2.md`.  
Phases 0–4 are **complete** (see original `TDD.md`). This document covers the
full revised architecture and provides the implementation plan for phases 5–8.

> **Implementation note:** Confirm all provider SDK names, model identifiers,
> and free-tier limits against current official docs before writing integration
> code. Do not assume values from memory.

---

## 1. Architecture overview

```
                      ┌──────────────────────────────────────┐
  Browser / mobile ──▶│  Next.js (Vercel)                    │
                      │  - Auth pages (Supabase JS client)   │
                      │  - Chat UI                            │
                      └────────────────┬─────────────────────┘
                                       │ HTTPS + Supabase JWT
                                       ▼
                      ┌──────────────────────────────────────┐
  Terminal ──────────▶│  FastAPI (Railway / Render)          │
  (direct module      │  - /memories  CRUD                   │
   calls, no hop)     │  - /chat      query + stream         │
                      │  - validates JWT via Supabase        │
                      └────────────────┬─────────────────────┘
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
            ┌─────────────────┐             ┌─────────────────┐
            │ Supabase        │             │ Gemini API       │
            │ Postgres+vector │             │ embed + chat     │
            │ + Auth          │             │ (free tier)      │
            └─────────────────┘             └─────────────────┘
```

**CLI relationship:** The CLI continues to call `store.py`, `embeddings.py`,
and `llm.py` directly (no network hop needed on a local machine). FastAPI is an
additional layer for the web client, not a replacement for the CLI's internal
architecture. Both clients share the same Supabase database and the same account
thanks to Phase 5 auth.

---

## 2. Updated tech stack

| Concern         | Choice                   | Notes                                              |
|-----------------|--------------------------|----------------------------------------------------|
| CLI             | Python REPL              | Unchanged. Direct module calls.                    |
| API backend     | FastAPI (Python)         | Thin layer over existing modules. Async-native.    |
| Backend hosting | Railway (free tier)      | Alternatively Render. One service to deploy.       |
| Frontend        | Next.js 14+ (App Router) | Vercel hosting. TypeScript throughout.             |
| Frontend host   | Vercel (free tier)       | Natural pairing with Next.js. Zero config.         |
| Auth (web)      | Supabase JS + `@supabase/ssr` | JWT issued by Supabase; validated by FastAPI. |
| DB / vectors    | Supabase pgvector        | Unchanged.                                         |
| Embeddings      | Gemini embeddings        | Unchanged.                                         |
| LLM             | Gemini 2.5 Flash         | Unchanged. Streaming enabled in Phase 8.           |
| Styling         | Tailwind CSS v3          | Custom tokens via CSS variables (see §8).          |

---

## 3. Full project structure

```
recall/                         ← Python monorepo root
  recall/                       ← existing Python package (phases 0–4)
    __init__.py
    __main__.py
    cli.py
    config.py
    store.py
    embeddings.py
    llm.py
    router.py
    models.py
    auth.py                     ← added in Phase 5
  api/                          ← new in Phase 6
    main.py                     ← FastAPI app entrypoint
    dependencies.py             ← JWT auth dependency
    routers/
      memories.py               ← CRUD endpoints
      chat.py                   ← query + streaming endpoint
  supabase/
    schema.sql                  ← updated in Phase 5 (RLS policies)
  requirements.txt              ← add fastapi, uvicorn, python-jose
  .env.example

web/                            ← Next.js project root (Phase 7)
  app/
    layout.tsx                  ← root layout: fonts, theme, metadata
    page.tsx                    ← redirects to /chat or /auth
    auth/
      page.tsx                  ← login / signup
    chat/
      layout.tsx                ← auth guard: redirect to /auth if no session
      page.tsx                  ← chat interface
    globals.css
  components/
    auth/
      AuthForm.tsx
    chat/
      ChatLayout.tsx
      MessageList.tsx
      MessageBubble.tsx
      DateDivider.tsx
      ChatInput.tsx
      EmptyState.tsx
    ui/
      Logo.tsx
      TopBar.tsx
  lib/
    supabase/
      client.ts                 ← browser Supabase client
      server.ts                 ← server Supabase client (for route handlers)
    api.ts                      ← typed wrapper for all FastAPI calls
  types/
    index.ts
  middleware.ts                 ← Supabase session refresh middleware
  tailwind.config.ts
  next.config.ts
  .env.local.example
  package.json
```

---

## 4. FastAPI — API contract

All endpoints require `Authorization: Bearer <supabase-jwt>`. The
`get_current_user` dependency (see §5) validates the token and returns the
`user_id`. All data operations are scoped to that `user_id`.

### `POST /memories`
Store a new memory.
```
Request body:  { "content": string }
Response 201:  { "id": string, "created_at": string }
```
Calls `embeddings.embed(content)` → `store.add_memory(client, content, embedding, user_id)`.

### `GET /memories`
List all memories for the authenticated user.
```
Response 200:  [{ "id": string, "content": string, "created_at": string }]
```

### `DELETE /memories/{id}`
Delete a memory.
```
Response 200:  { "deleted": true }
Response 404:  { "detail": "not found" }
```

### `POST /chat`
Route a message (store or query). Returns a streamed response in Phase 8;
returns a plain JSON response until then.

```
Request body:  { "message": string }

Non-streaming response 200:
{
  "intent":  "store" | "query",
  "reply":   string,
  "id":      string | null    ← memory id if intent was store, else null
}

Streaming response (Phase 8):
Content-Type: text/event-stream
Each event: data: <text chunk>\n\n
Final event: data: [DONE]\n\n
```

For `store` intent: `router.route(message)` → embed → save → return confirmation.  
For `query` intent: `router.route(message)` → embed → search → synthesise →
return answer (streaming or not).

### Error responses
All errors follow `{ "detail": string }`. HTTP codes: 401 (no/bad token),
404 (not found), 422 (validation), 500 (upstream failure).

---

## 5. Authentication flow

### Supabase JWT validation in FastAPI

```python
# api/dependencies.py
from supabase import create_client
from fastapi import HTTPException, Header

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.removeprefix("Bearer ")
    res = supabase.auth.get_user(token)
    if not res.user:
        raise HTTPException(401, "Invalid token")
    return res.user.id   # user_id passed to store functions
```

### Web app auth flow (Next.js + Supabase JS)

1. User submits email + password in `AuthForm`.
2. `supabase.auth.signInWithPassword(...)` or `signUp(...)` called from the browser.
3. On success, Supabase sets a cookie via `@supabase/ssr`.
4. `middleware.ts` refreshes the session on every request and redirects
   `/` → `/auth` if no valid session, `/` → `/chat` if one exists.
5. In `chat/layout.tsx`, a server-side session check ensures no flash of the
   chat UI for unauthenticated users.
6. For every FastAPI call, `lib/api.ts` reads the current access token via
   `supabase.auth.getSession()` and includes it as `Authorization: Bearer <token>`.

---

## 6. Streaming design (Phase 8)

### FastAPI side
Use `StreamingResponse` with `text/event-stream`:
```python
from fastapi.responses import StreamingResponse

async def stream_answer(question, memories):
    async def generator():
        async for chunk in llm.stream_answer(question, memories):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream")
```

Add `stream_answer` to `llm.py` using the Gemini SDK's streaming chat method.

### Next.js side
Read the SSE stream with the Fetch API and update React state as chunks arrive:
```typescript
const res = await fetch(`${API_URL}/chat`, { method: 'POST', ... });
const reader = res.body!.getReader();
const decoder = new TextDecoder();
let buffer = '';
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n\n');
  buffer = lines.pop()!;
  for (const line of lines) {
    if (line.startsWith('data: ') && !line.includes('[DONE]')) {
      const chunk = line.slice(6);
      setMessages(prev => appendToLastMessage(prev, chunk));
    }
  }
}
```

The `appendToLastMessage` helper finds the last message in state with
`role: 'assistant'` and concatenates the chunk to its `content`.

---

## 7. Frontend — component architecture

### State model

The chat page holds all state locally with `useState`. No global state manager
needed at this scale.

```typescript
type Role = 'user' | 'assistant';

interface Message {
  id: string;
  role: Role;
  content: string;
  date: Date;
}

// Chat page state
const [messages, setMessages] = useState<Message[]>([]);
const [input, setInput] = useState('');
const [loading, setLoading] = useState(false);
```

On mount, load recent memories via `GET /memories` and pre-populate the message
list as a prior conversation (optional — can start empty if preferred for
simplicity in Phase 7).

### Component responsibilities

**`app/chat/page.tsx`**  
Owns all state. Handles send: calls `POST /chat`, updates messages. On
streaming (Phase 8), adds an empty assistant message and streams chunks into it.
Auto-scrolls to the bottom after each message update.

**`ChatLayout.tsx`**  
Pure layout: top bar, scrollable messages area, input area. Receives children
or slots. Handles the viewport/keyboard edge case on mobile using a `dvh`-based
layout:
```css
.chat-root {
  height: 100dvh;   /* dynamic viewport height — accounts for mobile keyboard */
  display: flex;
  flex-direction: column;
}
```

**`MessageList.tsx`**  
Renders `Message[]`. Groups by date and inserts `<DateDivider>` between groups.
Holds a `ref` that `page.tsx` uses to scroll to the bottom.

**`MessageBubble.tsx`**  
Renders one message. Accepts `role` and `content`. No internal state.

**`ChatInput.tsx`**  
Controlled textarea. Calls `onSend(content)` on Enter (unless Shift held).
Auto-expands height using a hidden mirror div or `scrollHeight` technique.
Disables when `loading` is true.

**`AuthForm.tsx`**  
Handles both sign-in and sign-up via a `mode` toggle. Uses Supabase JS client
directly. On success, `router.push('/chat')`. On error, sets field-level error
strings. No external form library needed.

**`middleware.ts`**
```typescript
import { createServerClient } from '@supabase/ssr';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function middleware(request: NextRequest) {
  // refresh session, protect /chat, redirect /auth if already authed
}
export const config = { matcher: ['/chat/:path*', '/auth'] };
```

---

## 8. Design system implementation

### 8.1 Font loading (`app/layout.tsx`)

```typescript
import { Lora, Plus_Jakarta_Sans } from 'next/font/google';

const lora = Lora({
  subsets: ['latin'],
  weight: ['400', '600'],
  variable: '--font-lora',
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-jakarta',
});
```

Apply `${lora.variable} ${jakarta.variable}` to the `<html>` element.

In CSS:
```css
body        { font-family: var(--font-jakarta), sans-serif; }
.brand      { font-family: var(--font-lora), serif; }
textarea    { font-family: var(--font-lora), serif; }
```

### 8.2 Tailwind configuration

Extend Tailwind to use the CSS variables:
```typescript
// tailwind.config.ts
theme: {
  extend: {
    colors: {
      bg:          'var(--bg)',
      'bg-subtle': 'var(--bg-subtle)',
      text:        'var(--text)',
      muted:       'var(--text-muted)',
      faint:       'var(--text-faint)',
      accent:      'var(--accent)',
      border:      'var(--border)',
    },
    borderRadius: {
      bubble: 'var(--radius-bubble)',
      input:  'var(--radius-input)',
    },
  },
}
```

### 8.3 CSS variables (`app/globals.css`)

Copy the full `:root` and `[data-theme="dark"]` blocks verbatim from
`PRD-v2.md §6.2`. Add:

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 15px; }
body {
  background-color: var(--bg);
  color: var(--text);
  font-family: var(--font-jakarta), sans-serif;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
```

Theme detection:
```css
@media (prefers-color-scheme: dark) {
  :root { /* copy dark vars here so no JS is needed for initial render */ }
}
```

### 8.4 Message bubble CSS

```css
.bubble-user {
  background: var(--user-bubble-bg);
  color: var(--user-bubble-text);
  border-radius: var(--radius-bubble) var(--radius-bubble) 4px var(--radius-bubble);
  padding: 10px 14px;
  max-width: min(72%, 480px);
  align-self: flex-end;
  font-size: 0.933rem;   /* 14px */
}

.bubble-assistant {
  color: var(--text);
  padding: 4px 8px;
  max-width: min(72%, 520px);
  align-self: flex-start;
  font-size: 0.933rem;
}

/* Message entrance animation */
.message-enter {
  animation: message-in 200ms ease-out;
}
@keyframes message-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

### 8.5 Input area CSS

```css
.input-area {
  background: var(--bg-subtle);
  border-top: 1px solid var(--border);
  padding: 12px 16px;
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.chat-textarea {
  flex: 1;
  background: var(--input-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-input);
  padding: 10px 14px;
  font-family: var(--font-lora), serif;
  font-size: 0.933rem;
  color: var(--text);
  resize: none;
  min-height: 42px;
  max-height: 130px;   /* ~5 lines */
  line-height: 1.5;
  transition: border-color 150ms;
}
.chat-textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(155, 107, 74, 0.12);
}
.chat-textarea::placeholder { color: var(--text-faint); }
```

---

## 9. Environment variables

### Python backend (`.env`)
```
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...        ← service key for JWT validation in FastAPI
GEMINI_API_KEY=...
CHAT_MODEL=...
EMBED_MODEL=...
ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

### Next.js (`.env.local`)
```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=https://your-api.railway.app   ← FastAPI base URL
```

`NEXT_PUBLIC_` variables are exposed to the browser. The anon key is safe to
expose here — RLS enforces security. The service key must never appear in the
Next.js project.

---

## 10. Phase-by-phase implementation plan

### Phase 5 — Auth (CLI + Supabase)
*As specified in original TDD. Complete this first.*

**Files:** `recall/auth.py`, `supabase/schema.sql` (RLS + policies), update
`recall/store.py` and `recall/cli.py`, switch to anon key for CLI.

**Work:** Supabase email/password login; persist session to `~/.recall/session.json`;
all store calls scoped to `current_user_id()`; enable RLS with owner policy.

**Definition of Done:**
- `python -m recall` prompts for login on first run, stores session.
- A second login as the same account (new terminal session) sees existing memories.
- A different account sees none.

---

### Phase 6 — FastAPI backend
**New packages:** `fastapi`, `uvicorn[standard]`, `python-jose[cryptography]`
(add to `requirements.txt`).

**Files:** `api/main.py`, `api/dependencies.py`, `api/routers/memories.py`,
`api/routers/chat.py`.

**Work:**

1. `api/main.py` — create FastAPI app, configure CORS (allow `ALLOWED_ORIGINS`
   from env), include the two routers.
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. `api/dependencies.py` — `get_current_user` dependency as specified in §5.
   Uses the Supabase service key to validate the JWT.

3. `api/routers/memories.py` — implement `POST /memories`, `GET /memories`,
   `DELETE /memories/{id}` as specified in §4. Import `store`, `embeddings`
   from the `recall` package directly.

4. `api/routers/chat.py` — implement `POST /chat` (non-streaming version only
   in this phase). Import `router`, `store`, `embeddings`, `llm` from `recall`.

5. Add a `Procfile` or `railway.toml` for deployment. Start command:
   `uvicorn api.main:app --host 0.0.0.0 --port $PORT`.

**Definition of Done:**
Using `curl` or an API client (Bruno / Insomnia / Postman):
- Obtain a Supabase JWT by signing in via Supabase dashboard or `curl`.
- `POST /memories` with a valid JWT saves a memory visible in Supabase.
- `GET /memories` returns it.
- `DELETE /memories/{id}` removes it.
- `POST /chat` with a question returns a correct answer.
- `POST /chat` without a JWT returns HTTP 401.
- Deploy to Railway: same tests pass against the live URL.

---

### Phase 7 — Next.js frontend

**Run separately:** `cd web && npx create-next-app@latest .` (TypeScript,
Tailwind, App Router, no src directory).

**New packages:**
```
npm install @supabase/ssr @supabase/supabase-js
```

**Work — in this order:**

1. **Design foundation.** Set up fonts (`app/layout.tsx`), CSS variables
   (`app/globals.css`), and Tailwind config as specified in §8. Verify the
   palette renders correctly in both light and dark system modes before building
   components.

2. **Supabase client setup.** Create `lib/supabase/client.ts` (browser client)
   and `lib/supabase/server.ts` (server client using `cookies()`). Create
   `middleware.ts` to refresh sessions and protect `/chat`.

3. **Auth page** (`app/auth/page.tsx` + `components/auth/AuthForm.tsx`).
   Implement sign-in / sign-up toggle. On success, `router.push('/chat')`.
   Match the layout and typography from PRD-v2 §7.1 exactly.

4. **API wrapper** (`lib/api.ts`). Typed functions for all FastAPI calls.
   Each function reads the current JWT from `supabase.auth.getSession()` and
   sets the `Authorization` header. Point at `NEXT_PUBLIC_API_URL`.

5. **Chat page and components** in this order:
   - `ChatLayout.tsx` (pure layout shell with `100dvh`)
   - `TopBar.tsx` (brand mark + sign out)
   - `EmptyState.tsx` (the "tell me something" centred text)
   - `MessageBubble.tsx` (user and assistant variants)
   - `DateDivider.tsx`
   - `MessageList.tsx` (combines the above)
   - `ChatInput.tsx` (auto-expanding textarea, Enter to send)
   - `app/chat/page.tsx` (wires everything together, owns state)

6. **Auth guard.** In `app/chat/layout.tsx`, check for a session server-side
   and redirect to `/auth` if absent.

7. **App entry.** `app/page.tsx` should do a server-side redirect: if a session
   exists, go to `/chat`; otherwise go to `/auth`.

**Definition of Done:**
- The design matches PRD-v2 §6–§7 (palette, typography, layout) on both a
  desktop browser and a real mobile device (not just responsive emulation).
- Sign up creates an account; sign in with those credentials works.
- Sending a statement from the web UI saves it; asking a question returns a
  correct answer.
- Memories stored from the CLI appear when asked about in the web UI (same
  account) and vice versa.
- The empty state appears on first load; it disappears after the first message.
- Deploy to Vercel: all tests pass on the live URL.

---

### Phase 8 — Streaming + hardening

**Work:**

1. Add `stream_answer` to `recall/llm.py` using the Gemini SDK's async
   streaming interface.

2. Update `api/routers/chat.py` to detect a `stream=true` query param and
   return a `StreamingResponse` as specified in §6.

3. Update `app/chat/page.tsx` to consume the SSE stream as specified in §6.
   The send handler: adds an empty assistant message to state immediately, then
   fills it character-by-character as chunks arrive.

4. Add retry logic (3 attempts, exponential backoff starting 500ms) in both
   `api/routers/chat.py` and `lib/api.ts` for transient network / rate-limit
   errors.

5. Implement inline error display in `MessageBubble` (the assistant bubble
   shows the error text in `--accent` colour as specified in PRD §7.6).

**Definition of Done:**
- Response text begins appearing within ~1 second of sending (before Gemini
  has finished generating).
- Disconnecting the network mid-stream: the partial message is preserved;
  an error note is appended after it.
- A simulated rate-limit response triggers automatic retry; the user sees
  nothing but a slightly slower response.

---

## 11. Open items to confirm during build

- Current Gemini streaming API method name and async iterator interface.
- Railway free-tier sleep behaviour (free services may sleep after inactivity —
  check current policy; Render's free tier sleeps, Railway's may not).
- `@supabase/ssr` version compatibility with current Next.js App Router cookie
  handling (this API evolves; check the current Supabase docs for App Router).
- Gemini embedding model name and confirming output dimension matches the
  `vector(768)` column.
