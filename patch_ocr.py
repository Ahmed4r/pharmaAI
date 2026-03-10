import re, sys

content = open("app.py", encoding="utf-8").read()

# 
# 1.  Replace process_prescription_ocr() with Groq Vision impl
# 
OLD_OCR_FUNC_START = "def process_prescription_ocr(image_bytes: bytes) -> dict:"
OLD_OCR_FUNC_END   = "\ndef _get_ram_warning(exc: Exception, host: str) -> str:"

new_ocr_func = '''def process_prescription_ocr(image_bytes: bytes, filename: str = "prescription.png") -> dict:
    """OCR via Groq Vision API  llama-4-scout-17b-16e-instruct.
    Returns a dict with \'raw_json\' (parsed JSON from model), \'medications\',
    \'patient\', \'date\', \'prescriber\'. Uncertain fields contain ' (uncertain)'.
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
        )
        if not api_key:
            raise ValueError(
                "Groq API key not set. Add it in \u2699\ufe0f Settings \u2192 OCR Engine."
            )

        _ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "jpeg"
        _mime_map = {
            "png": "png", "jpg": "jpeg", "jpeg": "jpeg",
            "gif": "gif", "webp": "webp", "bmp": "png",
        }
        _mime = f"image/{_mime_map.get(_ext, \'jpeg\')}"

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        _groq = _Groq(api_key=api_key)

        completion = _groq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyse this handwritten prescription image. "
                                "Extract ALL medications and return ONLY a valid JSON object "
                                "with this exact structure:\\n"
                                "{\\n"
                                \'  "patient": "name or null",\\n\'
                                \'  "date": "date string or null",\\n\'
                                \'  "prescriber": "doctor name or null",\\n\'
                                \'  "medications": [\\n\'
                                \'    {"name": "drug name", "dosage": "dose with unit", \'
                                \'"frequency": "how often", "duration": "how long or null"}\\n\'
                                "  ]\\n"
                                "}\\n"
                                "IMPORTANT: If you are unsure about any word or value, "
                                "append \' (uncertain)\' to that field\'s string value. "
                                "Return ONLY the JSON object  no markdown, no explanation."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{_mime};base64,{b64}"},
                        },
                    ],
                }
            ],
            temperature=0.0,
            max_tokens=1024,
            top_p=1,
            stream=False,
            stop=None,
        )

        raw = completion.choices[0].message.content.strip()

        # Strip markdown fences if model wrapped in ```json ... ```
        _fence = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", raw, re.DOTALL)
        json_str = _fence.group(1) if _fence else raw

        parsed = json.loads(json_str)
        medications = parsed.get("medications") or []
        med_names = [
            (m.get("name", "") + " " + m.get("dosage", "")).strip()
            for m in medications
        ]

        # Run interaction check on extracted drug generic names
        interactions: list = []
        if med_names and INTERACTION_CHECKER_AVAILABLE:
            _drug_names = [
                re.sub(r"\\s*\\(uncertain\\)\\s*", "", m.get("name", ""), flags=re.IGNORECASE).split()[0]
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
            "extracted_text": raw,
            "medications":   med_names,
            "parsed_meds":   medications,
            "patient":       parsed.get("patient") or "",
            "date":          parsed.get("date") or "",
            "prescriber":    parsed.get("prescriber") or "",
            "dea":           "",
            "confidence":    1.0,
            "preprocessing": ["Groq Vision", "llama-4-scout-17b"],
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

'''

idx_start = content.find(OLD_OCR_FUNC_START)
idx_end   = content.find(OLD_OCR_FUNC_END)
if idx_start == -1 or idx_end == -1:
    sys.exit("ERROR: Could not find process_prescription_ocr or _get_ram_warning anchors")

content = content[:idx_start] + new_ocr_func + content[idx_end:]
print("[1/4] process_prescription_ocr replaced OK")

# 
# 2.  Replace the Results column (col_result) block
# 
OLD_COL_RESULT_START = "    # Results column\n    with col_result:"
OLD_COL_RESULT_END   = "\n\n# --- PAGE: DRUG INTERACTION CHAT ---"

