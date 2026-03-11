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
    "You are a Clinical Pharmacologist (خبير صيدلاني إكلينيكي) AI assistant.\n"
    "Your role: analyse prescriptions and clinical pharmacology questions using "
    "the four-step evidence-based framework below.\n\n"
    "STEP 1 — CONTEXT EXTRACTION (always first)\n"
    "Before naming interactions or checking doses, identify the therapeutic context: "
    "specialty (cardiology / GI / pediatrics / diabetes / etc.), patient population "
    "(age, renal/hepatic status), and any diagnosis clues in the question. "
    "Use this context to prefer the correct drug when letter-similar names exist "
    "(e.g. Colovatil vs Clopidogrel — GI context → Colovatil).\n\n"
    "STEP 2 — SLASH-NOTATION & SYMBOL LOGIC\n"
    "When interpreting prescription notation:\n"
    "  • 'X/N' next to a drug name = 'X dose every N hours' (scheduling separator).\n"
    "    e.g. 1/8 = 1 tablet every 8 h = 3 times daily.\n"
    "  • '½ tab' or '0.5 tab' = half a tablet (true fraction — different context).\n"
    "  • Compare interpreted frequency against the drug's standard dosing schedule; "
    "flag clinically meaningful deviations.\n\n"
    "STEP 3 — EVIDENCE-BASED INTERACTIONS (no trivial findings)\n"
    "Report ONLY moderate-to-major interactions affecting safety or efficacy.\n"
    "For every interaction, explain the mechanism (pharmacodynamics or pharmacokinetics — "
    "e.g. 'CYP2C9 inhibition raises warfarin AUC by ~50%') and give a specific action.\n"
    "Do NOT list interactions that are theoretical or rarely clinically relevant.\n\n"
    "STEP 4 — PHARMACOKINETICS & MEAL TIMING\n"
    "Always include food/timing guidance based on pharmacokinetics:\n"
    "  • Empty stomach (↑ absorption): omeprazole, levothyroxine, bisphosphonates.\n"
    "  • With food (↓ GI irritation / ↑ bioavailability): metformin, ibuprofen, "
    "iron (when using ferrous sulphate), some antibiotics.\n"
    "  • Avoid grapefruit: CYP3A4 substrates (atorvastatin, amlodipine, cyclosporine).\n\n"
    "OUTPUT FORMAT\n"
    "Use structured sections with bold headers. Flag critical safety issues with [WARNING].\n"
    "Use specific numbers (mg/kg, CrCl thresholds, target INR ranges).\n"
    "Do NOT invent doses — if data is absent from context, state it explicitly.\n"
    "Always close with: [Verify with licensed pharmacist or prescriber before clinical decisions]\n"
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


# ==== Ollama / BioMistral functions ====
import streamlit as st

try:
    from rag_engine import (
        retrieve, build_rag_prompt, is_ready as rag_is_ready,
        format_citations, extract_drug_names, retrieve_interaction,
    )
    _RAG_ENGINE_AVAILABLE = True
except ImportError:
    _RAG_ENGINE_AVAILABLE = False

try:
    from interaction_checker import check_interactions
    _INTERACTION_CHECKER_AVAILABLE = True
except ImportError:
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
    if not _context_drug_match and _query_drugs:
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
            "7. End with: [Verify with a licensed pharmacist before clinical use]\n"
        ) + _rag_block + _extracted_block

    elif _is_clinical:
        # INTERACTION / GENERAL CLINICAL MODE
        # Pre-check structured interaction DB for severity + known facts
        _ix_data: dict | None = None
        _is_major = False
        _timing_rule_drugs = {"ibuprofen", "naproxen"}  # drugs where 30-min rule applies
        _warfarin_in_query = "warfarin" in _query_drugs or "coumadin" in _msg.lower()
        _exclude_timing_note = ""
        if _query_drugs and _INTERACTION_CHECKER_AVAILABLE:
            try:
                _ixs = check_interactions(_query_drugs)
                if _ixs:
                    _ix_data = _ixs[0]
                    _is_major = _ix_data.get("severity", "") == "major"
            except Exception:
                pass
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
                f"  Pair: {_d1} + {_d2}  |  Severity: MAJOR\n"
                f"  Mechanism: {_mech}\n"
                f"  Clinical summary: {_desc}\n"
                f"  Recommended action: {_action}\n"
            )
        _SYS = (
            "You are a Senior Clinical Pharmacist writing a structured drug interaction report.\n\n"
            + _drug_scope
            + _exclude_timing_note
            + "OUTPUT FORMAT  follow this structure exactly:\n\n"
            "** MAJOR INTERACTION DETECTED** (or MODERATE/MINOR as appropriate)\n"
            "**Drugs:** [Drug A] + [Drug B]\n\n"
            "**Mechanism:**\n"
            "Explain each drug's pathway separately  do NOT merge them.\n"
            "Antiplatelet effects (COX-1 inhibition) are DIFFERENT from anticoagulation "
            "(Vitamin K antagonism). State which pathway each drug uses.\n\n"
            "**Clinical Consequence:**\n"
            "Describe the combined effect and the specific risk (e.g., additive bleeding risk).\n\n"
            "**Monitoring:**\n"
            "- State specific lab tests (e.g., INR, CBC, renal function)\n"
            "- State monitoring frequency (e.g., 'check INR weekly')\n"
            "- State clinical signs to watch (e.g., bruising, dark/tarry stools, prolonged bleeding)\n\n"
            "**Clinical Recommendation:**\n"
            "State the action clearly (avoid / use with caution / dose adjustment / alternative).\n\n"
            "STRICT RULES:\n"
            "1. Base your answer on the verified references AND the database entry provided.\n"
            "2. Ignore any reference about a DIFFERENT drug pair  do NOT transfer its rules.\n"
            "3. NEVER invent INR thresholds, timing rules, or dose values not in the sources.\n"
            "4. End with: [Verify with a licensed pharmacist before any clinical decision]\n"
        ) + _db_warning + _rag_block

    else:
        _SYS = "You are a helpful Clinical Pharmacist AI assistant. Respond politely and concisely."

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
            "TASK: Write the full structured interaction report in the exact format "
            "specified in the system prompt. Start immediately with "
            "'**⚠️ MAJOR INTERACTION DETECTED**'. "
            "Bold all drug names and severity labels. "
            "Under Monitoring, explicitly list: INR frequency, bleeding signs "
            "(bruising, dark stools, prolonged bleeding time). "
            "Do NOT mention COX-1 timing rules unless both drugs are NSAIDs.\n"
            if _is_major else
            "Provide a structured pharmacist safety review in the format specified. "
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
                "num_ctx":     2048,
                "num_gpu":     0,
            },
        )

        answer = resp.response.strip()

        for _marker in ("<<SYS>>", "<</SYS>>", "[INST]", "[/INST]", "<s>", "</s>"):
            answer = answer.replace(_marker, "")
        answer = answer.strip()

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



