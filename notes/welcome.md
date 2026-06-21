---
title: Welcome to SecondBrain
tags: [meta, getting-started]
---

# Welcome to SecondBrain

SecondBrain is a personal knowledge assistant. It reads your Markdown notes and
answers questions grounded in *your* content, with citations. It can also act on
your notes: create new ones, suggest tags, and add `[[wiki-links]]`.

## How it works

Your notes live in the `notes/` folder as plain `.md` files — that folder is the
single source of truth. SecondBrain embeds each note into a vector database
(ChromaDB) and retrieves the most relevant chunks to answer your questions.

## Two ways to use it

You can talk to SecondBrain through a web app (Streamlit) or from inside
Claude Desktop via an MCP server. Both share the same core logic, so they behave
identically. See [[RAG Basics]] and [[MCP Basics]] for the concepts.
