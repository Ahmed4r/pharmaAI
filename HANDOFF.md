# pharmaAI - Project Handoff Notes
# Last updated: 10 Mar 2026  (v9 - Agentic RAG + ChromaDB + citation UI; v8 Arabic/bilingual chatbot)

---

## Project Root
C:\Users\ahmed\pharmaAI

---

## Files Present

| File                        | Lines | Description                                                       |
|-----------------------------|-------|-------------------------------------------------------------------|
| app.py                      | ~1264 | Streamlit UI - 5 pages, RAG integration, citation expander        |
| ocr_engine.py               | ~681  | Real OCR pipeline (OpenCV + pytesseract + LLM refine)             |
| rag_engine.py               | ~312  | ChromaDB RAG engine - retrieval, prompt augmentation, citations   |
| knowledge_base/drugs.json   |  31   | Clinical drug knowledge chunks (31 entries, UTF-8)                |
| knowledge_base/chroma_db/   |   -   | Persistent ChromaDB vector index (auto-created on first run)      |
| .streamlit/config.toml      |  15   | Clinical color theme                                              |
| requirements.txt            |   9   | Python dependencies list                                          |
| HANDOFF.md                  | this  | Project status + install guide                                    |

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

Package                  Status      Notes
streamlit                INSTALLED   v1.55.0
numpy                    INSTALLED   v1.26.4
Pillow (PIL)             INSTALLED   v10.2.0
opencv-python            INSTALLED   v4.11.0  (cv2)
pandas                   INSTALLED   used for parsed meds table in UI
ollama (Python pkg)      INSTALLED   v0.17.7 client library
pytesseract              INSTALLED   pip install pytesseract (done)
requests                 INSTALLED   used for RxNav API calls
chromadb                 INSTALLED   v1.5.4 - local vector store for RAG
pdf2image                MISSING     pip install pdf2image (only for PDFs)
Tesseract binary         INSTALLED   v5.5.0 at C:\Program Files\Tesseract-OCR\
Arabic tessdata          INSTALLED   ara.traineddata at Tesseract\tessdata\
Ollama desktop app       INSTALLED   v0.17.7 running on http://localhost:11434
BioMistral model         INSTALLED   adrienbrault/biomistral-7b:Q4_K_M  (4.4 GB)
ONNX MiniLM embeddings   CACHED      all-MiniLM-L6-v2 at C:\Users\ahmed\.cache\chroma\onnx_models\
Poppler (for PDF)        UNKNOWN     required by pdf2image

---

## INSTALL GUIDE

STEP 1 - Install Tesseract OCR (Windows)
  Download: https://github.com/UB-Mannheim/tesseract/wiki
  Install to C:\Program Files\Tesseract-OCR\ with eng + ara language data.
  Add C:\Program Files\Tesseract-OCR to PATH. Verify: tesseract --version

STEP 2 - Python packages
  pip install -r requirements.txt
  Full: pip install streamlit Pillow pytesseract opencv-python-headless numpy pandas requests python-dotenv ollama chromadb pdf2image

STEP 3 - Poppler (for PDF only)
  https://github.com/oschwartz10612/poppler-windows/releases
  Extract to C:\poppler\ ; add C:\poppler\Library\bin to PATH.

STEP 4 - Ollama + BioMistral
  winget install Ollama.Ollama
  ollama serve
  ollama pull adrienbrault/biomistral-7b:Q4_K_M
  NOTE: only adrienbrault community tag works (not in public registry).

STEP 5 - Run
  streamlit run app.py  ->  http://localhost:8501

  NOTE: On first chat message, ChromaDB will load the knowledge base from
  knowledge_base/chroma_db/ (pre-indexed). The ONNX embedding model is
  cached at C:\Users\ahmed\.cache\chroma\onnx_models\ after first run.

---

## What Is DONE

### rag_engine.py (v9 - ~312 lines)

ChromaDB-backed vector search with ONNX all-MiniLM-L6-v2 embeddings.
TF-IDF pure-Python fallback (activates if ChromaDB unavailable).
Knowledge base: 31 clinical drug chunks across 10+ drugs in knowledge_base/drugs.json.

