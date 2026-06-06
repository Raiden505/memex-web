-- Run this once in the Supabase SQL editor for your project.
-- Safe to re-run (all statements are idempotent).

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Table
create table if not exists memories (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null,
  content    text not null,
  embedding  vector(768),
  metadata   jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- 3. Similarity search index (cosine distance, HNSW)
create index if not exists memories_embedding_idx
  on memories using hnsw (embedding vector_cosine_ops);

-- 3b. Temporal recall index (Phase 10)
create index if not exists memories_user_created_idx
  on memories (user_id, created_at desc);

-- 3c. Due-date column + index (Phase 24)
--     Typed, indexable due date. Kept in sync with metadata->>'due' by the
--     application write paths (store.add_memory / store.update_metadata).
alter table memories
  add column if not exists due_at timestamptz;

create index if not exists memories_user_due_idx
  on memories (user_id, due_at);

-- One-time backfill of due_at from any existing metadata.due values.
update memories
  set due_at = (metadata->>'due')::timestamptz
  where (metadata ? 'due') and metadata->>'due' is not null and due_at is null;

-- 4. RPC for semantic search — called by store.search_memories()
--    Drop first: CREATE OR REPLACE can't change an existing function's return
--    type (the returned columns changed when metadata was added in Phase 19).
drop function if exists match_memories(vector, uuid, integer);
create or replace function match_memories(
  query_embedding vector(768),
  match_user_id   uuid,
  match_count     int
)
returns table (id uuid, content text, created_at timestamptz, similarity float, metadata jsonb)
language sql stable
as $$
  select m.id, m.content, m.created_at,
         1 - (m.embedding <=> query_embedding) as similarity,
         m.metadata
  from memories m
  where m.user_id = match_user_id
  order by m.embedding <=> query_embedding
  limit match_count;
$$;

-- 4b. Optional GIN index for metadata queries (phases 19–22)
create index if not exists memories_metadata_idx on memories using gin (metadata);

-- 5. RLS — Phase 5+ enables row-level security with an owner policy.
--    Supabase enables RLS by default on new tables, so we enable it explicitly.
alter table memories enable row level security;
drop policy if exists "owner can do everything" on memories;
create policy "owner can do everything"
  on memories for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

--    Phase 1-4 (no auth): use these instead:
--
--    alter table memories disable row level security;