new_col_result = '''    # Results column
    with col_result:
        st.markdown("#### Extraction Results")
        ocr = st.session_state.ocr_result

        if ocr:
            raw_json = ocr.get("raw_json")

            #  Error banner 
            if ocr.get("status") == "error":
                st.markdown(
                    f"<div class=\'custom-alert alert-danger\'>;&#10060; OCR failed: "
                    f"<code style=\'font-size:.78rem;\'>{ocr.get(\'error\',\'\')}</code></div>",
                    unsafe_allow_html=True,
                )

            if raw_json:
                #  Helpers 
                def _is_uncertain(val):
                    return isinstance(val, str) and "(uncertain)" in val.lower()
                def _strip_unc(val):
                    return re.sub(r"\\s*\\(uncertain\\)\\s*", "", val or "",
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
                        st.markdown(f"**&#128100; Patient**\\n\\n{_pat or \'&mdash;\'}")
                with hc2:
                    if _is_uncertain(ocr.get("date", "")):
                        st.text_input(
                            "&#128197; Date *(uncertain)*",
                            value=_strip_unc(_dt), key="edit_date",
                        )
                    else:
                        st.markdown(f"**&#128197; Date**\\n\\n{_dt or \'&mdash;\'}")
                with hc3:
                    if _is_uncertain(ocr.get("prescriber", "")):
                        st.text_input(
                            "&#129658; Prescriber *(uncertain)*",
                            value=_strip_unc(_pre), key="edit_prescriber",
                        )
                    else:
                        st.markdown(f"**&#129658; Prescriber**\\n\\n{_pre or \'&mdash;\'}")

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
                        " <span style=\'background:#FFF8E1;color:#BF6000;"
                        "padding:1px 7px;border-radius:10px;font-size:.7rem;"
                        "font-weight:700;\'>\u26a0 Uncertain Fields</span>"
                        if _has_unc else ""
                    )
                    st.markdown(
                        f"<div style=\'border:1.5px solid {_border};border-radius:10px;"
                        f"padding:.9rem 1.1rem;margin-bottom:.8rem;background:#fff;\'>"
                        f"<span style=\'font-weight:700;color:#0B3C5D;font-size:.95rem;\'>"
                        f";&#128138; Medication {_mi + 1}{_unc_badge}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1:
                        if _nu:
                            st.text_input("Drug Name \u26a0", value=_strip_unc(_name),
                                          key=f"edit_med_{_mi}_name")
                        else:
                            st.markdown(f"**Drug Name**\\n\\n{_strip_unc(_name) or \'&mdash;\'}")
                    with mc2:
                        if _du:
                            st.text_input("Dosage \u26a0", value=_strip_unc(_dose),
                                          key=f"edit_med_{_mi}_dosage")
                        else:
                            st.markdown(f"**Dosage**\\n\\n{_strip_unc(_dose) or \'&mdash;\'}")
                    with mc3:
                        if _fu:
                            st.text_input("Frequency \u26a0", value=_strip_unc(_freq),
                                          key=f"edit_med_{_mi}_frequency")
                        else:
                            st.markdown(f"**Frequency**\\n\\n{_strip_unc(_freq) or \'&mdash;\'}")
                    with mc4:
                        if _uu:
                            st.text_input("Duration \u26a0", value=_strip_unc(_dur),
                                          key=f"edit_med_{_mi}_duration")
                        else:
                            st.markdown(f"**Duration**\\n\\n{_strip_unc(_dur) or \'&mdash;\'}")

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
                        st.success("\u2705 Corrections saved!")
                        st.rerun()

                st.markdown("---")

                #  Drug tag pills 
                st.markdown("**Detected medications (summary):**")
                _pill_html = "".join(
                    f"<span class=\'drug-tag\'>{re.sub(r\'\\\\s*\\\\(uncertain\\\\)\\\\s*\', \'\', m.get(\'name\',\'\'), flags=re.IGNORECASE).strip()}</span>"
                    for m in parsed_meds if m.get("name")
                )
                st.markdown(_pill_html, unsafe_allow_html=True)

            else:
                # Fallback display for error / non-JSON responses
                conf_pct   = int(ocr.get("confidence", 0) * 100)
                conf_color = "#388E3C" if conf_pct >= 90 else "#BF6000" if conf_pct >= 75 else "#C62828"
                st.markdown(
                    f"<div class=\'ocr-card\'>"
                    f"<div style=\'display:flex;justify-content:space-between;align-items:center;\'>"
                    f"<span style=\'font-weight:600;color:#0B3C5D;\'>Response</span>"
                    f"<span style=\'color:{conf_color};font-weight:700;font-size:.83rem;\'>"
                    f"Confidence: {conf_pct}%</span>"
                    f"</div><pre>{ocr.get(\'extracted_text\',\'\')}</pre></div>",
                    unsafe_allow_html=True,
                )
                pi1, pi2 = st.columns(2)
                with pi1:
                    st.markdown(f"**Patient:** {ocr.get(\'patient\', \'\')} ")
                    st.markdown(f"**Date:** {ocr.get(\'date\', \'\')} ")
                with pi2:
                    st.markdown(f"**Prescriber:** {ocr.get(\'prescriber\', \'\')} ")

            #  Interaction warnings 
            if ocr.get("interactions"):
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### \u26a0\ufe0f Drug Interaction Warnings")
                for _ix in ocr["interactions"]:
                    if INTERACTION_CHECKER_AVAILABLE:
                        st.markdown(format_interaction_alert(_ix), unsafe_allow_html=True)
                    else:
                        _icon = {"major": "\U0001f6ab", "moderate": "\u26a0\ufe0f",
                                 "minor": "\u2139\ufe0f"}.get(_ix.get("severity", "minor"), "\u2022")
                        st.warning(
                            f"{_icon} {_ix.get(\'drug1\',\'\')} + {_ix.get(\'drug2\',\'\')}: "
                            f"{_ix.get(\'description\',\'\')}"
                        )

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("\U0001f50e  Check Drug Interactions",
                         use_container_width=True, key="check_inter_btn"):
                with st.spinner("Querying interaction database..."):
                    _ixs = check_drug_interactions(ocr.get("medications", []))
                if _ixs:
                    try:
                        from database import log_event as _le
                        _ms2 = max(
                            (_i2.get("severity","minor") for _i2 in _ixs),
                            key=lambda s: {"major":2,"moderate":1,"minor":0}.get(s,0),
                            default="minor",
                        )
                        _le("interaction_flagged", {
                            "drugs": [_i2.get("drug_a","") for _i2 in _ixs[:3]],
                            "count": len(_ixs), "severity": _ms2,
                            "has_major": any(_i2.get("severity")=="major" for _i2 in _ixs),
                        })
                    except Exception:
                        pass
                st.markdown("**Interaction Report:**")
                if _ixs:
                    for _ix in _ixs:
                        _s = _ix["severity"]
                        st.markdown(
                            f"<div class=\'custom-alert alert-warning\'>"
                            f"<span class=\'sev-badge sev-{_s}\'>{_s}</span>"
                            f"&ensp;<strong>{_ix[\'drug_a\']}</strong>"
                            f" &harr; <strong>{_ix[\'drug_b\']}</strong><br>"
                            f"<span style=\'font-size:.86rem;margin-top:.3rem;display:block;\'>"
                            f"{_ix[\'description\']}</span></div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<div class=\'custom-alert alert-success\'>"
                        "\u2705  No significant interactions detected.</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                """
                <div style=\'text-align:center; padding:3rem 1rem; color:#6B8CAE;
                            background:#fff; border-radius:12px;
                            border: 2px dashed #B0CEE3;\'>
                    <div style=\'font-size:3rem; margin-bottom:0.75rem;\'>\U0001f4cb</div>
                    <div style=\'font-size:1rem; font-weight:500;\'>Awaiting prescription upload</div>
                    <div style=\'font-size:0.82rem; margin-top:0.35rem;\'>
                        Results will appear here after analysis
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
'''

