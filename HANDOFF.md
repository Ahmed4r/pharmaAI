# pharmaAI - Project Handoff Notes
# Last updated: 10 Mar 2026  (v7 - back buttons added; temp files cleaned; v6 BioMistral generate() fix)

---

## Project Root
C:\Users\ahmed\pharmaAI

---

## Files Present

| File                   | Lines | Description                                           |
|------------------------|-------|-------------------------------------------------------|
| app.py                 | ~1090 | Streamlit UI - all 5 pages + back buttons + connectors|
| ocr_engine.py          | ~670  | Real OCR pipeline (OpenCV + pytesseract + LLM refine) |
| .streamlit/config.toml |  15   | Clinical color theme                                  |
| requirements.txt       |   7   | Python dependencies list                              |
| HANDOFF.md             |  this | Project status + install guide                        |

---

## Color Theme (.streamlit/config.toml)

primaryColor             = #1A6B8A
backgroundColor          = #F0F4F8
secondaryBackgroundColor = #E3EEF7
textColor                = #0B3C5D
font                     = sans serif

---

## Environment (as of 10 Mar 2026)

Python    : 3.10 (Windows)
Streamlit : 1.55.0
Port      : http://localhost:8501
Run cmd   : streamlit run app.py   (from C:\Users\ahmed\pharmaAI)

---

## Dependency Status

Package                Status         Notes
-----------------------  -----------    ---------------------------------------
streamlit                INSTALLED      v1.55.0
numpy                    INSTALLED      v1.26.4
Pillow (PIL)             INSTALLED      v10.2.0
opencv-python            INSTALLED      v4.11.0  (cv2)
pandas                   INSTALLED      (used for parsed meds table in UI)
ollama (Python pkg)      INSTALLED      v0.17.7 client library
pytesseract              INSTALLED      pip install pytesseract (done)
requests                 INSTALLED      used for RxNav API calls
pdf2image                MISSING        pip install pdf2image  (only for PDFs)
Tesseract binary         INSTALLED      v5.5.0 at C:\Program Files\Tesseract-OCR\
Arabic tessdata          INSTALLED      ara.traineddata at Tesseract\tessdata\
Ollama desktop app       INSTALLED      v0.17.7 running on http://localhost:11434
BioMistral model         INSTALLED      adrienbrault/biomistral-7b:Q4_K_M  (4.4 GB)
Poppler (for PDF)        UNKNOWN        required by pdf2image - see Step 3 below

---

## INSTALL GUIDE (for new machine setup)

=======================================================================
STEP 1 - Install Tesseract OCR binary (Windows)
=======================================================================

1a. Download: https://github.com/UB-Mannheim/tesseract/wiki
    -> tesseract-ocr-w64-setup-5.x.x.x.exe  (64-bit)

1b. Install to default path: C:\Program Files\Tesseract-OCR\
    Check "English (eng)" and "Arabic (ara)" language data.

1c. Add to Windows PATH: C:\Program Files\Tesseract-OCR

1d. Verify: tesseract --version

=======================================================================
STEP 2 - Install Python packages
=======================================================================

    pip install pytesseract pdf2image requests

Full fresh install:
    pip install streamlit Pillow pytesseract opencv-python-headless numpy pandas requests python-dotenv ollama pdf2image

=======================================================================
STEP 3 - Install Poppler (needed ONLY for PDF prescriptions)
=======================================================================

3a. Download: https://github.com/oschwartz10612/poppler-windows/releases
3b. Extract to: C:\poppler\
3c. Add to PATH: C:\poppler\Library\bin
3d. Verify: pdftoppm -v

=======================================================================
STEP 4 - Install Ollama + BioMistral model
=======================================================================

4a. Install Ollama: winget install Ollama.Ollama
4b. Start server:  ollama serve
4c. Pull model:    ollama pull adrienbrault/biomistral-7b:Q4_K_M

    NOTE: "biomistral" and "meditron" are NOT in the Ollama public registry.
    The adrienbrault community tag is the only working one.

4d. App Settings page is pre-configured for this model.
    Click "Test Ollama Connection" to verify green checkmark.

=======================================================================
STEP 5 - Run the app
=======================================================================

    cd C:\Users\ahmed\pharmaAI
    streamlit run app.py

Open browser: http://localhost:8501

---

## What Is DONE

### ocr_engine.py (v5 - ~670 lines)

OCR pipeline stages:
  load -> upscale -> grayscale -> deskew -> denoise -> adaptive_threshold -> morph_close

Bilingual OCR:
  --oem 3 --psm 6 -l ara+eng  (Arabic + English LSTM engine)
  Confidence filter: words with conf < 40 or non-ASCII chars are discarded

BioMistral refinement layer (on-demand only - FIXED in v5; generate() fix in v6):
  _refine_with_llm(raw_text) is only called from the UI button (v5 fix).
  v6 fix: switched from chat() to generate(raw=True) using the same ChatML pattern
  as query_ollama_llm() (see above). Root cause was identical - Modelfile template
  does not accept the messages array format used by chat().
  - Sophisticated clinical prompt, JSON schema, temperature=0.1, num_predict=512
  - json.loads() validation with graceful plain-text fallback

