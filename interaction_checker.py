"""
interaction_checker.py - Drug-drug interaction checker.
Tries SQLite database first, falls back to built-in dict (works offline).
Public API: check_interactions(drug_list), format_interaction_alert(interaction)
"""
from __future__ import annotations
import re

_SYNONYMS: dict[str, str] = {
    "plavix":"clopidogrel","coumadin":"warfarin","jantoven":"warfarin",
    "aspocid":"aspirin","ecotrin":"aspirin","disprin":"aspirin",
    "advil":"ibuprofen","motrin":"ibuprofen","nurofen":"ibuprofen","brufen":"ibuprofen",
    "prilosec":"omeprazole","losec":"omeprazole",
    "glucophage":"metformin","fortamet":"metformin",
    "lipitor":"atorvastatin","zestril":"lisinopril","prinivil":"lisinopril",
    "lasix":"furosemide","cipro":"ciprofloxacin","ciproxin":"ciprofloxacin",
    "flagyl":"metronidazole","rozex":"metronidazole",
    "zoloft":"sertraline","lustral":"sertraline",
    "norvasc":"amlodipine","amlopres":"amlodipine",
    "lanoxin":"digoxin","cordarone":"amiodarone","pacerone":"amiodarone",
    "augmentin":"amoxicillin","amoxil":"amoxicillin",
    "tylenol":"paracetamol","panadol":"paracetamol","acetaminophen":"paracetamol",
    "aleve":"naproxen","naprosyn":"naproxen",
}

