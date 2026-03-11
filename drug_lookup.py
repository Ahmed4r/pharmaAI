from __future__ import annotations


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

