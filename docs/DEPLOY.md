# Deploying SecondBrain (free)

Two ways to use the app. Both share the same `core/` logic.

## A. Streamlit Community Cloud (friend-facing web app)

1. Push this repo to **GitHub** (public).
2. Get a **free Groq API key** at https://console.groq.com (no card needed).
3. Go to https://share.streamlit.io, connect the repo, set main file = `app.py`.
4. In the app's **Settings → Secrets**, paste:
   ```toml
   LLM_PROVIDER = "groq"
   GROQ_API_KEY = "gsk_...."
   GROQ_MODEL   = "llama-3.1-8b-instant"
   ```
5. Deploy → you get a public `https://<app>.streamlit.app` URL to share.

> **Why Groq, not Ollama?** Streamlit's free tier can't run a local model. Groq's
> free tier serves Llama models over an API at no cost. The embedding model
> (`all-MiniLM-L6-v2`) still runs inside the app on CPU — that's fine.

> **Ephemeral filesystem caveat:** Streamlit Cloud resets the disk on restart, so
> uploaded notes and the `.chroma/` index do not persist. For the demo, commit
> sample notes into the repo (the Upload tab handles per-session additions).
> List "persistent storage (e.g. Supabase free tier)" as Future Work in the report.

## B. Claude Desktop (local MCP server)

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
