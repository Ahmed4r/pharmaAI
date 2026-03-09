# pharmaAI - Project Handoff Notes
# Last updated: 09 Mar 2026  (v2 - after OCR engine added)

---

## Project Root
C:\Users\ahmed\pharmaAI

---

## Files Present

| File                   | Lines | Description                                           |
|------------------------|-------|-------------------------------------------------------|
| app.py                 | ~930  | Streamlit UI - all 5 pages + backend connector calls  |
| ocr_engine.py          | 482   | Real OCR pipeline (OpenCV + pytesseract + regex)      |
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

## Environment (as of 09 Mar 2026)

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
ollama (Python pkg)      INSTALLED      (client library ready)
pytesseract              MISSING        pip install pytesseract
pdf2image                MISSING        pip install pdf2image
Tesseract binary         NOT INSTALLED  installer required - see Step 1 below
Ollama desktop app       UNKNOWN        winget install Ollama.Ollama
Poppler (for PDF)        UNKNOWN        required by pdf2image - see Step 3 below

---

## INSTALL GUIDE - What You Need To Do

Follow these steps IN ORDER to make everything work.

=======================================================================
STEP 1 - Install Tesseract OCR binary (Windows)
=======================================================================

1a. Download the Windows installer from:
    https://github.com/UB-Mannheim/tesseract/wiki
    -> Download: tesseract-ocr-w64-setup-5.x.x.x.exe  (64-bit)

1b. Run the installer.
    - Keep the default install path:
      C:\Program Files\Tesseract-OCR\tesseract.exe
    - On the "Additional language data" screen, check:
      * English (eng)   <- required
      * Arabic (ara)    <- optional, for Arabic prescriptions

1c. Add Tesseract to Windows PATH:
    - Open: Start > System > Advanced System Settings > Environment Variables
    - Under "System variables", click "Path" > Edit > New
    - Add: C:\Program Files\Tesseract-OCR
    - Click OK, restart any open terminals

1d. Verify in a new terminal:
    tesseract --version

=======================================================================
STEP 2 - Install missing Python packages
=======================================================================

Run this command once in your terminal:

    pip install pytesseract pdf2image

That is all that is missing. Everything else (cv2, numpy, PIL, pandas, ollama) is already installed.

Full install command if starting fresh:
    pip install streamlit Pillow pytesseract opencv-python-headless numpy pandas requests python-dotenv ollama pdf2image

=======================================================================
STEP 3 - Install Poppler (needed ONLY for PDF prescriptions)
=======================================================================

pdf2image requires Poppler to convert PDF pages to images.

3a. Download prebuilt Windows binaries from:
    https://github.com/oschwartz10612/poppler-windows/releases
    -> Download: Release-xx.xx.x-0.zip

3b. Extract to: C:\poppler\

3c. Add to Windows PATH:
    C:\poppler\Library\bin

3d. Verify in a new terminal:
    pdftoppm -v

You can skip Step 3 if you are only uploading PNG/JPG prescriptions.

=======================================================================
STEP 4 - Install and start Ollama (for the AI chat feature)
=======================================================================

4a. Install Ollama:
    winget install Ollama.Ollama
    OR download from: https://ollama.com/download

4b. Open a terminal and start the server:
    ollama serve

    Leave that terminal open. Ollama runs on http://localhost:11434

4c. Pull a medical AI model (choose one):
    ollama pull meditron          <- best for medical/pharmacy queries (3.8 GB)
    ollama pull llama3            <- good general purpose (4.7 GB)
    ollama pull mistral           <- fast and lightweight (4.1 GB)

4d. In the app, go to Settings > Ollama LLM Configuration:
    - Host:  http://localhost:11434
    - Model: meditron  (or whichever you pulled)
    - Click "Test Ollama Connection" to verify

=======================================================================
STEP 5 - Run the app
=======================================================================

    cd C:\Users\ahmed\pharmaAI
    streamlit run app.py

Open browser: http://localhost:8501

---

## What Is DONE

### ocr_engine.py (NEW - 482 lines)
Real OCR pipeline with:
- OpenCV preprocessing stages (all toggleable):
    load -> upscale -> grayscale -> deskew -> denoise -> adaptive_threshold -> morph_close
  - upscale      : rescales to >=1000px on long side (helps low-res scans)
  - deskew       : Hough-line rotation correction for tilted prescriptions
  - denoise      : Gaussian blur removes scanner/camera noise
  - adaptive_threshold : handles uneven lighting across handwritten pages
  - morph_close  : fills gaps in thin ink strokes