Public API:
  retrieve(query, n_results=3, host)    -> list of {text, drug, category, id, score, source}
  build_rag_prompt(query, chunks)       -> ChatML-ready prompt with [REF 1][REF 2][REF 3] context
  format_citations(chunks)             -> Markdown citation block with relevance bars
  is_ready()                           -> True when index has documents
  rebuild_index(host)                  -> Drop + re-seed index from drugs.json

Drug coverage (drugs.json - 31 chunks):
  Amoxicillin, Ibuprofen, Warfarin (CYP2C9 interactions), Metformin,
  Omeprazole (CYP2C19/clopidogrel), Atorvastatin, Aspirin, Lisinopril,
  Clopidogrel, Furosemide, Paracetamol, Amlodipine
  + general topics: triple whammy (ACEi+NSAID+diuretic), anticoagulant bleeding,
    renal dosing adjustments, pregnancy drug safety

### ocr_engine.py (v6 - ~681 lines)

OCR pipeline: load -> upscale -> grayscale -> deskew -> denoise -> adaptive_threshold -> morph_close
Bilingual OCR: --oem 3 --psm 6 -l ara+eng  (Arabic + English LSTM)
Confidence filter: words conf < 40 or non-ASCII chars discarded

BioMistral refinement (_refine_with_llm):
  Only called on-demand from UI button (not automatically).
  Uses generate(raw=True) + manual ChatML string.
  Clinical JSON schema, temperature=0.1, num_predict=512, graceful fallback.

_run_ocr(): returns (clean_text, mean_conf) immediately after Tesseract. (~1-3 sec)
Parser: 3-strategy regex -> medications {name,dose,unit,sig}, patient, date, prescriber, DEA.

### app.py (v9 - ~1264 lines)

RAG integration (v9):
  - Imports rag_engine as _rag (line 4)
  - RAG retrieval block in query_ollama_llm() - top-3 chunks before LLM call
  - augmented_query injected into ChatML user turn (context + original question)
  - st.session_state["last_citations"] stores formatted citations per response
  - "Sources from knowledge base" expander shown below each chat answer

CUDA fix (v9):
  "num_gpu": 0 in Ollama generate options forces CPU-only inference.
  Prevents "unable to allocate CUDA0 buffer" error on low-VRAM GPUs.
  Trade-off: response time ~30-90s on CPU (vs instant on GPU).

Navigation (v5 fix):
  st.radio driven by key=nav_radio + direct session_state assignment (index= removed).
  Pattern: nav_page set -> rerun -> sidebar pops nav_page -> sets nav_radio.

query_ollama_llm() v6 fix:
  Root cause: Modelfile .Prompt/.System generate template; chat() messages array ignored.
  Fix: client.generate(raw=True) with manually-built ChatML full_prompt.
  Trailing <|im_end|> stripped via regex. Full history included.

query_ollama_llm() v8 - Arabic/bilingual:
  System prompt instructs auto-detection of user language:
    Arabic input  -> Arabic response (proper medical Arabic terminology)
    English input -> English response

check_drug_interactions() (v4): RxNav REST API - RxCUI lookup + interaction list.
  Severity: high/critical->major, moderate->moderate, low/minor->minor. Empty on error.

Back buttons (v7):
  All 4 non-Dashboard pages: st.columns([1,7]) button top-left sets nav_page=Dashboard.

Settings page: Ollama config + Test Connection (real ollama.Client().list()) + OCR config.

Session state keys:
  chat_history        list of {role,content}
  ocr_result          dict or None
  last_citations      formatted citation block for latest chat response
  nav_page / nav_radio  navigation control
  ol_host / ol_model / ol_system_prompt  (bilingual instruction since v8)

UI - 5 pages (complete):
  Dashboard / Prescription Scanner / Drug Interaction Chat / Drug Lookup / Settings

---

## Bug History

