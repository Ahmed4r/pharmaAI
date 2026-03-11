"""drug_lookup.py - Drug info + interaction lookup.
Tiers for lookup_drug_info():
  1. Local SQLite / knowledge_base/drugs.json  (drug_db)
  2. OpenFDA drug label API  (https://api.fda.gov/drug/label.json)
  3. RxNorm API              (https://rxnav.nlm.nih.gov)
"""
from __future__ import annotations
import re, urllib.request, urllib.parse, json as _json

# INN (international) -> USAN (US/FDA) name equivalences for OpenFDA lookups
_INN_TO_USAN: dict[str, str] = {
    "paracetamol":   "acetaminophen",
    "salbutamol":    "albuterol",
    "adrenaline":    "epinephrine",
    "noradrenaline": "norepinephrine",
    "suxamethonium": "succinylcholine",
    "lignocaine":    "lidocaine",
    "frusemide":     "furosemide",
    "glibenclamide": "glyburide",
    "pethidine":     "meperidine",
    "amfetamine":    "amphetamine",
}


# INN (international) -> USAN (US/FDA) name equivalences for OpenFDA lookups
_INN_TO_USAN: dict[str, str] = {
    "paracetamol":   "acetaminophen",
    "salbutamol":    "albuterol",
    "adrenaline":    "epinephrine",
    "noradrenaline": "norepinephrine",
    "suxamethonium": "succinylcholine",
    "lignocaine":    "lidocaine",
    "frusemide":     "furosemide",
    "glibenclamide": "glyburide",
    "pethidine":     "meperidine",
    "amfetamine":    "amphetamine",
}



#  helpers 

def _clean(text: str, max_chars: int = 400) -> str:
    """Strip HTML/legalese boilerplate from FDA label text."""
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"\s+", " ", t).strip()
    # Strip numbered FDA section headers (Title Case or ALL CAPS)
    t = re.sub(
        r"^\d+[\d.]*\s+"
        r"(?:Mechanism\s+of\s+Action|Indications?\s+and\s+Usage|"
        r"Contraindications?|Adverse\s+Reactions?|"
        r"Dosage\s+and\s+Administration|Clinical\s+Pharmacology|"
        r"Description|Warnings?|Precautions?|Drug\s+Interactions?)\s*",
        "", t, flags=re.I,
    )
    t = re.sub(
        r"^(INDICATIONS\s*AND\s*USAGE|CONTRAINDICATIONS|"
        r"ADVERSE\s*REACTIONS?|DOSAGE\s*AND\s*ADMINISTRATION"
        r"|DESCRIPTION|CLINICAL\s*PHARMACOLOGY)\s*[:\.\s]+",
        "", t, flags=re.I,
    )
    # Strip OTC Drug Facts section header words
    t = re.sub(
        r"^(Purpose|Uses|Directions|Warnings|Do not use|Stop use|Ask a doctor)[\s:]+",
        "", t, flags=re.I,
    )
    return t[:max_chars].rstrip(" ,;") + ("..." if len(t) > max_chars else "")


def _sentences(text: str, max_n: int = 4) -> list[str]:
    """Split paragraph into bullet-point sentences."""
    parts = re.split(r"[.;]\s+|\n+|[\u2022]", text)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) > 15:
            out.append(p[0].upper() + p[1:])
        if len(out) >= max_n:
            break
    return out


def _http_get(url: str, timeout: int = 5) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pharmaAI/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _json.loads(resp.read().decode())
    except Exception:
        return None


#  Tier 2: OpenFDA drug label 

