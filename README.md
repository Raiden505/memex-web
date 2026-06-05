# Recall — Personal memory assistant

Recall is a personal "second brain": a CLI-first app (with an optional web frontend and API) that saves short personal memories and answers questions using semantic search + LLM synthesis.

- Store facts, notes, links or short logs in natural language.
- Ask follow-up questions later; Recall retrieves relevant memories with vector search and composes answers with a chat model.

Contents
- Overview
- Features
- Quickstart (CLI, API, Web)
- Environment & secrets
- Database
- Commands & examples
- Development & testing
- Contributing

Overview

The project contains three main parts:
- recall/ (Python) — core library and CLI that embeds text, stores it in Supabase, and runs the router/LLM logic.
- api/ (FastAPI) — thin HTTP layer used by the Next.js web client (validates JWTs, scopes requests to a user).
- web/ (Next.js) — optional web frontend (App Router, TypeScript) that talks to the API.

Features
- Natural-language CLI for storing and querying memories
- Semantic search powered by embeddings (Gemini embeddings by default)
- LLM-based answer synthesis (Gemini/your configured CHAT_MODEL)
- Optional web UI and FastAPI backend for remote access
- Per-user scoping via Supabase auth and RLS (when configured)

Quickstart

Prerequisites
- Python 3.10+ (recommended)
- Node.js (18+) and npm/yarn (for the web client)
- A Supabase project (for Postgres + vector store)
- A Gemini API key (for embeddings & chat)

1) Clone

```bash
git clone https://github.com/Raiden505/memex-web.git
cd memex-web
```

2) Python dependencies

```bash
pip install -r requirements.txt
```

3) Environment

```bash
cp .env.example .env
# then edit .env and fill the variables described below
```

4) Database

Open the Supabase SQL editor for your project and run `supabase/schema.sql` to create tables and indexes.

5a) Run the CLI (local)

```bash
python -m recall
```

5b) Run the API (optional)

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

5c) Run the web frontend (optional)

```bash
cd web
npm install
npm run dev
# open http://localhost:3000
```

Environment & secrets

Fill these values in `.env` (backend) and `web/.env.local` (frontend) as appropriate:
- SUPABASE_URL — your Supabase project URL
- SUPABASE_ANON_KEY / SUPABASE_KEY — anon key for browser clients (use anon + RLS in production)
- SUPABASE_SERVICE_KEY — **service key** (server-only; used by FastAPI to validate JWTs)
- GEMINI_API_KEY — Google Gemini / AI Studio API key
- CHAT_MODEL — model id used for chat/synthesis
- EMBED_MODEL — embedding model id (embedding dim locked to 768)
- ALLOWED_ORIGINS — comma-separated origins for CORS in the API
- NEXT_PUBLIC_API_URL — frontend → API URL
- NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_SUPABASE_URL — for the web client

Important: the embedding output dimensionality is fixed at 768. Do not change EMBED_MODEL without re-embedding all rows.

Database

Run `supabase/schema.sql` in the Supabase SQL editor to create the `memories` table, vector index, and RPC functions used by the store/search logic.

Commands & examples (CLI)

- `/add <text>` — force-store text as a memory
- `/ask <text>` — treat text as a question and return an answer
- `/search <text>` — show raw matching memories
- `/list` — list stored memories and ids
- `/forget <id>` — delete a memory by id

Example session

```
you › my friend told me there are great jackets in Islamabad
bot › got it. saved.

you › where did I hear about jackets?
bot › Your friend mentioned there are some great jackets in Islamabad.
```

Privacy note

On the Gemini free tier, prompts and usage may be used by Google. Avoid storing sensitive personal data if this is a concern.

Development & testing

- Run unit tests: `pytest`
- FastAPI dev server: `uvicorn api.main:app --reload`
- Frontend: `cd web && npm run dev`

Contributing

See `AGENTS.md` and `CLAUDE.md` for the development workflow and repo conventions. When adding features, follow the phase progression in `MEMORY.md` and update documentation there.

License

No license file included — add a LICENSE to make the repository reusable. If a license exists in the repo, that takes precedence.

Support / Issues

Open issues on the repository (https://github.com/Raiden505/memex-web) or contact the maintainer.

--
Generated README: concise overview, setup, and run instructions for the CLI, API, and web frontend.