| Version | Bug / Change                              | Root Cause                                             | Fix Applied                                                    |
|---------|-------------------------------------------|--------------------------------------------------------|----------------------------------------------------------------|
| v9      | CUDA OOM: unable to allocate CUDA0 buffer | BioMistral 7B VRAM requirement exceeds GPU VRAM        | Added "num_gpu": 0 to generate options -> full CPU inference   |
| v9      | drugs.json UTF-8 BOM error                | PowerShell Out-File adds BOM, ChromaDB JSON parse fail | Re-saved via Python utf-8-sig read + utf-8 write              |
| v8      | Chatbot only replied in English           | System prompt had no language instruction              | Auto-detect: reply in user language (Arabic/English)           |
| v7      | No way to return from inner pages         | No back button on non-Dashboard pages                  | Added back button top-left on all 4 pages                      |
| v6      | BioMistral returned empty output          | Modelfile generate template; chat() array ignored      | generate(raw=True) + manual ChatML prompt                      |
| v5      | Nav buttons did nothing                   | Emojis stripped; index= unreliable                     | Restored emojis; key= + session_state assignment               |
| v5      | OCR page closed after upload              | Auto _refine_with_llm() blocked ~2 min                 | Moved to on-demand button; _run_ocr() instant                  |
| v4      | Quick Actions did nothing                 | Missing nav_page before rerun                          | Added session_state set before each st.rerun()                 |
| v4      | Drug interactions was stub                | Hardcoded demo data                                    | Full RxNav REST API integration                                |
| v4      | CONFIDENCE_FLOOR crashed pipeline         | RuntimeError not graceful                              | Replaced with _refine_with_llm() fallback                      |
| v3      | BOM encoding errors                       | File saved with UTF-8 BOM                              | Resaved without BOM                                            |
| v3      | PILImage NameError                        | Import alias mismatch                                  | Fixed import                                                   |
| v2      | Arabic OCR garbage output                 | eng-only tessdata                                      | Added ara.traineddata; switched to ara+eng                     |

---

## What Is STILL MISSING

Priority  Item
MEDIUM    lookup_drug_info() has only 3 local drugs - wire to RxNorm API (rxnav.nlm.nih.gov)
MEDIUM    Settings Save does not persist to disk - use config.json
MEDIUM    PDF support requires Poppler (see install guide)
MEDIUM    Expand knowledge_base/drugs.json - add more drugs and clinical guidelines
LOW       Add brand names to _DRUG_NAME_HINTS: norvasc|plavix|coversyl|perindopril|diamicron|colchicine
LOW       CLAHE preprocessing for faded prescriptions
LOW       Split app.py into pages/ directory
LOW       GPU inference: remove "num_gpu":0 if GPU has >= 5GB VRAM free (check: nvidia-smi)
LOW       Auth layer for non-local deployment
LOW       Audit log for dispensing decisions (regulatory requirement)
LOW       rebuild_index() trigger in Settings UI to refresh knowledge base after adding drugs

---

## Code Templates (future)

RxNorm drug lookup:
  cui = requests.get("https://rxnav.nlm.nih.gov/REST/rxcui.json", params={"name": name}).json()...
  props = requests.get(f"https://rxnav.nlm.nih.gov/REST/rxcui/{cui}/properties.json").json()...

Persist Settings:
  json.dump({"ol_host":..., "ol_model":..., "ol_system_prompt":...}, open("config.json","w"))
  # Startup: cfg=json.load(...); st.session_state.update({k:v for k,v in cfg.items() if k not in st.session_state})

Add drug to knowledge base:
  # Edit knowledge_base/drugs.json (same schema: {id, drug, category, text})
  # Then trigger rebuild in Python:
  import rag_engine as r
  r.rebuild_index()
  print("Ready:", r.is_ready())

Enable GPU inference (if VRAM >= 5GB):
  # In app.py line ~357, change:
  options={"num_predict": 1024, "temperature": 0.3, "repeat_penalty": 1.2, "num_gpu": 0}
  # To:
  options={"num_predict": 1024, "temperature": 0.3, "repeat_penalty": 1.2}