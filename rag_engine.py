"""
rag_engine.py
=============
Agentic RAG engine for PharmaAI.

Architecture
------------
Vector store  : ChromaDB (local persistent, no server needed)
Embeddings    : nomic-embed-text via Ollama (falls back to TF-IDF keyword search
                if Ollama is offline or the embed model is not pulled)
Knowledge base: knowledge_base/drugs.json  (seeded on first run, auto-updated)
Agent loop    : Lightweight ReAct-style: query -> retrieve -> augment -> generate

Public API
----------
retrieve(query, n_results=3)  -> list[dict]  # each dict has text + metadata + score
build_rag_prompt(query, chunks) -> str        # inserts retrieved chunks before LLM call
is_ready()                     -> bool        # True once collection is indexed
rebuild_index()                -> None        # re-index from drugs.json
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE = Path(__file__).parent
_KB_PATH   = _BASE / "knowledge_base" / "drugs.json"
_CHROMA_DIR = _BASE / "knowledge_base" / "chroma_db"

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------
_chroma_client     = None
_collection        = None
_tfidf_corpus: Optional[list[dict]] = None   # fallback

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_kb() -> list[dict]:
    """Load raw documents from knowledge_base/drugs.json."""
    if not _KB_PATH.exists():
        return []
    with open(_KB_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def _get_ollama_embedding(text: str, host: str = "http://localhost:11434") -> Optional[list[float]]:
    """Return embedding vector from nomic-embed-text via Ollama, or None on failure."""
    try:
        import ollama as _ol
        client = _ol.Client(host=host)
        resp = client.embeddings(model="nomic-embed-text", prompt=text)
        return resp.get("embedding") or resp.get("embeddings")
    except Exception:
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb + 1e-9)


# ---------------------------------------------------------------------------
# TF-IDF fallback (no external dependencies)
# ---------------------------------------------------------------------------

def _build_tfidf(docs: list[dict]) -> list[dict]:
    """Build a simple TF-IDF index over the text field of each document."""
    from collections import Counter
    corpus = []
    N = len(docs)
    all_terms: list[Counter] = []
    for doc in docs:
        tokens = re.findall(r"[a-z]+", doc["text"].lower())
        all_terms.append(Counter(tokens))

    # document frequency
    df: dict[str, int] = {}
    for cnt in all_terms:
        for t in cnt:
            df[t] = df.get(t, 0) + 1

    for i, doc in enumerate(docs):
        tf = all_terms[i]
        total = sum(tf.values()) or 1
        tfidf = {t: (c / total) * math.log((N + 1) / (df[t] + 1) + 1)
                 for t, c in tf.items()}
        corpus.append({**doc, "_tfidf": tfidf})
    return corpus


def _tfidf_search(query: str, corpus: list[dict], n: int = 3) -> list[dict]:
    tokens = re.findall(r"[a-z]+", query.lower())
    scores = []
    for doc in corpus:
        score = sum(doc["_tfidf"].get(t, 0.0) for t in tokens)
        scores.append((score, doc))
    scores.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, doc in scores[:n]:
        if score > 0:
            results.append({
                "text":     doc["text"],
                "drug":     doc.get("drug", ""),
                "category": doc.get("category", ""),
                "id":       doc.get("id", ""),
                "score":    round(score, 4),
                "source":   "tfidf",
            })
    return results


# ---------------------------------------------------------------------------
# ChromaDB index
# ---------------------------------------------------------------------------

def _get_collection(host: str = "http://localhost:11434"):
    """Return (or create) the ChromaDB collection, indexing if empty."""
    global _chroma_client, _collection

    if _collection is not None:
        return _collection

    import chromadb
    _chroma_client = chromadb.PersistentClient(path=str(_CHROMA_DIR))

    # Use a simple space (no embedding fn here; we embed manually via Ollama
    # and store as float arrays, or fall back to ChromaDB default).
    # We use the built-in default embedding fn (ONNX all-MiniLM) if Ollama
    # embed is unavailable, for maximum resilience.
    try:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        _ef = ONNXMiniLM_L6_V2()
    except Exception:
        _ef = None

    try:
        if _ef:
            _collection = _chroma_client.get_or_create_collection(
                name="pharma_kb",
                embedding_function=_ef,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            _collection = _chroma_client.get_or_create_collection(
                name="pharma_kb",
                metadata={"hnsw:space": "cosine"},
            )
    except Exception:
        _collection = _chroma_client.get_or_create_collection(name="pharma_kb")

    # Seed if empty
    if _collection.count() == 0:
        _index_documents(host=host)

    return _collection


def _index_documents(host: str = "http://localhost:11434") -> None:
    """Load drugs.json and upsert all documents into ChromaDB."""
    global _collection
    docs = _load_kb()
    if not docs or _collection is None:
        return

    ids        = [d["id"] for d in docs]
    texts      = [d["text"] for d in docs]
    metadatas  = [{"drug": d.get("drug",""), "category": d.get("category","")} for d in docs]

    # Try Ollama embeddings first, then let ChromaDB use its built-in model
    ollama_embeddings = []
    for t in texts:
        emb = _get_ollama_embedding(t, host=host)
        if emb is None:
            break
        ollama_embeddings.append(emb)

    if len(ollama_embeddings) == len(texts):
        _collection.upsert(ids=ids, documents=texts, metadatas=metadatas,
                           embeddings=ollama_embeddings)
    else:
        # Fall back to ChromaDB built-in embedding model
        _collection.upsert(ids=ids, documents=texts, metadatas=metadatas)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_ready() -> bool:
    """Return True if the knowledge base is indexed and ready."""
    try:
        col = _get_collection()
        return col.count() > 0
    except Exception:
        return False


def rebuild_index(host: str = "http://localhost:11434") -> None:
    """Drop and re-create the ChromaDB collection from drugs.json."""
    global _chroma_client, _collection, _tfidf_corpus
    try:
        if _chroma_client is None:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
        _chroma_client.delete_collection("pharma_kb")
    except Exception:
        pass
    _collection = None
    _tfidf_corpus = None
    _get_collection(host=host)


def retrieve(query: str, n_results: int = 3,
             host: str = "http://localhost:11434") -> list[dict]:
    """
    Retrieve the top-n most relevant drug knowledge chunks for a query.

    Tries ChromaDB vector search first; falls back to TF-IDF keyword search
    if ChromaDB or embedding model is unavailable.

    Returns list of dicts: {text, drug, category, id, score, source}
    """
    global _tfidf_corpus

    # ---- ChromaDB path -----------------------------------------------
    try:
        col = _get_collection(host=host)
        results = col.query(query_texts=[query], n_results=min(n_results, col.count()))
        chunks = []
        ids_list  = results.get("ids", [[]])[0]
        docs_list = results.get("documents", [[]])[0]
        metas     = results.get("metadatas", [[]])[0]
        dists     = results.get("distances", [[]])[0]
        for i, (doc_id, text, meta, dist) in enumerate(
                zip(ids_list, docs_list, metas, dists)):
            score = round(1.0 - dist, 4) if dist is not None else 0.0
            chunks.append({
                "text":     text,
                "drug":     meta.get("drug", ""),
                "category": meta.get("category", ""),
                "id":       doc_id,
                "score":    score,
                "source":   "chromadb",
            })
        if chunks:
            return chunks
    except Exception:
        pass

    # ---- TF-IDF fallback ---------------------------------------------
    if _tfidf_corpus is None:
        _tfidf_corpus = _build_tfidf(_load_kb())
    return _tfidf_search(query, _tfidf_corpus, n=n_results)


def build_rag_prompt(query: str, chunks: list[dict]) -> str:
    """
    Build the augmented query string that gets injected into the LLM prompt.

    Each retrieved chunk is presented as a numbered reference block so the
    model can cite it in its answer.
    """
    if not chunks:
        return query

    refs = []
    for i, c in enumerate(chunks, 1):
        drug_label = f"{c['drug']}  {c['category']}" if c.get("drug") else c.get("category", "")
        refs.append(f"[REF {i}] ({drug_label}): {c['text']}")

    context_block = "\n\n".join(refs)
    augmented = (
        f"Use the following clinical reference excerpts to answer the question.\n"
        f"Cite sources as [REF 1], [REF 2] etc. where relevant.\n\n"
        f"{context_block}\n\n"
        f"QUESTION: {query}"
    )
    return augmented


def format_citations(chunks: list[dict]) -> str:
    """
    Return a markdown string of citation cards for display in the Streamlit UI.
    """
    if not chunks:
        return ""
    lines = ["**Sources retrieved from knowledge base:**"]
    for i, c in enumerate(chunks, 1):
        drug  = c.get("drug", "General")
        cat   = c.get("category", "")
        score = c.get("score", 0.0)
        src   = c.get("source", "")
        bar   = "" * int(score * 10) + "" * (10 - int(score * 10))
        lines.append(
            f"**[REF {i}]** `{drug}`  {cat}  "
            f"| relevance {bar} {score:.2f}  _{src}_"
        )
    return "\n\n".join(lines)
