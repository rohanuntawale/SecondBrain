# Deploying SecondBrain (free)

Two ways to use the app. Both share the same `core/` logic.

## A. Streamlit Community Cloud (friend-facing web app)

1. Push this repo to **GitHub** (public or private — Cloud can read both once you
   authorize GitHub).
2. Get a **free Groq API key** at https://console.groq.com (no card needed).
3. Go to https://share.streamlit.io, sign in with GitHub, **Create app** →
   pick this repo, choose the **branch**, set **Main file path = `app.py`**.
4. Open **Advanced settings**:
   - **Python version: 3.11** (matches local).
   - **Secrets** — paste (copy the two key values from your local `.env`):
     ```toml
     LLM_PROVIDER    = "groq"
     GROQ_MODEL      = "llama-3.1-8b-instant"
     GROQ_API_KEY    = "gsk_...."                # from .env
     STORAGE_BACKEND = "supabase"                # shared vault
     SUPABASE_URL    = "https://<project>.supabase.co"
     SUPABASE_KEY    = "eyJ...."                 # anon key, from .env
     ```
5. Deploy → you get a public `https://<app>.streamlit.app` URL to share. First
   build takes a few minutes (installs torch/sentence-transformers; the embedding
   model downloads on first run).

> **Why Groq, not Ollama?** Streamlit's free tier can't run a local model. Groq's
> free tier serves Llama models over an API at no cost. The embedding model
> (`all-MiniLM-L6-v2`) still runs inside the app on CPU — that's fine.

> **Shared vault (Supabase):** with `STORAGE_BACKEND=supabase`, notes/diary/
> photos/love-notes live in Postgres, so both users see the same data. The
> `.chroma/` vector index is rebuilt locally on each boot from the shared vault
> (the sidebar auto-syncs). See `SUPABASE_SETUP.md`.

> **sqlite shim:** `app.py` swaps in `pysqlite3` at startup because Cloud's system
> sqlite is older than ChromaDB's 3.35 minimum (the wheel is Linux-only and listed
> in `requirements.txt`; it's a no-op locally).

> **Resource note:** the free tier has ~1 GB RAM. torch + sentence-transformers +
> ChromaDB is heavy; this small vault works, but first load is slow. If it OOMs,
> switch to a lighter embedding or ChromaDB's built-in embedder.

## B. Render (persistent web service)

Streamlit is a long-running WebSocket server, so it needs a real process — it
**cannot** run on Vercel/Netlify serverless functions. Render's free web service
runs it as a proper process.

1. Push this repo to **GitHub**.
2. Go to https://dashboard.render.com → **New +** → **Blueprint** → pick this
   repo. Render reads the committed **`render.yaml`** automatically (build =
   `pip install -r requirements.txt`, start = `streamlit run app.py
   --server.port $PORT --server.address 0.0.0.0 --server.headless true`).
3. In the **Environment** tab, fill the secret values (copied from your `.env`):
   `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`. The non-secret ones
   (`LLM_PROVIDER`, `GROQ_MODEL`, `STORAGE_BACKEND`) are already in `render.yaml`.
4. Deploy → you get a public `https://<app>.onrender.com` URL. First build takes
   a few minutes (installs torch/sentence-transformers).

> **Config source:** on Render there's no `st.secrets`, so `app.py` falls back to
> reading `os.environ` — Render injects the env vars above directly, so it just
> works. No code change needed.

> **Free-tier caveats:** 512 MB RAM (torch + sentence-transformers is heavy — a
> small vault is fine, but if it OOMs, bump the plan or use a lighter embedding),
> and the service **spins down after ~15 min idle**, so the first request after a
> lull is slow to wake.

## C. Claude Desktop (local MCP server)

Add to Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "secondbrain": {
      "command": "C:\\Users\\Admin\\SecondBrain-Project\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\Admin\\SecondBrain-Project\\mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. The SecondBrain tools (`ask`, `search_notes`,
`create_note`, `suggest_tags`, `add_link`, `find_orphans`, ...) will appear.

> Use the venv's Python so the MCP server has all dependencies. Make sure
> `python scripts\reindex.py` has been run at least once so the index exists.
