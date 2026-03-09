"""
ocr_engine.py  -  Handwritten Prescription OCR + Parser
=========================================================
Accepts an image file path (or raw bytes), applies a multi-stage OpenCV
preprocessing pipeline to improve OCR accuracy on handwriting, then runs
pytesseract and parses drug names / doses with regex.

Standalone usage
----------------
    python ocr_engine.py path/to/prescription.png

Programmatic usage
------------------
    from ocr_engine import process_image_path, process_image_bytes

    result = process_image_path("rx.jpg")
    # or
    result = process_image_bytes(open("rx.jpg", "rb").read(), filename="rx.jpg")

Windows Tesseract setup
-----------------------
1. Download installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default path (C:\\Program Files\\Tesseract-OCR\\tesseract.exe)
3. pip install pytesseract opencv-python-headless Pillow numpy

Returns
-------
dict with keys:
    status          : "success" | "error"
    extracted_text  : raw OCR string
    medications     : list of {"name": str, "dose": str, "unit": str, "sig": str}
    patient         : str or ""
    date            : str or ""
    prescriber      : str or ""
    confidence      : float 0-1  (pytesseract mean confidence)
    error           : str  (only present when status == "error")
    preprocessing   : list of stage names applied
"""

from __future__ import annotations

import io
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Optional

#  Optional heavy imports (graceful degradation) 

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# PIL import (always available)
try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

# pytesseract import (may be missing)
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

#  Tesseract binary path (Windows default; override via env var) 
_TESS_CMD = os.environ.get(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)
if TESSERACT_AVAILABLE and os.path.isfile(_TESS_CMD):
    pytesseract.pytesseract.tesseract_cmd = _TESS_CMD


# 
# PREPROCESSING PIPELINE
# 

def _to_numpy(image_input) -> "np.ndarray":
    """Accept file path, bytes, PIL Image, or numpy array."""
    if not CV2_AVAILABLE:
        raise RuntimeError("opencv-python is not installed")

    if isinstance(image_input, np.ndarray):
        return image_input
    if isinstance(image_input, PILImage.Image):
        return cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
    if isinstance(image_input, (bytes, bytearray)):
        arr = np.frombuffer(image_input, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if isinstance(image_input, (str, Path)):
        img = cv2.imread(str(image_input))
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_input}")
        return img
    raise TypeError(f"Unsupported image type: {type(image_input)}")


def _deskew(gray: "np.ndarray") -> "np.ndarray":
    """
    Correct skew using Hough line transform.
    Falls back to returning original on failure.
    """
    try:
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
        if lines is None:
            return gray

        angles = []
        for rho, theta in lines[:, 0]:
            angle = (theta - np.pi / 2) * (180 / np.pi)
            if abs(angle) < 45:          # ignore near-vertical lines
                angles.append(angle)

        if not angles:
            return gray

        median_angle = float(np.median(angles))
        if abs(median_angle) < 0.5:      # skip tiny corrections
            return gray

        h, w = gray.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            gray, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception:
        return gray


