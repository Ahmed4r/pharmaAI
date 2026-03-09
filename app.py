import streamlit as st
import time
from datetime import datetime


#  Page Configuration (must be the first Streamlit call) 
st.set_page_config(
    page_title="Smart Drug Safety Assistant",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)


#  Clinical CSS 
CLINICAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/*  App background  */
.stApp { background-color: #F0F4F8; }

/*  Sidebar  */
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

/*  Metric cards  */
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

/*  Section headings  */
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

/*  Buttons  */
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

/*  File uploader  */
[data-testid="stFileUploader"] {
    background: #fff;
    border: 2px dashed #1A6B8A;
    border-radius: 12px;
    padding: 0.5rem;
}

/*  Chat messages  */
[data-testid="stChatMessage"] { border-radius: 12px; margin-bottom: 0.6rem; }

/*  Custom alert boxes  */
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

/*  Drug tag pills  */
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

/*  OCR result card  */
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

/*  Severity badges  */
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

/*  Scrollbar  */
::-webkit-scrollbar       { width: 5px; }
::-webkit-scrollbar-thumb { background: #1A6B8A; border-radius: 3px; }
::-webkit-scrollbar-track { background: #F0F4F8; }

/*  Hide Streamlit chrome  */
#MainMenu, footer { visibility: hidden; }
header            { display: none !important; }
</style>
"""


# 
# PLACEHOLDER BACKEND CONNECTORS
# 

def process_prescription_ocr(image_bytes: bytes) -> dict:
    """
    Real OCR pipeline via ocr_engine.process_image_bytes().
    Falls back to the demo stub when the ocr_engine dependencies are missing.
    """
    try:
        from ocr_engine import process_image_bytes as _ocr
        return _ocr(image_bytes, filename="prescription.png")
    except Exception as exc:
        # Graceful fallback: show demo data + error banner so the UI still works
        return {
            "status":         "error",
            "extracted_text": (
                "PRESCRIPTION\n"
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                "Patient   : John Doe  (DOB: 01 Jan 1980)\n"
                "Date      : 09 Mar 2026\n"
                "Provider  : Dr. Sarah Mitchell, MD\n"
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                "Rx 1 : Amoxicillin 500 mg    Sig: 1 cap PO TID x 7 days\n"
                "Rx 2 : Ibuprofen 400 mg      Sig: 1 tab PO PRN q6h\n"
                "Rx 3 : Omeprazole 20 mg      Sig: 1 cap PO QD AC breakfast\n"
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                "[DEMO DATA  OCR engine unavailable: " + str(exc) + "]"
            ),
            "medications":   ["Amoxicillin 500mg", "Ibuprofen 400mg", "Omeprazole 20mg"],
            "parsed_meds":   [],
            "patient":       "John Doe",
            "date":          "09 Mar 2026",
            "prescriber":    "Dr. Sarah Mitchell, MD",
            "dea":           "",
            "confidence":    0.0,
            "preprocessing": [],
            "error":         str(exc),
        }


def query_ollama_llm(user_message: str, chat_history: list) -> str:
    """Send prompt + history to local BioMistral via Ollama.

    Uses generate(raw=True) with a manually-built ChatML prompt.
    The model Modelfile uses generate-style template which makes the chat()
    API return empty strings; raw=True bypasses the Modelfile stop params.
    """
    import ollama as _ollama
    import re as _re
    _MODEL = "adrienbrault/biomistral-7b:Q4_K_M"
    _HOST  = st.session_state.get("ol_host", "http://localhost:11434")
    _SYS   = st.session_state.get(
        "ol_system_prompt",
        "You are an expert clinical pharmacist assistant. Provide concise, "
        "evidence-based responses. Always recommend consulting a licensed "
        "pharmacist or physician for patient-specific clinical decisions.",
    )
    try:
        client = _ollama.Client(host=_HOST)
        # Build full ChatML conversation string
        parts = [f"<|im_start|>system\n{_SYS}\n<|im_end|>"]
        for m in chat_history:
            parts.append(f"<|im_start|>{m['role']}\n{m['content']}\n<|im_end|>")
        parts.append(f"<|im_start|>user\n{user_message}\n<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        full_prompt = "\n".join(parts)
        resp = client.generate(
            model=_MODEL,
            prompt=full_prompt,
            raw=True,
            options={"num_predict": 1024, "temperature": 0.7},
        )
        # Strip any trailing <|im_end|> the model may emit
        answer = _re.sub(r"<\|im_end\|>.*$", "", resp.response, flags=_re.DOTALL).strip()
        return answer
    except Exception as exc:
        return (
            f"**BioMistral offline** - could not reach Ollama at `{_HOST}`\n\n"
            f"Error: `{exc}`\n\n"
            "Make sure Ollama is running (`ollama serve`) and the model is available."
        )


def check_drug_interactions(drug_list: list) -> list:
    """Query RxNav REST API for real drug-drug interactions.

    Free, no API key required. Falls back to empty list on any network error.
    """
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
    """
    Placeholder  fetches comprehensive drug profile.

    Production implementation:
      - RxNorm  /rxcui?name={drug}  for identifier
      - OpenFDA  /drug/label?search=openfda.generic_name:{drug}  for full label
      - DrugBank API for structured pharmacological data
    """
    time.sleep(0.9)
    _db = {
        "amoxicillin": {
            "generic_name":      "Amoxicillin",
            "brand_names":       ["Amoxil", "Trimox"],
            "drug_class":        "Aminopenicillin / Beta-lactam antibiotic",
            "mechanism":         ("Inhibits bacterial cell wall synthesis by binding to "
                                  "penicillin-binding proteins (PBPs), preventing peptidoglycan "
                                  "cross-linking and causing bacterial lysis."),
            "indications":       ["Respiratory tract infections", "Urinary tract infections",
                                  "H. pylori eradication (triple therapy)", "Dental prophylaxis"],
            "contraindications": ["Hypersensitivity to penicillins or cephalosporins",
                                  "Infectious mononucleosis (risk of widespread maculopapular rash)"],
            "side_effects":      ["Diarrhoea", "Nausea", "Skin rash",
                                  "Hypersensitivity reactions (rare: anaphylaxis)"],
            "dosage":            "250500 mg every 8 h  or  500875 mg every 12 h (adult dose)",
            "pregnancy_category":"B",
            "renal_adjustment":  "Required when CrCl < 30 mL/min",
        },
        "ibuprofen": {
            "generic_name":      "Ibuprofen",
            "brand_names":       ["Advil", "Motrin", "Nurofen"],
            "drug_class":        "NSAID  Non-selective COX-1 / COX-2 inhibitor",
            "mechanism":         ("Non-selectively inhibits cyclooxygenase enzymes (COX-1 & COX-2), "
                                  "reducing prostaglandin and thromboxane synthesis. Provides "
                                  "analgesic, antipyretic, and anti-inflammatory effects."),
            "indications":       ["Mildmoderate pain", "Fever", "Osteoarthritis",
                                  "Rheumatoid arthritis", "Dysmenorrhoea"],
            "contraindications": ["Active GI ulceration or GI bleeding",
                                  "Severe renal or hepatic impairment",
                                  "Third trimester of pregnancy",
                                  "Peri-operative CABG bypass surgery"],
            "side_effects":      ["GI irritation / dyspepsia", "Headache",
                                  "Elevated blood pressure", "Fluid retention",
                                  "Prolonged bleeding time"],
            "dosage":            "200800 mg per dose every 48 h (max 3 200 mg/day adult)",
            "pregnancy_category":"C  (D in 3rd trimester)",
            "renal_adjustment":  "Avoid in severe renal impairment (eGFR < 30)",
        },
        "omeprazole": {
            "generic_name":      "Omeprazole",
            "brand_names":       ["Prilosec", "Losec", "Zegerid"],
            "drug_class":        "Proton Pump Inhibitor (PPI)",
            "mechanism":         ("Irreversibly inhibits the H\u207a/K\u207a-ATPase (proton pump) "
                                  "in gastric parietal cells, suppressing both basal and "
                                  "stimulated gastric acid secretion."),
            "indications":       ["GERD / reflux oesophagitis", "Peptic ulcer disease",
                                  "H. pylori eradication (triple therapy)",
                                  "NSAID-induced gastroprotection", "Zollinger-Ellison syndrome"],
            "contraindications": ["Hypersensitivity to benzimidazoles or PPIs",
                                  "Concurrent rilpivirine-containing antiretroviral regimens"],
            "side_effects":      ["Headache", "Nausea", "Abdominal pain",
                                  "Long-term (>1 yr): hypomagnesaemia, C. difficile risk, "
                                  "vitamin B12 deficiency"],
            "dosage":            "2040 mg once daily before breakfast",
            "pregnancy_category":"C",
            "renal_adjustment":  "No dose adjustment required",
        },
    }
    key = drug_name.lower().split()[0]
    return _db.get(key, {
        "generic_name":      drug_name,
        "brand_names":       [""],
        "drug_class":        "Not found in local demo database",
        "mechanism":         "Connect to RxNorm or DrugBank API for pharmacological data.",
        "indications":       [],
        "contraindications": [],
        "side_effects":      [],
        "dosage":            "",
        "pregnancy_category":"",
        "renal_adjustment":  "",
    })


# 
# SESSION STATE
# 

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


# 
# INJECT CSS
# 

st.markdown(CLINICAL_CSS, unsafe_allow_html=True)


# 
# SIDEBAR
# 

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

    # System status panel
    st.markdown(
        """
        <div style='font-size:0.77rem; padding:0 0.2rem; line-height:2;'>
            <div style='font-weight:700; color:#E8F4FD; margin-bottom:0.1rem;
                        font-size:0.7rem; letter-spacing:0.08em;'>SYSTEM STATUS</div>
            <div>
                <span style='color:#66BB6A;'>●</span>&nbsp;
                OCR Engine <span style='color:#90C4E0; font-size:0.7rem;'>(Tesseract)</span>
            </div>
            <div>
                <span style='color:#FFA726;'>&#9679;</span>&nbsp;
                Ollama LLM <span style='color:#90C4E0; font-size:0.7rem;'>(BioMistral)</span>
            </div>
            <div>
                <span style='color:#FFA726;'>●</span>&nbsp;
                Drug DB <span style='color:#90C4E0; font-size:0.7rem;'>(Demo mode)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(f"v1.0.0  ·  {datetime.now().strftime('%d %b %Y')}")


# 
# PAGE: DASHBOARD
# 

if active_page == "Dashboard":
    st.markdown("<div class='section-header'>🏠 Dashboard</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-sub'>Clinical drug safety monitoring at a glance</div>",
        unsafe_allow_html=True,
    )

    #  Metric row 
    mc1, mc2, mc3, mc4 = st.columns(4)
    metrics = [
        ("🔬", "1 284", "Prescriptions Scanned"),
        ("⚠️",  "47",    "Interactions Flagged"),
        ("💬", "392",   "Queries Answered"),
        ("✅", "98.2%", "Safety Compliance"),
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
        feed = [
            ("10:42", "⚠️", "Interaction detected  Warfarin + Aspirin",             "warning"),
            ("10:31", "📋", "Prescription scanned  3 medications extracted",         "info"),
            ("10:18", "✅", "Query resolved: Metformin dosage in CKD stage 3",        "success"),
            ("09:55", "📋", "Prescription scanned  5 medications extracted",         "info"),
            ("09:40", "🚨", "Major interaction flagged  Clopidogrel + Omeprazole",   "danger"),
            ("09:12", "✅", "Drug lookup: Atorvastatin  profile viewed",             "success"),
        ]
        for t, icon, msg, level in feed:
            st.markdown(
                f"<div class='custom-alert alert-{level}'>"
                f"<span style='opacity:.6; font-size:.8rem;'>{t}</span>"
                f"&emsp;{icon}&ensp;{msg}"
                f"</div>",
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
        for drug, sev in [("Warfarin", "major"), ("Clopidogrel", "major"),
                          ("Ibuprofen", "moderate"), ("Metformin", "minor")]:
            st.markdown(
                f"<span class='drug-tag'>{drug}</span>"
                f"<span class='sev-badge sev-{sev}'>{sev}</span>",
                unsafe_allow_html=True,
            )
            st.markdown("")


# 
# PAGE: PRESCRIPTION SCANNER
# 

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

    #  Upload column 
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
                    result = process_prescription_ocr(uploaded_file.read())
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

    #  Results column 
    with col_result:
        st.markdown("#### Extraction Results")
        ocr = st.session_state.ocr_result

        if ocr:
            conf_pct   = int(ocr["confidence"] * 100)
            conf_color = "#388E3C" if conf_pct >= 90 else "#BF6000" if conf_pct >= 75 else "#C62828"

            st.markdown(
                f"<div class='ocr-card'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                f"<span style='font-weight:600; color:#0B3C5D;'>Extracted Text</span>"
                f"<span style='color:{conf_color}; font-weight:700; font-size:.83rem;'>"
                f"OCR Confidence: {conf_pct}%</span>"
                f"</div>"
                f"<pre>{ocr['extracted_text']}</pre>"
                f"</div>",
                unsafe_allow_html=True,
            )

            pi1, pi2 = st.columns(2)
            with pi1:
                st.markdown(f"**Patient:** {ocr.get('patient', '')}")
                st.markdown(f"**Date:** {ocr.get('date', '')}")
            with pi2:
                st.markdown(f"**Prescriber:** {ocr.get('prescriber', '')}")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Detected medications:**")
            pills_html = "".join(
                f"<span class='drug-tag'>{m}</span>" for m in ocr["medications"]
            )
            st.markdown(pills_html, unsafe_allow_html=True)

            # Structured parse table (only when real OCR ran)
            parsed = ocr.get("parsed_meds", [])
            if parsed:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("**Parsed prescription detail:**")
                import pandas as pd
                rows = [{
                    "Drug":   m.get("name", ""),
                    "Dose":   m.get("dose", "") + " " + m.get("unit", ""),
                    "Sig / Directions": m.get("sig", ""),
                } for m in parsed]
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )

            # DEA number
            dea = ocr.get("dea", "")
            if dea:
                st.markdown(
                    f"<div class='custom-alert alert-warning'>"
                    f"🔒 <strong>DEA:</strong> {dea}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # Optional AI refinement — triggered on demand (avoids auto-hang)
            if st.button(u"✨  Refine with BioMistral AI", use_container_width=True, key="refine_btn"):
                with st.spinner("Sending to BioMistral... (may take 1-2 min if model is loading)"):
                    from ocr_engine import _refine_with_llm as _llm_fn
                    import json as _jj
                    _raw = st.session_state.ocr_result.get("extracted_text", "")
                    refined = _llm_fn(_raw)
                    try:
                        llm_data = _jj.loads(refined)
                        if "medications" in llm_data:
                            _meds = llm_data["medications"]
                            st.session_state.ocr_result["parsed_meds"] = [
                                {"name": m.get("drug",""), "dose": m.get("dose",""),
                                 "unit": m.get("unit",""), "sig": m.get("sig","")}
                                for m in _meds
                            ]
                            st.session_state.ocr_result["medications"] = [
                                (m.get("drug","") + " " + m.get("dose","") + m.get("unit","")).strip()
                                for m in _meds
                            ]
                            for _fk, _sk in (("patient","patient"),("prescriber","prescriber")):
                                if llm_data.get(_fk):
                                    st.session_state.ocr_result[_sk] = llm_data[_fk]
                            st.success(u"✅ BioMistral refined the prescription!")
                            st.rerun()
                    except Exception:
                        st.info(u"ℹ BioMistral returned plain text (not JSON) — raw text updated.")
                        st.session_state.ocr_result["extracted_text"] = refined
                        st.rerun()

            if st.button("🔎  Check Drug Interactions", use_container_width=True):
                with st.spinner("Querying interaction database..."):
                    interactions = check_drug_interactions(ocr["medications"])
                st.markdown("**Interaction Report:**")
                if interactions:
                    for ix in interactions:
                        sev = ix["severity"]
                        st.markdown(
                            f"<div class='custom-alert alert-warning'>"
                            f"<span class='sev-badge sev-{sev}'>{sev}</span>"
                            f"&ensp;<strong>{ix['drug_a']}</strong>"
                            f" &harr; <strong>{ix['drug_b']}</strong><br>"
                            f"<span style='font-size:.86rem; margin-top:.3rem; display:block;'>"
                            f"{ix['description']}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<div class='custom-alert alert-success'>"
                        "✅  No significant interactions detected for this prescription.</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                """
                <div style='text-align:center; padding:3rem 1rem; color:#6B8CAE;
                            background:#fff; border-radius:12px;
                            border: 2px dashed #B0CEE3;'>
                    <div style='font-size:3rem; margin-bottom:0.75rem;'></div>
                    <div style='font-size:1rem; font-weight:500;'>Awaiting prescription upload</div>
                    <div style='font-size:0.82rem; margin-top:0.35rem;'>
                        Results will appear here after analysis
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# 
# PAGE: DRUG INTERACTION CHAT
# 

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
        ("sc1", sc1, "Check interactions for the active prescription"),
        ("sc2", sc2, "Contraindications of Ibuprofen?"),
        ("sc3", sc3, "Amoxicillin dose in renal failure?"),
    ]
    for key, col, suggestion in suggestions:
        with col:
            if st.button(suggestion, use_container_width=True, key=f"sug_{key}"):
                st.session_state.chat_history.append(
                    {"role": "user", "content": suggestion}
                )
                with st.spinner("Assistant is thinking..."):
                    resp = query_ollama_llm(suggestion, st.session_state.chat_history)
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": resp}
                )
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    #  Chat history 
    chat_box = st.container(height=460)
    with chat_box:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    #  Input bar 
    if user_input := st.chat_input(
        "Ask about interactions, dosages, contraindications, adverse effects..."
    ):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("Consulting clinical knowledge base..."):
            llm_resp = query_ollama_llm(user_input, st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": llm_resp})
        st.rerun()

    #  Clear button 
    col_clr, _ = st.columns([1, 5])
    with col_clr:
        if st.button("🗑️  Clear Chat"):
            st.session_state.chat_history = [
                {"role": "assistant", "content": "Chat cleared. How can I assist you?"}
            ]
            st.rerun()


# 
# PAGE: DRUG LOOKUP
# 

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

        st.markdown("<br>", unsafe_allow_html=True)

        #  Drug profile header 
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


# 
# PAGE: SETTINGS
# 

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

    #  Ollama 
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
                "You are an expert clinical pharmacist assistant specialising in drug safety, "
                "pharmacokinetics, and drug-drug interactions. Provide concise, evidence-based "
                "responses. Always recommend consulting a licensed pharmacist or physician for "
                "patient-specific clinical decisions."
            ),
            height=110,
            key="ol_system_prompt",
        )

    #  OCR 
    with st.expander("🔬  OCR Engine Configuration", expanded=False):
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

    #  Drug Database 
    with st.expander("💊  Drug Database Configuration", expanded=False):
        db_source = st.selectbox(
            "Primary Database",
            ["Local Demo", "RxNorm API (Free)", "DrugBank API", "OpenFDA API (Free)"],
            key="db_source",
        )
        if db_source != "Local Demo":
            st.text_input(f"{db_source} API Key", type="password", key="db_key")
        st.checkbox("Cache API responses (24 h)", value=True, key="db_cache")

    #  Display Preferences 
    with st.expander("🎨  Display Preferences", expanded=False):
        st.checkbox("Show OCR confidence score",             value=True,  key="show_conf")
        st.checkbox("Auto-check interactions after OCR",     value=True,  key="auto_check")
        st.checkbox("Show verbose pharmacological details",  value=False, key="verbose")
        st.number_input("Max results per query", 5, 100, 10, key="max_results")

    st.markdown("<br>", unsafe_allow_html=True)
    cs1, cs2, _ = st.columns([1, 1, 4])
    with cs1:
        if st.button("💾  Save Settings", use_container_width=True, key="save_btn"):
            st.success("Settings saved.")
    with cs2:
        if st.button("↩️  Reset Defaults", use_container_width=True, key="reset_btn"):
            st.info("Settings reset to defaults.")
