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
    "You are a Clinical Pharmacologist AI assistant powered by a RAG pipeline "
    "backed by the British National Formulary (BNF).\n\n"
    "Always respond using ALL FOUR sections below in this exact order:\n\n"
    "## \U0001f48a Drug Identification\n"
    "State the generic INN name(s), therapeutic class, and primary mechanism of action. "
    "For EVERY drug you MUST name the specific receptor subtype or enzyme target "
    "(e.g., beta-1 adrenoceptor antagonist, COX-1/COX-2 inhibitor, CYP2C9 substrate, "
    "proton pump/H+K+-ATPase inhibitor). Do NOT write just 'anticoagulant' "
    "or 'antiplatelet' -- always explain the molecular target.\n\n"
    "## \u26a0\ufe0f Interaction Alerts\n"
    "List every MAJOR, MODERATE, or MINOR interaction found in the retrieved context. "
    "For each state: (a) severity level, (b) the exact PK or PD mechanism "
    "(e.g., CYP2C9 inhibition raises plasma warfarin AUC; additive bleeding via "
    "dual antiplatelet + anticoagulation pathway), (c) the specific clinical risk, "
    "(d) monitoring parameters (e.g., INR every 3-5 days). "
    "If no interactions documented: \'No significant interactions found in retrieved BNF context.\'\n\n"
    "## \U0001f4a1 Clinical Rationale (The Why)\n"
    "This section is MANDATORY -- must ALWAYS contain a mechanistic explanation.\n"
    "Search context for: absorption, bioavailability, acid-labile, half-life, "
    "protein binding, CYP450, enzyme inhibition/induction, transporter (P-gp/OATP), "
    "receptor binding, food effect, renal/hepatic clearance.\n"
    "CRITICAL: Even if the BNF chunk does NOT explicitly state the mechanism, you MUST "
    "use your core pharmacological knowledge and label it:\n"
    "  [Mechanism of Action -- pharmacological knowledge]: <explanation>\n"
    "Required depth:\n"
    "  - Warfarin: S-warfarin is a CYP2C9 substrate; inhibitors reduce clearance "
    "    and raise INR by increasing free plasma warfarin levels.\n"
    "  - Esomeprazole: acid-labile benzimidazole degraded at low gastric pH; enteric "
    "    coating and fasting ensure delivery to duodenum for peak acid suppression.\n"
    "  - Beta-blockers: beta-1 (heart rate/contractility) vs beta-2 (bronchospasm); "
    "    cardioselective agents preferred in asthma/COPD.\n\n"
    "## \U0001f4da BNF References\n"
    "List BNF page numbers from retrieved context (e.g. BNF80, Page 423). "
    "If no context: \'No BNF context retrieved for this query.\'\n\n"
    "STRICT RULES:\n"
    "1. Base all clinical facts on the verified references provided.\n"
    "2. NEVER invent INR thresholds, dose values, or monitoring frequencies not in sources.\n"
    "3. The Clinical Rationale section is NOT optional -- always explain the mechanism.\n"
    "4. Always end with: [Verify with a licensed pharmacist or prescriber before clinical decisions]\n"
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
                "num_ctx":     4096,
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


# ==== Ollama / BioMistral functions ====

try:
    from rag_engine import (
        retrieve, build_rag_prompt, is_ready as rag_is_ready,
        format_citations, extract_drug_names, retrieve_interaction,
    )
    _RAG_ENGINE_AVAILABLE = True
except Exception:
    _RAG_ENGINE_AVAILABLE = False

try:
    from interaction_checker import check_interactions
    _INTERACTION_CHECKER_AVAILABLE = True
except Exception:
    _INTERACTION_CHECKER_AVAILABLE = False

    def check_interactions(drugs):
        return []


def _get_ram_warning(exc: Exception, host: str) -> str:
    """Return an actionable error message for Ollama/BioMistral failures."""
    msg = str(exc)
    free_gb = 0.0
    try:
        import psutil
        free_gb = round(psutil.virtual_memory().available / 1073741824, 1)
    except Exception:
        pass
    needed_gb = 4.5
    ram_line = (
        f"**Free RAM:** {free_gb} GB available / ~{needed_gb} GB required.\n\n"
        if free_gb > 0 else ""
    )
    if "system memory" in msg or "allocate" in msg or free_gb < needed_gb:
        return (
            "**⚠️ BioMistral cannot load – not enough free RAM**\n\n"
            + ram_line
            + "**To free RAM, close any of these:**\n"
            "- Browser tabs (Edge/Chrome/Brave)\n"
            "- VS Code extensions (disable unused ones)\n"
            "- Other background applications\n\n"
            "After closing apps, wait 10 seconds then send your message again.\n\n"
            f"_Technical: {msg}_"
        )
    return (
        f"**BioMistral offline** – could not reach Ollama at {host}\n\n"
        f"Error: {msg}\n\n"
        "Make sure Ollama is running (ollama serve) and the model is available."
    )



