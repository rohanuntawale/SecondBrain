# Shared vault with Supabase (you + your partner see the same notes)

By default SecondBrain stores notes as Markdown files on one machine, so two
people can't see each other's notes. Switching the **storage backend** to
Supabase puts the notes (and diary entries) in a free cloud Postgres database
that you both read and write — one shared brain.

> **How it works:** Supabase is the *source of truth* for note text. The vector
> index (ChromaDB) stays local on each device and is rebuilt from the shared
> notes (the app does this automatically, and there's a **☁️ Sync from cloud**
> button). Embeddings are still computed locally, so retrieval behaves
> identically for both of you.

---

## 1. Create a free Supabase project

1. Go to <https://supabase.com> → sign in → **New project** (free tier, no card).
2. Pick a name and a database password. Wait ~2 min for it to provision.

## 2. Create the `notes` table

Open **SQL Editor** in the Supabase dashboard, paste this, and **Run**:

```sql
-- The shared note store. Path is the stable id (e.g. "diary/2026-06-22-x.md").
create table if not exists notes (
    path       text primary key,
    content    text not null,
    updated_at timestamptz not null default now()
);

-- Simple 2-person app using the anon key: allow read/write.
-- (For a public deployment, tighten this — see the security note below.)
alter table notes enable row level security;

create policy "anon can read notes"  on notes for select using (true);
create policy "anon can write notes" on notes for insert with check (true);
create policy "anon can update notes" on notes for update using (true) with check (true);
create policy "anon can delete notes" on notes for delete using (true);
```

## 3. Get your project URL and key

In **Project Settings → API**, copy:

- **Project URL** → `SUPABASE_URL`
- **anon public** API key → `SUPABASE_KEY`

## 4. Configure SecondBrain

In your `.env` (local) **or** Streamlit Cloud **Secrets** (deployed):

```
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=eyJ...   # the anon public key
```

Install the client (already added to requirements.txt):

```
pip install supabase
```

## 5. Seed the shared vault with your existing notes (one time)

This pushes every local `notes/*.md` file (including diary entries) into the
cloud table:

```
python scripts/sync_to_supabase.py
```

## 6. Run it

```
streamlit run app.py
```

The sidebar will show **Storage: `supabase` ☁️ (shared vault)** and sync the
index automatically. Now you and your partner — both pointing at the same
`SUPABASE_URL`/`SUPABASE_KEY` — see each other's notes and diary entries. When
one of you adds something, the other clicks **☁️ Sync from cloud** to pull it.

---

## Notes & limitations

- **Switching back** to single-machine mode: set `STORAGE_BACKEND=local`.
- **Security:** the policies above let anyone with the anon key read/write. That
  is fine for a private 2-person app where you don't share the key. For a public
  deployment, add Supabase **Auth** and per-user RLS policies (good "Future Work"
  for the report).
- **Real-time sync:** the app pulls on load and on the Sync button, not live.
  Live updates (Supabase Realtime subscriptions) are a possible enhancement.
- **Vector search** still runs locally via ChromaDB. A fully cloud-native option
  is Supabase's `pgvector` extension — another nice Future Work item.