def _openfda_lookup(name: str) -> dict | None:
    """Query OpenFDA label API for a drug name; return parsed dict or None."""
    name_l = name.lower().strip()

    for search_field in ("openfda.generic_name", "openfda.brand_name"):
        # NOTE: pass raw quoted string to urlencode  it will encode correctly
        url = "https://api.fda.gov/drug/label.json?" + urllib.parse.urlencode({
            "search": f'{search_field}:"{name}"',
            "limit": "1",
        })
        data = _http_get(url, timeout=6)
        if data and data.get("results"):
            label = data["results"][0]
            ofda = label.get("openfda", {})
            # Validate: result must actually contain our drug name
            all_names = (
                [n.lower() for n in ofda.get("generic_name", [])] +
                [n.lower() for n in ofda.get("brand_name", [])] +
                [n.lower() for n in ofda.get("substance_name", [])]
            )
            if any(name_l in n or n in name_l for n in all_names):
                return _parse_openfda_label(label)

    # Retry with US (USAN/FDA) name if INN name not found in OpenFDA
    usan = _INN_TO_USAN.get(name.lower().strip())
    if usan:
        return _openfda_lookup(usan)
    return None


def _parse_openfda_label(label: dict) -> dict:
    """Map OpenFDA label JSON to our standard drug profile dict."""
    ofda = label.get("openfda", {})

    brand_names = list(dict.fromkeys(
        b for b in ofda.get("brand_name", [])
        if not re.search(r"\d{2,}|\bfoundation\b|\bmoisturizer\b", b, re.I)
    ))[:5]
    generic_name = (ofda.get("generic_name") or [""])[0].title() or \
                   (ofda.get("substance_name") or [""])[0].title()

    # Drug class: prefer EPC (established pharmacological class)
    drug_class = ""
    for key in ("pharm_class_epc", "pharm_class_cs", "pharm_class_moa"):
        epc = ofda.get(key) or []
        if epc:
            drug_class = re.sub(r"\s*\[.*?\]", "", epc[0]).strip()
            break

    # Drug class OTC fallback: use purpose field if no pharm_class_epc
    if not drug_class:
        purpose = (label.get("purpose") or [])
        if purpose:
            dc_raw = re.sub(r"^Purpose\s+", "", purpose[0], flags=re.I).strip()
            drug_class = ", ".join(p.strip() for p in dc_raw.split("\n") if p.strip())[:60]

    # Mechanism: Rx label fields + OTC active_ingredient as fallback
    mechanism_raw = (
        (label.get("mechanism_of_action") or []) +
        (label.get("description") or []) +
        (label.get("clinical_pharmacology") or [])
    )
    if not mechanism_raw:
        # OTC labels: purpose describes the drug action
        mechanism_raw = label.get("purpose") or []
    mechanism = _clean(" ".join(mechanism_raw), 500) if mechanism_raw else ""

    # Indications
    ind_raw = " ".join(label.get("indications_and_usage") or [])
    indications = _sentences(_clean(ind_raw, 1000), 5) if ind_raw else []

    # Contraindications (Rx label or OTC do_not_use)
    ci_raw = " ".join(
        (label.get("contraindications") or []) +
        (label.get("do_not_use") or [])
    )
    contraindications = _sentences(_clean(ci_raw, 1000), 5) if ci_raw else []

    # Side effects (Rx adverse_reactions or OTC warnings/stop_use)
    se_raw = " ".join(
        (label.get("adverse_reactions") or []) +
        (label.get("warnings") or []) +
        (label.get("stop_use") or [])
    )
    side_effects = _sentences(_clean(se_raw, 1000), 6) if se_raw else []

    # Dosage
    dose_raw = " ".join(label.get("dosage_and_administration") or [])
    dosage = _clean(dose_raw, 300) if dose_raw else ""

    # Renal adjustment
    renal = ""
    if dose_raw:
        m = re.search(r"(renal[^.;]{0,200})", dose_raw, re.I)
        if m:
            renal = m.group(1)[:200].strip()

    # Pregnancy category
    preg = ""
    preg_raw = " ".join(
        (label.get("pregnancy") or []) +
        (label.get("teratogenic_effects") or []) +
        (label.get("use_in_specific_populations") or []) +
        (label.get("pregnancy_or_breast_feeding") or [])
    )
    m = re.search(r"Pregnancy\s+Category\s+([A-DX])\b", preg_raw, re.I)
    if m:
        preg = m.group(1)
    elif re.search(r"fetal\s+risk", preg_raw, re.I):
        preg = "D"
    elif preg_raw:
        preg = "See label"

    # Fall back to RxNorm drug class via CUI -> DAILYMED class if OpenFDA did not provide one
    if not drug_class and generic_name:
        try:
            _cui_data = _http_get(
                "https://rxnav.nlm.nih.gov/REST/rxcui.json?" +
                urllib.parse.urlencode({"name": generic_name.split()[0], "search": "2"}),
                timeout=4,
            )
            if _cui_data:
                _cuis = _cui_data.get("idGroup", {}).get("rxnormId", [])
                if _cuis:
                    _rxcls = _http_get(
                        "https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?" +
                        urllib.parse.urlencode({"rxcui": _cuis[0], "relaSource": "DAILYMED"}),
                        timeout=4,
                    )
                    if _rxcls:
                        _cls_items = _rxcls.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
                        if _cls_items:
                            drug_class = _cls_items[0].get("rxclassMinConceptItem", {}).get("className", "")
        except Exception:
            pass


    return {
        "generic_name":       generic_name or "Unknown",
        "brand_names":        brand_names,
        "drug_class":         drug_class,
        "mechanism":          mechanism,
        "indications":        indications,
        "contraindications":  contraindications,
        "side_effects":       side_effects,
        "dosage":             dosage,
        "pregnancy_category": preg,
        "renal_adjustment":   renal,
        "_source":            "openfda",
    }