def query_ollama_llm(user_message: str, chat_history: list) -> str:
    """BioMistral 7B via Ollama - clinical pharmacist analysis."""
    import ollama as _ollama
    import re as _re
    import streamlit as st

    # 1. Query expansion
    _SPELL = {
        "ckd":  "chronic kidney disease",
        "inr":  "warfarin monitoring",
        "renal": "kidney impairment",
        "dm":   "diabetes mellitus",
        "htn":  "hypertension",
        "afib": "atrial fibrillation",
    }
    _msg = user_message
    for _abbr, _full in _SPELL.items():
        _msg = _re.sub(r"\b" + _abbr + r"\b", _full, _msg, flags=_re.IGNORECASE)

    # Extract PDF context injected by generate_response() and move it into _SYS later
    _pdf_ctx_injected = ""
    _PDF_CTX_SEP = "\n\nQuestion: "
    if "REFERENCED CLINICAL CONTEXT (from PDF):" in _msg and _PDF_CTX_SEP in _msg:
        _pdf_ctx_injected, _msg = _msg.split(_PDF_CTX_SEP, 1)

    # 2. Detect clinical + intent flags
    _CLINICAL_RE = _re.compile(
        r"\b(mg|mcg|tablet|capsule|dose|drug|medication|medicine|prescription|"
        r"interaction|warfarin|metformin|aspirin|amoxicillin|ibuprofen|omeprazole|"
        r"renal|hepat|cardiac|diabetes|hypertens|antibiotic|antihypertens|"
        r"pharmacok|pharmacodyn|cyp[0-9]|inhibit|induc|patient|side.?effect|"
        r"contraindic|overdose|toxicity|mechanism|serotonin|bleeding|coumadin)\b",
        _re.IGNORECASE,
    )
    _is_clinical = bool(_CLINICAL_RE.search(_msg)) or len(_msg.split()) >= 6

    _DOSING_RE = _re.compile(
        r"\b(dose|dosing|dosage|mg|mcg|mg/kg|frequency|how much|how many|"
        r"renal.{0,20}fail|renal.{0,20}impair|kidney.{0,20}fail|crcl|"
        r"creatinine.{0,20}clearance|dose.{0,10}adjust|adjust|reduce)\b",
        _re.IGNORECASE,
    )
    _is_dosing_query   = bool(_DOSING_RE.search(_msg))
    _needs_renal_check = bool(_re.search(
        r"\b(renal.{0,20}fail|kidney.{0,20}fail|renal.{0,20}impair|crcl|ckd)\b",
        _msg, _re.IGNORECASE,
    ))

    # 3. RAG retrieval - targeted, cross-contamination-resistant
    _rag_block = ""
    rag_chunks: list = []
    _query_drugs: list[str] = []
    _context_drug_match = True   # strict RAG guardrail: context must mention queried drugs
    _confidence_pct = 0          # 0-100 RAG relevance score
    _low_confidence = False      # True when confidence < 80%
    _severity = ""              # set in elif _is_clinical branch; pre-init to avoid UnboundLocalError
    _is_major = False

    if _is_clinical and _RAG_ENGINE_AVAILABLE:
        try:
            # 3a. Identify drugs in the query
            _query_drugs = extract_drug_names(_msg)

            if _query_drugs:
                if not _is_dosing_query:
                    # Interaction query: verified drug-name retrieval
                    rag_chunks = retrieve_interaction(_query_drugs, n_results=5)
                else:
                    # Dosing query: wider pool to catch Dosing/Adjustment sections
                    _dose_query = (
                        " ".join(_query_drugs)
                        + " dose dosing renal adjustment CrCl creatinine clearance mg/kg"
                    )
                    rag_chunks = retrieve(_dose_query, n_results=8)
            else:
                _general_query = f"{_msg} renal dose adjustment creatinine clearance"
                rag_chunks = retrieve(_general_query, n_results=5)

            # 3c. Minimum relevance filter
            scored_chunks = [c for c in rag_chunks if c.get("score", 0) >= 0.35]

            # 3d. Context reranking: push Dosing/Adjustment sections to the top
            if _is_dosing_query and scored_chunks:
                _DOSE_CATS = {"dosing", "dose", "adjustment", "dose_adjustment", "renal_dosing"}
                def _dose_priority(c):
                    cat  = c.get("category", "").lower().replace(" ", "_")
                    text = c.get("text", "").lower()
                    top  = any(k in cat for k in _DOSE_CATS) or any(
                        k in text for k in ("crcl", "creatinine clearance", "mg/kg", "dose adjustment")
                    )
                    return (0 if top else 1, -c.get("score", 0.0))
                scored_chunks.sort(key=_dose_priority)

            # 3e. Renal CrCl validation
            _renal_data_found = False
            if _needs_renal_check and scored_chunks:
                _renal_data_found = any(
                    "crcl" in c.get("text", "").lower()
                    or "creatinine clearance" in c.get("text", "").lower()
                    for c in scored_chunks
                )

            # 3f. Build reference block (category label included)
            if scored_chunks:
                drug_label = (
                    " + ".join(d.title() for d in _query_drugs)
                    if _query_drugs else "General"
                )
                _refs = [
                    "[{drug}] [{cat}] (Relevance: {score:.2f})\n{text}".format(
                        drug=c.get("drug", "Unknown").upper(),
                        cat=c.get("category", "general").upper(),
                        score=c.get("score", 0),
                        text=c["text"],
                    )
                    for c in scored_chunks
                ]
                _rag_block = (
                    f"\n\nVERIFIED CLINICAL REFERENCES [{drug_label}]:\n"
                    + "\n\n".join(_refs)
                )
            elif _query_drugs:
                _rag_block = (
                    f"\n\n[KNOWLEDGE BASE NOTE: No verified data found"
                    f" for {', '.join(_query_drugs)} in current database.]"
                )

            # 3g. Safety guardrail: warn LLM if renal CrCl data is absent
            if _needs_renal_check and not _renal_data_found:
                _rag_block += (
                    "\n\n[RENAL VALIDATION NOTE: The retrieved context does NOT contain "
                    "explicit CrCl thresholds. You MUST NOT invent creatinine clearance "
                    "cutoffs. State 'CrCl-based dosing data not available in knowledge "
                    "base' instead.]"
                )

            # 3h. Strict drug-name matching guardrail
            if _query_drugs:
                if not scored_chunks:
                    _context_drug_match = False
                else:
                    _match_pats = [
                        _re.compile(r"\b" + _re.escape(d) + r"\b", _re.IGNORECASE)
                        for d in _query_drugs
                    ]
                    _matched_chunks = [
                        c for c in scored_chunks
                        if any(p.search(c.get("text", "") + " " + c.get("drug", ""))
                               for p in _match_pats)
                    ]
                    _context_drug_match = bool(_matched_chunks)

            # 3i. Confidence score (average relevance of retrieved context)
            if scored_chunks:
                _avg_rag_score = (
                    sum(c.get("score", 0.0) for c in scored_chunks)
                    / len(scored_chunks)
                )
                _confidence_pct = min(100, max(0, int(_avg_rag_score * 160)))
            _low_confidence = bool(_query_drugs) and _confidence_pct < 80

        except Exception as _re_err:
            print(f"RAG error: {_re_err}")

    # 3j. Context mismatch: refuse answer if no chunk mentions queried drugs
    # Skip guard when PDF context was already injected into the message
    _has_pdf_ctx = "REFERENCED CLINICAL CONTEXT (from PDF):" in user_message
    if not _context_drug_match and _query_drugs and not _has_pdf_ctx:
        _queried_str = ", ".join(d.title() for d in _query_drugs)
        return (
            f"\u26a0\ufe0f **Context Mismatch \u2014 Cannot Answer Reliably**\n\n"
            f"The knowledge base does not contain verified information about "
            f"**{_queried_str}** that matches your query.\n\n"
            f"**Please consult a physical clinical reference:**\n"
            f"- British National Formulary (BNF)\n"
            f"- ASHP Drug Information\n"
            f"- The drug\u2019s official Summary of Product Characteristics (SmPC)"
        )

    _MODEL = "adrienbrault/biomistral-7b:Q4_K_M"
    _HOST  = st.session_state.get("ol_host", "http://localhost:11434")

    # 4. Intent-aware system prompt
    _drug_scope = (
        f"Drugs under analysis: {', '.join(d.upper() for d in _query_drugs)}.\n"
        if _query_drugs else ""
    )

    if _is_clinical and _is_dosing_query:
        # DOSING MODE: scan context for explicit CrCl/mL/min values to surface upfront
        import re as _re2
        _EXTRACT_RE = _re2.compile(
            r"[^.\n]*(?:crcl|ml/min|creatinine clearance|dose adjustment|adjust(?:ed)? dose)"
            r"[^.\n]*",
            _re2.IGNORECASE,
        )
        _extracted_lines: list[str] = []
        for _ec in (scored_chunks if "scored_chunks" in dir() else []):
            for _hit in _EXTRACT_RE.findall(_ec.get("text", "")):
                _hit = _hit.strip()
                if _hit and _hit not in _extracted_lines:
                    _extracted_lines.append(_hit)
        _extracted_block = ""
        if _extracted_lines:
            _extracted_block = (
                "\n\nEXTRACTED DOSING VALUES (use these to start your answer):\n"
                + "\n".join(f"   {l}" for l in _extracted_lines[:8])
            )

        _renal_example = (
            "Your answer MUST start with a line in this exact format:\n"
            "  **For renal impairment (CrCl < X mL/min), the dose is: [DOSE]**\n"
            "Replace X and [DOSE] with the values found in the references.\n"
            "If multiple CrCl thresholds exist, list each as a separate bullet.\n"
            if _needs_renal_check else ""
        )

        _SYS = (
            "You are a precise Clinical Pharmacist. "
            "Your answer must START with the specific dose found in the sources.\n\n"
            + _drug_scope
            + _renal_example
            + "EXTRACTION RULES:\n"
            "1. Scan the references for the keywords CrCl, mL/min, Adjustment, mg/kg, "
            "   or any explicit dosage number.\n"
            "2. PRIORITISE sections labelled DOSING or ADJUSTMENT over general overview.\n"
            "3. Format every dosage value in **bold markdown** so it stands out.\n"
            "4. Use bullet points (-) for each dose tier / CrCl range.\n"
            "5. Do NOT provide general mechanism or pharmacology unless the specific "
            "   dose is completely absent from the references.\n"
            "6. If the exact dose is missing say: '**Exact dosing data not available "
            "   in knowledge base.** Consult current BNF/ASHP guidelines.'\n"
            "7. Critical Rule: When a contraindication or interaction is found, you MUST use your core medical knowledge to explain the"
            " Physiological Mechanism (e.g., mention receptor types like Beta-1 or Beta-2) even if the BNF text only mentions the warning without the explanation.\n"
            "8. End with: [Verify with a licensed pharmacist before clinical use]\n"
        ) + _rag_block + _extracted_block

    elif _is_clinical:
        # INTERACTION / GENERAL CLINICAL MODE
        # Pre-check structured interaction DB for severity + known facts
        _ix_data: dict | None = None
        _is_major = False
        _severity = ""  # "MAJOR" | "MODERATE" | "MINOR" | ""
        _timing_rule_drugs = {"ibuprofen", "naproxen"}  # drugs where 30-min rule applies
        _warfarin_in_query = "warfarin" in _query_drugs or "coumadin" in _msg.lower()
        _exclude_timing_note = ""
        if _query_drugs and _INTERACTION_CHECKER_AVAILABLE:
            try:
                _ixs = check_interactions(_query_drugs)
                if _ixs:
                    _ix_data = _ixs[0]
                    _severity = _ix_data.get("severity", "").upper()
                    _is_major = _severity == "MAJOR"
            except Exception:
                pass
        # Infer severity from PDF context when DB has no entry for this pair
        if not _severity and _pdf_ctx_injected:
            _ctx_lc = _pdf_ctx_injected.lower()
            if any(w in _ctx_lc for w in ("contraindicated", "avoid", "major", "severe", "life-threatening", "fatal", "do not use")):
                _severity = "MAJOR"; _is_major = True
            elif any(w in _ctx_lc for w in ("caution", "monitor", "moderate", "significant", "increase")):
                _severity = "MODERATE"
            elif any(w in _ctx_lc for w in ("minor", "minimal", "slight", "unlikely")):
                _severity = "MINOR"

        # If warfarin is involved, explicitly ban the 30-min COX-1 timing rule
        if _warfarin_in_query and not (_timing_rule_drugs & set(_query_drugs)):
            _exclude_timing_note = (
                "CRITICAL OVERRIDE: The '30-minute timing rule' applies ONLY to "
                "Aspirin + Ibuprofen (COX-1 competition). It does NOT apply to Warfarin. "
                "Do NOT mention any timing rule in the context of Warfarin. "
                "Warfarin interactions involve ANTICOAGULATION and BLEEDING RISK, not enzyme competition.\n\n"
            )
        # Build pre-synthesised warning block from structured DB data
        _db_warning = ""
        if _ix_data and _is_major:
            _d1 = _ix_data.get("drug1", "").title()
            _d2 = _ix_data.get("drug2", "").title()
            _mech  = _ix_data.get("mechanism", "")
            _desc  = _ix_data.get("description", "")
            _action = _ix_data.get("action", "")
            _db_warning = (
                f"\nVERIFIED INTERACTION DATABASE ENTRY:\n"
                f"  Pair: {_d1} + {_d2}  |  Severity: {_severity if _severity else 'MAJOR'}\n"
                f"  Mechanism: {_mech}\n"
                f"  Clinical summary: {_desc}\n"
                f"  Recommended action: {_action}\n"
            )
        _SYS = (
            "You are a Clinical Pharmacologist AI. Respond using ALL FOUR sections exactly.\n\n"
            + _drug_scope
            + _exclude_timing_note
            + "## 💊 Drug Identification\n"
            "Generic name, therapeutic class, mechanism of action.\n\n"
            "## ⚠️ Interaction Alerts\n"
            "List MAJOR/MODERATE/MINOR interactions from context. "
            "State mechanism (PD/PK / CYP pathway) and clinical risk per interaction.\n\n"
            "## 💡 Clinical Rationale (The Why)\n"
            "Search context for: absorption, bioavailability, acid-labile, CYP450. "
            "Explain the pharmacological reason. "
            "If not in context label it: '[Mechanism of Action]:\'\n\n"
            "## 📚 BNF References\n"
            "List BNF page numbers from context. If none: 'No BNF context retrieved.'\n\n"
            "STRICT RULES:\n"
            "1. Base clinical facts on the verified references AND the database entry.\n"
            "2. NEVER invent thresholds or dose values not in sources.\n"
            "3. End with: [Verify with a licensed pharmacist before any clinical decision]\n"
        ) + _db_warning + _rag_block

    else:
        _SYS = "You are a helpful Clinical Pharmacist AI assistant. Respond politely and concisely."

    # Inject extracted PDF context into the system prompt (correct placement)
    if _pdf_ctx_injected:
        _SYS = _SYS + "\n\n" + _pdf_ctx_injected

    # 5. Build prompt - intent-aware instruction
    if _is_clinical and _is_dosing_query:
        full_prompt = (
            f"<s>[INST] <<SYS>>\n{_SYS}\n<</SYS>>\n\n"
            f"Dosing question: {_msg}\n\n"
            "TASK: Extract ALL dosage values, CrCl thresholds, and mL/min cutoffs "
            "directly from the references above. Format each value in **bold**. "
            "Start your answer immediately with the dose  no introduction needed.\n"
            "[/INST]"
        )
    elif _is_clinical:
        _major_task = (
            "TASK: Write ONLY the body of the structured interaction report "
            "in the exact format specified. Do NOT write a title or header line. "
            "Start directly with '**Drugs:**'. "
            "Bold all drug names and severity labels. "
            "Under Monitoring, list: INR frequency and bleeding signs. "
            "Do NOT mention COX-1 timing rules unless both drugs are NSAIDs.\n"
            if _severity in ("MAJOR", "MODERATE", "MINOR") else
            "Write a structured pharmacist safety review. "
            "Do NOT write a title or header line. Start with '**Drugs:**'. "
            "Bold all severity labels and drug names.\n"
        )
        full_prompt = (
            f"<s>[INST] <<SYS>>\n{_SYS}\n<</SYS>>\n\n"
            f"Clinical question: {_msg}\n\n"
            + _major_task
            + "[/INST]"
        )
    else:
        full_prompt = f"<s>[INST] {_msg} [/INST]"

    # 6. Generate
    try:
        client = _ollama.Client(host=_HOST)
        resp = client.generate(
            model=_MODEL,
            prompt=full_prompt,
            raw=True,
            options={
                "num_predict": 1500,
                "temperature": 0.3,
                "top_p":       0.9,
                "num_ctx":     4096,
                "num_gpu":     0,
            },
        )

        answer = resp.response.strip()

        for _marker in ("<<SYS>>", "<</SYS>>", "[INST]", "[/INST]", "<s>", "</s>"):
            answer = answer.replace(_marker, "")
        answer = answer.strip()

        # Prepend severity header in Python - never trust small model to generate it
        if _severity and len(answer) >= 15:
            _sev_icon = "\u26a0\ufe0f" if _severity in ("MAJOR", "MODERATE") else "\u2139\ufe0f"
            _sev_hdr = f"**{_sev_icon} {_severity} INTERACTION DETECTED**\n\n"
            import re as _reh
            answer = _reh.sub(
                r"^\*\*[^\n]{0,80}INTERACTION[^\n]{0,40}\*\*\n*",
                "", answer.lstrip(), flags=_reh.MULTILINE
            )
            answer = _sev_hdr + answer.lstrip()

        if len(answer) < 15:
            return "\u26a0\ufe0f \u0644\u0645 \u064a\u0635\u062f\u0631 \u0627\u0644\u0645\u0648\u062f\u064a\u0644 \u0631\u062f\u0651\u0627\u064b. \u062d\u0627\u0648\u0644 \u0625\u0639\u0627\u062f\u0629 \u0635\u064a\u0627\u063a\u0629 \u0627\u0644\u0633\u0624\u0627\u0644."

        # Add source citations for high-confidence chunks
        scored = [c for c in rag_chunks if c.get("score", 0) >= 0.45]
        if scored:
            from rag_engine import format_citations
            answer += f"\n\n---\n{format_citations(scored)}"

        # Confidence warning appended when RAG relevance < 80%
        if _low_confidence and _confidence_pct > 0:
            answer += (
                f"\n\n---\n"
                f"\u26a0\ufe0f **RAG Confidence: {_confidence_pct}% "
                f"(Below 80% threshold)**\n"
                f"This response is based on limited or low-relevance context data. "
                f"**Please verify with a physical clinical reference** "
                f"(BNF, ASHP Drug Information, or official prescribing information) "
                f"before making any clinical decisions."
            )

        try:
            from database import log_event as _le
            _le("query_answered", {"query": user_message[:200]})
        except Exception:
            pass

        return answer

    except Exception as exc:
        return _get_ram_warning(exc, _HOST)





