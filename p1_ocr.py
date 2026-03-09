import sys
path = r"C:\Users\ahmed\pharmaAI\ocr_engine.py"
src = open(path, encoding="utf-8").read()

# ---------- PATCH 1: new _refine_with_llm ----------
NEW1 = open(r"C:\Users\ahmed\pharmaAI\p1_new_refine.py", encoding="utf-8").read()

import re as _re
pat = _re.compile(r"def _refine_with_llm\(.*?\n(?=\ndef )", _re.DOTALL)
m = pat.search(src)
if m:
    src = src[:m.start()] + NEW1 + "\n\n" + src[m.end():]
    print("PATCH1: replaced _refine_with_llm OK")
else:
    print("PATCH1: FAILED - pattern not found")
    sys.exit(1)

# ---------- PATCH 2: replace confidence floor with LLM call ----------
OLD2 = "    # After computing mean_conf, before the return:\n    CONFIDENCE_FLOOR = 0.25\n    if mean_conf < CONFIDENCE_FLOOR and clean_text.strip():\n        raise RuntimeError(\n            f\"OCR confidence too low ({mean_conf:.0%}) \u2014 image may be too blurry or \"\n            \"at an extreme angle. Try a clearer photo.\"\n        )"
NEW2 = "    # LLM refinement: send to BioMistral when confidence < 70%\n    if mean_conf < 0.70 and clean_text.strip():\n        clean_text = _refine_with_llm(clean_text)"
if OLD2 in src:
    src = src.replace(OLD2, NEW2)
    print("PATCH2: confidence floor replaced OK")
else:
    print("PATCH2: trying alternate...")
    # look for any CONFIDENCE_FLOOR block
    alt = _re.compile(r"    # After computing mean_conf.*?raise RuntimeError\([^)]+\)\s*\)", _re.DOTALL)
    m2 = alt.search(src)
    if m2:
        src = src[:m2.start()] + NEW2 + src[m2.end():]
        print("PATCH2: alt replace OK")
    else:
        print("PATCH2: FAILED")
        sys.exit(1)

open(path, "w", encoding="utf-8").write(src)
print("ocr_engine.py saved.")
