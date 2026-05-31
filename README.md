# Recall

A personal memory CLI. Tell it things in plain language; ask it later.

```
you › my friend told me there are sick jackets in Islamabad
bot › got it, I'll remember that.

you › where did I hear about jackets?
bot › Your friend mentioned there are some great jackets in Islamabad.
```

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Create your `.env` file**

```bash
cp .env.example .env
```

Open `.env` and fill in:

- `SUPABASE_URL` and `SUPABASE_KEY` — from your [Supabase project settings](https://supabase.com/dashboard).
- `GEMINI_API_KEY` — from [Google AI Studio](https://aistudio.google.com/app/apikey).
- `CHAT_MODEL` and `EMBED_MODEL` — confirm current model IDs from the [Gemini docs](https://ai.google.dev/gemini-api/docs/models/gemini) before filling these in.

**3. Set up the database**

Run `supabase/schema.sql` in the Supabase SQL editor of your project.

**4. Run**

```bash
python -m recall
```

## Privacy note

On the Gemini free tier, prompts may be used by Google for model training. Do not store sensitive personal data if this is a concern.

## Commands

| Command | Purpose |
|---|---|
| `/add <text>` | Force-store text as a memory |
| `/ask <text>` | Force-treat text as a question |
| `/search <text>` | Show raw matching memories (no AI answer) |
| `/list` | Show all stored memories with their ids |
| `/forget <id>` | Delete a memory by id |
| `/count` | How many memories are stored |
| `/help` | Show help |
| `/quit` | Exit |

Or just type naturally — the app detects whether you're storing or asking (Phase 4+).
