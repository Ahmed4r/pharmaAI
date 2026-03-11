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
_CHROMA_DIR    = _BASE / "knowledge_base" / "chroma_db"
_BRAND_MAP_PATH = _BASE / "knowledge_base" / "brand_map.json"

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------
_chroma_client     = None
_collection        = None
_tfidf_corpus: Optional[list[dict]] = None   # fallback
_brand_map_cache: Optional[dict] = None        # brand->generic, loaded lazily

# ---------------------------------------------------------------------------
# Brand-to-Generic mapping (Task 1)
# Covers common Egyptian/MENA local brands + universal trade names
# ---------------------------------------------------------------------------
BRAND_MAP: dict[str, str] = {
    # PPI / Gastro
    "mesopral": "esomeprazole",  "nexium": "esomeprazole",
    "omez": "omeprazole",        "losec": "omeprazole",      "prilosec": "omeprazole",
    "controloc": "pantoprazole", "pantoloc": "pantoprazole", "protonix": "pantoprazole",
    "pariet": "rabeprazole",     "aciphex": "rabeprazole",
    "prevacid": "lansoprazole",
    # Antibiotics
    "novaclar": "clarithromycin","klacid": "clarithromycin", "biaxin": "clarithromycin",
    "flagyl": "metronidazole",   "rozex": "metronidazole",
    "augmentin": "amoxicillin",  "amoxil": "amoxicillin",
    "cipro": "ciprofloxacin",    "ciproxin": "ciprofloxacin",
    # Cardiovascular
    "concor": "bisoprolol",      "emconcor": "bisoprolol",
    "coumadin": "warfarin",      "jantoven": "warfarin",
    "plavix": "clopidogrel",
    "norvasc": "amlodipine",     "amlopres": "amlodipine",
    "zestril": "lisinopril",     "prinivil": "lisinopril",
    "lasix": "furosemide",
    "cordarone": "amiodarone",   "pacerone": "amiodarone",
    "lanoxin": "digoxin",
    "crestor": "rosuvastatin",   "lipitor": "atorvastatin",  "zocor": "simvastatin",
    # Analgesics / NSAIDs
    "aspocid": "aspirin",        "ecotrin": "aspirin",       "disprin": "aspirin",
    "advil": "ibuprofen",        "motrin": "ibuprofen",      "brufen": "ibuprofen",
    "aleve": "naproxen",         "naprosyn": "naproxen",
    "dolowin": "aceclofenac",
    "tylenol": "paracetamol",    "panadol": "paracetamol",   "calpol": "paracetamol",
    # Diabetes
    "glucophage": "metformin",   "fortamet": "metformin",
    "diamicron": "gliclazide",
    # CNS
    "zoloft": "sertraline",      "lustral": "sertraline",
    # Misc
    "ventolin": "salbutamol",    "proventil": "salbutamol",
    "synthroid": "levothyroxine","euthyrox": "levothyroxine",
}


def normalize_query(query: str) -> str:
    """
    Replace brand names in *query* with their generic equivalents.
    Case-insensitive whole-word match so "Mesopral 40mg" -> "esomeprazole 40mg".
    Also tries drug_normalizer.normalize() for extended coverage.
    """
    result = query
    for brand, generic in BRAND_MAP.items():
        result = re.sub(
            r"\b" + re.escape(brand) + r"\b",
            generic, result, flags=re.IGNORECASE,
        )
    # Extended coverage via drug_normalizer (best-effort)
    try:
        from drug_normalizer import normalize as _dn_norm
        for word in query.split():
            nr = _dn_norm(word)
            if nr and nr.confidence >= 0.8 and nr.generic_name.lower() != word.lower():
                result = re.sub(
                    r"\b" + re.escape(word) + r"\b",
                    nr.generic_name, result, flags=re.IGNORECASE,
                )
    except Exception:
        pass
    return result



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


# ---------------------------------------------------------------------------
# Brand-name -> generic name mapping for query expansion
# ---------------------------------------------------------------------------
_BRAND_TO_GENERIC = {
    "plavix":     "clopidogrel",
    "crestor":    "rosuvastatin",
    "lipitor":    "atorvastatin",
    "norvasc":    "amlodipine",
    "zocor":      "simvastatin",
    "coumadin":   "warfarin",
    "jantoven":   "warfarin",
    "glucophage": "metformin",
    "prilosec":   "omeprazole",
    "losec":      "omeprazole",
    "nexium":     "esomeprazole",
    "advil":      "ibuprofen",
    "motrin":     "ibuprofen",
    "nurofen":    "ibuprofen",
    "brufen":     "ibuprofen",
    "tylenol":    "paracetamol acetaminophen",
    "panadol":    "paracetamol acetaminophen",
    "augmentin":  "amoxicillin clavulanate",
    "amoxil":     "amoxicillin",
    "lasix":      "furosemide",
    "zestril":    "lisinopril",
    "prinivil":   "lisinopril",
    "ecotrin":    "aspirin salicylate",
    "aspegic":    "aspirin salicylate",
    "flagyl":          "metronidazole",
    "rozex":           "metronidazole",
    "metro":           "metronidazole",
    # antihistamines
    "zyrtec":          "cetirizine cetirizine hydrochloride",
    "reactine":        "cetirizine cetirizine hydrochloride",
    "zirtek":          "cetirizine cetirizine hydrochloride",
    # antipsychotics
    "zyprexa":         "olanzapine",
    "zyprexa zydis":   "olanzapine",
    # benzodiazepines
    "valium":          "diazepam",
    "diastat":         "diazepam",
    # opioids
    "tylenol codeine": "acetaminophen codeine",
    "codalgin":        "acetaminophen codeine",
    # nsaids
    "naprosyn":        "naproxen",
    "aleve":           "naproxen",
    "anaprox":         "naproxen",
    "naprogesic":      "naproxen",
}