def preprocess_image(
    image_input,
    *,
    deskew: bool = True,
    upscale: bool = True,
    denoise: bool = True,
    adaptive_threshold: bool = True,
    morph_close: bool = True,
) -> tuple["np.ndarray", list[str]]:
    """
    Apply a configurable preprocessing pipeline and return
    (processed_grayscale_ndarray, list_of_applied_stage_names).

    Pipeline order
    --------------
    1. Load / convert to BGR numpy array
    2. Upscale if small (improves OCR on low-res scans)
    3. Convert to grayscale
    4. Deskew (Hough-based rotation correction)
    5. Gaussian denoise
    6. Adaptive thresholding (Gaussian mean, creates binary image)
    7. Morphological closing (fills small gaps in thin strokes)
    """
    if not CV2_AVAILABLE:
        raise RuntimeError("opencv-python-headless is required for preprocessing")

    stages: list[str] = []

    img = _to_numpy(image_input)
    stages.append("load")

    #  2. Upscale if smaller than 1000 px on the long side 
    if upscale:
        h, w = img.shape[:2]
        long_side = max(h, w)
        if long_side < 1000:
            scale = 1000 / long_side
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_CUBIC)
            stages.append(f"upscale x{scale:.2f}")

    #  3. Grayscale 
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    stages.append("grayscale")

    #  4. Deskew 
    if deskew:
        gray = _deskew(gray)
        stages.append("deskew")

    #  5. Gaussian denoise 
    if denoise:
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        stages.append("denoise")

    #  6. Adaptive threshold 
    if adaptive_threshold:
        gray = cv2.adaptiveThreshold(
            gray,
            maxValue=255,
            adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            thresholdType=cv2.THRESH_BINARY,
            blockSize=31,
            C=7,
        )
        stages.append("adaptive_threshold")

    #  7. Morphological close (fill small holes in strokes) 
    if morph_close:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        stages.append("morph_close")

    return gray, stages


# 
# OCR
# 

# Tesseract config optimised for printed + handwritten medical text
# Two configs: bilingual (ara+eng) when Arabic tessdata is present, else English-only
_ARA_TESSDATA = os.path.isfile(r"C:\Program Files\Tesseract-OCR\tessdata\ara.traineddata")
_LANG = "ara+eng" if _ARA_TESSDATA else "eng"
_OCR_CONFIG = f"--oem 3 --psm 6 -l {_LANG}" 




def _refine_with_llm(raw_text: str, host: str = "http://localhost:11434") -> str:
    try:
        import ollama as _ollama
        # برومبت متخصص في إصلاح كوارث الـ OCR للروشتات
        prompt = (
            "You are a clinical pharmacist assistant. The text below is a highly distorted OCR output from a handwritten prescription. "
            "Please extract the correct medication names and dosages. "
            "Example: 'Coversyl-plus', 'Norvasc 5mg', 'Diamicron 60 MR', 'Crestor 10mg', 'Plavix', 'Colchicine 0.5mg'. "
            f"CORRECT THE FOLLOWING TEXT:\n{raw_text}"
        )
        client = _ollama.Client(host=host)
        response = client.chat(
            model="adrienbrault/biomistral-7b:Q4_K_M", # تأكد من اسم الموديل عندك
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"].strip()
    except Exception:
        return raw_text

def _run_ocr(processed_gray: "np.ndarray") -> tuple[str, float]:
    """
    Run pytesseract on a preprocessed grayscale image.
    Returns (text, mean_confidence_0_to_1).
    """
    if not TESSERACT_AVAILABLE:
        raise RuntimeError(
            "pytesseract is not installed or Tesseract binary not found.\n"
            "Install: pip install pytesseract\n"
            f"Binary:  {_TESS_CMD}"
        )

    pil_img = PILImage.fromarray(processed_gray)

    # Get per-word confidence data
    data = pytesseract.image_to_data(
        pil_img,
        config=_OCR_CONFIG,
        output_type=pytesseract.Output.DICT,
    )

    conf_vals = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit()]
    pos_confs = [c for c in conf_vals if c >= 0]
    mean_conf = (sum(pos_confs) / len(pos_confs) / 100.0) if pos_confs else 0.0

    high_conf_words = [
        data["text"][k]
        for k in range(len(data["text"]))
        if str(data["conf"][k]).lstrip("-").isdigit()
        and int(data["conf"][k]) >= 40
        and data["text"][k].strip()
        and all(ord(c) < 128 for c in data["text"][k])
    ]
    clean_text = " ".join(high_conf_words)

    if not clean_text.strip():
        clean_text = pytesseract.image_to_string(pil_img, config=_OCR_CONFIG)

    # After computing mean_conf, before the return:
    CONFIDENCE_FLOOR = 0.25
    if mean_conf < CONFIDENCE_FLOOR and clean_text.strip():
        raise RuntimeError(
            f"OCR confidence too low ({mean_conf:.0%}) — image may be too blurry or "
            "at an extreme angle. Try a clearer photo."
        )

    return clean_text.strip(), round(mean_conf, 3)