_BUILTIN: list[dict] = [
    # MAJOR interactions
    {"drug1":"warfarin","drug2":"aspirin","severity":"major",
     "mechanism":"Additive anticoagulant+antiplatelet + COX-1 GI mucosal damage.",
     "description":"Warfarin + Aspirin: MAJOR. Significantly increases serious haemorrhage risk including GI bleeding. Aspirin irreversibly inhibits platelet COX-1 and damages gastric mucosa.",
     "action":"Avoid unless specifically indicated. Use lowest aspirin dose +PPI. Monitor INR weekly."},
    {"drug1":"warfarin","drug2":"ibuprofen","severity":"major",
     "mechanism":"Additive anticoagulation +GI mucosa damage; protein-binding displacement raises free warfarin.",
     "description":"Warfarin + NSAID: MAJOR. NSAIDs inhibit platelet aggregation and cause gastric mucosal injury, dramatically increasing haemorrhage risk.",
     "action":"AVOID. Substitute paracetamol. Monitor INR closely if NSAID unavoidable."},
    {"drug1":"warfarin","drug2":"naproxen","severity":"major",
     "mechanism":"Same as ibuprofen: additive anticoagulation +GI mucosal damage from NSAID.",
     "description":"Warfarin + Naproxen (NSAID): MAJOR bleeding risk, same mechanism as ibuprofen.",
     "action":"AVOID. Use paracetamol. Add PPI if combination is essential."},
    {"drug1":"warfarin","drug2":"metronidazole","severity":"major",
     "mechanism":"CYP2C9 inhibition reduces S-warfarin clearance; INR rises within 3-5 days.",
     "description":"Warfarin + Metronidazole: MAJOR. CYP2C9 inhibition causes dangerous INR elevation.",
     "action":"Reduce warfarin 30-50%. Monitor INR every 2-3 days during course."},
    {"drug1":"warfarin","drug2":"ciprofloxacin","severity":"major",
     "mechanism":"CYP1A2 inhibition +gut flora suppression reduces vitamin K2 production.",
     "description":"Warfarin + Ciprofloxacin: MAJOR. INR can rise unpredictably within 2-7 days.",
     "action":"Monitor INR 3-5 days after starting ciprofloxacin. May need dose reduction."},
    {"drug1":"warfarin","drug2":"amiodarone","severity":"major",
     "mechanism":"Potent CYP2C9 inhibition; effect persists months after stopping amiodarone (t1/2 ~50 days).",
     "description":"Warfarin + Amiodarone: MAJOR. INR may double or triple over 4-8 weeks.",
     "action":"Reduce warfarin 30-50% on starting amiodarone. Monitor INR weekly for months."},
    {"drug1":"warfarin","drug2":"amoxicillin","severity":"moderate",
     "mechanism":"Amoxicillin reduces gut flora vitamin K2 synthesis, potentiating warfarin.",
     "description":"Warfarin + Amoxicillin: MODERATE. INR may rise during antibiotic therapy.",
     "action":"Monitor INR during antibiotic course."},
    {"drug1":"clopidogrel","drug2":"omeprazole","severity":"major",
     "mechanism":"CYP2C19 inhibition by omeprazole reduces clopidogrel active metabolite by 40-50%.",
     "description":"Clopidogrel + Omeprazole: MAJOR. Reduced antiplatelet efficacy - increased stent thrombosis risk.",
     "action":"Switch to pantoprazole or lansoprazole. If PPI essential, consider prasugrel or ticagrelor."},
    {"drug1":"sertraline","drug2":"tramadol","severity":"major",
     "mechanism":"Additive serotonergic stimulation; tramadol inhibits serotonin reuptake.",
     "description":"SSRI + Tramadol: MAJOR serotonin syndrome risk (agitation, tremor, hyperthermia).",
     "action":"AVOID. Use non-serotonergic opioid. Monitor closely if combination unavoidable."},
    {"drug1":"digoxin","drug2":"amiodarone","severity":"major",
     "mechanism":"Amiodarone inhibits P-glycoprotein and reduces renal digoxin clearance by 70-100%.",
     "description":"Digoxin + Amiodarone: MAJOR. Digoxin toxicity (bradycardia, arrhythmias, nausea).",
     "action":"Reduce digoxin dose 50% when starting amiodarone. Monitor levels and ECG."},
    {"drug1":"methotrexate","drug2":"ibuprofen","severity":"major",
     "mechanism":"NSAIDs reduce renal tubular secretion of methotrexate causing toxic accumulation.",
     "description":"Methotrexate + NSAID: MAJOR. Bone marrow suppression, mucositis, hepatotoxicity.",
     "action":"AVOID combination. Use paracetamol. Monitor FBC and renal function."},
    # MODERATE interactions
    {"drug1":"aspirin","drug2":"ibuprofen","severity":"moderate",
     "mechanism":"Ibuprofen competes with aspirin for COX-1 binding, blocking irreversible acetylation.",
     "description":"Aspirin + Ibuprofen: MODERATE. Ibuprofen attenuates cardioprotective antiplatelet effect.",
     "action":"If both needed, take aspirin 30-60 min BEFORE ibuprofen."},
    {"drug1":"lisinopril","drug2":"ibuprofen","severity":"moderate",
     "mechanism":"NSAIDs inhibit renal prostaglandins, opposing ACE inhibitor vasodilation.",
     "description":"ACE Inhibitor + NSAID: MODERATE. Blunted BP control and risk of acute kidney injury.",
     "action":"Avoid in elderly/CKD. Monitor creatinine within 1-2 weeks if used together."},
    {"drug1":"sertraline","drug2":"ibuprofen","severity":"moderate",
     "mechanism":"SSRIs deplete platelet serotonin; NSAIDs further inhibit platelets +GI mucosal damage.",
     "description":"SSRI + NSAID: MODERATE. GI bleeding risk increased 3-15 fold.",
     "action":"Add PPI gastroprotection if combination needed. Prefer paracetamol."},
    {"drug1":"warfarin","drug2":"atorvastatin","severity":"moderate",
     "mechanism":"Atorvastatin mildly inhibits CYP2C9 and may modestly raise free warfarin.",
     "description":"Warfarin + Atorvastatin: MODERATE. INR may increase slightly (<20%).",
     "action":"Check INR 5-7 days after starting atorvastatin."},
    {"drug1":"lisinopril","drug2":"furosemide","severity":"moderate",
     "mechanism":"Additive antihypertensive +volume depletion - first-dose hypotension risk.",
     "description":"ACE Inhibitor + Loop Diuretic: MODERATE. First-dose hypotension especially if volume-depleted.",
     "action":"Start low doses. Monitor BP after first dose. Check K+ and renal function."},
    {"drug1":"digoxin","drug2":"furosemide","severity":"moderate",
     "mechanism":"Hypokalaemia from furosemide sensitises heart to digoxin toxicity.",
     "description":"Digoxin + Furosemide: MODERATE. Hypokalaemia increases digoxin toxicity risk.",
     "action":"Keep K+ >= 4.0. Consider K+ supplementation. Monitor digoxin levels."},
    {"drug1":"clopidogrel","drug2":"aspirin","severity":"moderate",
     "mechanism":"Dual antiplatelet - additive platelet inhibition via P2Y12 and COX-1.",
     "description":"Clopidogrel + Aspirin (DAPT): MODERATE - increases bleeding risk. Intentional post-ACS.",
     "action":"Use only when indicated. Limit duration. Add pantoprazole (not omeprazole). Monitor for bleeding."},
    {"drug1":"atorvastatin","drug2":"amiodarone","severity":"moderate",
     "mechanism":"Amiodarone inhibits CYP3A4, increasing atorvastatin levels and myopathy risk.",
     "description":"Statin + Amiodarone: MODERATE. Increased rhabdomyolysis risk.",
     "action":"Limit atorvastatin to 40 mg/day. Monitor for myalgia. Check CK if symptoms."},
    {"drug1":"ciprofloxacin","drug2":"metformin","severity":"moderate",
     "mechanism":"Ciprofloxacin inhibits OCT2 renal tubular uptake, increasing metformin by ~45%.",
     "description":"Ciprofloxacin + Metformin: MODERATE. Elevated metformin levels increase lactic acidosis risk.",
     "action":"Monitor renal function. Reduce metformin if renal function declines."},
    {"drug1":"metformin","drug2":"furosemide","severity":"moderate",
     "mechanism":"Volume depletion impairs metformin renal clearance; furosemide alters metformin secretion.",
     "description":"Metformin + Furosemide: MODERATE. Lactic acidosis risk in borderline renal function.",
     "action":"Monitor renal function and maintain adequate hydration."},
    # MINOR interactions
    {"drug1":"omeprazole","drug2":"metformin","severity":"minor",
     "mechanism":"PPI inhibition of OCT transporters slightly increases metformin exposure.",
     "description":"PPI + Metformin: MINOR. Modest increase in metformin levels.",
     "action":"No routine action. Monitor renal function if other risk factors present."},
    {"drug1":"aspirin","drug2":"atorvastatin","severity":"minor",
     "mechanism":"Minimal pharmacokinetic interaction; combination used in cardiovascular prevention.",
     "description":"Aspirin + Atorvastatin: MINOR. Safe and commonly co-prescribed.",
     "action":"No dose adjustment required."},
    {"drug1":"omeprazole","drug2":"sertraline","severity":"minor",
     "mechanism":"Both inhibit CYP2C19; minor increase in sertraline levels possible.",
     "description":"PPI + SSRI: MINOR. Modestly elevated sertraline levels may occur.",
     "action":"No action required unless patient develops SSRI side effects."},
    {"drug1":"amlodipine","drug2":"atorvastatin","severity":"minor",
     "mechanism":"Amlodipine weakly inhibits CYP3A4; slight increase in atorvastatin levels.",
     "description":"Amlodipine + Atorvastatin: MINOR. Not clinically significant at standard doses.",
     "action":"No dose adjustment required."},
]


