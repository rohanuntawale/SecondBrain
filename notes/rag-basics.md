---
title: RAG Basics
tags: [rag, ai, retrieval]
---

# RAG Basics

RAG stands for **Retrieval-Augmented Generation**. Instead of relying only on
what a language model memorized during training, RAG fetches relevant documents
at query time and feeds them to the model as context.

## Why use RAG

It grounds answers in your own data rather than the model's parametric memory.
This reduces hallucination and makes citations possible — you can show exactly
which source a fact came from.

## The pipeline

1. **Chunk** documents into passages.
2. **Embed** each chunk into a vector with an embedding model.
3. **Store** the vectors in a vector database.
4. **Retrieve** the top-k chunks most similar to the question.
5. **Generate** an answer from the retrieved context.

In SecondBrain the embedding model is `all-MiniLM-L6-v2` and the vector store is
ChromaDB. See [[MCP Basics]] for how the agent acts on retrieved knowledge.