#  Groq Cloud path 
_GROQ_CLOUD_MODEL = os.environ.get("PHARMA_GROQ_MODEL", "llama-3.1-8b-instant")


def _chat_groq(system_prompt: str, user_message: str, api_key: str) -> str:
    """Send a single request to Groq Cloud and return the response text."""
    try:
        from groq import Groq as _Groq
    except ImportError:
        return (
            "**Groq package not installed.**\n\n"
            "Run: `pip install groq` and restart the app."
        )
    if not api_key:
        return (
            "**Groq API key not set.**\n\n"
            "Add `GROQ_API_KEY=...` to your `.env` file or paste it in Settings."
        )
    try:
        _client = _Groq(api_key=api_key)
        completion = _client.chat.completions.create(
            model=_GROQ_CLOUD_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2048,
            top_p=0.9,
            stream=False,
        )
        answer = (completion.choices[0].message.content or "").strip()
        if len(answer) < 15:
            return "The model returned an empty response. Try rephrasing your question."
        try:
            from database import log_event as _le_g
            _le_g("query_answered", {"query": user_message[:200], "model": _GROQ_CLOUD_MODEL})
        except Exception:
            pass
        return answer
    except Exception as exc:
        return (
            f"**Groq API error** ({_GROQ_CLOUD_MODEL})\n\n"
            f"Error: {exc}\n\n"
            "Check that your GROQ_API_KEY is valid and the model name is correct."
        )



