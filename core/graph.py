"""Knowledge graph over the notes vault, built from [[wiki-links]].

Nodes are notes (by title); a directed edge A -> B means note A contains a
`[[B]]` link. This turns the vault into a navigable graph — the classic "second
brain" view — and powers orphan/hub analysis and an interactive visualization.

Pure-Python (networkx + pyvis), so it stays light enough for the cloud deploy.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import ingest, repo

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _title_index() -> tuple[dict, dict]:
    """Return (path->title, title_lower->title) over real content notes."""
    path_title: dict[str, str] = {}
    by_lower: dict[str, str] = {}
    for rec in repo.get_repo().content_notes():
        title = ingest._front_matter_title(rec.content, fallback=Path(rec.path).stem)
        path_title[rec.path] = title
        by_lower[title.lower()] = title
    return path_title, by_lower


def build_graph():
    """Build and return a networkx.DiGraph of notes linked by [[wiki-links]].

    Each node carries `path` and `tags`; only links whose target title matches a
    real note become edges (dangling links are ignored).
    """
    import networkx as nx

    path_title, by_lower = _title_index()
    g = nx.DiGraph()
    for rec in repo.get_repo().content_notes():
        title = path_title[rec.path]
        g.add_node(title, path=rec.path)
        for raw in _LINK_RE.findall(rec.content):
            tgt = by_lower.get(raw.strip().lower())
            if tgt and tgt != title:
                g.add_edge(title, tgt)
    return g


def graph_stats() -> dict:
    """Summary stats: counts, orphans (no links in/out), and top hubs."""
    g = build_graph()
    deg = {n: g.in_degree(n) + g.out_degree(n) for n in g.nodes}
    orphans = sorted(n for n, d in deg.items() if d == 0)
    hubs = sorted(deg.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "orphans": orphans,
        "hubs": [{"title": n, "degree": d} for n, d in hubs[:5] if d > 0],
    }


def to_pyvis_html(height: str = "600px") -> str:
    """Render the knowledge graph to a standalone interactive HTML string.

    Embed in Streamlit via `st.components.v1.html(html, height=...)`. Node size
    scales with degree so hubs stand out; isolated notes appear in a muted color.
    """
    from pyvis.network import Network

    g = build_graph()
    net = Network(height=height, width="100%", bgcolor="#ffffff", directed=True)
    net.barnes_hut(gravity=-8000, spring_length=120)

    for node in g.nodes:
        deg = g.in_degree(node) + g.out_degree(node)
        net.add_node(
            node,
            label=node,
            size=12 + 4 * deg,
            color="#caa84a" if deg else "#d9d9d9",  # gold hubs, grey orphans
            title=f"{node} — {deg} link(s)",
        )
    for a, b in g.edges:
        net.add_edge(a, b, color="#e3c869")

    # generate_html avoids writing a temp file (works on read-only cloud disks).
    try:
        return net.generate_html(notebook=False)
    except TypeError:  # older pyvis signature
        return net.generate_html()


if __name__ == "__main__":
    print(graph_stats())
