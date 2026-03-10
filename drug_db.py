"""drug_db.py - Drug database access layer (SQLite -> JSON fallback)."""
from __future__ import annotations
import json, re
from pathlib import Path

_KB = Path(__file__).parent / "knowledge_base" / "drugs.json"

_SYNONYMS = {
    "plavix":"clopidogrel","coumadin":"warfarin","jantoven":"warfarin",
    "advil":"ibuprofen","motrin":"ibuprofen","nurofen":"ibuprofen",
    "prilosec":"omeprazole","losec":"omeprazole",
    "glucophage":"metformin","lipitor":"atorvastatin",
    "zestril":"lisinopril","lasix":"furosemide",
    "cipro":"ciprofloxacin","flagyl":"metronidazole",
    "zoloft":"sertraline","norvasc":"amlodipine",
    "lanoxin":"digoxin","cordarone":"amiodarone",
    "augmentin":"amoxicillin","amoxil":"amoxicillin",
    "aspocid":"aspirin","ecotrin":"aspirin",
}


def _normalise(name: str) -> str:
    n = re.sub(r"\s+\d[\d.,]*\s*(?:mg|mcg|g|ml|iu)\b.*$", "", name.lower().strip(), flags=re.I)
    return _SYNONYMS.get(n.strip(), n.strip())


def get_drug_info(name: str) -> dict:
    """Return full drug profile dict. Tries SQLite first, then JSON knowledge base."""
    norm = _normalise(name)
    try:
        from database import get_connection, init_db
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM drugs WHERE name = ?", (norm,))
        row = cur.fetchone()
        if row:
            d = dict(row)
            for key in ("brand_names", "indications", "contraindications", "side_effects"):
                d[key] = json.loads(d.get(key) or "[]")
            cur.execute("SELECT * FROM dosing_rules WHERE drug_name = ? LIMIT 1", (norm,))
            r2 = cur.fetchone()
            if r2:
                d["dosing_rule"] = dict(r2)
            conn.close()
            return d
        conn.close()
    except Exception:
        pass
    # Fallback: knowledge_base/drugs.json
    if _KB.exists():
        docs = json.loads(_KB.read_text(encoding="utf-8"))
        chunks = [c for c in docs if c.get("drug", "").lower() == norm]
        if chunks:
            merged: dict = {"name": norm, "generic_name": norm.title()}
            for c in chunks:
                merged[c.get("category", "info")] = c.get("text", "")
            return merged
    return {"name": norm, "generic_name": name, "error": "Not found in local database."}


def search_drugs(query: str, limit: int = 10) -> list[dict]:
    """Search drugs by name substring."""
    q = query.lower().strip()
    try:
        from database import get_connection, init_db
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT name, generic_name, drug_class FROM drugs "
            "WHERE name LIKE ? OR generic_name LIKE ? LIMIT ?",
            (f"%{q}%", f"%{query}%", limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def get_all_drugs() -> list[str]:
    """Return list of all drug names in the database."""
    try:
        from database import get_connection, init_db
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM drugs ORDER BY name")
        names = [r[0] for r in cur.fetchall()]
        conn.close()
        return names
    except Exception:
        return []


def get_dosing_info(name: str) -> dict | None:
    """Return dosing rule dict for a drug, or None if not found."""
    norm = _normalise(name)
    try:
        from database import get_connection, init_db
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM dosing_rules WHERE drug_name = ? LIMIT 1", (norm,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None