# 
# REGEX PARSER
# 

#  Unit pattern 
_UNIT_PAT = r"(?:mg|mcg|ug|g|ml|mL|L|units?|IU|mmol|mEq|%)"

#  Dose + unit  e.g. "500 mg", "0.5mg", "10 mcg" 
_DOSE_PAT = rf"(\d+(?:\.\d+)?)\s*({_UNIT_PAT})"

#  Known medication name fragments (extend as needed) 
_DRUG_NAME_HINTS = re.compile(
    r"\b("
    # antibiotics
    r"amoxicillin|amoxil|augmentin|azithromycin|ciprofloxacin|doxycycline|"
    r"metronidazole|penicillin|trimethoprim|clindamycin|erythromycin|"
    # analgesics / NSAIDs
    r"ibuprofen|naproxen|diclofenac|aspirin|celecoxib|indomethacin|"
    r"paracetamol|acetaminophen|codeine|tramadol|morphine|oxycodone|"
    # PPIs / GI
    r"omeprazole|pantoprazole|lansoprazole|esomeprazole|ranitidine|"
    r"metoclopramide|ondansetron|"
    # antihypertensives / cardiac
    r"amlodipine|lisinopril|atenolol|metoprolol|ramipril|enalapril|"
    r"losartan|valsartan|furosemide|spironolactone|bisoprolol|"
    r"warfarin|clopidogrel|apixaban|rivaroxaban|atorvastatin|simvastatin|"
    r"rosuvastatin|digoxin|amiodarone|"
    # diabetes
    r"metformin|glipizide|gliclazide|insulin|sitagliptin|empagliflozin|"
    # respiratory
    r"salbutamol|albuterol|budesonide|fluticasone|montelukast|ipratropium|"
    r"prednisolone|prednisone|"
    # psych / neuro
    r"sertraline|fluoxetine|amitriptyline|diazepam|lorazepam|alprazolam|"
    r"haloperidol|risperidone|quetiapine|levodopa|donepezil"
    r")\b",
    re.IGNORECASE,
)

#  Rx line  e.g. "Rx 1 : Amoxicillin 500mg" 
_RX_LINE = re.compile(
    r"(?:Rx|R/|#)\s*\d*\s*[:\-]?\s*"
    r"([A-Za-z][A-Za-z\s\-]+?)\s+"
    + _DOSE_PAT,
    re.IGNORECASE,
)

#  Sig (directions) 
_SIG_LINE = re.compile(
    r"Sig\s*[:\-]?\s*(.{5,80})",
    re.IGNORECASE,
)

#  Patient / Date / Prescriber 
_PATIENT_RE = re.compile(
    r"(?:Patient|Pt|Name)\s*[:\-]\s*([A-Za-z][A-Za-z\s,\.]+?)(?:\s{2,}|$|\()",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"(?:Date|Dated?)\s*[:\-]\s*"
    r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}"
    r"|\d{1,2}\s+\w{3,9}\s+\d{4})",
    re.IGNORECASE,
)
_PRESCRIBER_RE = re.compile(
    r"(?:Provider|Physician|Dr\.?|Doctor|Prescriber)\s*[:\-]\s*"
    r"((?:Dr\.?\s+)?[A-Za-z][A-Za-z\s,\.]+?)(?:\s{2,}|$|,\s*M)",
    re.IGNORECASE,
)
_DEA_RE = re.compile(r"DEA\s*[:#]?\s*([A-Z]{2}\d{7})", re.IGNORECASE)