- pytesseract OCR with --oem 3 --psm 6 (LSTM engine, block text mode)
- Per-word confidence scoring -> mean confidence float 0-1
- 3-strategy regex parser:
    1. Explicit Rx lines  (Rx 1 : DrugName 500mg)
    2. Known drug dictionary (60+ drugs: antibiotics, NSAIDs, PPIs, cardiac, etc)
    3. Generic word+dose fallback
- Extracts: medications {name, dose, unit, sig}, patient, date, prescriber, DEA number
- Graceful degradation: works without cv2 (skips preprocessing) or pytesseract
- CLI:  python ocr_engine.py prescription.png
- API:  from ocr_engine import process_image_path, process_image_bytes

### app.py (UPDATED)
- process_prescription_ocr() now calls ocr_engine.process_image_bytes()
- Falls back to demo data with error banner if Tesseract is not installed
- Prescription Scanner page now shows:
    - Pipeline badge: stages applied (load -> grayscale -> deskew -> ...)
    - Parsed meds table: Drug | Dose | Sig/Directions  (pandas dataframe)
    - DEA number alert if detected
    - Error banner if OCR engine unavailable (instead of silent failure)

### UI - 5 pages (all previously completed)
Dashboard         : KPI cards + activity feed + quick actions
Prescription Scanner : file uploader + OCR + interaction check
Drug Interaction Chat: persisted chat + suggested chips + st.chat_input
Drug Lookup       : search + quick buttons + full drug profile cards (3 drugs local)
Settings          : Ollama config + OCR engine + drug DB + display prefs

### Session state keys
    chat_history  -> list of {role, content} dicts
    ocr_result    -> dict or None
                     keys: status, extracted_text, medications, parsed_meds,
                           patient, date, prescriber, dea, confidence, preprocessing, error

### Navigation
    active_page = page.split("  ", 1)[-1].strip()
    (derived from st.radio value in sidebar)

---

## What Is STILL MISSING

Priority  Item
--------  ---------------------------------------------------------------
HIGH      Tesseract binary not installed (see Step 1 above)
HIGH      pytesseract Python package not installed (see Step 2 above)
HIGH      Ollama + model not confirmed running (see Step 4 above)
HIGH      query_ollama_llm() is still a stub - needs real ollama.chat() wiring
HIGH      check_drug_interactions() is still a stub - no real API wired
MEDIUM    lookup_drug_info() only has 3 drugs locally (amox/ibuprofen/omeprazole)
           Wire to: https://rxnav.nlm.nih.gov/  (free, no API key needed)
MEDIUM    Dashboard quick-action buttons call st.rerun() but do NOT navigate
           Fix: set st.session_state["nav_page"] and use index= in st.radio
MEDIUM    Settings Save button does not persist to disk
           Fix: json.dump to config.json or os.environ via python-dotenv
MEDIUM    PDF support requires Poppler (see Step 3 above)
LOW       Split app.py into pages/ directory once backend is real
LOW       Auth layer for any non-local deployment
LOW       Audit log for dispensing decisions (regulatory requirement)

---

## How To Wire The Real Ollama LLM (query_ollama_llm in app.py)

Replace the body of query_ollama_llm() with:

    import ollama as _ollama
    SYSTEM_PROMPT = st.session_state.get(
        "ol_system_prompt",
        "You are an expert clinical pharmacist assistant..."
    )
    host  = st.session_state.get("ol_host",  "http://localhost:11434")
    model = st.session_state.get("ol_model", "meditron")
    client = _ollama.Client(host=host)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history
    messages.append({"role": "user", "content": user_message})
    response = client.chat(model=model, messages=messages)
    return response["message"]["content"]

---

## How To Wire Real Drug Interactions (check_drug_interactions in app.py)

RxNorm Interaction API - FREE, no API key needed:

    import requests
    def check_drug_interactions(drug_list):
        base = "https://rxnav.nlm.nih.gov/REST/interaction"
        results = []
        # Get RxCUI for each drug
        cuis = []
        for drug in drug_list:
            r = requests.get(f"{base}/../rxcui.json?name={drug}", timeout=8)
            cui = r.json().get("idGroup", {}).get("rxnormId", [None])[0]
            if cui:
                cuis.append(cui)
        # Check interactions
        if len(cuis) >= 2:
            r = requests.get(f"{base}/list.json?rxcuis={'+'.join(cuis)}", timeout=8)
            pairs = r.json().get("fullInteractionTypeGroup", [])
            for group in pairs:
                for itype in group.get("fullInteractionType", []):
                    for pair in itype.get("interactionPair", []):
                        results.append({
                            "drug_a":      pair["interactionConcept"][0]["minConceptItem"]["name"],
                            "drug_b":      pair["interactionConcept"][1]["minConceptItem"]["name"],
                            "severity":    pair.get("severity", "unknown").lower(),
                            "description": pair.get("description", ""),
                        })
        return results
