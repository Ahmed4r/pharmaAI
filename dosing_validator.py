"""
dosing_validator.py
===================
Validates extracted prescription doses against known safe ranges.

Public API
----------
validate_prescription(parsed_meds: list[dict]) -> list[dict]
    Each input dict: {name, dose, unit, sig}
    Each output dict: {drug, dose, unit, status, error_type, message, valid}

validate_dose(drug: str, dose: float, unit: str) -> dict
    Returns single validation result dict.
"""
from __future__ import annotations
import re

# Safe dose ranges: {drug_name: {min, max, unit, max_daily, max_daily_unit}}
_RANGES: dict[str, dict] = {
    "amoxicillin":    {"min": 250,   "max": 875,   "unit": "mg",  "max_daily": 3000},
    "ibuprofen":      {"min": 200,   "max": 800,   "unit": "mg",  "max_daily": 3200},
    "omeprazole":     {"min": 10,    "max": 40,    "unit": "mg",  "max_daily": 80},
    "metformin":      {"min": 500,   "max": 1000,  "unit": "mg",  "max_daily": 2550},
    "warfarin":       {"min": 1,     "max": 10,    "unit": "mg",  "max_daily": 15},
    "atorvastatin":   {"min": 10,    "max": 80,    "unit": "mg",  "max_daily": 80},
    "aspirin":        {"min": 75,    "max": 1000,  "unit": "mg",  "max_daily": 4000},
    "clopidogrel":    {"min": 75,    "max": 600,   "unit": "mg",  "max_daily": 600},
    "metronidazole":  {"min": 200,   "max": 500,   "unit": "mg",  "max_daily": 2000},
    "lisinopril":     {"min": 2.5,   "max": 40,    "unit": "mg",  "max_daily": 80},
    "furosemide":     {"min": 20,    "max": 80,    "unit": "mg",  "max_daily": 600},
    "ciprofloxacin":  {"min": 250,   "max": 750,   "unit": "mg",  "max_daily": 1500},
    "sertraline":     {"min": 25,    "max": 200,   "unit": "mg",  "max_daily": 200},
    "amlodipine":     {"min": 2.5,   "max": 10,    "unit": "mg",  "max_daily": 10},
    "digoxin":        {"min": 0.0625,"max": 0.25,  "unit": "mg",  "max_daily": 0.375},
    "amiodarone":     {"min": 100,   "max": 400,   "unit": "mg",  "max_daily": 1600},
    "paracetamol":    {"min": 325,   "max": 1000,  "unit": "mg",  "max_daily": 4000},
    "acetaminophen":  {"min": 325,   "max": 1000,  "unit": "mg",  "max_daily": 4000},
    "naproxen":       {"min": 220,   "max": 500,   "unit": "mg",  "max_daily": 1500},
    "diclofenac":     {"min": 25,    "max": 75,    "unit": "mg",  "max_daily": 150},
    "tramadol":       {"min": 50,    "max": 100,   "unit": "mg",  "max_daily": 400},
    "prednisolone":   {"min": 5,     "max": 60,    "unit": "mg",  "max_daily": 60},
    "salbutamol":     {"min": 100,   "max": 400,   "unit": "mcg", "max_daily": 1600},
    "insulin":        {"min": 4,     "max": 50,    "unit": "units","max_daily": 200},
}

_SYNONYMS: dict[str, str] = {
    "plavix":"clopidogrel","coumadin":"warfarin","advil":"ibuprofen",
    "motrin":"ibuprofen","nurofen":"ibuprofen","prilosec":"omeprazole",
    "losec":"omeprazole","glucophage":"metformin","lipitor":"atorvastatin",
    "zestril":"lisinopril","lasix":"furosemide","cipro":"ciprofloxacin",
    "flagyl":"metronidazole","zoloft":"sertraline","norvasc":"amlodipine",
    "lanoxin":"digoxin","cordarone":"amiodarone","augmentin":"amoxicillin",
    "amoxil":"amoxicillin","aspocid":"aspirin","tylenol":"paracetamol",
    "panadol":"paracetamol","acetaminophen":"paracetamol","aleve":"naproxen",
    "naprosyn":"naproxen",
}


def _normalise(name: str) -> str:
    n = re.sub(r"\s+\d[\d.,]*\s*(?:mg|mcg|g|ml|iu)\b.*$", "", name.lower().strip(), flags=re.I)
    return _SYNONYMS.get(n.strip(), n.strip())


def _try_db(drug_norm: str) -> dict | None:
    """Try to fetch dosing rule from SQLite database."""
    try:
        from database import get_connection, init_db
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT min_dose, max_dose, unit, max_daily FROM dosing_rules WHERE drug_name = ? LIMIT 1",
            (drug_norm,),
        )
        row = cur.fetchone()
        conn.close()
        if row and row["min_dose"] is not None:
            return {
                "min": row["min_dose"],
                "max": row["max_dose"],
                "unit": row["unit"] or "mg",
                "max_daily": row["max_daily"] or row["max_dose"] * 4,
            }
    except Exception:
        pass
    return None