_run_ocr() (v5 - FIXED):
  - Removed blocking LLM call: was `if mean_conf < 0.70: clean_text = _refine_with_llm(...)`
  - Now simply returns (clean_text, mean_conf) immediately after Tesseract
  - Result: OCR completes in ~1-3 seconds instead of 1-2 minutes

3-strategy regex parser (unchanged):
  1. Explicit Rx lines  (Rx 1 : DrugName 500mg)
  2. Known drug dictionary (60+ drugs: antibiotics, NSAIDs, PPIs, cardiac, diabetes, respiratory)
  3. Generic word+dose fallback
Extracts: medications {name, dose, unit, sig}, patient, date, prescriber, DEA number
CLI:  python ocr_engine.py prescription.png
API:  from ocr_engine import process_image_path, process_image_bytes

### app.py (v5 - ~1070 lines)

Navigation sidebar - FIXED in v5:
  Root causes found and fixed:
  1. Emoji icons were stripped from _NAV_OPTIONS (only spaces remained) - icons restored:
         Dashboard
         Prescription Scanner
         Drug Interaction Chat
         Drug Lookup
         Settings
  2. st.radio(index=_nav_idx) does NOT reliably drive programmatic navigation in Streamlit.
     Fix: Added key="nav_radio" to st.radio, then set session state directly:
       st.session_state["nav_radio"] = _NAV_OPTIONS[_NAV_LABELS.index(_nav_target)]
     This is the correct Streamlit pattern for widget state control.

  Navigation pattern (v5):
    # When a Quick Action button is clicked:
    st.session_state["nav_page"] = "Prescription Scanner"   # target label
    st.rerun()

    # At sidebar render time:
    _nav_target = st.session_state.pop("nav_page", None)
    if _nav_target and _nav_target in _NAV_LABELS:
        st.session_state["nav_radio"] = _NAV_OPTIONS[_NAV_LABELS.index(_nav_target)]
    page = st.radio("Navigation", options=_NAV_OPTIONS, key="nav_radio", ...)

Dashboard Quick Action buttons - FIXED in v5:
  Emoji icons restored on all three buttons:
      Scan New Prescription  -> nav_page = "Prescription Scanner"
      Open Drug Chat         -> nav_page = "Drug Interaction Chat"
      Lookup Drug Profile    -> nav_page = "Drug Lookup"

Prescription Scanner - " Refine with BioMistral AI" button (NEW in v5):
  Placed in the results column, above "Check Drug Interactions"
  Only visible after a file is uploaded and analysed
  On click:
    - Calls _refine_with_llm(extracted_text) inside a st.spinner
    - If LLM returns valid JSON: merges medications into parsed_meds table,
      updates medications list, patient/prescriber fields, then st.rerun()
    - If LLM returns plain text: updates extracted_text display, shows info banner
  This replaces the old automatic LLM call that caused the page crash.

query_ollama_llm() - REAL (v6 FIXED: generate instead of chat):
  - Root cause of empty output: model Modelfile uses generate-style template
    (.Prompt / .System fields). The chat() API passes a messages array that the
    template cannot render, so output is always an empty string.
  - Fix: switched to client.generate(model=..., prompt=full_prompt, raw=True)
    where full_prompt is a manually-built ChatML string:
        <|im_start|>system\n{system}\n<|im_end|>
        <|im_start|>user\n{message}\n<|im_end|>
        <|im_start|>assistant\n
  - Response is stripped of trailing <|im_end|> tokens via regex.
  - Full chat history still passed (built into ChatML string).
  - System prompt configurable from Settings page.
  - Graceful fallback message if Ollama is unreachable.

check_drug_interactions() - REAL RxNav REST API (unchanged from v4):
  - Step 1: resolves each drug name to RxCUI via GET /rxcui.json?name=<drug>&search=2
  - Step 2: queries GET /interaction/list.json?rxcuis=<cui1> <cui2> ...
  - Normalises severity: high/critical->major, moderate->moderate, low/minor->minor
  - Falls back to empty list (no crash) on any network error

Settings page:
  - Model dropdown: adrienbrault/biomistral-7b:Q4_K_M listed first
  - "Test Ollama Connection" calls ollama.Client().list() - real check, shows checkmark

### Session state keys
    chat_history  -> list of {role, content} dicts
    ocr_result    -> dict or None
                     keys: status, extracted_text, medications, parsed_meds,
                           patient, date, prescriber, dea, confidence, preprocessing, error
    nav_page      -> str (consumed on next rerun to set nav_radio)
    nav_radio     -> str (controls st.radio via key= binding)

### Tesseract + Arabic OCR
  Tesseract v5.5.0 at C:\Program Files\Tesseract-OCR\
  ara.traineddata manually placed at C:\Program Files\Tesseract-OCR\tessdata\
  OCR config: --oem 3 --psm 6 -l ara+eng