idx_s = content.find(OLD_COL_RESULT_START)
idx_e = content.find(OLD_COL_RESULT_END)
if idx_s == -1 or idx_e == -1:
    sys.exit("ERROR: col_result anchors not found")

content = content[:idx_s] + new_col_result + content[idx_e:]
print("[2/4] col_result block replaced OK")

# 
# 3.  Add groq_api_key + ocr_edited to session state
# 
OLD_STATE = "    st.session_state.pending_input = None\n"
NEW_STATE  = (
    "    st.session_state.pending_input = None\n\n"
    "if \"groq_api_key\" not in st.session_state:\n"
    "    st.session_state.groq_api_key = \"\"\n\n"
    "if \"ocr_edited\" not in st.session_state:\n"
    "    st.session_state.ocr_edited = {}\n"
)
if OLD_STATE not in content:
    sys.exit("ERROR: pending_input state anchor not found")
content = content.replace(OLD_STATE, NEW_STATE, 1)
print("[3/4] session state init updated OK")

# 
# 4.  Add Groq API key field to Settings OCR expander
# 
OLD_OCR_EXP = "    # OCR\n    with st.expander(\"\\U0001f52c  OCR Engine Configuration\", expanded=False):"
NEW_OCR_EXP = "    # OCR\n    with st.expander(\"\\U0001f52c  OCR Engine Configuration\", expanded=False):\n        st.markdown(\"**Groq Vision API (prescription OCR)**\")\n        st.text_input(\"Groq API Key\", type=\"password\", key=\"groq_api_key\",\n                      help=\"Required for prescription scanning. Get yours at console.groq.com\")\n        st.divider()"
if "OCR Engine Configuration" not in content:
    sys.exit("ERROR: OCR Engine Configuration expander not found")
# Use the raw open marker
_ocr_exp_marker = "with st.expander(\"\\U0001f52c  OCR Engine Configuration\", expanded=False):"
_ocr_exp_idx = content.find(_ocr_exp_marker)
if _ocr_exp_idx == -1:
    print("[4/4] WARN: OCR expander exact marker not found, skipping settings patch")
else:
    _ins_pos = _ocr_exp_idx + len(_ocr_exp_marker)
    _groq_key_block = (
        "\n        st.markdown(\"**Groq Vision API (used for prescription OCR)**\")\n"
        "        st.text_input(\"Groq API Key\", type=\"password\", key=\"groq_api_key\",\n"
        "                      help=\"Required for prescription scanning. Get yours at console.groq.com\")\n"
        "        st.divider()"
    )
    content = content[:_ins_pos] + _groq_key_block + content[_ins_pos:]
    print("[4/4] Settings OCR expander updated OK")

#  Write back 
open("app.py", "w", encoding="utf-8").write(content)
print("Done  app.py written.")