def validate_dose(drug: str, dose: float, unit: str) -> dict:
    """
    Validate a single dose against known safe ranges.

    Returns dict with keys:
        drug, dose, unit, status, error_type, message, valid
    status: 'ok' | 'high' | 'low' | 'too_high' | 'too_low' | 'unknown'
    """
    norm = _normalise(drug)

    # Try DB first, then built-in dict
    rng = _try_db(norm)
    if rng is None:
        rng = _RANGES.get(norm)

    if rng is None:
        return {
            "drug": drug, "dose": dose, "unit": unit,
            "status": "unknown", "error_type": None,
            "message": f"{drug}: dose range not in local database - verify manually.",
            "valid": None,
        }

    # Unit mismatch warning
    expected_unit = rng.get("unit", "mg")
    if unit and unit.lower() != expected_unit.lower():
        msg = (
            f"{drug}: unit mismatch - received {unit} but expected {expected_unit}. "
            "Verify the prescription unit before dispensing."
        )
        return {
            "drug": drug, "dose": dose, "unit": unit,
            "status": "unknown", "error_type": "unit_mismatch",
            "message": msg, "valid": None,
        }

    mn, mx = rng["min"], rng["max"]

    if dose > mx * 2:
        return {
            "drug": drug, "dose": dose, "unit": unit,
            "status": "too_high", "error_type": "too_high",
            "message": (
                f"CRITICAL: {drug} {dose} {unit} is more than double the maximum dose "
                f"({mx} {unit}). Possible prescription error - do not dispense without verification."
            ),
            "valid": False,
        }
    if dose > mx:
        return {
            "drug": drug, "dose": dose, "unit": unit,
            "status": "high", "error_type": "high",
            "message": (
                f"WARNING: {drug} {dose} {unit} exceeds standard maximum single dose "
                f"(max {mx} {unit}). Verify intent or indication."
            ),
            "valid": False,
        }
    if dose < mn * 0.5:
        return {
            "drug": drug, "dose": dose, "unit": unit,
            "status": "too_low", "error_type": "too_low",
            "message": (
                f"WARNING: {drug} {dose} {unit} is below the minimum recommended dose "
                f"(min {mn} {unit}). Verify if sub-therapeutic dosing is intentional."
            ),
            "valid": False,
        }
    if dose < mn:
        return {
            "drug": drug, "dose": dose, "unit": unit,
            "status": "low", "error_type": "low",
            "message": f"{drug} {dose} {unit}: slightly below standard minimum ({mn} {unit}).",
            "valid": True,
        }

    return {
        "drug": drug, "dose": dose, "unit": unit,
        "status": "ok", "error_type": None,
        "message": f"{drug} {dose} {unit}: dose within normal range ({mn}-{mx} {unit}). OK.",
        "valid": True,
    }


def validate_prescription(parsed_meds: list[dict]) -> list[dict]:
    """
    Validate a list of parsed prescription medications.

    Parameters
    ----------
    parsed_meds : list of dicts from ocr_engine parse_prescription_text
        Each dict: {name, dose, unit, sig, raw_line}

    Returns
    -------
    list of validation result dicts (one per medication)
    """
    results = []
    for med in parsed_meds:
        drug = med.get("name", "")
        try:
            dose = float(med.get("dose", 0) or 0)
        except (TypeError, ValueError):
            dose = 0.0
        unit = (med.get("unit", "mg") or "mg").lower()
        if not drug:
            continue
        if dose <= 0:
            results.append({
                "drug": drug, "dose": dose, "unit": unit,
                "status": "unknown", "error_type": "no_dose",
                "message": f"{drug}: no dose value extracted - cannot validate.",
                "valid": None,
            })
            continue
        results.append(validate_dose(drug, dose, unit))
    return results


def check_pediatric_dose(drug_generic_name: str, extracted_dosage_str: str,
                          patient_weight_kg: float):
    """
    Weight-based pediatric safety check.

    Returns a warning string if dose exceeds the weight-adjusted maximum,
    or None if the dose is safe / cannot be evaluated.

    Rules implemented
    -----------------
    - Paracetamol / Acetaminophen : max 15 mg/kg per single dose
    """
    if not drug_generic_name or not extracted_dosage_str or not patient_weight_kg:
        return None

    norm = _normalise(drug_generic_name)

    # Extract mg value from dosage string
    mg_m = re.search(r"(\d+(?:\.\d+)?)\s*mg", extracted_dosage_str, re.I)
    if not mg_m:
        return None
    dose_mg = float(mg_m.group(1))

    # Paracetamol / Acetaminophen  max 15 mg/kg/dose
    if norm in ("paracetamol", "acetaminophen"):
        max_safe = 15.0 * patient_weight_kg
        if dose_mg > max_safe:
            return (
                f"PEDIATRIC OVERDOSE WARNING: {drug_generic_name} {dose_mg:.0f} mg "
                f"exceeds maximum safe pediatric dose of {max_safe:.0f} mg "
                f"({patient_weight_kg:.1f} kg patient; limit 15 mg/kg per dose). "
                "Reduce dose immediately."
            )

    return None
