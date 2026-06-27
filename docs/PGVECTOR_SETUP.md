# Persistent vector search with Supabase pgvector (optional)

By default SecondBrain keeps embeddings in memory and rebuilds them from the
vault on every boot (`VECTOR_BACKEND=memory`). That's free and simple. If you
want **persistent** vector search that survives restarts and scales past RAM,
switch to Supabase's `pgvector` extension.

> Embedding model `all-MiniLM-L6-v2` produces **384-dim** vectors. If you change
> `EMBED_MODEL`, update the dimension in the SQL below to match.

## 1. One-time SQL (Supabase → SQL Editor)

```sql
-- enable the extension
create extension if not exists vector;

-- one row per note chunk
create table if not exists note_chunks (
  id          bigint generated always as identity primary key,
  chunk_id    text unique not null,         -- "<note path>::<chunk index>"
  content     text not null,
  source      text,
  heading     text,
  note_title  text,
  embedding   vector(384)
);

-- approximate-nearest-neighbour index (cosine)
create index if not exists note_chunks_embedding_idx
  on note_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- similarity search RPC used by core/pgvector.py
create or replace function match_note_chunks(
  query_embedding vector(384),
  match_count int default 5
)
returns table (
  content text, source text, heading text, note_title text, similarity float
)
language sql stable as $$
  select content, source, heading, note_title,
         1 - (embedding <=> query_embedding) as similarity
  from note_chunks
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

## 2. Turn it on

In `.env` (and in Streamlit secrets for the deploy):

```
VECTOR_BACKEND=pgvector
```

## 3. Populate it

```powershell
python scripts\sync_pgvector.py
```

This embeds every note chunk locally and upserts the vectors into `note_chunks`.
Re-run it whenever notes change (or rely on the app re-indexing on write).

## Notes / trade-offs
- pgvector mode is **dense-only**: the in-RAM BM25 hybrid is skipped, but
  cross-encoder **reranking (`RERANK=1`) still applies** on top of the pgvector
  candidates.
- The anon key can read/write `note_chunks` only if your RLS policies allow it —
  mirror the permissive policy you used for the `notes` table, or call the sync
  script with the service-role key.
