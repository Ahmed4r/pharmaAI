"""
ingest.py  --  PDF ingestion pipeline for PharmaAI RAG system.

Loads a medical PDF, splits it into clinical context-preserving chunks,
embeds them with sentence-transformers (all-MiniLM-L6-v2), and persists
the vectors to a local ChromaDB store at ./chroma_db.

Usage:
    python ingest.py <path/to/medical.pdf>
    python ingest.py  medical_reference.pdf  --chroma-dir ./chroma_db
"""
from __future__ import annotations

import sys
import os
from pathlib import Path


def ingest(pdf_path: str, chroma_dir: str | None = None) -> int:
    """
    Load, split, embed, and persist a PDF into ChromaDB.
    Returns the total number of chunks indexed.
    """
    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError:
        raise ImportError(
            "langchain-community is required: pip install langchain-community pypdf"
        )

    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            raise ImportError(
                "LangChain text splitter missing: pip install langchain langchain-text-splitters"
            )

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        raise ImportError(
            "langchain-huggingface is required: pip install langchain-huggingface sentence-transformers"
        )

    import chromadb

    _base = Path(__file__).parent
    _chroma_path = chroma_dir or str(_base / "chroma_db")
    Path(_chroma_path).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # 1. Load PDF pages
    # ------------------------------------------------------------------ #
    print(f"[ingest] Loading PDF: {pdf_path}")
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    print(f"[ingest] {len(pages)} pages loaded")

    # ------------------------------------------------------------------ #
    # 2. Split into clinical context-preserving chunks
    # ------------------------------------------------------------------ #
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages)
    print(f"[ingest] {len(chunks)} chunks created (size=800, overlap=150)")

    # ------------------------------------------------------------------ #
    # 3. Embed with all-MiniLM-L6-v2
    # ------------------------------------------------------------------ #
    print("[ingest] Loading embedding model: all-MiniLM-L6-v2 ...")
    embedder = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # ------------------------------------------------------------------ #
    # 4. Connect to ChromaDB and (re)create the pdf_kb collection
    # ------------------------------------------------------------------ #
    print(f"[ingest] Connecting to ChromaDB at: {_chroma_path}")
    client = chromadb.PersistentClient(path=_chroma_path)

    try:
        client.delete_collection("pdf_kb")
        print("[ingest] Cleared existing pdf_kb collection")
    except Exception:
        pass

    collection = client.create_collection(
        name="pdf_kb",
        metadata={"hnsw:space": "cosine"},
    )

    # ------------------------------------------------------------------ #
    # 5. Build IDs / texts / metadata / embeddings
    # ------------------------------------------------------------------ #
    pdf_name = Path(pdf_path).name
    ids, texts, metadatas, embed_vecs = [], [], [], []

    for i, chunk in enumerate(chunks):
        text = chunk.page_content.strip()
        if not text:
            continue
        # PyPDFLoader stores 0-based page index in metadata["page"]
        page_num = int(chunk.metadata.get("page", 0)) + 1
        vector = embedder.embed_query(text)
        ids.append(f"pdf_chunk_{i}")
        texts.append(text)
        metadatas.append(
            {
                "source": pdf_name,
                "page_number": page_num,
                "chunk_index": i,
            }
        )
        embed_vecs.append(vector)

    # ------------------------------------------------------------------ #
    # 6. Batch-upsert into ChromaDB
    # ------------------------------------------------------------------ #
    batch_size = 100
    total = len(ids)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
            embeddings=embed_vecs[start:end],
        )
        print(f"[ingest] Stored chunks {start + 1}–{end} / {total}")

    print(f"\n[ingest] Done. {total} chunks indexed in ChromaDB.")
    return total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <path/to/medical.pdf>")
        print("       python ingest.py medical_reference.pdf --chroma-dir ./chroma_db")
        sys.exit(1)

    _pdf = sys.argv[1]
    _dir = None
    if "--chroma-dir" in sys.argv:
        _idx = sys.argv.index("--chroma-dir")
        if _idx + 1 < len(sys.argv):
            _dir = sys.argv[_idx + 1]

    if not os.path.isfile(_pdf):
        print(f"Error: file not found: {_pdf}")
        sys.exit(1)

    count = ingest(_pdf, chroma_dir=_dir)
    print(f"\n  Successfully indexed {count} chunks from '{_pdf}'.")