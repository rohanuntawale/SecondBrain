"""FastMCP server exposing core/tools.py as MCP tools for Claude Desktop.

Run with stdio transport (Claude Desktop launches it). See README for the
Claude Desktop config snippet.

    python mcp_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core import beta, rag, tools

mcp = FastMCP("SecondBrain")


@mcp.tool()
def ask(question: str, mode: str = "notes") -> dict:
    """Answer a question. mode: 'notes' (grounded+cited), 'hybrid' (notes then
    general knowledge), or 'general' (no retrieval — everyday chat)."""
    return rag.answer(question, mode=mode)


@mcp.tool()
def search_notes(query: str, k: int = 4) -> list[dict]:
    """Semantic search over the notes vault — the RAG<->MCP bridge."""
    return tools.search_notes(query, k)


@mcp.tool()
def read_note(path: str) -> str:
    """Return the full text of a note (path relative to the vault)."""
    return tools.read_note(path)


@mcp.tool()
def list_notes() -> list[str]:
    """List all note paths in the vault."""
    return tools.list_notes()


@mcp.tool()
def create_note(
    title: str, body: str, tags: list[str] = [], author: str = "", auto: bool = False
) -> str:
    """Create a new Markdown note with front-matter and re-index it.
    author (optional) attributes it to a person for later filtering.
    auto=True lets the LLM fill tags and prepend a TL;DR."""
    return tools.create_note(title, body, tags, author=author, auto=auto)


@mcp.tool()
def append_to_note(path: str, text: str) -> str:
    """Append text to an existing note and re-index."""
    return tools.append_to_note(path, text)


@mcp.tool()
def suggest_tags(path: str) -> list[str]:
    """Suggest tags for a note, drawn from the existing tag vocabulary."""
    return tools.suggest_tags(path)


@mcp.tool()
def add_link(from_path: str, to_title: str) -> str:
    """Insert a [[wiki-link]] from one note to another title."""
    return tools.add_link(from_path, to_title)


@mcp.tool()
def find_orphans() -> list[str]:
    """List notes that no [[wiki-link]] points to."""
    return tools.find_orphans()


@mcp.tool()
def suggest_links(path: str, k: int = 3) -> list[dict]:
    """Suggest [[wiki-links]] to notes semantically related to the given note."""
    return tools.suggest_links(path, k)


@mcp.tool()
def auto_link(path: str, k: int = 3) -> str:
    """Insert [[wiki-links]] to the top related notes for a note and re-index."""
    return tools.auto_link(path, k)


@mcp.tool()
def daily_digest(on: str = "") -> dict:
    """Summarize notes created/edited on a day (ISO date, or today if empty)."""
    return tools.daily_digest(on or None)


@mcp.tool()
def summarize_note(path: str, sentences: int = 3) -> str:
    """Summarize a note in N sentences (TL;DR)."""
    return tools.summarize_note(path, sentences)


@mcp.tool()
def extract_action_items(path: str) -> list[str]:
    """Extract actionable to-dos from a note."""
    return tools.extract_action_items(path)


@mcp.tool()
def find_duplicate_notes(threshold: float = 0.8) -> list[dict]:
    """Find near-duplicate note pairs by embedding similarity."""
    return tools.find_duplicate_notes(threshold)


@mcp.tool()
def merge_notes(primary: str, secondary: str, delete_secondary: bool = False) -> str:
    """Merge a secondary note into a primary one; optionally delete the secondary."""
    return tools.merge_notes(primary, secondary, delete_secondary)


@mcp.tool()
def web_search(query: str, k: int = 5) -> list[dict]:
    """Free web search (DuckDuckGo, no API key) — returns {title, url, snippet}."""
    return tools.web_search(query, k)


@mcp.tool()
def add_diary_entry(
    body: str, author: str = "You", mood: str = "", title: str = "", on: str = ""
) -> str:
    """Add a dated diary entry (becomes a searchable note). on=ISO date or empty."""
    return tools.add_diary_entry(body, author=author, mood=mood, title=title, on=on or None)


@mcp.tool()
def list_diary_entries(author: str = "") -> list[dict]:
    """List diary entries newest-first, optionally filtered to one author."""
    return tools.list_diary_entries(author or None)


# --- Beta features (core/beta.py) — experimental but functional ---------------


@mcp.tool()
def add_time_capsule(sender: str, recipient: str, message: str, unlock_date: str) -> str:
    """Seal a message that only opens on/after unlock_date (ISO YYYY-MM-DD)."""
    return beta.add_time_capsule(sender, recipient, message, unlock_date)


@mcp.tool()
def list_time_capsules(recipient: str = "", include_sealed: bool = True) -> list[dict]:
    """List time capsules; unlocked ones reveal their message (sealed ones don't)."""
    return beta.list_time_capsules(recipient or None, include_sealed=include_sealed)


@mcp.tool()
def add_gratitude(author: str, text: str) -> str:
    """Add one appreciation to the shared gratitude jar."""
    return beta.add_gratitude(author, text)


@mcp.tool()
def list_gratitude(limit: int = 0) -> list[dict]:
    """List gratitude-jar entries newest-first (limit=0 for all)."""
    return beta.list_gratitude(limit or None)


@mcp.tool()
def mood_correlation() -> dict:
    """Cross-author mood stats: per-author/weekday averages + correlation."""
    return beta.mood_correlation()


@mcp.tool()
def partner_quiz(about_author: str, n: int = 5) -> list[dict]:
    """Generate a 'how well do you know me' quiz from a partner's diary."""
    return beta.partner_quiz(about_author, n)


@mcp.tool()
def year_in_review(year: int = 0) -> dict:
    """Compile a year of diary + photos into an AI 'year in review' recap."""
    return beta.year_in_review(year or None)


@mcp.tool()
def journal_prompt() -> str:
    """A reflective journaling prompt tailored to recent diary entries."""
    return beta.journal_prompt()


@mcp.tool()
def weekly_retrospective(days: int = 7) -> dict:
    """Reflect over notes & diary touched in the last N days."""
    return beta.weekly_retrospective(days)


@mcp.tool()
def resurface(seed_text: str = "", days: int = 14, k: int = 3) -> list[dict]:
    """Surface relevant notes you haven't touched in >= `days` days."""
    return beta.resurface(seed_text, days, k)


@mcp.tool()
def unified_search(query: str, k: int = 5) -> dict:
    """One query across both notes and the photo gallery."""
    return beta.unified_search(query, k)


if __name__ == "__main__":
    mcp.run(transport="stdio")