def parse_prescription_text(text: str) -> dict:
    """
    Parse raw OCR text into structured fields.

    Parameters
    ----------
    text : str
        Raw string returned by pytesseract.

    Returns
    -------
    dict with keys:
        medications  - list of dicts  {name, dose, unit, sig, raw_line}
        patient      - str
        date         - str
        prescriber   - str
        dea          - str
    """
    medications: list[dict] = []
    sig_lines = [m.group(1).strip() for m in _SIG_LINE.finditer(text)]
    sig_index = 0

    #  Strategy 1: explicit Rx lines 
    for match in _RX_LINE.finditer(text):
        name = match.group(1).strip().title()
        dose = match.group(2)
        unit = match.group(3)
        sig  = sig_lines[sig_index] if sig_index < len(sig_lines) else ""
        sig_index += 1
        medications.append({
            "name":     name,
            "dose":     dose,
            "unit":     unit,
            "sig":      sig,
            "raw_line": match.group(0).strip(),
        })

    #  Strategy 2: known drug name dictionary scan 
    found_names = {m["name"].lower() for m in medications}
    for line in text.splitlines():
        for drug_match in _DRUG_NAME_HINTS.finditer(line):
            drug_name = drug_match.group(1).strip().title()
            if drug_name.lower() in found_names:
                continue
            dose_match = re.search(_DOSE_PAT, line)
            if dose_match:
                medications.append({
                    "name":     drug_name,
                    "dose":     dose_match.group(1),
                    "unit":     dose_match.group(2),
                    "sig":      sig_lines[sig_index] if sig_index < len(sig_lines) else "",
                    "raw_line": line.strip(),
                })
                found_names.add(drug_name.lower())
                sig_index += 1

    #  Strategy 3: any "word + dose" pattern not yet captured 
    if not medications:
        for match in re.finditer(
            r"([A-Z][a-z]{3,}(?:\s+[A-Z]?[a-z]+)?)\s+" + _DOSE_PAT,
            text,
        ):
            name = match.group(1).strip().title()
            if name.lower() in found_names:
                continue
            medications.append({
                "name":     name,
                "dose":     match.group(2),
                "unit":     match.group(3),
                "sig":      sig_lines[sig_index] if sig_index < len(sig_lines) else "",
                "raw_line": match.group(0).strip(),
            })
            found_names.add(name.lower())
            sig_index += 1

    #  Header fields 
    def _first(pattern: re.Pattern, fallback: str = "") -> str:
        m = pattern.search(text)
        return m.group(1).strip() if m else fallback

    return {
        "medications": medications,
        "patient":     _first(_PATIENT_RE),
        "date":        _first(_DATE_RE),
        "prescriber":  _first(_PRESCRIBER_RE),
        "dea":         _first(_DEA_RE),
    }


# 
# PUBLIC API
# 

def process_image_path(
    file_path: str | Path,
    *,
    deskew: bool = True,
    upscale: bool = True,
    denoise: bool = True,
    adaptive_threshold: bool = True,
    morph_close: bool = True,
) -> dict:
    """
    Full pipeline: file path -> preprocessed image -> OCR -> parsed dict.

    Parameters
    ----------
    file_path : str or Path
        Path to PNG, JPG, TIFF, or BMP image.
    deskew, upscale, denoise, adaptive_threshold, morph_close : bool
        Toggle individual preprocessing stages.

    Returns
    -------
    dict  (see module docstring for key reference)
    """
    try:
        processed, stages = preprocess_image(
            Path(file_path),
            deskew=deskew,
            upscale=upscale,
            denoise=denoise,
            adaptive_threshold=adaptive_threshold,
            morph_close=morph_close,
        )
        raw_text, confidence = _run_ocr(processed)
        parsed = parse_prescription_text(raw_text)

        med_labels = [
            f"{m['name']} {m['dose']}{m['unit']}"
            for m in parsed["medications"]
        ]

        return {
            "status":         "success",
            "extracted_text": raw_text,
            "medications":    med_labels,
            "parsed_meds":    parsed["medications"],   # full structured list
            "patient":        parsed["patient"],
            "date":           parsed["date"],
            "prescriber":     parsed["prescriber"],
            "dea":            parsed["dea"],
            "confidence":     confidence,
            "preprocessing":  stages,
        }

    except Exception as exc:
        return {
            "status":         "error",
            "extracted_text": "",
            "medications":    [],
            "parsed_meds":    [],
            "patient":        "",
            "date":           "",
            "prescriber":     "",
            "dea":            "",
            "confidence":     0.0,
            "preprocessing":  [],
            "error":          str(exc),
        }