### UI - 5 pages (all complete)
  Dashboard           : KPI cards + activity feed + working quick action buttons (v5 fixed)
  Prescription Scanner: file uploader + fast OCR + on-demand AI refine + interaction check
  Drug Interaction Chat: persisted chat + suggested chips + st.chat_input (BioMistral)
  Drug Lookup         : search + quick buttons + full drug profile cards (3 drugs local)
  Settings            : Ollama config + real Test Connection + OCR engine + display prefs

Back buttons (NEW in v7):
  All 4 non-Dashboard pages now have a small " Dashboard" button at the top-left.
  Pattern: st.columns([1,7]) with st.button() that sets nav_page="Dashboard" + st.rerun()
  Keys: back_scanner, back_chat, back_lookup, back_settings

Back buttons (NEW in v7):
  All 4 non-Dashboard pages now have a small " Dashboard" button at the top-left.
  Pattern: st.columns([1,7]) with st.button() that sets nav_page="Dashboard" + st.rerun()
  Keys: back_scanner, back_chat, back_lookup, back_settings

---

## Bug History

| Version | Bug                                    | Root Cause                                          | Fix Applied                                      |
|---------|----------------------------------------|-----------------------------------------------------|--------------------------------------------------|
| v5      | Nav buttons did nothing                | Emojis stripped from _NAV_OPTIONS; index= unreliable| Restored emojis; switched to key= + session_state|
| v5      | OCR page popped/closed after upload    | Auto _refine_with_llm() blocked pipeline ~2 min     | Moved to on-demand button; _run_ocr() now instant |
| v4      | Quick Actions did nothing              | Missing st.session_state["nav_page"] before rerun   | Added session_state set before each st.rerun()   |
| v4      | Check interactions was stub            | Hardcoded demo data                                 | Full RxNav REST API integration                  |
| v4      | CONFIDENCE_FLOOR crashed pipeline      | RuntimeError thrown instead of graceful handling    | Replaced with _refine_with_llm() fallback        |
| v7      | No way to return from inner pages      | No back button on non-Dashboard pages               | Added ← Dashboard button top-left of all 4 pages |
| v6      | BioMistral always returns empty string | Modelfile uses generate template; chat() can't render messages | generate(raw=True)+manual ChatML prompt  |
| v7      | No way to return from inner pages      | No back button on non-Dashboard pages               | Added ← Dashboard button top-left of all 4 pages |
| v6      | BioMistral always returns empty string | Modelfile uses generate template; chat() can't render messages | generate(raw=True)+manual ChatML prompt  |
| v3      | BOM encoding errors                    | File saved with UTF-8 BOM                           | Resaved without BOM                              |
| v3      | PILImage NameError                     | Import alias mismatch                               | Fixed import                                     |
| v2      | Arabic OCR garbage output              | eng-only tessdata                                   | Added ara.traineddata, switched to ara+eng        |

---

## What Is STILL MISSING

Priority  Item
--------  ---------------------------------------------------------------
MEDIUM    lookup_drug_info() only has 3 drugs locally (amox/ibuprofen/omeprazole)
           Wire to: https://rxnav.nlm.nih.gov/  (free, no API key needed)
MEDIUM    Settings Save button does not persist to disk
           Fix: json.dump to config.json or os.environ via python-dotenv
MEDIUM    PDF support requires Poppler (see Step 3 in install guide)
LOW       Drug name list missing some brand names in _DRUG_NAME_HINTS (ocr_engine.py)
           Add: norvasc|plavix|coversyl|perindopril|diamicron|colchicine
LOW       CLAHE preprocessing not yet applied (improves contrast on faded prescriptions)
           In preprocess_image(), after grayscale step:
               clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
               gray = clahe.apply(gray)
               stages.append("clahe")
LOW       Split app.py into pages/ directory once backend is real
LOW       Auth layer for any non-local deployment
LOW       Audit log for dispensing decisions (regulatory requirement)

---

## How To Wire RxNorm into lookup_drug_info (future)

    import requests
    def lookup_drug_info(drug_name):
        r = requests.get("https://rxnav.nlm.nih.gov/REST/rxcui.json",
                         params={"name": drug_name}, timeout=6)
        cui = (r.json().get("idGroup", {}).get("rxnormId") or [None])[0]
        if not cui:
            return {}
        r2 = requests.get(f"https://rxnav.nlm.nih.gov/REST/rxcui/{cui}/properties.json", timeout=6)
        return r2.json().get("properties", {})

---

## How To Persist Settings to disk (future)

On Settings Save button click:
    import json
    json.dump({"ol_host": ol_host, "ol_model": ol_model, "ol_system_prompt": sys_prompt},
              open("config.json", "w"))

On app startup (before session state init):
    import json, os
    if os.path.exists("config.json"):
        cfg = json.load(open("config.json"))
        for k, v in cfg.items():
            if k not in st.session_state:
                st.session_state[k] = v