def _load_brand_map() -> dict:
    """Merge hardcoded _BRAND_TO_GENERIC with knowledge_base/brand_map.json."""
    merged = dict(_BRAND_TO_GENERIC)
    if _BRAND_MAP_PATH.exists():
        try:
            with open(_BRAND_MAP_PATH, encoding="utf-8") as _f:
                merged.update(json.load(_f))
        except Exception:
            pass
    return merged


def reload_brand_map() -> None:
    """Force-reload the brand map from disk (call after updating brand_map.json)."""
    global _brand_map_cache
    _brand_map_cache = None


def _expand_query(query: str) -> str:
    global _brand_map_cache
    if _brand_map_cache is None:
        _brand_map_cache = _load_brand_map()
    q_lower = query.lower()
    additions = []
    for brand, generic in _brand_map_cache.items():
        if brand in q_lower:
            additions.append(generic)
    if additions:
        return query + " " + " ".join(additions)
    return query


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


def retrieve(query: str, n_results: int = 5,
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
        expanded_query = _expand_query(query)
        results = col.query(query_texts=[expanded_query], n_results=min(n_results, col.count()))
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
    expanded_query = _expand_query(query)
    return _tfidf_search(expanded_query, _tfidf_corpus, n=n_results)


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
        f"{query}\n\n"
        f"---\n"
        f"Reference information:\n{context_block}"
    )
    return augmented

# ---------------------------------------------------------------------------
# Drug extraction + targeted interaction retrieval (anti-cross-contamination)
# ---------------------------------------------------------------------------

_KNOWN_DRUGS: set[str] = {
    "warfarin", "aspirin", "ibuprofen", "naproxen", "paracetamol", "acetaminophen",
    "metformin", "omeprazole", "esomeprazole", "pantoprazole", "lansoprazole",
    "clopidogrel", "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin",
    "metronidazole", "ciprofloxacin", "amoxicillin", "amoxicillin-clavulanate",
    "furosemide", "lisinopril", "enalapril", "ramipril", "amlodipine", "nifedipine",
    "digoxin", "amiodarone", "sertraline", "fluoxetine", "escitalopram", "citalopram",
    "tramadol", "codeine", "morphine", "oxycodone", "methotrexate", "prednisolone",
    "dexamethasone", "diazepam", "lorazepam", "olanzapine", "quetiapine", "cetirizine",
    "salbutamol", "atenolol", "bisoprolol", "carvedilol", "spironolactone",
    "hydrochlorothiazide", "insulin", "glibenclamide", "gliclazide", "sitagliptin",
    "heparin", "enoxaparin", "rivaroxaban", "apixaban", "dabigatran",
}


def extract_drug_names(query: str) -> list[str]:
    """
    Extract recognised drug names (generic + brand-mapped) from a free-text query.
    Returns a deduplicated list of lowercase generic names found in the query.
    """
    global _brand_map_cache
    if _brand_map_cache is None:
        _brand_map_cache = _load_brand_map()

    q_lower = query.lower()
    found: set[str] = set()

    # 1. Match against known generic names
    for drug in _KNOWN_DRUGS:
        if re.search(r"\b" + re.escape(drug) + r"\b", q_lower):
            found.add(drug)

    # 2. Expand brand names → generic
    for brand, generic in _brand_map_cache.items():
        if re.search(r"\b" + re.escape(brand) + r"\b", q_lower):
            for token in generic.split():
                if len(token) > 3:
                    found.add(token)

    return sorted(found)


def retrieve_interaction(
    drug_names: list[str],
    n_results: int = 5,
    host: str = "http://localhost:11434",
) -> list[dict]:
    """
    Targeted, cross-contamination-resistant retrieval for drug interaction queries.

    Algorithm
    ---------
    1. Build a specific composite query:  "<drug_a> <drug_b> interaction mechanism"
    2. Pull a wider candidate pool (n_results × 3) from ChromaDB.
    3. VERIFY each chunk: keep only those whose text or metadata mentions
       at least one of the queried drug names.
    4. Sort verified chunks by score (descending) and return top n_results.
    5. If no chunk survives verification, return [] so the caller can admit
       "insufficient context" rather than hallucinate a mixed answer.
    """
    if not drug_names:
        return []

    # Step 1 — targeted query
    interaction_query = (
        " ".join(drug_names)
        + " interaction mechanism clinical safety pharmacokinetics"
    )

    # Step 2 — wide candidate pool
    candidates = retrieve(interaction_query, n_results=n_results * 3, host=host)
    if not candidates:
        return []

    # Step 3 — drug-name verification
    patterns = [
        re.compile(r"\b" + re.escape(d) + r"\b", re.IGNORECASE)
        for d in drug_names
    ]

    verified: list[dict] = []
    for chunk in candidates:
        text      = chunk.get("text", "")
        meta_drug = chunk.get("drug", "")
        haystack  = text + " " + meta_drug
        if any(p.search(haystack) for p in patterns):
            verified.append(chunk)

    # Step 4 — rank and cap
    verified.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return verified[:n_results]