#  Tier 3: RxNorm 

def _rxnorm_lookup(name: str) -> dict | None:
    """Minimal RxNorm lookup: CUI -> brand names + drug class."""
    cui_data = _http_get(
        "https://rxnav.nlm.nih.gov/REST/rxcui.json?" +
        urllib.parse.urlencode({"name": name, "search": "2"}),
        timeout=5,
    )
    if not cui_data:
        return None
    cuis = cui_data.get("idGroup", {}).get("rxnormId", [])
    if not cuis:
        return None
    cui = cuis[0]

    # RxTerms for brand name
    terms = _http_get(
        f"https://rxnav.nlm.nih.gov/REST/RxTerms/rxcui/{cui}/allinfo.json",
        timeout=5,
    )
    brands_raw: list[str] = []
    drug_class = ""
    if terms:
        ti = terms.get("rxtermsProperties") or {}
        if ti.get("brandName"):
            brands_raw = [ti["brandName"]]
        drug_class = ti.get("synonym") or ""

    # Drug class via MEDRT
    cls_data = _http_get(
        "https://rxnav.nlm.nih.gov/REST/rxclass/byDrugName.json?" +
        urllib.parse.urlencode({"drugName": name, "relaSource": "MEDRT"}),
        timeout=5,
    )
    if cls_data:
        classes = cls_data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
        if classes:
            drug_class = classes[0].get("rxclassMinConceptItem", {}).get("className", "") or drug_class

    if not cuis:
        return None

    return {
        "generic_name":       name.title(),
        "brand_names":        brands_raw,
        "drug_class":         drug_class,
        "mechanism":          "Retrieved from RxNorm. For full clinical details, check the FDA label.",
        "indications":        [],
        "contraindications":  [],
        "side_effects":       [],
        "dosage":             "",
        "pregnancy_category": "",
        "renal_adjustment":   "",
        "_source":            "rxnorm",
    }


#  Public API 

