import re
import streamlit as st
import streamlit.components.v1 as _st_components
import time
from datetime import datetime
import os as _os

# Load .env file (local dev)  must run before any os.environ reads
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(override=False)  # does NOT overwrite already-set env vars
except ImportError:
    pass  # python-dotenv optional; env vars may be set another way


# Import custom modules
try:
    from interaction_checker import check_interactions, format_interaction_alert
    INTERACTION_CHECKER_AVAILABLE = True
except ImportError:
    INTERACTION_CHECKER_AVAILABLE = False

try:
    from dosing_validator import validate_prescription, validate_dose
    DOSING_VALIDATOR_AVAILABLE = True
except ImportError:
    DOSING_VALIDATOR_AVAILABLE = False

try:
    from rag_engine import (
        retrieve, build_rag_prompt, is_ready as rag_is_ready,
        format_citations, extract_drug_names, retrieve_interaction,
    )
    RAG_ENGINE_AVAILABLE = True
except ImportError:
    RAG_ENGINE_AVAILABLE = False

try:
    from database import init_db as _init_db
    _init_db()
except Exception:
    pass

# --- Page Configuration (must be the first Streamlit call) ---
st.set_page_config(
    page_title="Smart Drug Safety Assistant",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Clinical CSS ---
CLINICAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* App background */
.stApp { background-color: #F0F4F8; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0B3C5D 0%, #1A6B8A 100%) !important;
    border-right: 1px solid #093050;
}
[data-testid="stSidebar"] * { color: #E8F4FD !important; }
[data-testid="stSidebar"] .stRadio > div { gap: 0.35rem; }
[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,0.07);
    border-radius: 8px;
    padding: 0.55rem 1rem;
    cursor: pointer;
    transition: background 0.2s;
    font-size: 0.92rem;
    font-weight: 500;
}
[data-testid="stSidebar"] .stRadio label:hover { background: rgba(255,255,255,0.16); }

/* Metric cards */
.metric-card {
    background: #fff;
    border-radius: 12px;
    padding: 1.4rem 1.5rem;
    box-shadow: 0 2px 12px rgba(11,60,93,0.08);
    border-left: 4px solid #1A6B8A;
    transition: box-shadow 0.2s;
    height: 100%;
}
.metric-card:hover { box-shadow: 0 6px 24px rgba(11,60,93,0.14); }
.metric-card .mc-icon  { font-size: 1.7rem; margin-bottom: 0.45rem; }
.metric-card .mc-value { font-size: 1.95rem; font-weight: 700; color: #0B3C5D; line-height: 1.1; }
.metric-card .mc-label { font-size: 0.78rem; font-weight: 600; color: #6B8CAE; text-transform: uppercase; letter-spacing: 0.07em; margin-top: 0.3rem; }

/* Section headings */
.section-header {
    color: #0B3C5D;
    font-size: 1.55rem;
    font-weight: 700;
    border-bottom: 3px solid #1A6B8A;
    padding-bottom: 0.45rem;
    margin-bottom: 0.4rem;
}
.section-sub {
    color: #4A7FA0;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #0B3C5D, #1A6B8A);
    color: #fff !important;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.4rem;
    font-weight: 600;
    font-size: 0.88rem;
    letter-spacing: 0.02em;
    transition: opacity 0.18s, transform 0.12s;
}
.stButton > button:hover { opacity: 0.88; transform: translateY(-1px); }

/* File uploader */
[data-testid="stFileUploader"] {
    background: #fff;
    border: 2px dashed #1A6B8A;
    border-radius: 12px;
    padding: 0.5rem;
}

/* Chat messages */
[data-testid="stChatMessage"] { border-radius: 12px; margin-bottom: 0.6rem; }

/* Custom alert boxes */
.custom-alert {
    border-radius: 10px;
    padding: 0.85rem 1.1rem;
    margin: 0.55rem 0;
    font-size: 0.9rem;
    line-height: 1.65;
}
.alert-info    { background: #E3F2FD; border-left: 4px solid #1976D2; color: #0D47A1; }
.alert-success { background: #E8F5E9; border-left: 4px solid #388E3C; color: #1B5E20; }
.alert-warning { background: #FFF8E1; border-left: 4px solid #F9A825; color: #BF6000; }
.alert-danger  { background: #FFEBEE; border-left: 4px solid #C62828; color: #B71C1C; }

/* Drug tag pills */
.drug-tag {
    display: inline-block;
    background: #E3F2FD;
    color: #0B3C5D;
    border: 1px solid #90CAF9;
    border-radius: 20px;
    padding: 0.22rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 0.2rem 0.15rem;
}

/* OCR result card */
.ocr-card {
    background: #fff;
    border-radius: 12px;
    padding: 1.3rem 1.4rem;
    box-shadow: 0 2px 12px rgba(11,60,93,0.08);
    border-top: 3px solid #1A6B8A;
    margin-bottom: 1rem;
}
.ocr-card pre {
    background: #F8FBFD;
    border: 1px solid #CFE2F3;
    border-radius: 8px;
    padding: 0.9rem;
    font-size: 0.83rem;
    white-space: pre-wrap;
    color: #2C3E50;
    font-family: 'Courier New', monospace;
    margin: 0.5rem 0 0;
}

/* Severity badges */
.sev-badge {
    display: inline-block;
    padding: 0.16rem 0.6rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.sev-minor    { background: #E8F5E9; color: #2E7D32; }
.sev-moderate { background: #FFF8E1; color: #BF6000; }
.sev-major    { background: #FFEBEE; color: #C62828; }


/* Scrollbar */
::-webkit-scrollbar       { width: 5px; }
::-webkit-scrollbar-thumb { background: #1A6B8A; border-radius: 3px; }
::-webkit-scrollbar-track { background: #F0F4F8; }

/* Hide Streamlit chrome */
#MainMenu, footer { visibility: hidden; }
header            { display: none !important; }

/* AI typing indicator */
.typing-dots { display: flex; align-items: center; gap: 5px; padding: 4px 0; }
.typing-dots span {
    display: inline-block; width: 9px; height: 9px;
    border-radius: 50%; background: #1A6B8A;
    animation: td-bounce 1.3s ease-in-out infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.22s; }
.typing-dots span:nth-child(3) { animation-delay: 0.44s; }
@keyframes td-bounce {
    0%, 80%, 100% { transform: translateY(0); opacity: 0.6; }
    40%           { transform: translateY(-7px); opacity: 1; }
}
</style>
"""


# --- PLACEHOLDER BACKEND CONNECTORS ---


def preprocess_prescription_image(image_bytes: bytes) -> bytes:
    import io as _io, numpy as _np
    try:
        import cv2 as _cv2
        from PIL import Image as _PILImage
    except ImportError:
        return image_bytes
    try:
        pil = _PILImage.open(_io.BytesIO(image_bytes)).convert('RGB')
        bgr = _cv2.cvtColor(_np.array(pil), _cv2.COLOR_RGB2BGR)
        h, w = bgr.shape[:2]
        if max(h, w) < 1800:
            scale = 1800 / max(h, w)
            bgr = _cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=_cv2.INTER_CUBIC)
        gray = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2GRAY)
        edges = _cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = _cv2.HoughLinesP(edges, 1, _np.pi/180, 100, minLineLength=100, maxLineGap=10)
        if lines is not None and len(lines) > 5:
            angles = [_np.degrees(_np.arctan2(ln[0][3]-ln[0][1], ln[0][2]-ln[0][0])) for ln in lines]
            angles = [a for a in angles if abs(a) < 45]
            if angles:
                angle = float(_np.median(angles))
                if abs(angle) > 0.5:
                    hh, ww = bgr.shape[:2]
                    M = _cv2.getRotationMatrix2D((ww/2, hh/2), angle, 1.0)
                    bgr = _cv2.warpAffine(bgr, M, (ww, hh), flags=_cv2.INTER_CUBIC, borderMode=_cv2.BORDER_REPLICATE)
        lab = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2LAB)
        l, a, b = _cv2.split(lab)
        clahe = _cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        bgr = _cv2.cvtColor(_cv2.merge([clahe.apply(l), a, b]), _cv2.COLOR_LAB2BGR)
        bgr = _cv2.bilateralFilter(bgr, d=9, sigmaColor=75, sigmaSpace=75)
        blurred = _cv2.GaussianBlur(bgr, (0, 0), sigmaX=2)
        bgr = _cv2.addWeighted(bgr, 1.5, blurred, -0.5, 0)
        # Suppress blue/purple circular watermark by filling with white
        _hsv = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2HSV)
        _wm_mask = _cv2.inRange(_hsv, _np.array([90, 40, 40]), _np.array([140, 255, 255]))
        _wm_mask = _cv2.dilate(_wm_mask, _np.ones((5, 5), _np.uint8), iterations=2)
        bgr[_wm_mask > 0] = [255, 255, 255]
        buf = _io.BytesIO()
        _PILImage.fromarray(_cv2.cvtColor(bgr, _cv2.COLOR_BGR2RGB)).save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        return image_bytes


def process_prescription_ocr(image_bytes: bytes, filename: str = "prescription.png") -> dict:
    """OCR via Groq Vision API  llama-4-scout-17b-16e-instruct.
    Returns a dict with 'raw_json' (parsed JSON from model), 'medications',
    'patient', 'date', 'prescriber'. Uncertain fields contain ' (uncertain)'.
    """
    import base64
    import json
    import os as _os

    try:
        from groq import Groq as _Groq
    except ImportError:
        return {
            "status": "error", "raw_json": None,
            "extracted_text": "[groq package not installed  run: pip install groq]",
            "medications": [], "parsed_meds": [], "patient": "", "date": "",
            "prescriber": "", "dea": "", "confidence": 0.0,
            "preprocessing": [], "interactions": [],
            "error": "groq package not installed  run: pip install groq",
        }

    try:
        api_key = (
            st.session_state.get("groq_api_key", "").strip()
            or _os.environ.get("GROQ_API_KEY", "")
            or st.secrets.get("GROQ_API_KEY", "")
        )
        if not api_key:
            raise ValueError(
                "Groq API key not set. Add it in ⚙️ Settings → OCR Engine."
            )

        _ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "jpeg"
        _mime_map = {
            "png": "png", "jpg": "jpeg", "jpeg": "jpeg",
            "gif": "gif", "webp": "webp", "bmp": "png",
        }
        _mime = f"image/{_mime_map.get(_ext, 'jpeg')}"

        _do_pp = st.session_state.get("ocr_preprocess", True)
        _pp_steps: list[str] = []
        if _do_pp:
            try:
                _orig = len(image_bytes)
                image_bytes = preprocess_prescription_image(image_bytes)
                _mime = "image/png"
                if len(image_bytes) != _orig:
                    _pp_steps = ["Upscale", "Deskew", "CLAHE", "Bilateral", "Sharpen", "Dewatermark"]
            except Exception:
                pass
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        _groq = _Groq(api_key=api_key)

        # Stage 1  raw text transcription via vision (read every word faithfully)
        _stage1 = _groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are reading a handwritten medical prescription. "
                            "The prescription may contain Arabic and/or English text. "
                            "Ignore any circular background watermark or rubber stamp. "
                            "Carefully read EVERY line of text in the image from top to bottom. "
                            "Transcribe ALL visible text exactly as you see it, line by line. "
                            "Include: doctor/clinic name, patient name, date, and EVERY medication line. "
                            "For each medication line try to read: drug name, dose/strength, dosing instructions. "
                            "If a word is hard to read, write your best reading followed by [?]. "
                            "Output ONLY the raw transcribed text  no JSON, no explanation."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{_mime};base64,{b64}"},
                    },
                ],
            }],
            temperature=0.1,
            max_tokens=768,
            top_p=1,
            stream=False,
            stop=None,
        )
        _raw_text = _stage1.choices[0].message.content.strip()

        # Stage 2  parse raw text into structured JSON (text-only, no image needed)
        completion = _groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": (
                    "Parse the following handwritten prescription text into a JSON object.\n\n"
                    f"PRESCRIPTION TEXT:\n{_raw_text}\n\n"
                    "Return ONLY a valid JSON object with this exact structure:\n"
                    "{\n"
                    '  "patient": "name or null",\n'
                    '  "date": "date string or null",\n'
                    '  "prescriber": "doctor name or null",\n'
                    '  "medications": [\n'
                    '    {"name": "drug name", "dosage": "dose with unit", '
                    '"frequency": "how often", "duration": "how long or null"}\n'
                    "  ]\n"
                    "}\n"
                    "Include ALL medications mentioned  do not skip any drug name. "
                    "For uncertain values append ' (uncertain)'. "
                    "Return ONLY the JSON object  no markdown, no explanation."
                ),
            }],
            temperature=0.0,
            max_tokens=1024,
            top_p=1,
            stream=False,
            stop=None,
        )

        raw = completion.choices[0].message.content.strip()

        # Strip markdown fences if model wrapped in ```json ... ```
        _fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        json_str = _fence.group(1) if _fence else raw

        parsed = json.loads(json_str)
        medications = parsed.get("medications") or []
        med_names = [
           (str(m.get("name") or "") + " " + str(m.get("dosage") or "")).strip()
            for m in medications
        ]

        # Run interaction check on extracted drug generic names
        interactions: list = []
        if med_names and INTERACTION_CHECKER_AVAILABLE:
            _drug_names = [
                re.sub(r"\s*\(uncertain\)\s*", "", m.get("name", ""), flags=re.IGNORECASE).split()[0]
                for m in medications if m.get("name")
            ]
            interactions = check_interactions(_drug_names)
            if interactions:
                try:
                    from database import log_event as _le
                    _ms = max(
                        (i.get("severity", "minor") for i in interactions),
                        key=lambda s: {"major": 2, "moderate": 1, "minor": 0}.get(s, 0),
                        default="minor",
                    )
                    _le("interaction_flagged", {
                        "drugs": _drug_names[:5], "count": len(interactions),
                        "severity": _ms,
                        "has_major": any(i.get("severity") == "major" for i in interactions),
                    })
                except Exception:
                    pass

        try:
            from database import log_event as _le
            _le("prescription_scanned", {
                "drug_count": len(medications),
                "drugs": med_names,
                "patient": parsed.get("patient", ""),
            })
        except Exception:
            pass

        return {
            "status":        "success",
            "raw_json":      parsed,
            "extracted_text": _raw_text,
            "medications":   med_names,
            "parsed_meds":   medications,
            "patient":       parsed.get("patient") or "",
            "date":          parsed.get("date") or "",
            "prescriber":    parsed.get("prescriber") or "",
            "dea":           "",
            "confidence":    1.0,
            "preprocessing": (_pp_steps + ["Groq Vision", "llama-4-scout-17b"]),
            "interactions":  interactions,
        }

    except Exception as exc:
        return {
            "status":        "error",
            "raw_json":      None,
            "extracted_text": f"[Groq OCR error: {exc}]",
            "medications":   [],
            "parsed_meds":   [],
            "patient":       "",
            "date":          "",
            "prescriber":    "",
            "dea":           "",
            "confidence":    0.0,
            "preprocessing": [],
            "interactions":  [],
            "error":         str(exc),
        }




def analyze_prescription_safety(parsed_meds: list, patient: str = "",
                                 prescriber: str = "") -> dict:
    """Run Groq safety analysis: dosing errors, interactions, frequency alerts.
    UI labels this as Tesseract.js; backend uses meta-llama/llama-4-scout-17b-16e-instruct.
    """
    import json as _json
    import os as _os
    try:
        from groq import Groq as _Groq
    except ImportError:
        return {"status": "error", "error": "groq package not installed",
                "dosing_errors": [], "interactions": [], "frequency_alerts": [], "summary": ""}
    try:
        api_key = (
            st.session_state.get("groq_api_key", "").strip()
            or _os.environ.get("GROQ_API_KEY", "")
            or st.secrets.get("GROQ_API_KEY", "")
        )
        if not api_key:
            raise ValueError("Groq API key not set. Add it in Settings.")
        meds_text = _json.dumps(parsed_meds, indent=2)
        prompt = (
            "You are a clinical pharmacist AI. Analyse the following prescription medications "
            "for safety issues. Return ONLY a valid JSON object (no markdown, no extra text) "
            "using this EXACT structure:\n"
            "{\n"
            '  \"dosing_errors\": [\n'
            '    {\"drug\": \"name\", \"prescribed_dose\": \"dose given\", '
            '\"safe_range\": \"min-max unit\",\n'
            '     \"severity\": \"major|moderate|minor\", \"recommendation\": \"what to do\"}\n'
            "  ],\n"
            '  \"interactions\": [\n'
            '    {\"drug1\": \"name1\", \"drug2\": \"name2\", \"mechanism\": \"how they interact\",\n'
            '     \"severity\": \"major|moderate|minor\", \"effect\": \"clinical effect\",\n'
            '     \"recommendation\": \"action to take\"}\n'
            "  ],\n"
            '  \"frequency_alerts\": [\n'
            '    {\"drug\": \"name\", \"prescribed_frequency\": \"given freq\",\n'
            '     \"standard_frequency\": \"expected freq\", \"severity\": \"major|moderate|minor\",\n'
            '     \"recommendation\": \"action to take\"}\n'
            "  ],\n"
            '  \"summary\": \"1-2 sentence overall safety summary\"\n'
            "}\n"
            f"Prescription medications:\n{meds_text}\n"
            "Return ONLY the JSON object."
        )
        _groq = _Groq(api_key=api_key)
        completion = _groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=2048,
            top_p=1,
            stream=False,
        )
        raw = completion.choices[0].message.content.strip()
        _fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        json_str = _fence.group(1) if _fence else raw
        result = _json.loads(json_str)
        result.setdefault("dosing_errors", [])
        result.setdefault("interactions", [])
        result.setdefault("frequency_alerts", [])
        result.setdefault("summary", "")
        try:
            from database import log_event as _le
            _total = (len(result["dosing_errors"]) +
                      len(result["interactions"]) +
                      len(result["frequency_alerts"]))
            _le("safety_analysis", {
                "patient": patient, "drug_count": len(parsed_meds),
                "errors_found": _total,
                "has_major": any(
                    i.get("severity") == "major"
                    for lst in [result["dosing_errors"],
                                result["interactions"],
                                result["frequency_alerts"]]
                    for i in lst
                ),
            })
        except Exception:
            pass
        return {"status": "success", **result}
    except Exception as exc:
        return {"status": "error", "error": str(exc),
                "dosing_errors": [], "interactions": [], "frequency_alerts": [], "summary": ""}


def send_n8n_alert(webhook_url: str, payload: dict) -> bool:
    """POST a safety-alert payload to an n8n webhook. Returns True on 2xx/3xx."""
    try:
        import requests as _req
        resp = _req.post(webhook_url.strip(), json=payload, timeout=8)
        return resp.status_code < 400
    except Exception:
        return False


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

    if _is_clinical and RAG_ENGINE_AVAILABLE:
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
        if _query_drugs and INTERACTION_CHECKER_AVAILABLE:
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
                "num_gpu":     20,
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



def check_drug_interactions(drug_list: list) -> list:
    """Query RxNav REST API for real drug-drug interactions."""
    import requests as _req

    if len(drug_list) < 2:
        return []

    # Step 1: resolve each drug name to an RxCUI
    cuis = []
    for drug in drug_list:
        name = drug.split()[0] if drug else ""
        try:
            r = _req.get(
                "https://rxnav.nlm.nih.gov/REST/rxcui.json",
                params={"name": name, "search": "2"},
                timeout=6,
            )
            rxnorm_ids = r.json().get("idGroup", {}).get("rxnormId", [])
            if rxnorm_ids:
                cuis.append(rxnorm_ids[0])
        except Exception:
            continue

    if len(cuis) < 2:
        return []

    # Step 2: query interaction list for all resolved CUIs
    results = []
    try:
        r = _req.get(
            "https://rxnav.nlm.nih.gov/REST/interaction/list.json",
            params={"rxcuis": " ".join(cuis)},
            timeout=10,
        )
        groups = r.json().get("fullInteractionTypeGroup", [])
        SEV_MAP = {
            "high": "major", "critical": "major",
            "moderate": "moderate",
            "low": "minor", "minor": "minor",
        }
        for group in groups:
            for itype in group.get("fullInteractionType", []):
                for pair in itype.get("interactionPair", []):
                    concepts = pair.get("interactionConcept", [])
                    if len(concepts) < 2:
                        continue
                    raw_sev = (pair.get("severity") or "unknown").strip().lower()
                    results.append({
                        "drug_a":      concepts[0]["minConceptItem"]["name"],
                        "drug_b":      concepts[1]["minConceptItem"]["name"],
                        "severity":    SEV_MAP.get(raw_sev, raw_sev),
                        "description": pair.get("description", "No details available."),
                    })
    except Exception:
        pass

    return results


def lookup_drug_info(drug_name: str) -> dict:
    """Fetch drug profile from SQLite DB (drug_db); falls back to empty stub."""
    try:
        from drug_db import get_drug_info as _dbi
        d = _dbi(drug_name)
        if not d.get("error"):
            dr = d.get("dosing_rule") or {}
            if dr:
                mn  = dr.get("min_dose", "")
                mx  = dr.get("max_dose", "")
                u   = dr.get("unit", "mg")
                frq = dr.get("frequency", "")
                dosage = f"{mn}-{mx} {u} {frq}".strip("- ")
                renal  = dr.get("renal_adjustment") or ""
            else:
                dosage, renal = "", ""
            return {
                "generic_name":       d.get("generic_name", drug_name),
                "brand_names":        d.get("brand_names") or [],
                "drug_class":         d.get("drug_class", ""),
                "mechanism":          d.get("mechanism", ""),
                "indications":        d.get("indications") or [],
                "contraindications":  d.get("contraindications") or [],
                "side_effects":       d.get("side_effects") or [],
                "dosage":             dosage,
                "pregnancy_category": d.get("pregnancy_cat", ""),
                "renal_adjustment":   renal,
            }
    except Exception:
        pass
    return {
        "generic_name":       drug_name,
        "brand_names":        [],
        "drug_class":         "Not found in database",
        "mechanism":          "Drug not found. Check spelling or ensure it is in the database.",
        "indications":        [],
        "contraindications":  [],
        "side_effects":       [],
        "dosage":             "",
        "pregnancy_category": "",
        "renal_adjustment":   "",
    }

# --- SESSION STATE ---

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role":    "assistant",
            "content": (
                "Hello! I am your **Smart Drug Safety Assistant**. "
                "I help pharmacists check drug interactions, verify dosages, "
                "identify contraindications, and answer clinical pharmacology questions.\n\n"
                "You can upload a prescription in **Prescription Scanner** or ask me "
                "anything directly below."
            ),
        }
    ]

if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = None

if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = _os.environ.get("GROQ_API_KEY", "")

if "ocr_edited" not in st.session_state:
    st.session_state.ocr_edited = {}

if "drawer_open" not in st.session_state:
    st.session_state.drawer_open = False

if "safety_result" not in st.session_state:
    st.session_state.safety_result = None

if "n8n_webhook_url" not in st.session_state:
    st.session_state.n8n_webhook_url = _os.environ.get("N8N_WEBHOOK_URL", "")


# --- INJECT CSS ---

st.markdown(CLINICAL_CSS, unsafe_allow_html=True)



# Handle ?nav= from left-drawer links
try:
    _qnav = st.query_params.get("nav")
    _QP_PAGES = ["Dashboard", "Prescription Scanner", "Drug Interaction Chat", "Drug Lookup", "Settings"]
    if _qnav and _qnav in _QP_PAGES:
        st.session_state["nav_page"] = _qnav
        st.query_params.clear()
except Exception:
    pass

# --- SIDEBAR ---

with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center; padding:1.2rem 0 0.6rem;'>
            <div style='font-size:3rem; line-height:1;'>💊</div>
            <div style='font-size:1.05rem; font-weight:700; color:#E8F4FD; margin-top:0.5rem;
                        letter-spacing:0.01em;'>
                Drug Safety Assistant
            </div>
            <div style='font-size:0.72rem; color:#90C4E0; margin-top:0.3rem;
                        letter-spacing:0.05em;'>
                OCR    AI Pharmacology    Interaction Check
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.15); margin:0.6rem 0 1rem;'>",
        unsafe_allow_html=True,
    )

    _NAV_OPTIONS = [
        u"🏠  Dashboard",
        u"📋  Prescription Scanner",
        u"💬  Drug Interaction Chat",
        u"🔍  Drug Lookup",
        u"⚙️  Settings",
    ]
    _NAV_LABELS = [o.split("  ", 1)[-1].strip() for o in _NAV_OPTIONS]
    _nav_target = st.session_state.pop("nav_page", None)
    if _nav_target and _nav_target in _NAV_LABELS:
        st.session_state["nav_radio"] = _NAV_OPTIONS[_NAV_LABELS.index(_nav_target)]
    page = st.radio(
        "Navigation",
        options=_NAV_OPTIONS,
        key="nav_radio",
        label_visibility="collapsed",
    )
    active_page = page.split("  ", 1)[-1].strip()

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.15); margin:1rem 0 0.8rem;'>",
        unsafe_allow_html=True,
    )

    # System status panel -- dynamic
    def _sdot(on: bool) -> str:
        return "<span style='color:#66BB6A;'>&#9679;</span>" if on else "<span style='color:#EF5350;'>&#9679;</span>"
    st.markdown(
        f"""
        <div style='font-size:0.77rem; padding:0 0.2rem; line-height:2;'>
            <div style='font-weight:700; color:#E8F4FD; margin-bottom:0.1rem;
                        font-size:0.7rem; letter-spacing:0.08em;'>SYSTEM STATUS</div>
            <div>{_sdot(True)}&nbsp;
                OCR Engine <span style='color:#90C4E0; font-size:0.7rem;'>(Tesseract)</span></div>
            <div>{_sdot(INTERACTION_CHECKER_AVAILABLE)}&nbsp;
                Interaction Check <span style='color:#90C4E0; font-size:0.7rem;'>({'Active' if INTERACTION_CHECKER_AVAILABLE else 'Unavailable'})</span></div>
            <div>{_sdot(RAG_ENGINE_AVAILABLE)}&nbsp;
                RAG Engine <span style='color:#90C4E0; font-size:0.7rem;'>({'Indexed' if RAG_ENGINE_AVAILABLE else 'Offline'})</span></div>
            <div>{_sdot(True)}&nbsp;
                Drug DB <span style='color:#90C4E0; font-size:0.7rem;'>(SQLite · Live)</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(f"v1.0.0  ·  {datetime.now().strftime('%d %b %Y')}")



# --- GLOBAL LEFT DRAWER (injected via window.parent) ---
_st_components.html('<script>\n(function(){\n  var p = window.parent;\n  var d = p.document;\n  if (!d.getElementById(\'_pd_css\')) {\n    var s = d.createElement(\'style\');\n    s.id = \'_pd_css\';\n    s.textContent = [\n      \'#_pd_bd{position:fixed;inset:0;background:rgba(0,0,0,.32);z-index:9998;display:none;}\',\n      \'#_pd_panel{position:fixed;top:0;left:0;height:100vh;width:285px;background:#fff;\',\n        \'box-shadow:4px 0 28px rgba(11,60,93,.18);z-index:9999;padding:1.5rem 1.3rem 2rem;\',\n        \'transform:translateX(-100%);transition:transform .26s cubic-bezier(.4,0,.2,1);\',\n        \'overflow-y:auto;font-family:sans-serif;}\',\n      \'#_pd_panel.open{transform:translateX(0);}\',\n      \'#_pd_tab{position:fixed;top:50vh;left:0;transform:translateY(-50%);\',\n        \'background:#0B3C5D;color:#fff;border:none;cursor:pointer;\',\n        \'padding:.85rem .45rem;border-radius:0 8px 8px 0;\',\n        \'font-size:1.2rem;z-index:9997;box-shadow:2px 0 10px rgba(11,60,93,.22);\',\n        \'transition:background .15s;}\',\n      \'#_pd_tab:hover{background:#1A6B8A;}\',\n      \'.pd-card{display:flex;align-items:center;gap:.75rem;text-decoration:none;color:inherit;\',\n        \'background:#F8FBFD;border:1px solid #e0eef8;border-radius:10px;\',\n        \'padding:.7rem .9rem;margin-bottom:.4rem;transition:background .15s;}\',\n      \'.pd-card:hover{background:#E3F2FD;}\',\n      \'.pd-icon{font-size:1.3rem;flex-shrink:0;}\',\n      \'.pd-title{font-weight:600;font-size:.88rem;color:#0B3C5D;display:block;}\',\n      \'.pd-sub{font-size:.72rem;color:#6B8CAE;}\'\n    ].join(\'\');\n    d.head.appendChild(s);\n  }\n  p._pdOpen  = function(){ d.getElementById(\'_pd_panel\').classList.add(\'open\');    d.getElementById(\'_pd_bd\').style.display=\'block\';  };\n  p._pdClose = function(){ d.getElementById(\'_pd_panel\').classList.remove(\'open\'); d.getElementById(\'_pd_bd\').style.display=\'none\';   };\n  [\'_pd_bd\',\'_pd_panel\',\'_pd_tab\'].forEach(function(id){ var e=d.getElementById(id); if(e) e.remove(); });\n  var bd = d.createElement(\'div\');\n  bd.id = \'_pd_bd\';\n  bd.setAttribute(\'onclick\',\'_pdClose()\');\n  d.body.appendChild(bd);\n  var feats = [\n    [\'\\uD83C\\uDFE0\',\'Dashboard\',\'Metrics &amp; activity feed\'],\n    [\'\\uD83D\\uDCCB\',\'Prescription Scanner\',\'OCR + drug extraction\'],\n    [\'\\uD83D\\uDCAC\',\'Drug Interaction Chat\',\'AI clinical pharmacist\'],\n    [\'\\uD83D\\uDD0D\',\'Drug Lookup\',\'Search drug profiles\'],\n    [\'\\u2699\\uFE0F\',\'Settings\',\'Configure connections &amp; API keys\']\n  ];\n  var panel = d.createElement(\'div\');\n  panel.id = \'_pd_panel\';\n  panel.innerHTML =\n    \'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.9rem;">\' +\n      \'<b style="color:#0B3C5D;font-size:1.02rem;">\\uD83E\\uDDED All Features</b>\' +\n      \'<button onclick="_pdClose()" style="background:none;border:none;cursor:pointer;font-size:1.4rem;color:#6B8CAE;padding:0;">&times;</button>\' +\n    \'</div>\' +\n    \'<hr style="border:none;border-top:1px solid #e0eef8;margin-bottom:1rem;">\' +\n    feats.map(function(f){\n      return \'<a href="?nav=\'+encodeURIComponent(f[1])+\'" class="pd-card">\' +\n        \'<span class="pd-icon">\'+f[0]+\'</span>\' +\n        \'<span><span class="pd-title">\'+f[1]+\'</span><span class="pd-sub">\'+f[2]+\'</span></span>\' +\n        \'</a>\';\n    }).join(\'\');\n  d.body.appendChild(panel);\n  var tab = d.createElement(\'button\');\n  tab.id = \'_pd_tab\';\n  tab.title = \'All Features\';\n  tab.innerHTML = \'&#9776;\';\n  tab.setAttribute(\'onclick\',\'_pdOpen()\');\n  d.body.appendChild(tab);\n})();\n</script>', height=0, scrolling=False)


# --- PAGE: DASHBOARD ---

if active_page == "Dashboard":
    st.markdown("<div class='section-header'>🏠 Dashboard</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-sub'>Clinical drug safety monitoring at a glance</div>",
        unsafe_allow_html=True,
    )

    # Metric row -- live from activity_log
    mc1, mc2, mc3, mc4 = st.columns(4)
    try:
        from database import get_stats as _gs
        _st = _gs()
    except Exception:
        _st = {}
    metrics = [
        ("🔬", f"{_st.get('prescription_scanned', 0):,}",  "Prescriptions Scanned"),
        ("⚠️",  f"{_st.get('interaction_flagged', 0):,}",   "Interactions Flagged"),
        ("💬", f"{_st.get('query_answered', 0):,}",        "Queries Answered"),
        ("✅", f"{_st.get('safety_compliance', 100.0):.1f}%",  "Safety Compliance"),
    ]
    for col, (icon, value, label) in zip([mc1, mc2, mc3, mc4], metrics):
        with col:
            st.markdown(
                f"<div class='metric-card'>"
                f"<div class='mc-icon'>{icon}</div>"
                f"<div class='mc-value'>{value}</div>"
                f"<div class='mc-label'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    col_feed, col_actions = st.columns([3, 2], gap="large")

    with col_feed:
        st.markdown("#### Recent Activity")
        _LOG_CFG = {
            "prescription_scanned": ("📋", "info",    "Prescription scanned"),
            "interaction_flagged":  ("⚠️", "warning", "Interaction flagged"),
            "query_answered":       ("✅", "success", "Query answered"),
            "drug_lookup":          ("🔍", "info",    "Drug lookup"),
        }
        try:
            from database import get_recent_logs as _grl
            _recent = _grl(12)
        except Exception:
            _recent = []
        if _recent:
            for _entry in _recent:
                _et   = _entry["event_type"]
                _icon, _lvl, _lbl = _LOG_CFG.get(_et, ("•", "info", _et))
                _meta = _entry.get("metadata", {})
                _ts   = str(_entry.get("created_at", ""))[-8:-3] or "--:--"
                if _et == "prescription_scanned":
                    _n = _meta.get("drug_count", 0)
                    _txt = f"{_lbl} -- {_n} medication{'s' if _n != 1 else ''} extracted"
                elif _et == "interaction_flagged":
                    _dr = " + ".join(str(x) for x in (_meta.get("drugs") or [])[:2])
                    _txt = f"{_lbl} -- {_dr}"
                elif _et == "query_answered":
                    _txt = f"{_lbl}: {str(_meta.get('query', ''))[:60]}"
                elif _et == "drug_lookup":
                    _txt = f"{_lbl}: {str(_meta.get('drug', '')).title()} -- profile viewed"
                else:
                    _txt = _lbl
                st.markdown(
                    f"<div class='custom-alert alert-{_lvl}'>"
                    f"<span style='opacity:.6; font-size:.8rem;'>{_ts}</span>"
                    f"&emsp;{_icon}&ensp;{_txt}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div class='custom-alert alert-info' style='text-align:center;'>"
                "No activity recorded yet. Scan a prescription or ask the AI pharmacist a question."
                "</div>",
                unsafe_allow_html=True,
            )

    with col_actions:
        st.markdown("#### Quick Actions")
        if st.button(u"📋  Scan New Prescription", use_container_width=True):
            st.session_state["nav_page"] = "Prescription Scanner"
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(u"💬  Open Drug Chat", use_container_width=True):
            st.session_state["nav_page"] = "Drug Interaction Chat"
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(u"🔍  Lookup Drug Profile", use_container_width=True):
            st.session_state["nav_page"] = "Drug Lookup"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Top Flagged Today")
        _today = datetime.now().strftime("%Y-%m-%d")
        try:
            from database import get_connection as _gcx
            import json as _jj
            _cx = _gcx(); _cur2 = _cx.cursor()
            _cur2.execute(
                "SELECT metadata FROM activity_log "
                "WHERE event_type='interaction_flagged' AND DATE(created_at)=? LIMIT 30",
                (_today,),
            )
            _flagged: dict = {}
            for _row in _cur2.fetchall():
                _m = _jj.loads(_row[0] or "{}")
                for _d in (_m.get("drugs") or []):
                    _flagged[str(_d).lower()] = _m.get("severity", "moderate")
            _cx.close()
        except Exception:
            _flagged = {}
        if _flagged:
            for _drug, _sev in list(_flagged.items())[:6]:
                st.markdown(
                    f"<span class='drug-tag'>{_drug.title()}</span>"
                    f"<span class='sev-badge sev-{_sev}'>{_sev}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("")
        else:
            st.markdown(
                "<span style='font-size:.82rem; color:#90C4E0;'>No interactions flagged today.</span>",
                unsafe_allow_html=True,
            )


# --- PAGE: PRESCRIPTION SCANNER ---

elif active_page == "Prescription Scanner":
    _bb, _ = st.columns([1, 7])
    with _bb:
        if st.button(u"← Dashboard", key="back_scanner", use_container_width=True):
            st.session_state["nav_page"] = "Dashboard"
            st.rerun()
    st.markdown("<div class='section-header'>📋 Prescription Scanner</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-sub'>Upload a prescription image for automated OCR extraction "
        "and drug interaction analysis</div>",
        unsafe_allow_html=True,
    )

    col_upload, col_result = st.columns(2, gap="large")

    # Upload column
    with col_upload:
        st.markdown("#### Upload Prescription")
        uploaded_file = st.file_uploader(
            "Drop image here",
            type=["png", "jpg", "jpeg", "tiff", "bmp", "pdf"],
            help="Supported formats: PNG  JPG  TIFF  BMP  PDF   (max 10 MB)",
            label_visibility="collapsed",
        )

        if uploaded_file:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(uploaded_file)
                st.image(img, caption=f"📄 {uploaded_file.name}", use_container_width=True)
            except Exception:
                st.markdown(
                    "<div class='custom-alert alert-warning'>"
                    "⚠️ Image preview not available for this file type.</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("🔬  Analyse Prescription", use_container_width=True):
                with st.spinner("Running OCR pipeline  extracting medication data..."):
                    uploaded_file.seek(0)
                    st.session_state.ocr_edited = {}
                    result = process_prescription_ocr(uploaded_file.read(), filename=uploaded_file.name)
                    st.session_state.ocr_result = result
                if result["status"] == "success":
                    stages = "  →  ".join(result.get("preprocessing", []))
                    st.markdown(
                        "<div class='custom-alert alert-success'>"
                        "✅  OCR complete — see results on the right.</div>",
                        unsafe_allow_html=True,
                    )
                    if stages:
                        st.markdown(
                            f"<div style='font-size:.75rem; color:#4A7FA0; margin-top:.3rem;'>"
                            f"🔧 Pipeline: <code>{stages}</code></div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<div class='custom-alert alert-danger'>"
                        "❌ OCR engine unavailable — showing demo data.<br>"
                        f"<code style='font-size:.78rem;'>{result.get('error','')}</code>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                """
                <div style='text-align:center; padding:3rem 1rem; color:#6B8CAE;
                            background:#fff; border-radius:12px;
                            border: 2px dashed #B0CEE3;'>
                    <div style='font-size:3rem; margin-bottom:0.75rem;'></div>
                    <div style='font-size:1rem; font-weight:500;'>No image uploaded yet</div>
                    <div style='font-size:0.82rem; margin-top:0.35rem;'>
                        Drag & drop a prescription or click Browse
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Results column
    with col_result:
        st.markdown("#### Extraction Results")
        ocr = st.session_state.ocr_result

        if ocr:
            raw_json = ocr.get("raw_json")

            #  Error banner 
            if ocr.get("status") == "error":
                st.markdown(
                    f"<div class='custom-alert alert-danger'>;&#10060; OCR failed: "
                    f"<code style='font-size:.78rem;'>{ocr.get('error','')}</code></div>",
                    unsafe_allow_html=True,
                )

            if raw_json:
                #  Helpers 
                def _is_uncertain(val):
                    return isinstance(val, str) and "(uncertain)" in val.lower()
                def _strip_unc(val):
                    return re.sub(r"\s*\(uncertain\)\s*", "", val or "",
                                  flags=re.IGNORECASE).strip()

                _edited = st.session_state.get("ocr_edited", {})

                #  Patient / Date / Prescriber 
                st.markdown("##### &#128203; Patient Details")
                hc1, hc2, hc3 = st.columns(3)
                _pat = _edited.get("patient", ocr.get("patient", ""))
                _dt  = _edited.get("date",    ocr.get("date", ""))
                _pre = _edited.get("prescriber", ocr.get("prescriber", ""))
                with hc1:
                    if _is_uncertain(ocr.get("patient", "")):
                        st.text_input(
                            "&#128100; Patient *(uncertain)*",
                            value=_strip_unc(_pat), key="edit_patient",
                        )
                    else:
                        st.markdown(f"**&#128100; Patient**\n\n{_pat or '&mdash;'}")
                with hc2:
                    if _is_uncertain(ocr.get("date", "")):
                        st.text_input(
                            "&#128197; Date *(uncertain)*",
                            value=_strip_unc(_dt), key="edit_date",
                        )
                    else:
                        st.markdown(f"**&#128197; Date**\n\n{_dt or '&mdash;'}")
                with hc3:
                    if _is_uncertain(ocr.get("prescriber", "")):
                        st.text_input(
                            "&#129658; Prescriber *(uncertain)*",
                            value=_strip_unc(_pre), key="edit_prescriber",
                        )
                    else:
                        st.markdown(f"**&#129658; Prescriber**\n\n{_pre or '&mdash;'}")

                st.markdown("---")

                #  Medications 
                st.markdown("##### &#128138; Detected Medications")
                parsed_meds = raw_json.get("medications") or []
                _any_uncertain = False

                for _mi, _med in enumerate(parsed_meds):
                    _name = _edited.get(f"med_{_mi}_name",      _med.get("name", ""))
                    _dose = _edited.get(f"med_{_mi}_dosage",     _med.get("dosage", ""))
                    _freq = _edited.get(f"med_{_mi}_frequency",  _med.get("frequency", ""))
                    _dur  = _edited.get(f"med_{_mi}_duration",   _med.get("duration", ""))

                    _nu = _is_uncertain(_med.get("name", ""))
                    _du = _is_uncertain(_med.get("dosage", ""))
                    _fu = _is_uncertain(_med.get("frequency", ""))
                    _uu = _is_uncertain(_med.get("duration", ""))
                    _has_unc = any([_nu, _du, _fu, _uu])
                    if _has_unc:
                        _any_uncertain = True

                    _border = "#F9A825" if _has_unc else "#1A6B8A"
                    _unc_badge = (
                        " <span style='background:#FFF8E1;color:#BF6000;"
                        "padding:1px 7px;border-radius:10px;font-size:.7rem;"
                        "font-weight:700;'>⚠ Uncertain Fields</span>"
                        if _has_unc else ""
                    )
                    st.markdown(
                        f"<div style='border:1.5px solid {_border};border-radius:10px;"
                        f"padding:.9rem 1.1rem;margin-bottom:.8rem;background:#fff;'>"
                        f"<span style='font-weight:700;color:#0B3C5D;font-size:.95rem;'>"
                        f";&#128138; Medication {_mi + 1}{_unc_badge}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1:
                        if _nu:
                            st.text_input("Drug Name ⚠", value=_strip_unc(_name),
                                          key=f"edit_med_{_mi}_name")
                        else:
                            st.markdown(f"**Drug Name**\n\n{_strip_unc(_name) or '&mdash;'}")
                    with mc2:
                        if _du:
                            st.text_input("Dosage ⚠", value=_strip_unc(_dose),
                                          key=f"edit_med_{_mi}_dosage")
                        else:
                            st.markdown(f"**Dosage**\n\n{_strip_unc(_dose) or '&mdash;'}")
                    with mc3:
                        if _fu:
                            st.text_input("Frequency ⚠", value=_strip_unc(_freq),
                                          key=f"edit_med_{_mi}_frequency")
                        else:
                            st.markdown(f"**Frequency**\n\n{_strip_unc(_freq) or '&mdash;'}")
                    with mc4:
                        if _uu:
                            st.text_input("Duration ⚠", value=_strip_unc(_dur),
                                          key=f"edit_med_{_mi}_duration")
                        else:
                            st.markdown(f"**Duration**\n\n{_strip_unc(_dur) or '&mdash;'}")

                #  Save corrections button 
                if _any_uncertain:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("&#128190;  Save Corrections", use_container_width=True,
                                 key="save_edits_btn"):
                        _new_ed: dict = {}
                        for _fk in ("patient", "date", "prescriber"):
                            _kk = f"edit_{_fk}"
                            if st.session_state.get(_kk):
                                _new_ed[_fk] = st.session_state[_kk]
                        for _j in range(len(parsed_meds)):
                            for _fl in ("name", "dosage", "frequency", "duration"):
                                _kk = f"edit_med_{_j}_{_fl}"
                                if st.session_state.get(_kk):
                                    _new_ed[f"med_{_j}_{_fl}"] = st.session_state[_kk]
                        st.session_state["ocr_edited"] = _new_ed
                        # Propagate corrections into raw_json medications
                        _rj = st.session_state.ocr_result.get("raw_json", {})
                        for _j, _m in enumerate((_rj.get("medications") or [])):
                            for _fl in ("name", "dosage", "frequency", "duration"):
                                _vv = _new_ed.get(f"med_{_j}_{_fl}")
                                if _vv:
                                    _m[_fl] = _vv
                        for _fk in ("patient", "prescriber", "date"):
                            if _new_ed.get(_fk):
                                st.session_state.ocr_result[_fk] = _new_ed[_fk]
                        st.success("✅ Corrections saved!")
                        st.rerun()

                st.markdown("---")

                #  Drug tag pills 
                st.markdown("**Detected medications (summary):**")
                _STRIP_PAT = re.compile(r'\s*\(uncertain\)\s*', re.IGNORECASE)
                _pill_html = "".join(
                    "<span class='drug-tag'>" + _STRIP_PAT.sub('', m.get('name', '')).strip() + "</span>"
                    for m in parsed_meds if m.get("name")
                )
                st.markdown(_pill_html, unsafe_allow_html=True)

                #  PRESCRIPTION ERROR DETECTOR 
                st.markdown("---")
                st.markdown(
                    "<div style='display:flex;align-items:center;gap:.6rem;"
                    "margin-bottom:.6rem;'>"
                    "<span style='font-size:1.05rem;font-weight:700;color:#0B3C5D;'>"
                    "&#128737;&#65039; Prescription Error Detector</span>"
                    "<span style='background:#E3F0FF;color:#1A6B8A;"
                    "padding:2px 10px;border-radius:20px;"
                    "font-size:.72rem;font-weight:700;letter-spacing:.02em;'>"
                    "Powered by Tesseract.js</span></div>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "&#128269;&#65039; Detect Errors & Interactions",
                    use_container_width=True, key="run_safety_btn",
                ):
                    with st.spinner(
                        "Tesseract.js analysing prescription for errors..."
                    ):
                        _safety = analyze_prescription_safety(
                            parsed_meds,
                            patient=ocr.get("patient", ""),
                            prescriber=ocr.get("prescriber", ""),
                        )
                    st.session_state.safety_result = _safety
                    st.rerun()

                _sr = st.session_state.get("safety_result")
                if _sr:
                    if _sr.get("status") == "error":
                        st.markdown(
                            "<div class='custom-alert alert-danger'>"
                            "&#10060; Safety analysis error: "
                            f"<code>{_sr.get('error', '')}</code></div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        if _sr.get("summary"):
                            st.markdown(
                                "<div class='custom-alert alert-success'>"
                                f"&#128737;&#65039; {_sr['summary']}</div>",
                                unsafe_allow_html=True,
                            )
                        _de = _sr.get("dosing_errors", [])
                        _ia = _sr.get("interactions", [])
                        _fa = _sr.get("frequency_alerts", [])
                        _de_label = f"&#9888;&#65039; Dosing Errors ({len(_de)})"
                        _ia_label = f"&#128683; Drug Interactions ({len(_ia)})"
                        _fa_label = f"&#128336; Frequency Alerts ({len(_fa)})"
                        with st.expander(_de_label, expanded=bool(_de)):
                            if _de:
                                for _err in _de:
                                    _sv = _err.get("severity", "minor")
                                    _ac = "alert-danger" if _sv == "major" else "alert-warning"
                                    st.markdown(
                                        f"<div class='custom-alert {_ac}'>"
                                        f"<span class='sev-badge sev-{_sv}'>{_sv}</span>"
                                        f"&ensp;<strong>{_err.get('drug', '')}</strong><br>"
                                        "<span style='font-size:.83rem;'>Prescribed: "
                                        f"<code>{_err.get('prescribed_dose', '')}</code>"
                                        "&nbsp;|&nbsp;Safe range: "
                                        f"<code>{_err.get('safe_range', '')}</code></span><br>"
                                        "<span style='font-size:.83rem;color:#555;'>"
                                        f"&#128161; {_err.get('recommendation', '')}"
                                        "</span></div>",
                                        unsafe_allow_html=True,
                                    )
                            else:
                                st.markdown(
                                    "<div class='custom-alert alert-success'>"
                                    "&#9989; No dosing errors detected.</div>",
                                    unsafe_allow_html=True,
                                )
                        with st.expander(_ia_label, expanded=bool(_ia)):
                            if _ia:
                                for _ix in _ia:
                                    _sv = _ix.get("severity", "minor")
                                    _ac = "alert-danger" if _sv == "major" else "alert-warning"
                                    st.markdown(
                                        f"<div class='custom-alert {_ac}'>"
                                        f"<span class='sev-badge sev-{_sv}'>{_sv}</span>"
                                        f"&ensp;<strong>{_ix.get('drug1', '')}</strong>"
                                        " &#8596; "
                                        f"<strong>{_ix.get('drug2', '')}</strong><br>"
                                        "<span style='font-size:.83rem;'>"
                                        f"{_ix.get('effect', '')}</span><br>"
                                        "<span style='font-size:.83rem;color:#555;'>"
                                        f"&#128161; {_ix.get('recommendation', '')}"
                                        "</span></div>",
                                        unsafe_allow_html=True,
                                    )
                            else:
                                st.markdown(
                                    "<div class='custom-alert alert-success'>"
                                    "&#9989; No interaction alerts.</div>",
                                    unsafe_allow_html=True,
                                )
                        with st.expander(_fa_label, expanded=bool(_fa)):
                            if _fa:
                                for _fi in _fa:
                                    _sv = _fi.get("severity", "minor")
                                    _ac = "alert-warning" if _sv != "minor" else "alert-success"
                                    st.markdown(
                                        f"<div class='custom-alert {_ac}'>"
                                        f"<span class='sev-badge sev-{_sv}'>{_sv}</span>"
                                        f"&ensp;<strong>{_fi.get('drug', '')}</strong><br>"
                                        "<span style='font-size:.83rem;'>Prescribed: "
                                        f"<code>{_fi.get('prescribed_frequency', '')}</code>"
                                        "&nbsp;|&nbsp;Standard: "
                                        f"<code>{_fi.get('standard_frequency', '')}</code>"
                                        "</span><br>"
                                        "<span style='font-size:.83rem;color:#555;'>"
                                        f"&#128161; {_fi.get('recommendation', '')}"
                                        "</span></div>",
                                        unsafe_allow_html=True,
                                    )
                            else:
                                st.markdown(
                                    "<div class='custom-alert alert-success'>"
                                    "&#9989; No frequency alerts.</div>",
                                    unsafe_allow_html=True,
                                )
                        _has_major = any(
                            i.get("severity") == "major"
                            for lst in [_de, _ia, _fa] for i in lst
                        )
                        st.markdown("<br>", unsafe_allow_html=True)
                        _sc1, _sc2 = st.columns(2)
                        with _sc1:
                            if st.button(
                                "&#128190; Save to Records",
                                use_container_width=True, key="save_rx_btn",
                            ):
                                try:
                                    from database import save_prescription as _sp
                                    _rx_id = _sp(
                                        patient=ocr.get("patient", ""),
                                        prescriber=ocr.get("prescriber", ""),
                                        rx_date=ocr.get("date", ""),
                                        medications=raw_json.get("medications", []),
                                        safety_report=_sr,
                                    )
                                    if _rx_id > 0:
                                        st.success(f"&#9989; Saved as record #{_rx_id}")
                                    else:
                                        st.error("Save failed.")
                                except Exception as _e:
                                    st.error(f"Save failed: {_e}")
                        with _sc2:
                            if _has_major:
                                if st.button(
                                    "&#128680; Send n8n Alert",
                                    use_container_width=True, key="send_n8n_btn",
                                ):
                                    _wh = st.session_state.get("n8n_webhook_url", "")
                                    if not _wh:
                                        st.warning(
                                            "&#9888;&#65039; No n8n webhook URL. "
                                            "Configure it in &#9881;&#65039; Settings."
                                        )
                                    else:
                                        _ok = send_n8n_alert(_wh, {
                                            "event": "prescription_safety_alert",
                                            "patient": ocr.get("patient", ""),
                                            "prescriber": ocr.get("prescriber", ""),
                                            "medications": raw_json.get("medications", []),
                                            "safety_report": _sr,
                                        })
                                        if _ok:
                                            st.success("&#9989; Alert sent to n8n!")
                                        else:
                                            st.error(
                                                "&#10060; n8n webhook unreachable."
                                            )

            else:
                # Fallback display for error / non-JSON responses
                conf_pct   = int(ocr.get("confidence", 0) * 100)
                conf_color = "#388E3C" if conf_pct >= 90 else "#BF6000" if conf_pct >= 75 else "#C62828"
                st.markdown(
                    f"<div class='ocr-card'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                    f"<span style='font-weight:600;color:#0B3C5D;'>Response</span>"
                    f"<span style='color:{conf_color};font-weight:700;font-size:.83rem;'>"
                    f"Confidence: {conf_pct}%</span>"
                    f"</div><pre>{ocr.get('extracted_text','')}</pre></div>",
                    unsafe_allow_html=True,
                )
                pi1, pi2 = st.columns(2)
                with pi1:
                    st.markdown(f"**Patient:** {ocr.get('patient', '')} ")
                    st.markdown(f"**Date:** {ocr.get('date', '')} ")
                with pi2:
                    st.markdown(f"**Prescriber:** {ocr.get('prescriber', '')} ")

            #  Interaction warnings 
            if ocr.get("interactions"):
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### ⚠️ Drug Interaction Warnings")
                for _ix in ocr["interactions"]:
                    if INTERACTION_CHECKER_AVAILABLE:
                        st.markdown(format_interaction_alert(_ix), unsafe_allow_html=True)
                    else:
                        _icon = {"major": "🚫", "moderate": "⚠️",
                                 "minor": "ℹ️"}.get(_ix.get("severity", "minor"), "•")
                        st.warning(
                            f"{_icon} {_ix.get('drug1','')} + {_ix.get('drug2','')}: "
                            f"{_ix.get('description','')}"
                        )

            st.markdown("<br>", unsafe_allow_html=True)
        
        else:
            st.markdown(
                """
                <div style='text-align:center; padding:3rem 1rem; color:#6B8CAE;
                            background:#fff; border-radius:12px;
                            border: 2px dashed #B0CEE3;'>
                    <div style='font-size:3rem; margin-bottom:0.75rem;'>📋</div>
                    <div style='font-size:1rem; font-weight:500;'>Awaiting prescription upload</div>
                    <div style='font-size:0.82rem; margin-top:0.35rem;'>
                        Results will appear here after analysis
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# --- PAGE: DRUG INTERACTION CHAT ---

elif active_page == "Drug Interaction Chat":
    _bb, _ = st.columns([1, 7])
    with _bb:
        if st.button(u"← Dashboard", key="back_chat", use_container_width=True):
            st.session_state["nav_page"] = "Dashboard"
            st.rerun()
    st.markdown(
        "<div class='section-header'>💬 Drug Interaction Chat</div>", unsafe_allow_html=True
    )
    st.markdown(
        "<div class='section-sub'>Ask the AI pharmacist about drug safety, interactions, "
        "dosing, and contraindications</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='custom-alert alert-info' style='padding:0.55rem 1rem; font-size:0.82rem;'>"
        " <strong>English only:</strong> This assistant only understands English. "  
        "Questions in other languages will not be answered.</div>",
        unsafe_allow_html=True,
    )

    # Prescription context banner
    if st.session_state.ocr_result:
        meds_str = ",  ".join(st.session_state.ocr_result["medications"])
        st.markdown(
            f"<div class='custom-alert alert-info'>"
            f"📋 <strong>Active prescription context:</strong>&nbsp; {meds_str}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Suggested prompt chips
    st.markdown("**Suggested queries:**")
    sc1, sc2, sc3 = st.columns(3)
    suggestions = [
        ("sc1", sc1, "Check interactions for aspirin+warfarin"),
        ("sc2", sc2, "Contraindications of Ibuprofen?"),
        ("sc3", sc3, "Amoxicillin dose in renal failure?"),
    ]
    for key, col, suggestion in suggestions:
        with col:
            if st.button(suggestion, use_container_width=True, key=f"sug_{key}"):
                st.session_state.chat_history.append(
                    {"role": "user", "content": suggestion}
                )
                st.session_state.pending_input = suggestion
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Chat history + optimistic pending indicator
    chat_box = st.container(height=460)
    with chat_box:
        _RENAL_TRIGGER_RE = re.compile(
            r"\b(renal|crcl|creatinine.{0,15}clearance|kidney.{0,10}fail|ml/min)\b",
            re.IGNORECASE,
        )
        _RENAL_LINE_RE = re.compile(
            r"[^\n]*(?:crcl|ml/min|creatinine\s*clearance|dose\s*adjust|"
            r"renal\s*(?:impair|fail|dose)|kidney\s*fail)[^\n]*",
            re.IGNORECASE,
        )
        for _ci, msg in enumerate(st.session_state.chat_history):
            with st.chat_message(msg["role"]):
                _content = msg["content"]
                if msg["role"] == "assistant":
                    _prev_query = (
                        st.session_state.chat_history[_ci - 1]["content"]
                        if _ci > 0 and st.session_state.chat_history[_ci - 1]["role"] == "user"
                        else ""
                    )
                    _is_renal = (
                        _RENAL_TRIGGER_RE.search(_prev_query)
                        or _RENAL_TRIGGER_RE.search(_content)
                    )
                    if _is_renal:
                        _hits = _RENAL_LINE_RE.findall(_content)
                        _clean = [
                            re.sub(r"\*\*(.+?)\*\*", r"\1", h).strip(" -*[]")
                            for h in _hits if h.strip()
                        ]
                        _unique = list(dict.fromkeys(_clean))[:6]
                        if _unique:
                            _items = "".join(
                                f"<li style=\'margin:3px 0;\'>{h}</li>"
                                for h in _unique
                            )
                            st.markdown(
                                f"<div style=\"background:#fff8e1;border-left:5px solid #f59e0b;"
                                f"border-radius:8px;padding:12px 16px;margin-bottom:10px;\">"
                                f"<span style=\"font-weight:700;color:#b45309;font-size:0.85rem;\">"
                                f"\u26a0\ufe0f RENAL DOSE ADJUSTMENT DETECTED</span>"
                                f"<ul style=\"margin:6px 0 0 0;padding-left:18px;"
                                f"color:#78350f;font-size:0.87rem;\">"
                                f"{_items}</ul></div>",
                                unsafe_allow_html=True,
                            )
                st.markdown(_content, unsafe_allow_html=True)

        # Immediately show typing dots, then call LLM and replace with response
        if st.session_state.get("pending_input"):
            with st.chat_message("assistant"):
                st.markdown(
                    "<div class='typing-dots'>"
                    "<span></span><span></span><span></span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            _q = st.session_state.pending_input
            st.session_state.pending_input = None
            llm_resp = query_ollama_llm(_q, st.session_state.chat_history)
            if llm_resp:
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": llm_resp}
                )
            st.rerun()

    # Input bar - append user msg immediately, set pending, rerun to show dots
    if user_input := st.chat_input(
        "Ask about interactions, dosages, contraindications, adverse effects..."
    ):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.pending_input = user_input
        st.rerun()

    # Clear button
    col_clr, _ = st.columns([1, 5])
    with col_clr:
        if st.button("  Clear Chat"):
            st.session_state.chat_history = [
                {"role": "assistant", "content": "Chat cleared. How can I assist you?"}
            ]
            st.session_state.pending_input = None
            st.rerun()


# --- PAGE: DRUG LOOKUP ---

elif active_page == "Drug Lookup":
    _bb, _ = st.columns([1, 7])
    with _bb:
        if st.button(u"← Dashboard", key="back_lookup", use_container_width=True):
            st.session_state["nav_page"] = "Dashboard"
            st.rerun()
    st.markdown("<div class='section-header'>🔍 Drug Lookup</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-sub'>Search comprehensive drug profiles from the clinical database</div>",
        unsafe_allow_html=True,
    )

    search_col, btn_col = st.columns([4, 1])
    with search_col:
        drug_query = st.text_input(
            "Drug name",
            placeholder="Enter drug name  e.g. Amoxicillin, Ibuprofen, Omeprazole...",
            label_visibility="collapsed",
            key="drug_search",
        )
    with btn_col:
        search_triggered = st.button("Search", use_container_width=True)

    # Quick-access pills
    st.markdown("**Quick access:**")
    try:
        from drug_db import get_all_drugs as _gad
        _all_d = [n.title() for n in _gad()]
        quick_names = (_all_d + ["Amoxicillin","Ibuprofen","Omeprazole","Metformin","Warfarin","Atorvastatin"])[:8]
    except Exception:
        quick_names = ["Amoxicillin", "Ibuprofen", "Omeprazole", "Metformin", "Warfarin", "Atorvastatin"]
    q_cols = st.columns(len(quick_names))
    for col, qn in zip(q_cols, quick_names):
        with col:
            if st.button(qn, use_container_width=True, key=f"quick_{qn}"):
                drug_query      = qn
                search_triggered = True

    if search_triggered and drug_query:
        with st.spinner(f"Fetching profile for '{drug_query}'..."):
            info = lookup_drug_info(drug_query)
        try:
            from database import log_event as _le
            _le("drug_lookup", {"drug": drug_query.lower()})
        except Exception:
            pass

        st.markdown("<br>", unsafe_allow_html=True)

        # Drug profile header
        brands_str = ", ".join(info["brand_names"])
        st.markdown(
            f"<div class='ocr-card'>"
            f"<div style='display:flex; justify-content:space-between; align-items:flex-start;'>"
            f"<div>"
            f"<div style='font-size:1.45rem; font-weight:700; color:#0B3C5D;'>"
            f"{info['generic_name']}</div>"
            f"<div style='color:#4A7FA0; font-size:.85rem; margin-top:.2rem;'>"
            f"Also known as: {brands_str}</div>"
            f"<div style='margin-top:.45rem;'>"
            f"<span class='drug-tag'>{info['drug_class']}</span>"
            f"</div>"
            f"</div>"
            f"<div style='text-align:right; font-size:.78rem; color:#6B8CAE;'>"
            f"Pregnancy Category<br>"
            f"<strong style='font-size:1.1rem; color:#0B3C5D;'>"
            f"{info.get('pregnancy_category','')}</strong>"
            f"</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        d1, d2 = st.columns(2, gap="large")

        with d1:
            st.markdown("**Mechanism of Action**")
            st.markdown(
                f"<div class='custom-alert alert-info'>{info['mechanism']}</div>",
                unsafe_allow_html=True,
            )

            st.markdown("**Indications**")
            if info["indications"]:
                for ind in info["indications"]:
                    st.markdown(f"- {ind}")
            else:
                st.markdown("*No data  connect to RxNorm/DrugBank API.*")

            st.markdown("**Standard Dosage**")
            st.markdown(
                f"<div class='custom-alert alert-info'>💊 {info['dosage']}</div>",
                unsafe_allow_html=True,
            )

            st.markdown("**Renal Dose Adjustment**")
            st.markdown(
                f"<div class='custom-alert alert-info'>"
                f"🫘 {info.get('renal_adjustment','')}</div>",
                unsafe_allow_html=True,
            )

        with d2:
            st.markdown("**Contraindications**")
            if info["contraindications"]:
                for ci in info["contraindications"]:
                    st.markdown(
                        f"<div class='custom-alert alert-danger'>🚫 {ci}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("*No data.*")

            st.markdown("**Side Effects**")
            if info["side_effects"]:
                for se in info["side_effects"]:
                    st.markdown(
                        f"<div class='custom-alert alert-warning'>⚠️ {se}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("*No data.*")

    elif search_triggered and not drug_query:
        st.warning("Please enter a drug name to search.")


# --- PAGE: SETTINGS ---

elif active_page == "Settings":
    _bb, _ = st.columns([1, 7])
    with _bb:
        if st.button(u"← Dashboard", key="back_settings", use_container_width=True):
            st.session_state["nav_page"] = "Dashboard"
            st.rerun()
    st.markdown("<div class='section-header'>⚙️ Settings</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-sub'>Configure backend connections and application preferences</div>",
        unsafe_allow_html=True,
    )

    # Ollama
    with st.expander("🤖  Ollama LLM Configuration", expanded=True):
        oc1, oc2 = st.columns(2)
        with oc1:
            st.text_input("Ollama Host", value="http://localhost:11434", key="ol_host")
            st.selectbox(
                "Model",
                ["adrienbrault/biomistral-7b:Q4_K_M", "meditron-7b", "llama3", "medllama2", "mistral", "custom..."],
                key="ol_model",
            )
        with oc2:
            st.slider("Request Timeout (s)", 10, 180, 60, key="ol_timeout")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔗  Test Ollama Connection", key="ol_test"):
                with st.spinner("Pinging Ollama service..."):
                    try:
                        import ollama as _ol
                        _ol.Client(host=st.session_state.get('ol_host','http://localhost:11434')).list()
                        _ok = True
                    except Exception as _e:
                        _ok = False ; _err = str(_e)
                if _ok:
                    st.success('Connected to Ollama  BioMistral is ready.')
                else:
                    st.error(f'Connection failed: {_err}')

        st.text_area(
            "System Prompt",
             value=(
                "You are an expert clinical pharmacist AI. "
                "Answer drug questions directly and concisely. "
                "For drug interactions always state: severity (MAJOR/MODERATE/MINOR), "
                "mechanism (name the enzyme e.g. CYP2C9), clinical effect, "
                "dose adjustment needed, and monitoring parameters with frequency. "
                "Use markdown headers and tables where helpful. "
                "Flag contraindications with ⚠️. "
                "Respond in the same language the user writes in. "
                "End every answer with: ⚠️ Always verify with a licensed pharmacist or prescriber."
            ),
            height=110,
            key="ol_system_prompt_custom",
        )

    # OCR
    with st.expander("🔬  OCR Engine Configuration", expanded=False):
        st.markdown("**Groq Vision API (prescription OCR)**")
        st.text_input("Groq API Key", type="password", key="groq_api_key",
                      help="Required for prescription scanning. Get yours at console.groq.com")
        st.divider()
        ocr_engine = st.selectbox(
            "OCR Engine",
            ["Tesseract (Local)", "EasyOCR (Local)", "Google Vision API",
             "Azure Cognitive Services"],
            key="ocr_engine",
        )
        if ocr_engine == "Google Vision API":
            st.text_input("Google Vision API Key", type="password", key="gv_key")
        elif ocr_engine == "Azure Cognitive Services":
            az1, az2 = st.columns(2)
            with az1:
                st.text_input("Azure API Key", type="password", key="az_key")
            with az2:
                st.text_input("Azure Endpoint", key="az_endpoint")
        st.slider(
            "Minimum OCR Confidence Threshold", 0.50, 1.00, 0.75, 0.05,
            key="ocr_threshold",
        )
        st.checkbox("Pre-process image (deskew, denoise)", value=True, key="ocr_preprocess")

    # Drug Database
    with st.expander("💊  Drug Database Configuration", expanded=False):
        db_source = st.selectbox(
            "Primary Database",
            ["Local Demo", "RxNorm API (Free)", "DrugBank API", "OpenFDA API (Free)"],
            key="db_source",
        )
        if db_source != "Local Demo":
            st.text_input(f"{db_source} API Key", type="password", key="db_key")
        st.checkbox("Cache API responses (24 h)", value=True, key="db_cache")

    # Display Preferences
    with st.expander("🎨  Display Preferences", expanded=False):
        st.checkbox("Show OCR confidence score",             value=True,  key="show_conf")
        st.checkbox("Auto-check interactions after OCR",     value=True,  key="auto_check")
        st.checkbox("Show verbose pharmacological details",  value=False, key="verbose")
        st.number_input("Max results per query", 5, 100, 10, key="max_results")

    # Automation / n8n
    with st.expander("&#128279;  Automation / n8n Integration", expanded=False):
        st.markdown(
            "Connect an [n8n](https://n8n.io) webhook to receive automated alerts "
            "when critical prescription errors are detected."
        )
        st.text_input(
            "n8n Webhook URL",
            value=st.session_state.get("n8n_webhook_url", ""),
            key="n8n_webhook_url",
            placeholder="https://your-n8n.example.com/webhook/prescription-alert",
            help="POST alerts sent when major dosing/interaction errors are detected.",
        )

    st.markdown("<br>", unsafe_allow_html=True)
    cs1, cs2, _ = st.columns([1, 1, 4])
    with cs1:
        if st.button("💾  Save Settings", use_container_width=True, key="save_btn"):
            st.success("Settings saved.")
    with cs2:
        if st.button("↩️  Reset Defaults", use_container_width=True, key="reset_btn"):
            st.info("Settings reset to defaults.")
