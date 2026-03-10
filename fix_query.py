APP = r"c:\Users\ahmed\pharmaAI\app.py"

with open(APP, encoding="utf-8-sig") as f:
    src = f.read()

OLD = '''    # 4. System prompt  two modes: clinical 5-section vs conversational
    if _is_clinical:
        _SYS = (
            "You are a Senior Clinical Pharmacist AI.\\n"
            "Analyze the drug interaction or clinical case below.\\n\\n"
            "Your response must contain exactly five numbered sections:\\n"
            "  1. INTERACTION SUMMARY: classify as MAJOR, MODERATE, or MINOR; give a one-sentence reason.\\n"
            "  2. MECHANISM: explain the pharmacokinetic or pharmacodynamic basis.\\n"
            "  3. CLINICAL EFFECT: describe the consequences for the patient.\\n"
            "  4. MANAGEMENT: state the recommended clinician or pharmacist action.\\n"
            "  5. MONITORING: list the parameters to monitor (labs, vitals, symptoms).\\n\\n"
            "LANGUAGE: reply in the same language as the user; keep drug names and enzyme names in English.\\n"
            "Provide real clinical details. Do not copy these instructions into your answer.\\n"
            "IMPORTANT: Write ALL FIVE sections in one reply. Do not stop after section 1."
        ) + _rag_block
    else:
        _SYS = (
            "You are a helpful Clinical Pharmacist AI assistant. "
            "Respond politely and concisely. "
            "Match the language the user used (Arabic or English)."
        )

    # 5. Build raw ChatML prompt
    # client.chat() and generate(system=) trigger stop tokens on first token -- returns empty.
    # Raw generate with manual ChatML is the only reliable method for this model.
    if _is_clinical:
        _user_msg = f"Analyze this drug interaction or clinical case: {_msg}"
    else:
        _user_msg = _msg

    full_prompt = (
        f"<|im_start|>system\\n{_SYS}\\n<|im_end|>\\n"
        f"<|im_start|>user\\n{_user_msg}\\n<|im_end|>\\n"
        f"<|im_start|>assistant\\n"
    )

    # 6. Generate
    try:
        client = _ollama.Client(host=_HOST)
        resp = client.generate(
            model=_MODEL,
            prompt=full_prompt,
            raw=True,
            options={
                "num_predict": 2048,
                "temperature": 0.2,
                "top_p":       0.85,
                "num_ctx":     4096,
                "num_gpu":     20,
            },
        )
        answer = resp.response.strip()

        if len(answer) < 15:
            return "\\u26a0\\ufe0f \\u0644\\u0645 \\u064a\\u0635\\u062f\\u0631 \\u0627\\u0644\\u0645\\u0648\\u062f\\u064a\\u0644 \\u0631\\u062f\\u0627\\u064b. \\u062a\\u0623\\u0643\\u062f \\u0645\\u0646 \\u062a\\u0634\\u063a\\u064a\\u0644 Ollama \\u0648\\u0623\\u0639\\u062f \\u0627\\u0644\\u0645\\u062d\\u0627\\u0648\\u0644\\u0629."

        if rag_chunks and rag_chunks[0].get("score", 0) >= 0.65:
            from rag_engine import format_citations
            answer += f"\\n\\n---\\n{format_citations(rag_chunks)}"

        return answer'''

NEW = '''    # 4. System prompt  simple narrative (numbered section lists cause model to stop after 1-5 tokens)
    if _is_clinical:
        _SYS = (
            "You are a Senior Clinical Pharmacist AI. "
            "Give thorough, accurate clinical answers about drug interactions. "
            "Match the language the user used (Arabic or English)."
        ) + _rag_block
    else:
        _SYS = (
            "You are a helpful Clinical Pharmacist AI assistant. "
            "Respond politely and concisely. "
            "Match the language the user used (Arabic or English)."
        )

    # 5. Build raw ChatML prompt
    # client.chat() and generate(system=) trigger stop tokens on first token -- returns empty.
    # Raw generate with manual ChatML + stop=None is the only reliable method for this model.
    # Structured numbered-section prompts also cause the model to stop after 1-5 tokens;
    # instead we ask a free-form question covering all five clinical topics.
    if _is_clinical:
        _user_msg = (
            f"Tell me about this drug interaction or clinical case: {_msg}. "
            "Cover the severity level (MAJOR/MODERATE/MINOR), the pharmacological mechanism, "
            "the clinical effects on the patient, the management recommendations, "
            "and the monitoring parameters."
        )
    else:
        _user_msg = _msg

    full_prompt = (
        f"<|im_start|>system\\n{_SYS}\\n<|im_end|>\\n"
        f"<|im_start|>user\\n{_user_msg}\\n<|im_end|>\\n"
        f"<|im_start|>assistant\\n"
    )

    # 6. Generate
    try:
        client = _ollama.Client(host=_HOST)
        resp = client.generate(
            model=_MODEL,
            prompt=full_prompt,
            raw=True,
            options={
                "num_predict": 1500,
                "temperature": 0.2,
                "top_p":       0.85,
                "num_ctx":     2048,
                "num_gpu":     20,
                "stop":        None,   # disables ChatML <|im_end|> stop tokens from modelfile
            },
        )
        answer = resp.response.strip()

        if len(answer) < 15:
            return "\\u26a0\\ufe0f \\u0644\\u0645 \\u064a\\u0635\\u062f\\u0631 \\u0627\\u0644\\u0645\\u0648\\u062f\\u064a\\u0644 \\u0631\\u062f\\u0627\\u064b. \\u062a\\u0623\\u0643\\u062f \\u0645\\u0646 \\u062a\\u0634\\u063a\\u064a\\u0644 Ollama \\u0648\\u0623\\u0639\\u062f \\u0627\\u0644\\u0645\\u062d\\u0627\\u0648\\u0644\\u0629."

        if rag_chunks and rag_chunks[0].get("score", 0) >= 0.65:
            from rag_engine import format_citations
            answer += f"\\n\\n---\\n{format_citations(rag_chunks)}"

        return answer'''

if OLD not in src:
    print("OLD block NOT found  check indentation/content")
else:
    src = src.replace(OLD, NEW, 1)
    with open(APP, "w", encoding="utf-8") as f:
        f.write(src)
    print("Patch applied OK")
