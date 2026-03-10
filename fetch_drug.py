"""
fetch_drug.py    Auto-populate pharmaAI knowledge base from OpenFDA

Usage:
    python fetch_drug.py <drug_name> [drug_name2] ...
    python fetch_drug.py --rebuild-index
    python fetch_drug.py aspirin warfarin metformin --rebuild-index

Examples:
    python fetch_drug.py zyrtec zyprexa diazepam
    python fetch_drug.py --rebuild-index          # just rebuild ChromaDB
"""

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

import requests

KB_PATH = Path(__file__).parent / "knowledge_base" / "drugs.json"
OPENFDA_URL = "https://api.fda.gov/drug/label.json"
MAX_FIELD_CHARS  = 800   # keep each text chunk under this to fit in context window
BRAND_MAP_PATH   = Path(__file__).parent / "knowledge_base" / "brand_map.json"
OPENFDA_NDC_URL  = "https://api.fda.gov/drug/ndc.json"


def _clean(text: str, max_chars: int = MAX_FIELD_CHARS) -> str:
    """Strip FDA section headers, table markers, brackets, extra whitespace."""
    if not text:
        return ""
    # Remove section numbers like "7 DRUG INTERACTIONS" or "5.1 Heading"
    text = re.sub(r"\b\d+(\.\d+)*\s+[A-Z][A-Z\s]+\n?", " ", text)
    # Remove bracketed cross-references like [see Warnings (5.1)]
    text = re.sub(r"\[see[^\]]+\]", "", text, flags=re.IGNORECASE)
    # Collapse whitespace
    text = re.sub(r"\s{2,}", " ", text).strip()
    # Truncate neatly at a sentence boundary if too long
    if len(text) > max_chars:
        cut = text[:max_chars]
        last_period = cut.rfind(".")
        if last_period > max_chars // 2:
            cut = cut[:last_period + 1]
        text = cut
    return text


def _fetch_brand_names(generic_name: str) -> dict[str, str]:
    """Query OpenFDA NDC for all brand names of a generic drug.

    Returns {brand_lower: generic_lower} mapping for brand_map.json.
    """
    try:
        r = requests.get(
            OPENFDA_NDC_URL,
            params={"search": f'generic_name:"{generic_name}"', "limit": 20},
            timeout=10,
        )
        if r.status_code != 200:
            return {}
        mapping: dict[str, str] = {}
        for item in r.json().get("results", []):
            brand   = item.get("brand_name", "").strip().lower()
            generic = item.get("generic_name", "").strip().lower()
            # Only add if they differ (skip when brand == generic)
            if brand and generic and brand != generic:
                mapping[brand] = generic
        return mapping
    except Exception:
        return {}