def _get_pdf_rag_context(query: str, n: int = 5):
    try:
        from rag_engine import retrieve_from_pdf, is_pdf_ready, PDF_LOW_CONF_BANNER
        if not is_pdf_ready():
            return "", [], False
        chunks = retrieve_from_pdf(query, n_results=n)
        if not chunks:
            return "", [], False
        best_score = max(c.get("score", 0.0) for c in chunks)
        if best_score < 0.30:
            return "", [], True
        refs = [
            "[PDF REF {}] (Page {}, score {:.2f})\n{}".format(
                i, c["page_number"], c["score"], c["text"]
            )
            for i, c in enumerate(chunks, 1)
        ]
        block = "\n\nREFERENCED CLINICAL CONTEXT (from PDF):\n" + "\n\n".join(refs)
        sources = [{"file": c["source"], "page": c["page_number"]} for c in chunks]
        return block, sources, False
    except Exception:
        return "", [], False


def generate_response(
    user_message: str,
    chat_history: list | None = None,
    mode: str = "local",
    groq_api_key: str = "",
    ocr_context: str = "",
) -> tuple:
    """
    Unified LLM router for the Drug Interaction Chat page.

    Parameters
    ----------
    user_message  : the user's question
    chat_history  : list of {role, content} dicts (for context only)
    mode          : "cloud"    Groq llama-3.1-70b-versatile
                    "local"    Ollama BioMistral-7B (default)
    groq_api_key  : required when mode == "cloud"

    Returns
    -------
    str  the assistant response (may contain Markdown)
    """
    # Short-circuit for casual/greeting messages -- no clinical framework needed
    _casual_re = re.compile(
        r"^\s*(hi+|hello+|hey+|howdy|greetings|good\s*(morning|afternoon|evening|day)|"
        r"how are you|what.s up|sup|yo|thanks?|thank you|ok|okay|bye|goodbye|"
        r"who are you|what are you|what can you do|help)[\.!?\s]*$",
        re.IGNORECASE,
    )
    if _casual_re.match(user_message):
        _casual_sys = (
            "You are a friendly Drug Safety Assistant. "
            "Respond naturally and conversationally to greetings and small talk. "
            "Be warm but brief. If the user seems ready to ask a clinical question, "
            "invite them to do so."
        )
        if mode == "cloud":
            return _chat_groq(_casual_sys, user_message, groq_api_key), []
        else:
            return query_ollama_llm(user_message, []), []

    # Short-circuit for casual/greeting messages -- no clinical framework needed
    _casual_re = re.compile(
        r"^\s*(hi+|hello+|hey+|howdy|greetings|good\s*(morning|afternoon|evening|day)|"
        r"how are you|what.s up|sup|yo|thanks?|thank you|ok|okay|bye|goodbye|"
        r"who are you|what are you|what can you do|help)[\.!?\s]*$",
        re.IGNORECASE,
    )
    if _casual_re.match(user_message):
        _casual_sys = (
            "You are a friendly Drug Safety Assistant. "
            "Respond naturally and conversationally to greetings and small talk. "
            "Be warm but brief. If the user seems ready to ask a clinical question, "
            "invite them to do so."
        )
        if mode == "cloud":
            return _chat_groq(_casual_sys, user_message, groq_api_key), []
        else:
            return query_ollama_llm(user_message, []), []

    if mode == "cloud":
        # Re-use the same query-expansion + RAG + system-prompt logic, then send
        # to Groq instead of Ollama.  We build the composite system prompt inline
        # so the quality of the cloud response matches the local one.
        import re as _re_gr
        _SPELL_GR = {
            "ckd":  "chronic kidney disease",
            "inr":  "warfarin monitoring",
            "renal": "kidney impairment",
            "dm":   "diabetes mellitus",
            "htn":  "hypertension",
            "afib": "atrial fibrillation",
        }
        _msg_gr = user_message
        for _abbr, _full in _SPELL_GR.items():
            _msg_gr = _re_gr.sub(r"\b" + _abbr + r"\b", _full, _msg_gr, flags=_re_gr.IGNORECASE)
        try:
            from rag_engine import normalize_query as _nq_gr
            _msg_gr = _nq_gr(_msg_gr)
        except Exception:
            pass

        # RAG context (best-effort; falls back gracefully)
        _rag_block_gr = ""
        try:
            _rag_block_gr, _ = _get_rag_context(_msg_gr, n=5)
        except Exception:
            pass

        # PDF RAG context (primary retrieval layer)
        _pdf_block_gr, _pdf_srcs_gr, _pdf_low_gr = _get_pdf_rag_context(_msg_gr)
        if _pdf_low_gr:
            _pdf_block_gr = ""
        # Build system prompt: clinical framework + JSON RAG + PDF RAG
        _sys_gr = (
            _SYSTEM_CLINICAL
            + (("\n\nACTIVE PRESCRIPTION CONTEXT (from OCR scan):\n" + ocr_context) if ocr_context else "")
            + _rag_block_gr
            + _pdf_block_gr
        )
        if _pdf_low_gr:
            _sys_gr += (
                "\n\nFALLBACK: No high-confidence PDF context found. "
                "Provide a response based on general clinical knowledge."
            )
        _resp_gr = _chat_groq(_sys_gr, _msg_gr, groq_api_key)
        if _pdf_low_gr:
            try:
                from rag_engine import PDF_LOW_CONF_BANNER
                _resp_gr = PDF_LOW_CONF_BANNER + _resp_gr
            except Exception:
                pass
        return _resp_gr, _pdf_srcs_gr
    else:
        # PDF RAG context for local path
        _local_query = user_message
        try:
            from rag_engine import normalize_query as _nq_l
            _local_query = _nq_l(user_message)
        except Exception:
            pass
        _pdf_block_l, _pdf_srcs_l, _pdf_low_l = _get_pdf_rag_context(_local_query)
        _local_msg = user_message
        if ocr_context:
            _local_msg = "ACTIVE PRESCRIPTION CONTEXT (from OCR scan):\n" + ocr_context + "\n\nQuestion: " + user_message
        if _pdf_block_l:
            # Truncate for local small model to prevent context overflow
            _pdf_block_l = _pdf_block_l[:1200]
            _local_msg = _pdf_block_l + "\n\nQuestion: " + _local_msg
        _resp_l = query_ollama_llm(_local_msg, chat_history or [])
        if _pdf_low_l:
            try:
                from rag_engine import PDF_LOW_CONF_BANNER
                _resp_l = PDF_LOW_CONF_BANNER + _resp_l
            except Exception:
                pass
        return _resp_l, _pdf_srcs_l


