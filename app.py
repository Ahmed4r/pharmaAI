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
        is_pdf_ready,
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
# --- Backend module imports ---
from ocr import (
    preprocess_prescription_image,
    process_prescription_ocr,
    analyze_prescription_safety,
)
from chatbot import query_ollama_llm, generate_response
import threading as _threading

from drug_lookup import check_drug_interactions, lookup_drug_info


def send_n8n_alert(webhook_url: str, payload: dict) -> bool:
    """POST a safety-alert payload to an n8n webhook. Returns True on 2xx/3xx."""
    try:
        import requests as _req
        resp = _req.post(webhook_url.strip(), json=payload, timeout=8)
        return resp.status_code < 400
    except Exception:
        return False



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

if "llm_mode" not in st.session_state:
    st.session_state.llm_mode = "local"

if "llm_mode_radio" not in st.session_state:
    st.session_state.llm_mode_radio = "💻  Local (Ollama)"

if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = _os.environ.get("GROQ_API_KEY", "")

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = _os.environ.get("GEMINI_API_KEY", "") or _os.environ.get("GOOGLE_API_KEY", "")

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



# Handle ?nav= and ?model= from drawer links -- read ALL params first, then clear
try:
    _qnav = st.query_params.get("nav")
    _qmodel = st.query_params.get("model")
    _QP_PAGES = ["Dashboard", "Prescription Scanner", "Drug Interaction Chat", "Drug Lookup"]
    if _qnav and _qnav in _QP_PAGES:
        st.session_state["nav_page"] = _qnav
        del st.query_params["nav"]  # only remove nav; keep ?model= so it persists
    if _qmodel in ("cloud", "local"):
        st.session_state["llm_mode"] = _qmodel
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
    _pdf_rag_active = False
    if RAG_ENGINE_AVAILABLE:
        try:
            _pdf_rag_active = is_pdf_ready()
        except Exception:
            pass
    st.markdown(
        f"""
        <div style='font-size:0.77rem; padding:0 0.2rem; line-height:2;'>
            <div style='font-weight:700; color:#E8F4FD; margin-bottom:0.1rem;
                        font-size:0.7rem; letter-spacing:0.08em;'>SYSTEM STATUS</div>
            <div>{_sdot(True)}&nbsp;
                OCR Engine <span style='color:#90C4E0; font-size:0.7rem;'>(Tesseract)</span></div>
            <div>{_sdot(INTERACTION_CHECKER_AVAILABLE)}&nbsp;
                Interaction Check <span style='color:#90C4E0; font-size:0.7rem;'>({'Active' if INTERACTION_CHECKER_AVAILABLE else 'Unavailable'})</span></div>
            <div>{_sdot(_pdf_rag_active)}&nbsp;
                RAG Engine <span style='color:#90C4E0; font-size:0.7rem;'>({'ChromaDB (Active)' if _pdf_rag_active else 'ChromaDB (Inactive)'})</span></div>
            <div>{_sdot(True)}&nbsp;
                Drug DB <span style='color:#90C4E0; font-size:0.7rem;'>(SQLite · Live)</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(f"v1.0.0  ·  {datetime.now().strftime('%d %b %Y')}")



# --- GLOBAL SETTINGS DRAWER (right-side, injected via window.parent) ---
_llm_m = st.session_state.get("llm_mode", "local")
_drawer_html = (
    '<script>\n(function(){\n'
    '  var M = "' + _llm_m + '";\n'
    '  var p = window.parent;\n'
    '  var d = p.document;\n'
    '  if (!d.getElementById("_pd_css")) {\n'
    '    var s = d.createElement("style");\n'
    '    s.id = "_pd_css";\n'
    '    s.textContent = [\n'
    '      "#_pd_bd{position:fixed;inset:0;background:rgba(0,0,0,.32);z-index:9998;display:none;}",\n'
    '      "#_pd_panel{position:fixed;top:0;right:0;height:100vh;width:295px;background:#fff;",\n'
    '        "box-shadow:-4px 0 28px rgba(11,60,93,.18);z-index:9999;padding:0;",\n'
    '        "transform:translateX(100%);transition:transform .26s cubic-bezier(.4,0,.2,1);",\n'
    '        "overflow-y:auto;font-family:sans-serif;}",\n'
    '      "#_pd_panel.open{transform:translateX(0);}",\n'
    '      "#_pd_tab{position:fixed;top:50vh;right:0;transform:translateY(-50%);",\n'
    '        "background:#0B3C5D;color:#fff;border:none;cursor:pointer;",\n'
    '        "padding:.85rem .45rem;border-radius:8px 0 0 8px;",\n'
    '        "font-size:1.2rem;z-index:9997;box-shadow:-2px 0 10px rgba(11,60,93,.22);",\n'
    '        "transition:background .15s;}",\n'
    '      "#_pd_tab:hover{background:#1A6B8A;}",\n'
    '      ".pd-hdr{background:#0B3C5D;color:#fff;padding:1.1rem 1.3rem .9rem;display:flex;justify-content:space-between;align-items:center;}",\n'
    '      ".pd-hdr-title{font-size:1.05rem;font-weight:700;letter-spacing:.01em;}",\n'
    '      ".pd-body{padding:1rem 1.2rem 2rem;}",\n'
    '      ".pd-sec{font-size:.7rem;font-weight:700;letter-spacing:.08em;color:#6B8CAE;text-transform:uppercase;margin:1rem 0 .45rem;}",\n'
    '      ".pd-card{display:flex;align-items:center;gap:.75rem;text-decoration:none;color:inherit;",\n'
    '        "background:#F8FBFD;border:1px solid #e0eef8;border-radius:10px;",\n'
    '        "padding:.7rem .9rem;margin-bottom:.4rem;transition:background .15s;}",\n'
    '      ".pd-card:hover{background:#E3F2FD;}",\n'
    '      ".pd-icon{font-size:1.3rem;flex-shrink:0;}",\n'
    '      ".pd-title{font-weight:600;font-size:.88rem;color:#0B3C5D;display:block;}",\n'
    '      ".pd-sub{font-size:.72rem;color:#6B8CAE;}",\n'
    '      ".pd-mrow{display:flex;gap:.5rem;margin:.1rem 0 .6rem;}",\n'
    '      ".pd-mbtn{flex:1;padding:.55rem .4rem;border:2px solid #CBD5E0;border-radius:8px;",\n'
    '        "background:#F8FBFD;color:#0B3C5D;font-size:.82rem;font-weight:600;cursor:pointer;",\n'
    '        "transition:all .15s;text-align:center;text-decoration:none;display:flex;align-items:center;justify-content:center;}",\n'
    '      ".pd-mbtn:hover{background:#E3F2FD;border-color:#1A6B8A;}",\n'
    '      ".pd-mbtn.on{background:#1A6B8A;border-color:#1A6B8A;color:#fff;}",\n'
    '      ".pd-active{font-size:.72rem;color:#6B8CAE;margin-top:.25rem;text-align:center;}"\n'
    '    ].join("");\n'
    '    d.head.appendChild(s);\n'
    '  }\n'
    '  p._pdOpen  = function(){ d.getElementById("_pd_panel").classList.add("open");    d.getElementById("_pd_bd").style.display="block"; };\n'
    '  p._pdClose = function(){ d.getElementById("_pd_panel").classList.remove("open"); d.getElementById("_pd_bd").style.display="none"; };\n'
    '  ["_pd_bd","_pd_panel","_pd_tab"].forEach(function(id){ var e=d.getElementById(id); if(e) e.remove(); });\n'
    '  var bd = d.createElement("div");\n'
    '  bd.id = "_pd_bd";\n'
    '  bd.setAttribute("onclick","_pdClose()");\n'
    '  d.body.appendChild(bd);\n'
    '  var feats = [\n'
    '    ["\U0001F3E0","Dashboard","Metrics &amp; activity feed"],\n'
    '    ["\U0001F4CB","Prescription Scanner","OCR + drug extraction"],\n'
    '    ["\U0001F4AC","Drug Interaction Chat","AI clinical pharmacist"],\n'
    '    ["\U0001F50D","Drug Lookup","Search drug profiles"]\n'
    '  ];\n'
    '  var panel = d.createElement("div");\n'
    '  panel.id = "_pd_panel";\n'
    '  var isCloud = (M === "cloud");\n'
    '  var cloudOn = isCloud ? " on" : "";\n'
    '  var localOn = isCloud ? "" : " on";\n'
    '  var activeLbl = isCloud ? "\u2601\ufe0f llama-3.3-70b (Groq)" : "\U0001f4bb BioMistral-7B (Ollama)";\n'
    + '  panel.innerHTML =\n'
    + '    \'<div class="pd-hdr"><span class="pd-hdr-title">\u2699\ufe0f Settings</span>\' +\n'
    + '    \'<button onclick="_pdClose()" style="background:none;border:none;cursor:pointer;font-size:1.4rem;color:rgba(255,255,255,.7);padding:0;">&times;</button></div>\' +\n'
    + '    \'<div class="pd-body">\' +\n'
    + '    \'<div class="pd-sec">PAGES</div>\' +\n'
    + '    feats.map(function(f){\n'
    + '      return \'<a href="?nav=\'+encodeURIComponent(f[1])+\'&model=\'+M+\'" class="pd-card">\' +\n'
    + '        \'<span class="pd-icon">\'+f[0]+\'</span>\' +\n'
    + '        \'<span><span class="pd-title">\'+f[1]+\'</span><span class="pd-sub">\'+f[2]+\'</span></span>\' +\n'
    + '        \'</a>\';\n'
    + '    }).join("") +\n'
    + '    \'<div class="pd-sec" style="margin-top:1.2rem;">AI ENGINE</div>\' +\n'
    + '    \'<div class="pd-mrow">\' +\n'
    + '    \'<a class="pd-mbtn\' + cloudOn + \'" href="?model=cloud">\u2601\ufe0f Cloud (Groq)</a>\' +\n'
    + '    \'<a class="pd-mbtn\' + localOn + \'" href="?model=local">\U0001f4bb Local (Ollama)</a>\' +\n'
    + '    \'</div>\' +\n'
    + '    \'<div id="_pdM_lbl" class="pd-active">\' + activeLbl + \'</div>\' +\n'
    + '    \'</div>\';\n'
    + '  d.body.appendChild(panel);\n'
    + '  var tab = d.createElement("button");\n'
    + '  tab.id = "_pd_tab";\n'
    + '  tab.title = "Settings";\n'
    + '  tab.innerHTML = "&#9881;&#65039;";\n'
    + '  tab.setAttribute("onclick","_pdOpen()");\n'
    + '  d.body.appendChild(tab);\n'
    + '})();\n'
    + '</script>'
)
_st_components.html(_drawer_html, height=0, scrolling=False)


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

                # ── Confidence Dashboard ──────────
                _ocr_conf  = int(round(ocr.get("confidence", 0.5) * 100))
                _drug_conf = int(round(ocr.get("drug_match_confidence", 0.80) * 100))
                _ix_conf   = int(round(ocr.get("interaction_confidence", 0.88) * 100))
                def _cbar(pct, label, sub=""):
                    c = "#388E3C" if pct >= 80 else "#F9A825" if pct >= 60 else "#C62828"
                    filled = min(20, int(pct / 5))
                    bar = "█" * filled + "░" * (20 - filled)
                    return (
                        "<div style='margin-bottom:.5rem;'>"
                        "<div style='display:flex;justify-content:space-between;margin-bottom:.1rem;'>"
                        f"<span style='font-size:.8rem;font-weight:600;color:#0B3C5D;'>{label}</span>"
                        f"<span style='font-size:.8rem;font-weight:700;color:{c};'>{pct}%</span>"
                        "</div>"
                        f"<div style='font-family:monospace;font-size:.72rem;color:{c};'>{bar}</div>"
                        + (f"<div style='font-size:.68rem;color:#6B8CAE;margin-top:.05rem;'>{sub}</div>" if sub else "")
                        + "</div>"
                    )
                st.markdown(
                    "<div style='background:#fff;border-radius:10px;padding:.9rem 1.1rem;"
                    "box-shadow:0 2px 10px rgba(11,60,93,.07);margin-bottom:.9rem;"
                    "border-left:4px solid #1A6B8A;'>"
                    "<div style='font-size:.85rem;font-weight:700;color:#0B3C5D;margin-bottom:.6rem;'>"
                    "&#128202; Confidence Report</div>"
                    + _cbar(_ocr_conf,  "OCR Confidence",        "Gemini Vision quality score")
                    + _cbar(_drug_conf, "Drug Name Match",       "Brand → Generic normalization")
                    + _cbar(_ix_conf,   "Interaction Reliability","Evidence-source quality")
                    + "</div>",
                    unsafe_allow_html=True,
                )

                #  AI disclaimer banner 
                st.markdown(
                    "<div style='background:#FFF8E1;border:1.5px solid #F9A825;"
                    "border-radius:10px;padding:.65rem 1rem;margin-bottom:.9rem;"
                    "display:flex;align-items:flex-start;gap:.6rem;'>"
                    "<span style='font-size:1.1rem;'>&#x1F916;</span>"
                    "<span style='font-size:.82rem;color:#7A4F00;'>"
                    "<strong>AI may make mistakes</strong> &mdash; accuracy depends on image "
                    "quality and handwriting clarity. Please review every field below and "
                    "correct any errors before running the analysis."
                    "</span></div>",
                    unsafe_allow_html=True,
                )

                _edited = st.session_state.get("ocr_edited", {})

                #  Patient / Date / Prescriber (always editable) 
                st.markdown("##### &#128203; Patient Details")
                hc1, hc2, hc3 = st.columns(3)
                _pat = _strip_unc(_edited.get("patient", ocr.get("patient", "") or ""))
                _dt  = _strip_unc(_edited.get("date",    ocr.get("date", "") or ""))
                _pre = _strip_unc(_edited.get("prescriber", ocr.get("prescriber", "") or ""))
                with hc1:
                    st.text_input("&#128100; Patient", value=_pat, key="edit_patient",
                                  placeholder="e.g. Ahmed Mohamed")
                with hc2:
                    st.text_input("&#128197; Date", value=_dt, key="edit_date",
                                  placeholder="YYYY-MM-DD")
                with hc3:
                    st.text_input("&#129658; Prescriber", value=_pre, key="edit_prescriber",
                                  placeholder="Dr. Name")

                _wc1, _wc2, _wc3, _wc4 = st.columns(4)
                with _wc1:
                    st.number_input(
                        "⚖️ Patient Weight (kg)",
                        min_value=2.0,
                        max_value=150.0,
                        value=float(st.session_state.get("patient_weight_kg", 20.0)),
                        step=0.5,
                        key="patient_weight_kg",
                        help="Used for pediatric weight-based dosage safety checks",
                    )

                st.markdown("---")

                #  Medications (all fields always editable) 
                st.markdown("##### &#128138; Detected Medications")
                parsed_meds = raw_json.get("medications") or []

                for _mi, _med in enumerate(parsed_meds):
                    _name = _strip_unc(_edited.get(f"med_{_mi}_name",     _med.get("name", "") or ""))
                    _dose = _strip_unc(_edited.get(f"med_{_mi}_dosage",    _med.get("dosage", "") or ""))
                    _freq = _strip_unc(_edited.get(f"med_{_mi}_frequency", _med.get("frequency", "") or ""))
                    _dur  = _strip_unc(_edited.get(f"med_{_mi}_duration",  _med.get("duration", "") or ""))

                    _has_unc = any(
                        _is_uncertain(_med.get(k, ""))
                        for k in ("name", "dosage", "frequency", "duration")
                    )
                    _border = "#F9A825" if _has_unc else "#1A6B8A"
                    _unc_badge = (
                        " <span style='background:#FFF8E1;color:#BF6000;"
                        "padding:1px 7px;border-radius:10px;font-size:.7rem;"
                        "font-weight:700;'>&#9888; Uncertain</span>"
                        if _has_unc else ""
                    )
                    _gen_name = (_med.get("generic_name") or "").strip()
                    _gen_mtype = (_med.get("name_match_type") or "not_found")
                    _gen_conf = _med.get("name_confidence", 0.0)
                    _generic_badge = ""
                    if _gen_name and _gen_name.lower() != _name.lower() and _gen_mtype != "not_found":
                        _gc = "#388E3C" if _gen_conf >= 0.80 else "#F9A825"
                        _generic_badge = (
                            f" <span style='background:#E8F5E9;color:{_gc};"
                            f"padding:1px 8px;border-radius:20px;font-size:.7rem;"
                            f"font-weight:600;border:1px solid {_gc};white-space:nowrap;'>"
                            f"&#10132; {_gen_name}</span>"
                        )
                    st.markdown(
                        f"<div style='border:1.5px solid {_border};border-radius:10px;"
                        f"padding:.7rem 1rem .3rem 1rem;margin-bottom:.4rem;background:#FAFCFF;'>"
                        f"<span style='font-weight:700;color:#0B3C5D;font-size:.9rem;'>"
                        f"&#128138; Medication {_mi + 1}{_unc_badge}{_generic_badge}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1:
                        st.text_input("Drug Name", value=_name,
                                      key=f"edit_med_{_mi}_name",
                                      placeholder="e.g. Amoxicillin")
                    with mc2:
                        st.text_input("Dosage", value=_dose,
                                      key=f"edit_med_{_mi}_dosage",
                                      placeholder="e.g. 5 ml")
                    with mc3:
                        st.text_input("Frequency", value=_freq,
                                      key=f"edit_med_{_mi}_frequency",
                                      placeholder="e.g. مرة يومياً")
                    with mc4:
                        st.text_input("Duration", value=_dur,
                                      key=f"edit_med_{_mi}_duration",
                                      placeholder="e.g. 7 days")

                #  Confirm & save button (always visible) 
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(
                    "✔️  Confirm & Save Corrections",
                    use_container_width=True,
                    key="save_edits_btn",
                    type="primary",
                ):
                    _new_ed: dict = {}
                    for _fk in ("patient", "date", "prescriber"):
                        _new_ed[_fk] = st.session_state.get(f"edit_{_fk}", "") or ""
                    for _j in range(len(parsed_meds)):
                        for _fl in ("name", "dosage", "frequency", "duration"):
                            _new_ed[f"med_{_j}_{_fl}"] = st.session_state.get(f"edit_med_{_j}_{_fl}", "") or ""
                    st.session_state["ocr_edited"] = _new_ed
                    # Propagate corrections into raw_json so analysis uses corrected values
                    _rj = st.session_state.ocr_result.get("raw_json", {})
                    for _j, _m in enumerate((_rj.get("medications") or [])):
                        for _fl in ("name", "dosage", "frequency", "duration"):
                            _vv = _new_ed.get(f"med_{_j}_{_fl}", "")
                            _m[_fl] = _vv if _vv else None
                    for _fk2 in ("patient", "prescriber", "date"):
                        _vv2 = _new_ed.get(_fk2, "")
                        st.session_state.ocr_result[_fk2] = _vv2 if _vv2 else None
                    st.success("✅ Corrections saved — ready for analysis!")
                    st.rerun()

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
                    "Powered by ai</span></div>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "&#128269;&#65039; Detect Errors & Interactions",
                    use_container_width=True, key="run_safety_btn",
                ):
                    _low_conf_ids = [
                        (i, m) for i, m in enumerate(parsed_meds)
                        if m.get("name_confidence", 1.0) < 0.75
                    ]
                    if _low_conf_ids:
                        st.session_state.show_low_conf_review = True
                        st.rerun()
                    else:
                        st.session_state.show_low_conf_review = False
                        with st.spinner("Tesseract.js analysing prescription for errors..."):
                            _safety = analyze_prescription_safety(
                                parsed_meds,
                                patient=ocr.get("patient", ""),
                                prescriber=ocr.get("prescriber", ""),
                                patient_weight_kg=float(
                                    st.session_state.get("patient_weight_kg", 0.0)
                                ),
                            )
                        st.session_state.safety_result = _safety
                        _wh = st.session_state.get("n8n_webhook_url", "")
                        if _wh:
                            _meds_q = " ".join(
                                m.get("name", "") for m in parsed_meds if m.get("name")
                            )
                            if _meds_q:
                                _threading.Thread(
                                    target=send_n8n_alert,
                                    args=(_wh, {"query": _meds_q}),
                                    daemon=True,
                                ).start()
                        st.rerun()

                # --- MODULE 4: Low-Confidence Manual Override ---
                if st.session_state.get("show_low_conf_review"):
                    _low_conf_items = [
                        (i, m) for i, m in enumerate(parsed_meds)
                        if m.get("name_confidence", 1.0) < 0.75
                    ]
                    st.warning(
                        "⚠️ Low confidence in reading some drug names. "
                        "Please verify before running safety analysis."
                    )
                    for _lci, _lcm in _low_conf_items:
                        _cands = list(_lcm.get("name_candidates") or [])
                        _orig_name = (_lcm.get("name") or "").strip()
                        if _orig_name and _orig_name not in _cands:
                            _cands.insert(0, _orig_name)
                        _cands = [c for c in _cands if c] or ["Unknown"]
                        _conf_pct = int(round(_lcm.get("name_confidence", 0.0) * 100))
                        st.selectbox(
                            f"Medication {_lci + 1} "
                            f"(confidence: {_conf_pct}%) — select correct name:",
                            options=_cands,
                            key=f"low_conf_select_{_lci}",
                        )
                    if st.button(
                        "✅ Confirm & Proceed to Safety Analysis",
                        use_container_width=True,
                        key="low_conf_confirm_btn",
                        type="primary",
                    ):
                        _rj_live = st.session_state.ocr_result.get("raw_json", {})
                        _pm_live = _rj_live.get("medications") or []
                        for _lci2, _lcm2 in [
                            (i, m) for i, m in enumerate(_pm_live)
                            if m.get("name_confidence", 1.0) < 0.75
                        ]:
                            _sel_name = st.session_state.get(f"low_conf_select_{_lci2}")
                            if _sel_name:
                                _lcm2["name"] = _sel_name
                        with st.spinner("Tesseract.js analysing prescription for errors..."):
                            _safety = analyze_prescription_safety(
                                _pm_live,
                                patient=ocr.get("patient", ""),
                                prescriber=ocr.get("prescriber", ""),
                                patient_weight_kg=float(
                                    st.session_state.get("patient_weight_kg", 0.0)
                                ),
                            )
                        st.session_state.safety_result = _safety
                        st.session_state.show_low_conf_review = False
                        _wh = st.session_state.get("n8n_webhook_url", "")
                        if _wh:
                            _pm_meds_q = " ".join(
                                m.get("name", "") for m in _pm_live if m.get("name")
                            )
                            if _pm_meds_q:
                                _threading.Thread(
                                    target=send_n8n_alert,
                                    args=(_wh, {"query": _pm_meds_q}),
                                    daemon=True,
                                ).start()
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
                                        "</span>"
                                        + (f"<br><span style='font-size:.8rem;color:#1A6B8A;padding-top:.2rem;display:inline-block;'>&#127859; Meal timing: {_fi.get('meal_timing', '')}</span>" if _fi.get('meal_timing') else "")
                                        + "</div>",
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
                                            "Configure it in"
                                        )
                                    else:
                                        _btn_meds = " ".join(
                                            m.get("name", "") if isinstance(m, dict) else str(m)
                                            for m in (raw_json.get("medications") or [])
                                        )
                                        _ok = send_n8n_alert(_wh, {"query": _btn_meds or "prescription check"})
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
    _ci_mode = st.session_state.get('llm_mode', 'local')
    _ci_model_label = (
        "llama-3.3-70b-versatile (Groq ☁️)" if _ci_mode == "cloud"
        else "BioMistral-7B (Ollama 💻)"
    )
    st.markdown(
        f"<div style='display:inline-block;background:#E3F0FF;color:#1A6B8A;"
        f"padding:3px 12px;border-radius:20px;font-size:.75rem;font-weight:700;"
        f"border:1px solid #1A6B8A;margin-bottom:.5rem;'>"
        f"🤖 Active Model: {_ci_model_label}</div>",
        unsafe_allow_html=True,
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
                # Source badge for PDF-retrieved content
                _msg_sources = msg.get("sources", [])
                if _msg_sources and msg["role"] == "assistant":
                    _badges = " &nbsp;".join(
                        "<span style='display:inline-block;background:#E3F2FD;"
                        "border:1px solid #1A6B8A;color:#0B3C5D;"
                        "border-radius:20px;padding:2px 10px;"
                        "font-size:.72rem;font-weight:600;margin:2px 1px;'>"
                        f"📚 Source: {s['file']}, Page {s['page']}</span>"
                        for s in _msg_sources
                    )
                    st.markdown(
                        f"<div style='margin-top:4px;'>{_badges}</div>",
                        unsafe_allow_html=True,
                    )

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
            # Build OCR context string if a prescription was scanned
            _ocr = st.session_state.get("ocr_result") or {}
            _ocr_ctx = ""
            if _ocr.get("medications"):
                _meds = _ocr.get("medications", [])
                _ocr_ctx = "Scanned prescription medications: " + ", ".join(_meds) + "."
                _raw = _ocr.get("raw_json") or _ocr.get("raw_js")
                if isinstance(_raw, dict):
                    import json as _json
                    _ocr_ctx += "\nFull OCR data: " + _json.dumps(_raw, ensure_ascii=False)[:1200]
            llm_resp, _resp_sources = generate_response(
                _q,
                st.session_state.chat_history,
                mode=st.session_state.get("llm_mode", "local"),
                groq_api_key=st.session_state.get("groq_api_key", ""),
                ocr_context=_ocr_ctx,
            )
            if llm_resp:
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": llm_resp,
                     "sources": _resp_sources}
                )
            _wh = st.session_state.get("n8n_webhook_url", "")
            if _wh and _q:
                _threading.Thread(
                    target=send_n8n_alert,
                    args=(_wh, {"query": _q}),
                    daemon=True,
                ).start()
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
            + ((
                "&ensp;<span style='background:#E0F4FF;color:#0277BD;"
                "padding:2px 10px;border-radius:20px;font-size:.72rem;"
                "font-weight:600;border:1px solid #0277BD;'>"
                + {"openfda":"&#127757; OpenFDA","rxnorm":"&#128197; RxNorm","local":"&#128218; Local DB"}.get(info.get("_source",""),"")
                + "</span>"
            ) if info.get("_source","") else "") +
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
                st.markdown("*No indication data in OpenFDA label.*")

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