def update_brand_map(new_entries: dict[str, str]) -> None:
    """Merge new_entries into knowledge_base/brand_map.json."""
    if not new_entries:
        return
    existing: dict = {}
    if BRAND_MAP_PATH.exists():
        try:
            existing = json.loads(BRAND_MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    before = len(existing)
    existing.update(new_entries)
    BRAND_MAP_PATH.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    added = len(existing) - before
    if added > 0:
        print(f"  Brand map: +{added} new brand names ({len(existing)} total)")


def _search_openfda(drug_name: str) -> dict | None:
    """Try generic name first, then brand name search."""
    for field in ("openfda.generic_name", "openfda.brand_name"):
        try:
            r = requests.get(
                OPENFDA_URL,
                params={"search": f'{field}:"{drug_name}"', "limit": 1},
                timeout=15,
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    return results[0]
        except requests.RequestException as e:
            print(f"  Network error: {e}")
    return None


def _extract_entries(label: dict, drug_name: str) -> list[dict]:
    """Turn an FDA label dict into 4 knowledge-base entries."""
    openfda = label.get("openfda", {})

    # Prefer the generic name from the label itself
    generic_names = openfda.get("generic_name", [])
    canonical = generic_names[0].title() if generic_names else drug_name.title()

    brand_names = openfda.get("brand_name", [])
    brand_str = ", ".join(brand_names[:3]) if brand_names else ""

    def _get(*keys) -> str:
        for k in keys:
            val = label.get(k, [])
            if val:
                return _clean(val[0])
        return ""

    #  OVERVIEW 
    description   = _get("description")
    mechanism     = _get("mechanism_of_action", "clinical_pharmacology")
    indications   = _get("indications_and_usage")
    overview_text = " ".join(filter(None, [
        f"{canonical}" + (f" (brands: {brand_str})" if brand_str else "") + ".",
        indications[:300] if indications else "",
        mechanism[:300] if mechanism else "",
        description[:200] if description else "",
    ]))
    overview_text = _clean(overview_text, 900)

    #  DOSING 
    dosing_text = _get("dosage_and_administration")
    renal        = _get("use_in_specific_populations")
    geriatric    = _get("geriatric_use")
    if renal:
        dosing_text += " Renal: " + renal[:250]
    if geriatric:
        dosing_text += " Elderly: " + geriatric[:150]
    dosing_text = _clean(dosing_text, 900)

    #  INTERACTIONS 
    interactions_text = _get("drug_interactions")
    interactions_text = _clean(interactions_text, 900)

    #  CONTRAINDICATIONS 
    contra_text  = _get("contraindications")
    warnings     = _get("warnings_and_cautions", "warnings", "boxed_warning")
    if warnings:
        contra_text += " WARNINGS: " + warnings[:350]
    contra_text = _clean(contra_text, 900)

    drug_id = re.sub(r"[^a-z0-9]", "_", canonical.lower())

    entries = []
    for category, text in [
        ("overview",         overview_text),
        ("dosing",           dosing_text),
        ("interactions",     interactions_text),
        ("contraindications", contra_text),
    ]:
        if text:
            entries.append({
                "id":       f"{drug_id}_{category}",
                "drug":     canonical,
                "category": category,
                "text":     text,
            })

    return entries


def add_drugs(drug_names: list[str]) -> list[str]:
    """Fetch each drug from OpenFDA and append to drugs.json. Returns list of added IDs."""
    data: list[dict] = json.loads(KB_PATH.read_text(encoding="utf-8"))
    existing_ids = {d["id"] for d in data}
    added_ids: list[str] = []

    for name in drug_names:
        print(f"\nFetching: {name} ...", end=" ", flush=True)
        label = _search_openfda(name)
        if not label:
            print(f"NOT FOUND in OpenFDA")
            continue
        entries = _extract_entries(label, name)
        count = 0
        for entry in entries:
            if entry["id"] not in existing_ids:
                data.append(entry)
                existing_ids.add(entry["id"])
                added_ids.append(entry["id"])
                count += 1
            else:
                print(f"\n  (skipped existing: {entry['id']})", end="")
        print(f"added {count} entries  [{', '.join(e['id'] for e in entries)}]")
        # Auto-fetch brand names for this drug and update brand_map.json
        canonical_lower = entries[0]["drug"].lower() if entries else name.lower()
        _brands = _fetch_brand_names(canonical_lower)
        update_brand_map(_brands)

    KB_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nKnowledge base: {len(data)} total entries")
    return added_ids


def rebuild_index() -> None:
    """Delete ChromaDB collection and re-index everything in drugs.json."""
    print("\nRebuilding ChromaDB index ...", flush=True)
    sys.path.insert(0, str(Path(__file__).parent))
    from rag_engine import rebuild_index as _rebuild
    _rebuild()
    print("Index rebuilt.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-fetch drug data from OpenFDA into pharmaAI knowledge base")
    parser.add_argument("drugs", nargs="*", help="Drug name(s) to fetch, e.g. zyrtec diazepam")
    parser.add_argument("--rebuild-index", action="store_true", help="Rebuild ChromaDB after adding drugs")
    parser.add_argument("--update-brand-map", metavar="DRUG", nargs="+",
                        help="Fetch brand names only (no KB entries added), e.g. --update-brand-map cetirizine metformin")
    args = parser.parse_args()

    if not args.drugs and not args.rebuild_index and not args.update_brand_map:
        parser.print_help()
        sys.exit(0)

    if args.drugs:
        add_drugs(args.drugs)

    if args.update_brand_map:
        print(f"Fetching brand names for: {args.update_brand_map}")
        for d in args.update_brand_map:
            brands = _fetch_brand_names(d.lower())
            update_brand_map(brands)
            print(f"  {d}: {len(brands)} brand names found")

    if args.rebuild_index:
        rebuild_index()