def process_image_bytes(
    image_bytes: bytes,
    filename: str = "image.png",
    **kwargs,
) -> dict:
    """
    Same as process_image_path but accepts raw bytes (e.g. from Streamlit uploader).
    Decodes in memory via cv2.imdecode to avoid temp-file read failures on Windows.
    """
    if not image_bytes:
        return {"status": "error", "error": "Empty image bytes received", "extracted_text": "", "medications": [], "parsed_meds": [], "patient": "", "date": "", "prescriber": "", "dea": "", "confidence": 0.0, "preprocessing": []}

    try:
        deskew = kwargs.pop("deskew", True)
        upscale = kwargs.pop("upscale", True)
        denoise = kwargs.pop("denoise", True)
        adaptive_threshold = kwargs.pop("adaptive_threshold", True)
        morph_close = kwargs.pop("morph_close", True)

        processed, stages = preprocess_image(
            image_bytes,
            deskew=deskew,
            upscale=upscale,
            denoise=denoise,
            adaptive_threshold=adaptive_threshold,
            morph_close=morph_close,
        )
        raw_text, confidence = _run_ocr(processed)
        parsed = parse_prescription_text(raw_text)

        med_labels = [
            f"{m['name']} {m['dose']}{m['unit']}"
            for m in parsed["medications"]
        ]

        return {
            "status":         "success",
            "extracted_text": raw_text,
            "medications":    med_labels,
            "parsed_meds":    parsed["medications"],
            "patient":        parsed.get("patient", ""),
            "date":           parsed.get("date", ""),
            "prescriber":     parsed.get("prescriber", ""),
            "dea":            parsed.get("dea", ""),
            "confidence":     round(confidence, 3),
            "preprocessing":  stages,
        }
    except Exception as exc:
        return {
            "status":         "error",
            "error":          str(exc),
            "extracted_text": "",
            "medications":    [],
            "parsed_meds":    [],
            "patient":        "",
            "date":           "",
            "prescriber":     "",
            "dea":            "",
            "confidence":     0.0,
            "preprocessing":  [],
        }


# 
# CLI  (python ocr_engine.py path/to/image.png)
# 

def _cli() -> None:
    import json
    import argparse

    parser = argparse.ArgumentParser(
        description="OCR a prescription image and print structured JSON."
    )
    parser.add_argument("image", help="Path to prescription image")
    parser.add_argument("--no-deskew",    dest="deskew",    action="store_false")
    parser.add_argument("--no-upscale",   dest="upscale",   action="store_false")
    parser.add_argument("--no-denoise",   dest="denoise",   action="store_false")
    parser.add_argument("--no-threshold", dest="adaptive_threshold", action="store_false")
    parser.add_argument("--no-morph",     dest="morph_close", action="store_false")
    parser.set_defaults(deskew=True, upscale=True, denoise=True,
                        adaptive_threshold=True, morph_close=True)
    args = parser.parse_args()

    result = process_image_path(
        args.image,
        deskew=args.deskew,
        upscale=args.upscale,
        denoise=args.denoise,
        adaptive_threshold=args.adaptive_threshold,
        morph_close=args.morph_close,
    )

    if result["status"] == "success":
        print("\n--- RAW OCR TEXT ---")
        print(result["extracted_text"])
        print("\n--- PARSED RESULT ---")
        printable = {k: v for k, v in result.items() if k != "extracted_text"}
        print(json.dumps(printable, indent=2))
    else:
        print(f"[ERROR] {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
