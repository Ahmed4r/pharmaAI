"""
ingest.py -- Rebuild the ChromaDB knowledge base for PharmaAI.

Sources:  knowledge_base/*.pdf (BNF80.pdf + any future PDFs)
          knowledge_base/drugs.json

Usage:    python ingest.py

Steps: 1) Delete chroma_db to remove stale/duplicate data
       2) Load PDFs via PyPDFDirectoryLoader
       3) Load drugs.json as text documents
       4) Split with chunk_size=1000 / chunk_overlap=200
       5) Embed via nomic-embed-text (Ollama) and upsert into ChromaDB
          collection "pharma_kb" (same path/name as rag_engine.py)
"""

import json
import shutil
from pathlib import Path

import chromadb
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import ollama

_BASE       = Path(__file__).parent
_KB_DIR     = _BASE / "knowledge_base"
_CHROMA_DIR = _KB_DIR / "chroma_db"
_OLLAMA_URL = "http://localhost:11434"

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _embed(text: str):
    """Embed text with nomic-embed-text via Ollama; return None on failure."""
    try:
        client = ollama.Client(host=_OLLAMA_URL)
        resp = client.embeddings(model="nomic-embed-text", prompt=text)
        return resp.get("embedding") or resp.get("embeddings")
    except Exception as exc:
        print(f"  WARNING: Embedding error: {exc}")
        return None


def _safe_meta(meta: dict) -> dict:
    """ChromaDB only accepts str/int/float/bool metadata values."""
    safe = {}
    for k, v in (meta or {}).items():
        if isinstance(v, (str, int, float, bool)):
            safe[str(k)] = v
        else:
            safe[str(k)] = str(v)
    return safe


def _load_pdfs() -> list:
    """Load every PDF in knowledge_base/ using PyPDFDirectoryLoader."""
    loader = PyPDFDirectoryLoader(str(_KB_DIR))
    docs = loader.load()
    print(f"  PDFs  : {len(docs)} pages loaded")
    return docs


def _load_drugs_json() -> list:
    """Convert drugs.json entries into Document objects."""
    path = _KB_DIR / "drugs.json"
    if not path.exists():
        print("  drugs.json not found -- skipping")
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    docs = []
    if isinstance(data, list):
        for i, entry in enumerate(data):
            text = json.dumps(entry, ensure_ascii=False)
            docs.append(Document(
                page_content=text,
                metadata={"source": "drugs.json", "index": i},
            ))
    elif isinstance(data, dict):
        for drug, details in data.items():
            text = f"{drug}: {json.dumps(details, ensure_ascii=False)}"
            docs.append(Document(
                page_content=text,
                metadata={"source": "drugs.json", "drug": drug},
            ))
    print(f"  JSON  : {len(docs)} drug entries from drugs.json")
    return docs


def main():
    # 1. Clear old ChromaDB
    if _CHROMA_DIR.exists():
        try:
            shutil.rmtree(_CHROMA_DIR)
            print(f"[1/4] Cleared existing ChromaDB at {_CHROMA_DIR}")
        except PermissionError:
            print("[ERROR] Cannot delete chroma_db -- locked by another process.")
            print("        Stop the Streamlit app first, then re-run: python ingest.py")
            raise SystemExit(1)
    else:
        print("[1/4] No existing ChromaDB -- fresh start")

    # 2. Load documents
    print("[2/4] Loading documents ...")
    all_docs = _load_pdfs() + _load_drugs_json()
    print(f"       {len(all_docs)} total raw documents")

    # 3. Split into chunks
    print("[3/4] Splitting into chunks (size=1000, overlap=200) ...")
    chunks = _SPLITTER.split_documents(all_docs)
    print(f"       {len(chunks)} chunks created")

    # 4. Embed and index
    print("[4/4] Embedding and indexing into ChromaDB ...")
    _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client     = chromadb.PersistentClient(path=str(_CHROMA_DIR))
    collection = client.get_or_create_collection(
        name="pharma_kb",
        metadata={"hnsw:space": "cosine"},
    )

    BATCH   = 25
    total   = len(chunks)
    done    = 0
    skipped = 0

    for i in range(0, total, BATCH):
        batch = chunks[i : i + BATCH]
        ids, vecs, texts, metas = [], [], [], []

        for j, chunk in enumerate(batch):
            text = chunk.page_content.strip()
            if not text:
                skipped += 1
                continue
            vec = _embed(text)
            if vec is None:
                skipped += 1
                continue
            ids.append(f"chunk_{i + j}")
            vecs.append(vec)
            texts.append(text)
            metas.append(_safe_meta(chunk.metadata))

        if ids:
            collection.upsert(
                ids=ids,
                embeddings=vecs,
                documents=texts,
                metadatas=metas,
            )
            done += len(ids)

        print(f"  {done}/{total} chunks indexed ...", end="\r")

    print(f"\n[OK] Ingestion complete -- {collection.count()} chunks in pharma_kb")
    if skipped:
        print(f"     ({skipped} chunks skipped: empty text or embedding failure)")


if __name__ == "__main__":
    main()