def _normalise(name: str) -> str:
    n = re.sub(r"\s+\d[\d.,]*\s*(?:mg|mcg|g|ml|iu)\b.*$", "", name.lower().strip(), flags=re.I)
    return _SYNONYMS.get(n.strip(), n.strip())


def check_interactions(drug_list: list[str]) -> list[dict]:
    """Return all known interactions between drugs in drug_list, sorted major-first."""
    normalised = list(dict.fromkeys(_normalise(d) for d in drug_list if d and d.strip()))
    found: list[dict] = []
    seen: set[frozenset] = set()

    # 1. Try SQLite
    try:
        from database import get_connection, init_db
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        for i in range(len(normalised)):
            for j in range(i + 1, len(normalised)):
                a, b = normalised[i], normalised[j]
                pair: frozenset = frozenset([a, b])
                if pair in seen:
                    continue
                cur.execute(
                    "SELECT drug1,drug2,severity,mechanism,description,action "
                    "FROM interactions WHERE (drug1=? AND drug2=?) OR (drug1=? AND drug2=?)",
                    (a, b, b, a),
                )
                row = cur.fetchone()
                if row:
                    seen.add(pair)
                    found.append(dict(row))
        conn.close()
        if found:
            return _sort(found)
    except Exception:
        pass

    # 2. Built-in fallback
    for i in range(len(normalised)):
        for j in range(i + 1, len(normalised)):
            a, b = normalised[i], normalised[j]
            pair = frozenset([a, b])
            if pair in seen:
                continue
            for ix in _BUILTIN:
                if frozenset([ix["drug1"], ix["drug2"]]) == pair:
                    seen.add(pair)
                    found.append(ix.copy())
                    break
    return _sort(found)


def _sort(interactions: list[dict]) -> list[dict]:
    order = {"major": 0, "moderate": 1, "minor": 2}
    return sorted(interactions, key=lambda x: order.get(x.get("severity", "minor"), 3))


def format_interaction_alert(interaction: dict) -> str:
    """Return a styled HTML alert block for a single interaction dict."""
    sev  = interaction.get("severity", "minor")
    d1   = interaction.get("drug1", "").title()
    d2   = interaction.get("drug2", "").title()
    desc = interaction.get("description", "")
    action   = interaction.get("action", "")
    mechanism = interaction.get("mechanism", "")

    _CFG = {
        "major":    ("alert-danger",   "sev-major",   ""),
        "moderate": ("alert-warning",  "sev-moderate",""),
        "minor":    ("alert-info",     "sev-minor",   "ℹ"),
    }
    cls, badge, icon = _CFG.get(sev, _CFG["minor"])

    mech_html = (
        f"<div style='font-size:.8rem;color:#555;margin-top:.3rem;'>"
        f"<strong>Mechanism:</strong> {mechanism}</div>"
    ) if mechanism else ""

    action_html = (
        f"<div style='font-size:.84rem;margin-top:.4rem;padding:.35rem .6rem;"
        f"background:rgba(0,0,0,.04);border-radius:6px;'>"
        f"<strong>Recommended action:</strong> {action}</div>"
    ) if action else ""

    return (
        f"<div class='custom-alert {cls}' style='margin:.4rem 0;'>"
        f"<div style='display:flex;align-items:center;gap:.5rem;'>"
        f"{icon}&nbsp;<span class='sev-badge {badge}'>{sev.upper()}</span>"
        f"&ensp;<strong>{d1}</strong>&nbsp;&harr;&nbsp;<strong>{d2}</strong></div>"
        f"<div style='margin-top:.35rem;font-size:.88rem;'>{desc}</div>"
        f"{mech_html}{action_html}"
        f"</div>"
    )
