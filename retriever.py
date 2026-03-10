"""retriever.py - thin facade over rag_engine"""
from __future__ import annotations
from rag_engine import retrieve as _retrieve, build_rag_prompt, is_ready, format_citations

def retrieve_context(query: str, n: int = 5) -> list[dict]:
    return _retrieve(query, n_results=n)

def get_drug_context(drug_name: str, n: int = 4) -> list[dict]:
    return _retrieve(f"{drug_name} dosing interactions side effects renal", n_results=n)

__all__ = ["retrieve_context", "get_drug_context", "build_rag_prompt", "is_ready", "format_citations"]