def format_citations(chunks: list[dict]) -> str:
    """
    Return styled HTML source cards for display in the Streamlit UI.
    """
    if not chunks:
        return ""

    cards = []
    for i, c in enumerate(chunks, 1):
        drug  = c.get("drug", "General")
        cat   = c.get("category", "").replace("_", " ").title()
        score = c.get("score", 0.0)
        pct   = int(score * 100)
        if pct >= 65:
            colour, bg, badge = "#1a7a4a", "#e8f5ee", "#1a7a4a"
        elif pct >= 45:
            colour, bg, badge = "#7a5a00", "#fff8e1", "#e6a800"
        else:
            colour, bg, badge = "#7a2020", "#fdecea", "#c0392b"
        cards.append(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'padding:7px 12px;margin:3px 0;border-radius:10px;'
            f'background:{bg};border-left:4px solid {badge};">'
            f'<span style="font-size:0.72rem;font-weight:700;color:#888;'
            f'min-width:40px;">REF {i}</span>'
            f'<span style="font-size:0.84rem;font-weight:600;color:{colour};">{drug}</span>'
            f'<span style="font-size:0.78rem;color:#666;font-style:italic;">{cat}</span>'
            f'<span style="margin-left:auto;font-size:0.78rem;font-weight:700;'
            f'color:{colour};">{pct}%</span></div>'
        )

    inner = "".join(cards)
    return (
        '<div style="margin-top:10px;padding:10px 14px;border-radius:12px;'
        'background:#f8f9fb;border:1px solid #e0e4ea;">'
        '<p style="font-size:0.74rem;font-weight:700;color:#999;'
        'letter-spacing:0.05em;margin:0 0 6px 0;">'
        '\U0001f4da SOURCES FROM KNOWLEDGE BASE</p>'
        f'{inner}</div>'
    )


# ===========================================================================
# PDF-BASED RAG  (ChromaDB + HuggingFace all-MiniLM-L6-v2)
# Populated by  ingest.py  --  separate from the drugs.json knowledge base.
# ===========================================================================

_PDF_CHROMA_DIR    = _BASE / "chroma_db"
_pdf_chroma_client = None
_pdf_collection_ref = None
_hf_embedder        = None


def _get_hf_embedder():
    global _hf_embedder
    if _hf_embedder is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _hf_embedder = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _hf_embedder


def _get_pdf_collection():
    global _pdf_chroma_client, _pdf_collection_ref
    if _pdf_collection_ref is not None:
        return _pdf_collection_ref
    if not _PDF_CHROMA_DIR.exists():
        return None
    try:
        import chromadb as _cdb
        _pdf_chroma_client = _cdb.PersistentClient(path=str(_PDF_CHROMA_DIR))
        _pdf_collection_ref = _pdf_chroma_client.get_collection("pdf_kb")
        return _pdf_collection_ref
    except Exception:
        return None


def is_pdf_ready() -> bool:
    try:
        col = _get_pdf_collection()
        return col is not None and col.count() > 0
    except Exception:
        return False


_PDF_SCORE_THRESHOLD = 0.30

PDF_LOW_CONF_BANNER = (
    "\u26a0\ufe0f **Verified info not in local DB, providing general knowledge...**\n\n"
)


def retrieve_from_pdf(user_query: str, n_results: int = 5) -> list:
    # Normalize brand names to generics before embedding
    user_query = normalize_query(user_query)
    col = _get_pdf_collection()
    if col is None:
        return []
    count = col.count()
    if count == 0:
        return []
    try:
        embedder = _get_hf_embedder()
        query_vec = embedder.embed_query(user_query)
        results = col.query(
            query_embeddings=[query_vec],
            n_results=min(n_results, count),
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        ids_list  = results.get("ids",        [[]])[0]
        docs_list = results.get("documents",  [[]])[0]
        metas     = results.get("metadatas",  [[]])[0]
        dists     = results.get("distances",  [[]])[0]
        for doc_id, text, meta, dist in zip(ids_list, docs_list, metas, dists):
            score = round(1.0 - (dist or 0.0), 4)
            chunks.append({
                "text":           text,
                "source":         meta.get("source", "Unknown PDF"),
                "page_number":    int(meta.get("page_number", 1)),
                "chunk_index":    int(meta.get("chunk_index", 0)),
                "id":             doc_id,
                "score":          score,
                "low_confidence": score < _PDF_SCORE_THRESHOLD,
            })
        return chunks
    except Exception as _e:
        print(f"[rag_engine] PDF retrieval error: {_e}")
        return []
