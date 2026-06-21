---
title: MCP Basics
tags: [mcp, ai, tools]
---

# MCP Basics

MCP stands for **Model Context Protocol**. It is an open standard that lets a
language model call external tools and data sources through a uniform interface,
instead of every app inventing its own plugin format.

## Tools

An MCP server exposes **tools** — named functions with typed inputs the model can
call. SecondBrain's MCP server exposes note actions like `search_notes`,
`create_note`, `suggest_tags`, and `add_link`.

## Where RAG and MCP meet

The `search_notes` tool runs the vector retrieval from [[RAG Basics]]. So
retrieval itself is exposed as a tool: the agent can both **read** the knowledge
base (RAG) and **write** to it (create notes, add links). That bidirectional
read/write loop is what makes SecondBrain an *active* second brain rather than a
read-only chatbot.
