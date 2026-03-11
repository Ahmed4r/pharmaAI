from __future__ import annotations
import re
import streamlit as st

try:
    from interaction_checker import check_interactions
    _INTERACTION_CHECKER_AVAILABLE = True
except ImportError:
    _INTERACTION_CHECKER_AVAILABLE = False

    def check_interactions(drugs):
        return []


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
    """OCR via Google Gemini 1.5 Flash  native JSON mode, Egyptian prescription specialist."""
    import json
    import os as _os

    try:
        import google.generativeai as _genai
    except ImportError:
        return {
            "status": "error", "raw_json": None, "extracted_text": "",
            "medications": [], "parsed_meds": [], "patient": "", "date": "",
            "prescriber": "", "dea": "", "confidence": 0.0,
            "interactions": [], "preprocessing": [],
            "error": "google-generativeai not installed  run: pip install google-generativeai",
        }

    try:
        api_key = (
            st.session_state.get("gemini_api_key", "").strip()
            or _os.environ.get("GEMINI_API_KEY", "")
            or _os.environ.get("GOOGLE_API_KEY", "")
        )
        if not api_key:
            raise ValueError(
                "Gemini API key not set. Check your .env file for GEMINI_API_KEY."
            )

        # For Gemini vision: only upscale if too small  no aggressive CV processing
        # (CLAHE / bilateral / unsharp / deskew distort the image and hurt accuracy)
        _pp_steps: list[str] = []
        try:
            import io as _io2, numpy as _np2
            from PIL import Image as _PILImg2
            import cv2 as _cv2b
            _pil2 = _PILImg2.open(_io2.BytesIO(image_bytes)).convert("RGB")
            _h2, _w2 = _pil2.height, _pil2.width
            if max(_h2, _w2) < 1600:
                _scale2 = 1600 / max(_h2, _w2)
                _bgr2 = _cv2b.cvtColor(_np2.array(_pil2), _cv2b.COLOR_RGB2BGR)
                _bgr2 = _cv2b.resize(_bgr2, None, fx=_scale2, fy=_scale2,
                                     interpolation=_cv2b.INTER_LANCZOS4)
                _buf2 = _io2.BytesIO()
                _PILImg2.fromarray(_cv2b.cvtColor(_bgr2, _cv2b.COLOR_BGR2RGB)).save(_buf2, format="JPEG", quality=95)
                image_bytes = _buf2.getvalue()
                _pp_steps = ["Upscale"]
        except Exception:
            pass

        # Determine MIME type for Gemini
        _ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "jpeg"
        _mime = "image/jpeg" if _pp_steps else (f"image/jpeg" if _ext in ("jpg", "jpeg") else f"image/{_ext}")

        # Configure Gemini
        _genai.configure(api_key=api_key)
        _model = _genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 4096,
                "response_mime_type": "application/json",
            },
        )

        _prompt = (
            "You are an expert Egyptian Clinical Pharmacologist with years of experience "
            "reading handwritten Arabic/English prescriptions.\n\n"
            "==== STEP 1 — CONTEXT EXTRACTION (do this FIRST before reading drug names) ====\n"
            "Scan the entire image for any text that reveals the medical context:\n"
            "  a) Doctor name + speciality on the letterhead "
            "('\u0637\u0628\u064a\u0628 \u0623\u0637\u0641\u0627\u0644' = Pediatrics, "
            "'\u0628\u0627\u0637\u0646\u0629' = Internal Medicine, "
            "'\u062c\u0647\u0627\u0632 \u0647\u0636\u0645\u064a' = Gastroenterology, "
            "'\u0642\u0644\u0628' = Cardiology).\n"
            "  b) Diagnosis or chief-complaint words "
            "('\u0642\u0648\u0644\u0648\u0646', '\u0636\u063a\u0637', "
            "'\u0633\u0643\u0631', '\u0645\u0636\u0627\u062f \u062d\u064a\u0648\u064a').\n"
            "  c) Patient age if visible (pediatric vs adult changes drug families).\n"
            "Store these as 'doctor_specialty' and 'diagnosis_context' in the output.\n\n"
            "==== STEP 2 — SLASH NOTATION LOGIC ====\n"
            "The forward-slash '/' in a drug instruction is a SCHEDULING SEPARATOR, "
            "NOT a mathematical fraction, unless a plain fraction like '\u00bd tab' precedes a unit.\n"
            "  • '1/8'  = 1 tablet every 8 h  -> frequency: '3 times daily (every 8 h)', dosage: '1 tablet'\n"
            "  • '1/12' = 1 tablet every 12 h -> frequency: 'twice daily (every 12 h)', dosage: '1 tablet'\n"
            "  • '2/6'  = 2 tablets every 6 h -> frequency: '4 times daily (every 6 h)', dosage: '2 tablets'\n"
            "  • '\u00bd tab' or '\u0646\u0635 \u0642\u0631\u0635' = HALF a tablet (true fraction).\n"
            "  Set 'slash_notation_used': true in root JSON if you applied this rule.\n\n"
            "==== STEP 3 — DRUG NAME DISAMBIGUATION (use context from Step 1) ====\n"
            "When two drugs share similar letter shapes, choose the one matching the specialty/diagnosis.\n"
            "  • 'Colovatil' vs 'Clopidogrel': GI/pediatric context -> Colovatil.\n"
            "  • 'Norvasc' vs 'Novasc': cardiology/hypertension -> Norvasc (amlodipine).\n"
            "  • 'Glucophage' vs 'Glucovance': check for '\u0633\u0643\u0631'/diabetes.\n"
            "  • If genuinely ambiguous, set uncertain:true and list both in 'name_candidates'.\n\n"
            "==== STEP 4 — FIELD EXTRACTION ====\n"
            "For each medication extract:\n"
            "  name: Complete visible characters using Steps 2-3 logic.\n"
            "  dosage: Amount per dose. Apply slash-notation rule (1/8 -> '1 tablet', NOT 0.125).\n"
            "  frequency: Timing phrase; convert slash notation to plain English.\n"
            "  dose_interpretation: One sentence explaining how dose/freq was decoded.\n"
            "  uncertain: true only if completely unreadable.\n\n"
            "COMMON EGYPTIAN DRUGS (handwriting key):\n"
            "  Pediatric: V-Drop, Sanso Immune, eubion, Limotal Kids, Kidssi Appetite\n"
            "  GI:        Colovatil, Lactulose, Buscopan, Antinal, Flagyl, Smecta\n"
            "  Cardiac:   Norvasc, Concor, Aldactone, Lasix, Coversyl, Digoxin\n"
            "  Diabetes:  Glucophage, Amaryl, Januvia, Galvus, Jardiance\n"
            "  Antibiotics: Augmentin, Amoxil, Zithromax, Cephalexin, Ciprofloxacin\n\n"
            "DOSAGE RULES:\n"
            "- Number + unit (\u0633\u0645/ml/drop) on SAME or NEXT line after drug name = dosage.\n"
            "- NEVER skip a visible number.\n"
            "- Arabic amounts: '\u062e\u0645\u0633 \u0633\u0645'='5 ml', "
            "'\u0642\u0637\u0627\u0631\u0629'='1 drop', '\u0643\u064a\u0633'='1 sachet'.\n\n"
            "GENERAL RULES:\n"
            "- Read ALL lines top to bottom; do not skip any medication.\n"
            "- Do NOT invent drug names not visible on paper.\n"
            "- Ignore rubber stamps, clinic logos, watermarks.\n"
            "- Return ONLY a single compact JSON line, no newlines inside values.\n\n"
            "JSON SCHEMA:\n"
            '{\"patient\":\"string or null\",'
            '\"date\":\"YYYY-MM-DD or null\",'
            '\"prescriber\":\"doctor name + specialty or null\",'
            '\"doctor_specialty\":\"specialty or null\",'
            '\"diagnosis_context\":\"diagnosis/complaint clues or null\",'
            '\"slash_notation_used\":false,'
            '\"medications\":[{'
            '\"name\":\"string\",'
            '\"dosage\":\"string or null\",'
            '\"frequency\":\"string or null\",'
            '\"dose_interpretation\":\"string or null\",'
            '\"uncertain\":false,'
            '\"name_candidates\":[]}],'
            '\"confidence_score\":0.0}'
        )
        _response = _model.generate_content([
            _prompt,
            {"mime_type": _mime, "data": image_bytes},
        ])

        # Robust JSON extraction: handle fences, truncation, trailing commas
        _raw = _response.text.strip()
        parsed = None
        _errors = []

        # Strategy 1: direct parse
        try:
            parsed = json.loads(_raw)
        except Exception as e1:
            _errors.append(str(e1))

        # Strategy 2: strip markdown fences then parse
        if parsed is None:
            import re as _re
            _fenced = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", _raw, _re.DOTALL)
            if _fenced:
                try:
                    parsed = json.loads(_fenced.group(1))
                except Exception as e2:
                    _errors.append(str(e2))

        # Strategy 3: greedy brace extraction + repair
        if parsed is None:
            _start = _raw.find("{")
            _end = _raw.rfind("}")
            if _start != -1:
                _candidate = _raw[_start:(_end + 1 if _end != -1 else len(_raw))]
                # Remove trailing commas before } or ]
                _candidate = _re.sub(r",\s*([}\]])", r"\1", _candidate)
                # If string is still unterminated, close it
                try:
                    parsed = json.loads(_candidate)
                except Exception:
                    # Try completing truncated JSON
                    _opens = _candidate.count("{") - _candidate.count("}")
                    _arr   = _candidate.count("[") - _candidate.count("]")
                    # close any open string, array, object
                    if _candidate.rstrip()[-1] not in ('"', '}', ']'):
                        _candidate += '"'
                    _candidate += "]" * max(0, _arr) + "}" * max(0, _opens)
                    try:
                        parsed = json.loads(_candidate)
                    except Exception as e3:
                        _errors.append(str(e3))

        if parsed is None:
            raise ValueError(f"JSON parse failed after 3 strategies. Raw response snippet: {_raw[:300]!r}. Errors: {_errors}")


        medications = parsed.get("medications", [])
        med_names = [
            ((m.get("name") or "") + " " + (m.get("dosage") or "")).strip()
            for m in medications
        ]

        # Drug interaction check
        interactions: list = []
        if med_names and _INTERACTION_CHECKER_AVAILABLE:
            _drug_names = [(m.get("name") or "").split()[0] for m in medications if m.get("name")]
            interactions = check_interactions(_drug_names)

        # Drug normalization + confidence scoring
        _drug_match_conf = 0.80
        _interact_conf = 0.88
        try:
            from drug_normalizer import normalize_list as _nl, avg_confidence as _ac
            _norm_results = _nl([(m.get("name") or "") for m in medications])
            _drug_match_conf = _ac(_norm_results)
            for _m2, _nr in zip(medications, _norm_results):
                _m2["generic_name"] = _nr.generic
                _m2["brand_matched"] = _nr.brand_matched
                _m2["name_match_type"] = _nr.match_type
                _m2["name_confidence"] = _nr.confidence
                _m2["normalization_notes"] = _nr.notes
        except Exception:
            pass
        if interactions:
            _interact_conf = round(
                sum(_ix.get("interaction_confidence", 0.88) for _ix in interactions)
                / len(interactions), 3
            )

        # Log to DB
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
            "extracted_text": (parsed.get("prescriber") or "") + " | " + ", ".join(
                (m.get("name") or "") for m in medications
            ),
            "medications":   med_names,
            "parsed_meds":   medications,
            "patient":       parsed.get("patient", "") or "",
            "date":          parsed.get("date", "") or "",
            "prescriber":    parsed.get("prescriber", "") or "",
            "dea":           "",
            "confidence":    float(parsed.get("confidence_score", 1.0)),
            "interactions":  interactions,
            "drug_match_confidence": _drug_match_conf,
            "interaction_confidence": _interact_conf,
            "preprocessing": (_pp_steps + ["Gemini 2.5 Flash Vision", "JSON Mode"]),
        }

    except Exception as exc:
        return {
            "status":        "error",
            "raw_json":      None,
            "extracted_text": "",
            "medications":   [],
            "parsed_meds":   [],
            "patient":       "",
            "date":          "",
            "prescriber":    "",
            "dea":           "",
            "confidence":    0.0,
            "interactions":  [],
            "preprocessing": [],
            "error":         f"OCR failed: {exc}",
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
            raise ValueError("Groq API key not set. Check your .env file for GROQ_API_KEY.")
        meds_text = _json.dumps(parsed_meds, indent=2)
        prompt = (
            "You are a Clinical Pharmacologist specialising in Egyptian prescription "
            "safety review. Analyse the medications using the four-step framework.\n\n"
            "STEP 1 — CONTEXT VALIDATION\n"
            "Infer the therapeutic specialty from the drug list (GI, cardiology, "
            "pediatrics, diabetes, antibiotics, etc.). Flag any drug whose class is "
            "INCONSISTENT with the inferred specialty as a possible OCR misread. "
            "Add to 'dosing_errors' with severity 'moderate' and recommendation "
            "'Verify drug name — possible OCR error given patient context'.\n\n"
            "STEP 2 — SLASH NOTATION AWARENESS\n"
            "Frequency strings like '1/8', '1/12', '2/6' mean 'dose every N hours', "
            "NOT fractions. Interpret correctly before checking against standard freq.\n\n"
            "STEP 3 — EVIDENCE-BASED INTERACTIONS ONLY\n"
            "Report ONLY clinically significant interactions (moderate or major). "
            "Do NOT list trivial or theoretical ones.\n"
            "For every interaction include:\n"
            "  mechanism: PK/PD explanation "
            "(e.g. 'CYP2C9 inhibition increases warfarin exposure by ~50%').\n"
            "  effect: the clinical consequence.\n"
            "  recommendation: a specific actionable step.\n\n"
            "STEP 4 — PHARMACOKINETIC MEAL TIMING\n"
            "Add 'meal_timing' for EVERY medication in frequency_alerts:\n"
            "  'Take on empty stomach (30-60 min before food)': omeprazole, "
            "levothyroxine, bisphosphonates.\n"
            "  'Take with food to reduce GI upset / increase absorption': metformin, "
            "ibuprofen, ferrous sulphate.\n"
            "  'Avoid grapefruit (CYP3A4 substrate)': atorvastatin, amlodipine.\n"
            "  'Take with or without food': amoxicillin, azithromycin.\n\n"
            "Return ONLY a valid JSON object (no markdown) with this structure:\n"
            "{\n"
            '  \"inferred_specialty\": \"string\",\n'
            '  \"context_flags\": [\"string\"],\n'
            '  \"dosing_errors\": [\n'
            '    {\"drug\": \"name\", \"prescribed_dose\": \"given\", '
            '\"safe_range\": \"min-max unit\",\n'
            '     \"severity\": \"major|moderate|minor\", \"recommendation\": \"action\"}\n'
            "  ],\n"
            '  \"interactions\": [\n'
            '    {\"drug1\": \"name1\", \"drug2\": \"name2\",\n'
            '     \"mechanism\": \"PK/PD explanation\",\n'
            '     \"severity\": \"major|moderate|minor\", \"effect\": \"clinical effect\",\n'
            '     \"recommendation\": \"action\"}\n'
            "  ],\n"
            '  \"frequency_alerts\": [\n'
            '    {\"drug\": \"name\", \"prescribed_frequency\": \"given\",\n'
            '     \"standard_frequency\": \"expected\", '
            '\"meal_timing\": \"before/with/after food guidance\",\n'
            '     \"severity\": \"major|moderate|minor\", \"recommendation\": \"action\"}\n'
            "  ],\n"
            '  \"summary\": \"2-3 sentence safety summary\"\n'
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