def lookup_drug_info(drug_name: str) -> dict:
    """Fetch drug profile. Tier 1: local DB; Tier 2: OpenFDA; Tier 3: RxNorm."""
    if not drug_name or not drug_name.strip():
        return _not_found(drug_name)

    # Normalize brand -> generic first
    search_name = drug_name.strip()
    try:
        from drug_normalizer import normalize as _norm
        _nr = _norm(drug_name)
        if _nr.match_type in ("exact", "generic", "alias"):
            search_name = _nr.generic
    except Exception:
        pass

    # Tier 1: local DB
    try:
        from drug_db import get_drug_info as _dbi
        d = _dbi(search_name)
        if not d.get("error"):
            dr = d.get("dosing_rule") or {}
            dosage = ""
            if dr:
                mn = dr.get("min_dose", "")
                mx = dr.get("max_dose", "")
                u  = dr.get("unit", "mg")
                frq = dr.get("frequency", "")
                dosage = f"{mn}-{mx} {u} {frq}".strip("- ")
            local_result = {
                "generic_name":       d.get("generic_name", search_name),
                "brand_names":        d.get("brand_names") or [],
                "drug_class":         d.get("drug_class", ""),
                "mechanism":          d.get("mechanism", ""),
                "indications":        d.get("indications") or [],
                "contraindications":  d.get("contraindications") or [],
                "side_effects":       d.get("side_effects") or [],
                "dosage":             dosage,
                "pregnancy_category": d.get("pregnancy_cat", ""),
                "renal_adjustment":   dr.get("renal_adjustment", "") if dr else "",
                "_source":            "local",
            }
            # If the local entry has structured clinical data, return it immediately
            _has_clinical = (
                local_result["mechanism"] or
                local_result["indications"] or
                local_result["contraindications"] or
                local_result["side_effects"] or
                local_result["dosage"]
            )
            if _has_clinical:
                return local_result
            # Local entry exists but lacks structured clinical fields (e.g. JSON-only overview blob).
            # Enrich silently from OpenFDA, preserving the confirmed generic name.
            _openfda = _openfda_lookup(local_result["generic_name"])
            if _openfda:
                _openfda["generic_name"] = local_result["generic_name"]
                _openfda["brand_names"]  = list(dict.fromkeys(
                    local_result["brand_names"] + _openfda.get("brand_names", [])
                ))
                _openfda["_source"] = "local"
                return _openfda
            return local_result  # Return even if empty rather than risk wrong API match
    except Exception:
        pass

    # Tier 2: OpenFDA (generic name first, then original brand name if different)
    for _name in list(dict.fromkeys([search_name, drug_name.strip()])):
        result = _openfda_lookup(_name)
        if result:
            return result

    # Tier 3: RxNorm
    result = _rxnorm_lookup(search_name)
    if result:
        return result

    return _not_found(drug_name)


def _not_found(name: str) -> dict:
    return {
        "generic_name":       name or "Unknown",
        "brand_names":        [],
        "drug_class":         "Not found",
        "mechanism":          "Drug not found in local database, OpenFDA, or RxNorm. Check spelling.",
        "indications":        [],
        "contraindications":  [],
        "side_effects":       [],
        "dosage":             "",
        "pregnancy_category": "",
        "renal_adjustment":   "",
        "_source":            "none",
    }


def check_drug_interactions(drug_list: list) -> list:
    """Query RxNav REST API for real drug-drug interactions."""
    if len(drug_list) < 2:
        return []

    # Step 1: resolve each drug name to an RxCUI
    cuis = []
    for drug in drug_list:
        name = drug.split()[0] if drug else ""
        if not name:
            continue
        data = _http_get(
            "https://rxnav.nlm.nih.gov/REST/rxcui.json?" +
            urllib.parse.urlencode({"name": name, "search": "2"}),
            timeout=6,
        )
        rxnorm_ids = (data or {}).get("idGroup", {}).get("rxnormId", [])
        if rxnorm_ids:
            cuis.append(rxnorm_ids[0])

    if len(cuis) < 2:
        return []

    # Step 2: query interaction list for all resolved CUIs
    results = []
    data = _http_get(
        "https://rxnav.nlm.nih.gov/REST/interaction/list.json?" +
        urllib.parse.urlencode({"rxcuis": " ".join(cuis)}),
        timeout=10,
    )
    SEV_MAP = {
        "high": "major", "critical": "major",
        "moderate": "moderate",
        "low": "minor", "minor": "minor",
    }
    for group in (data or {}).get("fullInteractionTypeGroup", []):
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
    return results