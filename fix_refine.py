import pathlib

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\ocr_engine.py")
src = path.read_text(encoding="utf-8")

REFINE_FUNC = (
    "\n\ndef _refine_with_llm(raw_text: str, host: str = \"http://localhost:11434\") -> str:\n"
    "    \"\"\"\n"
    "    Send raw OCR text to BioMistral via Ollama for clinical correction.\n"
    "    Returns refined text, or original on any failure.\n"
    "    \"\"\"\n"
    "    try:\n"
    "        import ollama as _ollama\n"
    "        prompt = (\n"
    "            \"You are a clinical pharmacist. The following text was extracted by OCR \"\n"
    "            \"from a handwritten prescription and may contain errors.\\n\\n\"\n"
    "            \"Rules:\\n\"\n"
    "            \"- Correct obvious OCR errors in drug names and dosages only\\n\"\n"
    "            \"- Preserve ALL numbers exactly unless clearly wrong (e.g. 5OO -> 500)\\n\"\n"
    "            \"- Return ONLY the corrected prescription text, no explanation\\n\\n\"\n"
    "            f\"OCR TEXT:\\n{raw_text}\"\n"
    "        )\n"
    "        client = _ollama.Client(host=host)\n"
    "        response = client.chat(\n"
    "            model=\"adrienbrault/biomistral-7b:Q4_K_M\",\n"
    "            messages=[{\"role\": \"user\", \"content\": prompt}],\n"
    "        )\n"
    "        return response[\"message\"][\"content\"].strip()\n"
    "    except Exception:\n"
    "        return raw_text\n"
)

CALL_SITE_OLD = "    if not clean_text.strip():\n        clean_text = pytesseract.image_to_string(pil_img, config=_OCR_CONFIG)\n\n    return clean_text.strip(), round(mean_conf, 3)"
CALL_SITE_NEW = (
    "    if not clean_text.strip():\n"
    "        clean_text = pytesseract.image_to_string(pil_img, config=_OCR_CONFIG)\n\n"
    "    # AI refinement: fix OCR errors via BioMistral when confidence is low\n"
    "    if mean_conf < 0.70 and clean_text.strip():\n"
    "        clean_text = _refine_with_llm(clean_text)\n\n"
    "    return clean_text.strip(), round(mean_conf, 3)"
)

# Insert _refine_with_llm before def _run_ocr
if "_refine_with_llm" not in src:
    src = src.replace("def _run_ocr(", REFINE_FUNC + "\ndef _run_ocr(", 1)
    print("_refine_with_llm added")
else:
    print("_refine_with_llm already present")

# Add call site
if CALL_SITE_OLD in src:
    src = src.replace(CALL_SITE_OLD, CALL_SITE_NEW, 1)
    print("LLM call site wired")
else:
    print("call site not found")

path.write_text(src, encoding="utf-8")
print("Saved.")