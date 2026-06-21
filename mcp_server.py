"""FastMCP server exposing core/tools.py as MCP tools for Claude Desktop.

Run with stdio transport (Claude Desktop launches it). See README for the
Claude Desktop config snippet.

    python mcp_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core import rag, tools

mcp = FastMCP("SecondBrain")


@mcp.tool()
def ask(question: str) -> dict:
    """Answer a question grounded in the notes, with citations (RAG)."""
    return rag.answer(question)


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
def create_note(title: str, body: str, tags: list[str] = []) -> str:
    """Create a new Markdown note with front-matter and re-index it."""
    return tools.create_note(title, body, tags)


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
