"""chatbot.py  standalone chatbot module for PharmaAI."""
from __future__ import annotations
import re
import os

_MODEL = os.environ.get("PHARMA_MODEL", "adrienbrault/biomistral-7b:Q4_K_M")
_HOST  = os.environ.get("OLLAMA_HOST",  "http://localhost:11434")

_SPELL = {
    "ckd": "chronic kidney disease",
    "inr": "warfarin monitoring",
    "renal": "kidney impairment",
    "dm": "diabetes mellitus",
    "htn": "hypertension",
    "afib": "atrial fibrillation",
    "aki": "acute kidney injury",
    "gi": "gastrointestinal",
}

_CLINICAL_RE = re.compile(
    r"\b(mg|mcg|tablet|capsule|dose|drug|medication|medicine|prescription|"
    r"interaction|warfarin|metformin|aspirin|amoxicillin|ibuprofen|omeprazole|"
    r"clopidogrel|atorvastatin|furosemide|lisinopril|digoxin|amiodarone|"
    r"ciprofloxacin|metronidazole|sertraline|amlodipine|"
    r"renal|hepat|cardiac|diabetes|hypertens|antibiotic|antihypertens|"
    r"pharmacok|pharmacodyn|cyp[0-9]|inhibit|induc|patient|side.?effect|"
    r"contraindic|overdose|toxicity|mechanism|serotonin|bleeding)\b",
    re.IGNORECASE,
)

_SYSTEM_CLINICAL = (
    "You are an experienced Clinical Pharmacist AI assistant.\n"
    "Your role is to perform professional medication safety reviews for clinicians.\n\n"
    "When drugs are mentioned, analyze:\n"
    "- Drug mechanism of action and pharmacokinetics\n"
    "- Drug-drug interactions (specify mechanism: e.g. CYP2C9 inhibition, additive)\n"
    "- Dosing information with specific mg/kg ranges for adults and key populations\n"
    "- Renal dose adjustments (mention CrCl thresholds explicitly)\n"
    "- Hepatic dose adjustments when relevant\n"
    "- Major side effects, contraindications, and clinical red flags\n"
    "- Monitoring parameters (specify: lab, frequency, target range)\n\n"
    "Rules:\n"
    "- Use verified clinical knowledge only. Do NOT invent drug doses.\n"
    "- If dose data is missing from context, state it clearly.\n"
    "- Use clear structured paragraphs. Flag critical warnings with [WARNING].\n"
    "- Always end with: [Verify with licensed pharmacist or prescriber before clinical decisions]\n"
)


def _expand_query(query: str) -> str:
    q = query.lower()
    for abbr, full in _SPELL.items():
        q = re.sub(r"\b" + abbr + r"\b", full, q, flags=re.IGNORECASE)
    return q


def _get_rag_context(query: str, n: int = 5) -> tuple[str, list[dict]]:
    """Return (rag_block_str, chunks_list). Empty string if RAG unavailable."""
    try:
        from rag_engine import retrieve
        expanded = query + " renal dose adjustment creatinine clearance interaction"
        chunks = retrieve(expanded, n_results=n)
        scored = [c for c in chunks if c.get("score", 0) >= 0.35]
        if not scored:
            return "", []
        refs = [
            "[{drug}] (score {score:.2f})\n{text}".format(
                drug=c.get("drug", "Unknown").upper(),
                score=c.get("score", 0),
                text=c["text"],
            )
            for c in scored
        ]
        block = "\n\nVERIFIED CLINICAL REFERENCES:\n" + "\n\n".join(refs)
        return block, scored
    except Exception:
        return "", []


def chat(
    user_message: str,
    chat_history: list[dict] | None = None,
    model: str | None = None,
    host: str | None = None,
) -> str:
    """
    Send a message to BioMistral and return the clinical response string.

    Parameters
    ----------
    user_message  : the user's question
    chat_history  : list of {role, content} dicts (for context, not re-sent)
    model         : override Ollama model name
    host          : override Ollama host URL

    Returns
    -------
    str  the assistant response (may contain Markdown)
    """
    import ollama as _ollama

    _model = model or _MODEL
    _host  = host  or _HOST

    # 1. Expand abbreviations
    msg = _expand_query(user_message)

    # 2. Detect clinical query
    is_clinical = bool(_CLINICAL_RE.search(msg)) or len(msg.split()) >= 5

    # 3. RAG retrieval
    rag_block = ""
    rag_chunks: list[dict] = []
    if is_clinical:
        rag_block, rag_chunks = _get_rag_context(msg)

    # 4. Build system prompt
    if is_clinical:
        sys_prompt = _SYSTEM_CLINICAL + rag_block
    else:
        sys_prompt = "You are a helpful Clinical Pharmacist AI assistant. Respond politely and concisely."

    # 5. Build Llama2/BioMistral ChatML prompt
    full_prompt = (
        f"<s>[INST] <<SYS>>\n{sys_prompt}\n<</SYS>>\n\n"
        f"Clinical question: {msg}\n\n"
        f"Please provide a structured pharmacist response covering all relevant safety aspects.\n"
        f"[/INST]"
    )

    # 6. Generate
    try:
        client = _ollama.Client(host=_host)
        resp = client.generate(
            model=_model,
            prompt=full_prompt,
            raw=True,
            options={
                "num_predict": 1500,
                "temperature": 0.3,
                "top_p":       0.9,
                "num_ctx":     2048,
                "num_gpu":     20,
            },
        )
        answer = resp.response.strip()

        # Strip leaked control tokens
        for tok in ("<<SYS>>", "<</SYS>>", "[INST]", "[/INST]", "<s>", "</s>"):
            answer = answer.replace(tok, "")
        answer = answer.strip()

        if len(answer) < 15:
            return "The model returned an empty response. Try rephrasing your question."

        # Append RAG citations if any
        high_scored = [c for c in rag_chunks if c.get("score", 0) >= 0.45]
        if high_scored:
            try:
                from rag_engine import format_citations
                answer += f"\n\n---\n{format_citations(high_scored)}"
            except Exception:
                pass

        return answer

    except Exception as exc:
        err = str(exc)
        try:
            import psutil
            free_gb = round(psutil.virtual_memory().available / 1073741824, 1)
            if free_gb < 4.5:
                return (
                    f"**BioMistral cannot load  insufficient free RAM** "
                    f"({free_gb} GB available, ~4.5 GB needed).\n\n"
                    "Close browser tabs and other applications, then try again.\n\n"
                    f"_Technical: {err}_"
                )
        except Exception:
            pass
        return f"**Ollama/BioMistral offline**  {_host}\n\nError: {err}"


def quick_interaction_check(drug_a: str, drug_b: str) -> str:
    """
    Return a plain-text interaction summary for two drugs.
    Uses local interaction_checker, no LLM call needed.
    """
    try:
        from interaction_checker import check_interactions
        results = check_interactions([drug_a, drug_b])
        if not results:
            return f"No known interaction between {drug_a} and {drug_b} in local database."
        ix = results[0]
        return (
            f"SEVERITY: {ix['severity'].upper()}\n"
            f"{ix['description']}\n"
            f"ACTION: {ix.get('action', 'Consult pharmacist.')}"
        )
    except Exception as e:
        return f"Interaction check error: {e}"