# ===========================================================================
# Structured JSON output for n8n / API integration
# ===========================================================================

import re as _re_struct


def _extract_section(markdown: str, header_keyword: str) -> str:
    """Extract a section body from the 4-section markdown response."""
    m = _re_struct.search(
        r"##[^#\n]*" + re.escape(header_keyword) + r"(.*?)(?=##|\Z)",
        markdown, _re_struct.S | _re_struct.I,
    )
    return m.group(1).strip() if m else ""


def generate_response_structured(
    user_message: str,
    mode: str = "cloud",
    groq_api_key: str = "",
    ocr_context: str = "",
) -> "dict":
    """
    Calls generate_response() and parses the 4-section markdown into a
    flat structured dict.  Used by api.py for n8n / Telegram output.

    Returns
    -------
    dict with keys:
        query                      str
        drug_name                  list[str]
        interaction_severity       str   MAJOR | MODERATE | MINOR | NONE
        clinical_rationale_the_why str
        bnf_source_page            list[dict]  [{file, page}, ...]
        full_markdown              str
        confidence_pct             int   0-100
        alert_level                str   CRITICAL | WARNING | INFO | SAFE
    """
    # Get the raw markdown + sources from the existing router
    raw_markdown, sources = generate_response(
        user_message=user_message,
        mode=mode,
        groq_api_key=groq_api_key,
        ocr_context=ocr_context,
    )

    # ── Drug names ─────────────────────────────────────────────────────────
    drug_section = _extract_section(raw_markdown, "Drug Identification")
    drug_names: list[str] = []
    # Look for bold generic names in the Drug ID section
    for hit in _re_struct.findall(r"\*\*([A-Za-z][a-zA-Z\-]{3,30})\*\*", drug_section):
        candidate = hit.strip().lower()
        if (
            len(candidate) > 3
            and candidate not in drug_names
            and candidate not in ("major", "moderate", "minor", "none", "drug", "generic")
        ):
            drug_names.append(candidate)
    # Fallback: extract via rag_engine drug extractor
    if not drug_names:
        try:
            from rag_engine import normalize_query as _nq, extract_drug_names
            norm = _nq(user_message)
            drug_names = [d.lower() for d in extract_drug_names(norm)]
        except Exception:
            pass
    if not drug_names:
        drug_names = [user_message.lower()[:60]]

    # ── Severity ───────────────────────────────────────────────────────────
    sev_m = _re_struct.search(r"\b(MAJOR|MODERATE|MINOR)\b", raw_markdown, _re_struct.I)
    severity = sev_m.group(1).upper() if sev_m else "NONE"

    # ── Clinical Rationale ─────────────────────────────────────────────────
    rationale = _extract_section(raw_markdown, "Clinical Rationale")
    if not rationale:
        # Try [Mechanism of Action] block
        moa_m = _re_struct.search(
            r"\[Mechanism of Action[^\]]*\]:(.*?)(?=\n\n|##|\Z)",
            raw_markdown, _re_struct.S,
        )
        rationale = moa_m.group(1).strip() if moa_m else "See full response."
    rationale = rationale[:1200]

    # ── BNF sources ────────────────────────────────────────────────────────
    bnf_sources = [{"file": s.get("file", "BNF80.pdf"), "page": s.get("page", 0)} for s in sources]
    if not bnf_sources:
        for pg_m in _re_struct.finditer(r"(?:BNF80|Page)[,\s]+(?:[Pp]age[\s]+)?(\d+)", raw_markdown):
            bnf_sources.append({"file": "BNF80.pdf", "page": int(pg_m.group(1))})

    # ── Confidence ─────────────────────────────────────────────────────────
    conf_m = _re_struct.search(r"RAG Confidence:\s*(\d+)%", raw_markdown)
    confidence_pct = int(conf_m.group(1)) if conf_m else (88 if sources else 42)

    # ── Alert level ────────────────────────────────────────────────────────
    alert_map = {"MAJOR": "CRITICAL", "MODERATE": "WARNING", "MINOR": "INFO"}
    alert_level = alert_map.get(severity, "SAFE")

    return {
        "query": user_message,
        "drug_name": drug_names,
        "interaction_severity": severity,
        "clinical_rationale_the_why": rationale,
        "bnf_source_page": bnf_sources,
        "full_markdown": raw_markdown,
        "confidence_pct": confidence_pct,
        "alert_level": alert_level,
    }
