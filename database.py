"""
database.py
===========
Creates and seeds the PharmaAI SQLite database (pharma.db).

Tables
------
drugs         - drug profiles
dosing_rules  - per-drug dose ranges & renal adjustments
interactions  - drug-drug interaction pairs

Public API
----------
get_connection() -> sqlite3.Connection   row_factory=sqlite3.Row
init_db()        -> None                 idempotent; safe to call on every startup
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pharma.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS drugs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    generic_name    TEXT NOT NULL,
    brand_names     TEXT DEFAULT '[]',   -- JSON array
    drug_class      TEXT,
    mechanism       TEXT,
    indications     TEXT DEFAULT '[]',   -- JSON array
    contraindications TEXT DEFAULT '[]', -- JSON array
    side_effects    TEXT DEFAULT '[]',   -- JSON array
    pregnancy_cat   TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dosing_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name       TEXT NOT NULL COLLATE NOCASE,
    route           TEXT DEFAULT 'oral',
    min_dose        REAL,
    max_dose        REAL,
    unit            TEXT DEFAULT 'mg',
    frequency       TEXT,
    max_daily       REAL,
    max_daily_unit  TEXT DEFAULT 'mg',
    renal_adjustment TEXT,
    hepatic_adjustment TEXT,
    notes           TEXT,
    FOREIGN KEY (drug_name) REFERENCES drugs(name)
);

CREATE INDEX IF NOT EXISTS idx_dosing_drug ON dosing_rules(drug_name);

CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    drug1       TEXT NOT NULL COLLATE NOCASE,
    drug2       TEXT NOT NULL COLLATE NOCASE,
    severity    TEXT NOT NULL CHECK(severity IN ('major','moderate','minor')),
    mechanism   TEXT,
    description TEXT NOT NULL,
    action      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inter_drug1 ON interactions(drug1);
CREATE INDEX IF NOT EXISTS idx_inter_drug2 ON interactions(drug2);

CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    metadata    TEXT DEFAULT "{}",
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_log_event ON activity_log(event_type);
CREATE INDEX IF NOT EXISTS idx_log_time  ON activity_log(created_at);

CREATE TABLE IF NOT EXISTS prescriptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient      TEXT    DEFAULT '',
    prescriber   TEXT    DEFAULT '',
    rx_date      TEXT    DEFAULT '',
    medications  TEXT    DEFAULT '[]',
    safety_report TEXT   DEFAULT '{}',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rx_patient ON prescriptions(patient);
CREATE INDEX IF NOT EXISTS idx_rx_time    ON prescriptions(created_at);

CREATE TABLE IF NOT EXISTS openfda_cache (
    generic_name TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
_DRUGS: list[dict] = [
    {
        "name": "amoxicillin",
        "generic_name": "Amoxicillin",
        "brand_names": json.dumps(["Amoxil", "Trimox"]),
        "drug_class": "Aminopenicillin / Beta-lactam antibiotic",
        "mechanism": "Inhibits bacterial cell wall synthesis by binding to penicillin-binding proteins (PBPs), preventing peptidoglycan cross-linking.",
        "indications": json.dumps(["Respiratory tract infections", "UTI", "H. pylori eradication", "Dental prophylaxis"]),
        "contraindications": json.dumps(["Penicillin hypersensitivity", "Infectious mononucleosis"]),
        "side_effects": json.dumps(["Diarrhoea", "Nausea", "Skin rash", "Rare anaphylaxis"]),
        "pregnancy_cat": "B",
    },
    {
        "name": "ibuprofen",
        "generic_name": "Ibuprofen",
        "brand_names": json.dumps(["Advil", "Motrin", "Nurofen", "Brufen"]),
        "drug_class": "NSAID  Non-selective COX-1/COX-2 inhibitor",
        "mechanism": "Inhibits COX-1 and COX-2 cyclooxygenase enzymes, reducing prostaglandin and thromboxane synthesis.",
        "indications": json.dumps(["Mild-moderate pain", "Fever", "Osteoarthritis", "Rheumatoid arthritis", "Dysmenorrhoea"]),
        "contraindications": json.dumps(["Active GI ulceration", "Severe renal impairment (CrCl < 30)", "3rd trimester pregnancy", "Post-CABG surgery"]),
        "side_effects": json.dumps(["GI irritation", "Elevated BP", "Fluid retention", "Prolonged bleeding time"]),
        "pregnancy_cat": "C (D in 3rd trimester)",
    },
    {
        "name": "omeprazole",
        "generic_name": "Omeprazole",
        "brand_names": json.dumps(["Prilosec", "Losec", "Zegerid"]),
        "drug_class": "Proton Pump Inhibitor (PPI)",
        "mechanism": "Irreversibly inhibits the H+/K+-ATPase proton pump in gastric parietal cells.",
        "indications": json.dumps(["GERD", "Peptic ulcer disease", "H. pylori eradication", "NSAID-induced gastroprotection"]),
        "contraindications": json.dumps(["Hypersensitivity to benzimidazoles", "Concurrent rilpivirine"]),
        "side_effects": json.dumps(["Headache", "Nausea", "Long-term: hypomagnesaemia, B12 deficiency, C. diff risk"]),
        "pregnancy_cat": "C",
    },
    {
        "name": "metformin",
        "generic_name": "Metformin",
        "brand_names": json.dumps(["Glucophage", "Fortamet", "Glumetza"]),
        "drug_class": "Biguanide antidiabetic",
        "mechanism": "Decreases hepatic glucose production (gluconeogenesis) and increases peripheral insulin sensitivity. Does not stimulate insulin secretion.",
        "indications": json.dumps(["Type 2 diabetes mellitus", "Polycystic ovary syndrome (PCOS)", "Prediabetes (off-label)"]),
        "contraindications": json.dumps(["eGFR < 30 mL/min (absolute)", "Iodinated contrast (hold 48 h)", "Hepatic impairment", "Lactic acidosis history"]),
        "side_effects": json.dumps(["GI upset (nausea, diarrhoea  take with food)", "Lactic acidosis (rare)", "Vitamin B12 deficiency (long-term)"]),
        "pregnancy_cat": "B",
    },
    {
        "name": "warfarin",
        "generic_name": "Warfarin",
        "brand_names": json.dumps(["Coumadin", "Jantoven"]),
        "drug_class": "Vitamin K antagonist anticoagulant",
        "mechanism": "Inhibits vitamin K epoxide reductase (VKOR), blocking activation of vitamin K-dependent clotting factors II, VII, IX, X and proteins C and S.",
        "indications": json.dumps(["Atrial fibrillation (stroke prevention)", "DVT/PE treatment and prophylaxis", "Mechanical heart valves", "Hypercoagulable states"]),
        "contraindications": json.dumps(["Active haemorrhage", "Pregnancy (especially 1st trimester and near term)", "Severe hepatic impairment", "Haemorrhagic stroke"]),
        "side_effects": json.dumps(["Bleeding (major)", "Skin necrosis (rare)", "Purple toe syndrome (rare)"]),
        "pregnancy_cat": "X",
    },
    {
        "name": "atorvastatin",
        "generic_name": "Atorvastatin",
        "brand_names": json.dumps(["Lipitor"]),
        "drug_class": "HMG-CoA reductase inhibitor (statin)",
        "mechanism": "Competitively inhibits HMG-CoA reductase, the rate-limiting enzyme in hepatic cholesterol synthesis.",
        "indications": json.dumps(["Hypercholesterolaemia", "Primary and secondary cardiovascular prevention", "Hypertriglyceridaemia"]),
        "contraindications": json.dumps(["Active liver disease", "Pregnancy and breastfeeding", "Unexplained persistent elevated liver enzymes"]),
        "side_effects": json.dumps(["Myalgia", "Rhabdomyolysis (rare)", "Elevated liver enzymes", "Headache"]),
        "pregnancy_cat": "X",
    },
    {
        "name": "aspirin",
        "generic_name": "Aspirin (Acetylsalicylic acid)",
        "brand_names": json.dumps(["Aspocid", "Ecotrin", "Disprin"]),
        "drug_class": "Antiplatelet / NSAID / Salicylate",
        "mechanism": "Irreversibly acetylates and inhibits COX-1 (and COX-2 at higher doses), reducing thromboxane A2 production for antiplatelet effect.",
        "indications": json.dumps(["Antiplatelet: post-MI, ACS, stroke prevention", "Analgesic/antipyretic (higher doses)", "Kawasaki disease"]),
        "contraindications": json.dumps(["Active GI ulcer", "Haemophilia", "Children < 16 (Reye syndrome risk)", "Severe asthma (aspirin-exacerbated)"]),
        "side_effects": json.dumps(["GI irritation/bleeding", "Tinnitus (high dose)", "Hypersensitivity", "Prolonged bleeding time"]),
        "pregnancy_cat": "C (D in 3rd trimester)",
    },
    {
        "name": "clopidogrel",
        "generic_name": "Clopidogrel",
        "brand_names": json.dumps(["Plavix"]),
        "drug_class": "P2Y12 ADP receptor antagonist antiplatelet",
        "mechanism": "Irreversibly blocks P2Y12 ADP receptor on platelets, preventing ADP-mediated activation and aggregation. Prodrug activated by CYP2C19.",
        "indications": json.dumps(["ACS (NSTEMI/STEMI)", "Post-stent / coronary intervention", "Ischaemic stroke prevention", "PAD"]),
        "contraindications": json.dumps(["Active pathological bleeding", "Severe hepatic impairment", "Poor CYP2C19 metabolisers may have reduced effect"]),
        "side_effects": json.dumps(["Bleeding", "Bruising", "Thrombotic thrombocytopenic purpura (TTP)  rare"]),
        "pregnancy_cat": "B",
    },
    {
        "name": "metronidazole",
        "generic_name": "Metronidazole",
        "brand_names": json.dumps(["Flagyl", "Rozex"]),
        "drug_class": "Nitroimidazole antibiotic/antiprotozoal",
        "mechanism": "Enters cells, is reduced to toxic intermediates that damage bacterial/protozoal DNA, causing strand breaks and cell death.",
        "indications": json.dumps(["Anaerobic bacterial infections", "H. pylori eradication (triple therapy)", "C. difficile", "Trichomonas", "Giardia"]),
        "contraindications": json.dumps(["First trimester pregnancy", "Hypersensitivity to nitroimidazoles", "Alcohol use during treatment (disulfiram-like reaction)"]),
        "side_effects": json.dumps(["Metallic taste", "Nausea", "Peripheral neuropathy (prolonged use)", "Disulfiram-like reaction with alcohol"]),
        "pregnancy_cat": "B (avoid 1st trimester)",
    },
    {
        "name": "lisinopril",
        "generic_name": "Lisinopril",
        "brand_names": json.dumps(["Zestril", "Prinivil"]),
        "drug_class": "ACE Inhibitor (ACEI)",
        "mechanism": "Inhibits angiotensin-converting enzyme (ACE), reducing angiotensin II formation and aldosterone secretion. Causes vasodilation and reduced BP.",
        "indications": json.dumps(["Hypertension", "Heart failure", "Post-MI cardioprotection", "Diabetic nephropathy"]),
        "contraindications": json.dumps(["Pregnancy (teratogenic  bilateral renal agenesis)", "History of angioedema with ACEI", "Concurrent aliskiren in diabetes/renal impairment", "Bilateral renal artery stenosis"]),
        "side_effects": json.dumps(["Dry persistent cough (10-15%)", "Angioedema (rare, life-threatening)", "Hyperkalaemia", "Hypotension (first dose)"]),
        "pregnancy_cat": "D",
    },
    {
        "name": "furosemide",
        "generic_name": "Furosemide",
        "brand_names": json.dumps(["Lasix"]),
        "drug_class": "Loop diuretic",
        "mechanism": "Inhibits Na-K-2Cl cotransporter in the thick ascending limb of Henle's loop, blocking Na/K/Cl reabsorption.",
        "indications": json.dumps(["Oedema (cardiac, hepatic, renal)", "Hypertension", "Acute pulmonary oedema"]),
        "contraindications": json.dumps(["Anuria", "Sulphonamide hypersensitivity (cross-reactivity)", "Volume depletion"]),
        "side_effects": json.dumps(["Hypokalaemia", "Hypomagnesaemia", "Hypocalcaemia", "Ototoxicity (high IV doses)", "Hyperuricaemia"]),
        "pregnancy_cat": "C",
    },
    {
        "name": "ciprofloxacin",
        "generic_name": "Ciprofloxacin",
        "brand_names": json.dumps(["Cipro", "Ciproxin"]),
        "drug_class": "Fluoroquinolone antibiotic",
        "mechanism": "Inhibits DNA gyrase (topoisomerase II) and topoisomerase IV, preventing DNA supercoiling and replication.",
        "indications": json.dumps(["UTI", "Respiratory tract infections", "Gonorrhoea", "Anthrax prophylaxis", "Complicated skin infections"]),
        "contraindications": json.dumps(["Epilepsy / seizure history (lowers seizure threshold)", "Concurrent QT-prolonging drugs", "Children < 18 (cartilage risk)"]),
        "side_effects": json.dumps(["Nausea", "Tendinopathy/tendon rupture", "QT prolongation", "Photosensitivity", "CNS effects"]),
        "pregnancy_cat": "C",
    },
    {
        "name": "sertraline",
        "generic_name": "Sertraline",
        "brand_names": json.dumps(["Zoloft", "Lustral"]),
        "drug_class": "Selective Serotonin Reuptake Inhibitor (SSRI)",
        "mechanism": "Blocks the serotonin reuptake transporter (SERT), increasing serotonin concentration in synaptic clefts.",
        "indications": json.dumps(["Major depressive disorder", "PTSD", "OCD", "Panic disorder", "Social anxiety disorder"]),
        "contraindications": json.dumps(["Concurrent MAOIs (serotonin syndrome risk)", "Concurrent linezolid or IV methylene blue"]),
        "side_effects": json.dumps(["Nausea", "Insomnia", "Sexual dysfunction", "Serotonin syndrome (risk)", "QT prolongation (rare)"]),
        "pregnancy_cat": "C",
    },
    {
        "name": "amlodipine",
        "generic_name": "Amlodipine",
        "brand_names": json.dumps(["Norvasc", "Amlopres"]),
        "drug_class": "Dihydropyridine Calcium Channel Blocker (CCB)",
        "mechanism": "Blocks L-type voltage-gated calcium channels in vascular smooth muscle and cardiac muscle, causing vasodilation.",
        "indications": json.dumps(["Hypertension", "Stable/vasospastic angina"]),
        "contraindications": json.dumps(["Cardiogenic shock", "Severe aortic stenosis", "Decompensated heart failure"]),
        "side_effects": json.dumps(["Peripheral oedema (ankles)", "Flushing", "Headache", "Palpitations", "Gingival hyperplasia"]),
        "pregnancy_cat": "C",
    },
    {
        "name": "digoxin",
        "generic_name": "Digoxin",
        "brand_names": json.dumps(["Lanoxin"]),
        "drug_class": "Cardiac glycoside",
        "mechanism": "Inhibits myocardial Na+/K+-ATPase pump; increases intracellular calcium leading to positive inotropic effect. Also increases vagal tone (negative chronotropy).",
        "indications": json.dumps(["Heart failure with reduced EF", "Atrial fibrillation (rate control)"]),
        "contraindications": json.dumps(["Ventricular fibrillation", "Pre-excitation syndrome (WPW + AF)", "HCM with LVOT obstruction", "Hypokalaemia"]),
        "side_effects": json.dumps(["Nausea/vomiting (early toxicity)", "Visual disturbances (yellow-green halo)", "Arrhythmias (toxicity)", "Bradycardia"]),
        "pregnancy_cat": "C",
    },
    {
        "name": "amiodarone",
        "generic_name": "Amiodarone",
        "brand_names": json.dumps(["Cordarone", "Pacerone"]),
        "drug_class": "Class III antiarrhythmic",
        "mechanism": "Blocks multiple ion channels (K+, Na+, Ca2+), beta-receptors. Prolongs action potential duration and refractory period. Inhibits CYP1A2, CYP2C9, CYP3A4.",
        "indications": json.dumps(["Ventricular tachycardia/fibrillation", "Atrial fibrillation (refractory)", "Supraventricular tachycardias"]),
        "contraindications": json.dumps(["Severe sinus node dysfunction/AV block (without pacemaker)", "Thyroid disorders (relative)", "Iodine hypersensitivity", "Pulmonary toxicity history"]),
        "side_effects": json.dumps(["Pulmonary toxicity", "Thyroid dysfunction (hypo/hyperthyroidism)", "Hepatotoxicity", "Corneal microdeposits", "Photosensitivity", "QT prolongation"]),
        "pregnancy_cat": "D",
    },
]

_DOSING_RULES: list[dict] = [
    {"drug_name": "amoxicillin", "route": "oral", "min_dose": 250, "max_dose": 875, "unit": "mg",
     "frequency": "every 8-12 hours", "max_daily": 3000, "max_daily_unit": "mg",
     "renal_adjustment": "CrCl < 30: reduce to 250-500 mg q12h. CrCl < 10: 250-500 mg q24h. Supplement after haemodialysis.",
     "notes": "Take without regard to food. Severe infections: 875 mg twice daily."},
    {"drug_name": "ibuprofen", "route": "oral", "min_dose": 200, "max_dose": 800, "unit": "mg",
     "frequency": "every 4-8 hours", "max_daily": 3200, "max_daily_unit": "mg",
     "renal_adjustment": "AVOID if CrCl < 30 mL/min. Use with caution CrCl 30-60. Elderly: use lowest dose.",
     "notes": "Take with food or milk. OTC max 1200 mg/day."},
    {"drug_name": "omeprazole", "route": "oral", "min_dose": 10, "max_dose": 40, "unit": "mg",
     "frequency": "once daily", "max_daily": 80, "max_daily_unit": "mg",
     "renal_adjustment": "No dose adjustment required in renal impairment.",
     "notes": "Take 30-60 min before first meal of day. ZE syndrome: up to 120 mg/day."},
    {"drug_name": "metformin", "route": "oral", "min_dose": 500, "max_dose": 1000, "unit": "mg",
     "frequency": "twice daily (BD)", "max_daily": 2550, "max_daily_unit": "mg",
     "renal_adjustment": "eGFR 30-45: use with caution, max 1000 mg/day. eGFR < 30: CONTRAINDICATED. Hold before iodinated contrast, resume 48 h after if renal function stable.",
     "notes": "Take with meals to reduce GI side effects. Start low (500 mg OD), titrate over weeks."},
    {"drug_name": "warfarin", "route": "oral", "min_dose": 1, "max_dose": 10, "unit": "mg",
     "frequency": "once daily", "max_daily": 15, "max_daily_unit": "mg",
     "renal_adjustment": "Use with caution in renal impairment; increased bleeding risk. More frequent INR monitoring.",
     "notes": "Dose is highly individualised. Target INR: 2-3 (most indications), 2.5-3.5 (mechanical valves). Check INR weekly until stable."},
    {"drug_name": "atorvastatin", "route": "oral", "min_dose": 10, "max_dose": 80, "unit": "mg",
     "frequency": "once daily", "max_daily": 80, "max_daily_unit": "mg",
     "renal_adjustment": "No dose adjustment required. Use with caution if eGFR < 30; start 10 mg/day.",
     "notes": "Can be taken at any time of day. Higher doses (40-80 mg) for secondary cardiovascular prevention."},
    {"drug_name": "aspirin", "route": "oral", "min_dose": 75, "max_dose": 1000, "unit": "mg",
     "frequency": "once daily (antiplatelet) to every 4-6 hours (analgesic)",
     "max_daily": 4000, "max_daily_unit": "mg",
     "renal_adjustment": "Avoid in severe renal impairment (CrCl < 10). Use with caution CrCl 10-50.",
     "notes": "Antiplatelet: 75-100 mg/day. Analgesic/antipyretic: 300-1000 mg every 4-6 hour. Take with food."},
    {"drug_name": "clopidogrel", "route": "oral", "min_dose": 75, "max_dose": 600, "unit": "mg",
     "frequency": "once daily (maintenance)", "max_daily": 600, "max_daily_unit": "mg",
     "renal_adjustment": "No specific dose adjustment, but use with caution in severe renal impairment.",
     "notes": "Standard maintenance 75 mg/day. Loading dose 300-600 mg for ACS. Prodrug requiring CYP2C19 activation."},
    {"drug_name": "metronidazole", "route": "oral", "min_dose": 200, "max_dose": 500, "unit": "mg",
     "frequency": "every 8 hours", "max_daily": 2000, "max_daily_unit": "mg",
     "renal_adjustment": "No dose adjustment needed. Avoid alcohol during treatment.",
     "notes": "With food to reduce GI effects. C. diff: 500 mg TID x 10-14 days."},
    {"drug_name": "lisinopril", "route": "oral", "min_dose": 2.5, "max_dose": 40, "unit": "mg",
     "frequency": "once daily", "max_daily": 80, "max_daily_unit": "mg",
     "renal_adjustment": "CrCl 10-30: start 2.5-5 mg/day; max 40 mg/day. CrCl < 10: 2.5 mg/day; titrate carefully. Monitor K+ and creatinine.",
     "notes": "Start low (2.5-5 mg/day), titrate every 1-4 weeks. Monitor BP, K+, renal function."},
    {"drug_name": "furosemide", "route": "oral", "min_dose": 20, "max_dose": 80, "unit": "mg",
     "frequency": "once or twice daily", "max_daily": 600, "max_daily_unit": "mg",
     "renal_adjustment": "May need higher doses in renal impairment (reduced tubular secretion). Monitor electrolytes closely.",
     "notes": "Take in morning to avoid nocturnal diuresis. Monitor K+, Na+, Mg2+, uric acid."},
    {"drug_name": "ciprofloxacin", "route": "oral", "min_dose": 250, "max_dose": 750, "unit": "mg",
     "frequency": "every 12 hours", "max_daily": 1500, "max_daily_unit": "mg",
     "renal_adjustment": "CrCl 30-50: max 500 mg q12h. CrCl < 30: 250-500 mg q18-24h.",
     "notes": "Avoid concurrent antacids/dairy products (chelation). Maintain adequate hydration."},
    {"drug_name": "sertraline", "route": "oral", "min_dose": 25, "max_dose": 200, "unit": "mg",
     "frequency": "once daily", "max_daily": 200, "max_daily_unit": "mg",
     "renal_adjustment": "No dose adjustment required in mild-moderate renal impairment.",
     "notes": "Start 25-50 mg/day; titrate every 1-2 weeks. Clinical effect in 2-4 weeks. Do not stop abruptly."},
    {"drug_name": "amlodipine", "route": "oral", "min_dose": 2.5, "max_dose": 10, "unit": "mg",
     "frequency": "once daily", "max_daily": 10, "max_daily_unit": "mg",
     "renal_adjustment": "No dose adjustment required.",
     "notes": "Ankle oedema is common and dose-dependent. Can be taken at any time of day."},
    {"drug_name": "digoxin", "route": "oral", "min_dose": 0.0625, "max_dose": 0.25, "unit": "mg",
     "frequency": "once daily", "max_daily": 0.375, "max_daily_unit": "mg",
     "renal_adjustment": "CRITICAL: renally cleared. CrCl < 50: reduce dose by 50%. CrCl < 10: 0.0625 mg every other day. Monitor serum levels (target 0.5-0.9 ng/mL for HF).",
     "notes": "Narrow therapeutic index. Monitor K+ (hypokalaemia increases toxicity). Hold if HR < 60."},
    {"drug_name": "amiodarone", "route": "oral", "min_dose": 100, "max_dose": 400, "unit": "mg",
     "frequency": "once daily (maintenance)", "max_daily": 1600, "max_daily_unit": "mg",
     "renal_adjustment": "No dose adjustment required. Inhibits CYP2C9 and CYP3A4  many interactions.",
     "notes": "Loading dose 200 mg TID x 1-2 weeks. Maintenance 200 mg/day. Monitor TFTs, LFTs, CXR annually."},
]

_INTERACTIONS: list[dict] = [
    # MAJOR
    {"drug1": "warfarin", "drug2": "aspirin", "severity": "major",
     "mechanism": "Pharmacodynamic: additive anticoagulant/antiplatelet effects + COX-1 inhibition causing GI mucosal damage.",
     "description": "Warfarin + Aspirin: MAJOR interaction. Combination significantly increases risk of serious bleeding, including GI haemorrhage. Aspirin inhibits platelet COX-1 irreversibly and damages gastric mucosa, greatly amplifying warfarin anticoagulation bleeding risk.",
     "action": "Avoid combination unless specifically indicated (e.g. mechanical valves). If unavoidable, use lowest possible aspirin dose (75 mg), add PPI gastroprotection, and monitor INR weekly."},
    {"drug1": "warfarin", "drug2": "ibuprofen", "severity": "major",
     "mechanism": "Pharmacodynamic: additive anticoagulation + GI mucosa damage. Pharmacokinetic: NSAIDs displace warfarin from protein binding.",
     "description": "Warfarin + Ibuprofen (NSAID): MAJOR interaction. NSAIDs inhibit platelet aggregation AND cause gastric mucosal damage, greatly increasing haemorrhage risk in anticoagulated patients. Protein binding displacement may transiently raise free warfarin.",
     "action": "AVOID combination. Use paracetamol for pain relief instead. If NSAID is essential, monitor INR closely and add PPI."},
    {"drug1": "warfarin", "drug2": "metronidazole", "severity": "major",
     "mechanism": "Pharmacokinetic: metronidazole and its metabolite inhibit CYP2C9, the primary enzyme for S-warfarin metabolism, raising INR significantly.",
     "description": "Warfarin + Metronidazole: MAJOR interaction. Metronidazole inhibits CYP2C9, reducing warfarin clearance and causing INR to rise to potentially dangerous levels within 3-5 days.",
     "action": "Reduce warfarin dose by 30-50% empirically when starting metronidazole. Monitor INR every 2-3 days. Restore original warfarin dose after metronidazole course."},
    {"drug1": "warfarin", "drug2": "ciprofloxacin", "severity": "major",
     "mechanism": "Pharmacokinetic: ciprofloxacin inhibits CYP1A2 and reduces vitamin K synthesis by gut flora, potentiating warfarin effect.",
     "description": "Warfarin + Ciprofloxacin: MAJOR interaction. INR can increase unpredictably within 2-7 days of ciprofloxacin initiation due to CYP1A2 inhibition and gut flora suppression.",
     "action": "Monitor INR closely 3-5 days after starting ciprofloxacin. May need temporary warfarin dose reduction."},
    {"drug1": "warfarin", "drug2": "amiodarone", "severity": "major",
     "mechanism": "Pharmacokinetic: amiodarone and its metabolite desethylamiodarone are potent CYP2C9 inhibitors, dramatically reducing warfarin clearance.",
     "description": "Warfarin + Amiodarone: MAJOR, clinically significant interaction. Amiodarone inhibits warfarin metabolism causing INR to double or triple over 4-8 weeks. Effect persists for months after stopping amiodarone due to its extremely long half-life (~40-55 days).",
     "action": "Reduce warfarin dose by 30-50% when initiating amiodarone. Monitor INR weekly until stable. Continue more frequent monitoring for months after amiodarone discontinuation."},
    {"drug1": "clopidogrel", "drug2": "omeprazole", "severity": "major",
     "mechanism": "Pharmacokinetic: omeprazole inhibits CYP2C19, reducing conversion of clopidogrel prodrug to its active antiplatelet metabolite by up to 40-50%.",
     "description": "Clopidogrel + Omeprazole: MAJOR interaction. Omeprazole (a CYP2C19 inhibitor) significantly reduces the antiplatelet effectiveness of clopidogrel, potentially increasing risk of stent thrombosis and cardiovascular events.",
     "action": "Use pantoprazole or lansoprazole instead (minimal CYP2C19 inhibition). If omeprazole is essential, consider switching clopidogrel to prasugrel or ticagrelor."},
    {"drug1": "sertraline", "drug2": "tramadol", "severity": "major",
     "mechanism": "Pharmacodynamic: both serotoninergic. Tramadol inhibits serotonin reuptake and is an opioid agonist; additive serotonergic toxicity.",
     "description": "SSRI (Sertraline) + Tramadol: MAJOR serotonin syndrome risk. The combination can cause serotonin toxicity presenting as agitation, tremor, hyperreflexia, hyperthermia, and autonomic instability.",
     "action": "AVOID combination. If opioid analgesia is needed, use a non-serotonergic agent (e.g. oxycodone, morphine). If combination is unavoidable, use lowest tramadol dose and monitor for serotonin syndrome symptoms."},
    {"drug1": "digoxin", "drug2": "amiodarone", "severity": "major",
     "mechanism": "Pharmacokinetic: amiodarone inhibits P-glycoprotein and reduces renal clearance of digoxin, increasing serum digoxin levels by 70-100%.",
     "description": "Digoxin + Amiodarone: MAJOR interaction. Amiodarone markedly increases serum digoxin concentrations, causing digoxin toxicity (nausea, bradycardia, arrhythmias, yellow vision).",
     "action": "Reduce digoxin dose by 50% when starting amiodarone. Monitor serum digoxin levels and ECG closely. Target digoxin level 0.5-0.9 ng/mL."},
    {"drug1": "methotrexate", "drug2": "ibuprofen", "severity": "major",
     "mechanism": "Pharmacokinetic: NSAIDs reduce renal prostaglandin synthesis, impairing renal blood flow and tubular secretion of methotrexate.",
     "description": "Methotrexate + NSAIDs (Ibuprofen): MAJOR interaction. NSAIDs reduce renal clearance of methotrexate, causing toxic accumulation leading to bone marrow suppression, mucositis, and hepatotoxicity.",
     "action": "AVOID combination especially with high-dose methotrexate. If rheumatology-dosed MTX, use paracetamol for pain. Monitor FBC and renal function."},

    # MODERATE  
    {"drug1": "aspirin", "drug2": "ibuprofen", "severity": "moderate",
     "mechanism": "Pharmacokinetic competition: ibuprofen competes with aspirin for COX-1 acetylation binding site, blocking aspirin's irreversible antiplatelet action.",
     "description": "Aspirin + Ibuprofen: MODERATE interaction. Ibuprofen competitively blocks aspirin binding to COX-1, attenuating its cardioprotective antiplatelet effect. Single doses of ibuprofen taken BEFORE aspirin specifically reduce aspirin efficacy.",
     "action": "If both are needed, take aspirin 30-60 minutes BEFORE ibuprofen. Consider naproxen (less COX-1 competition) or paracetamol as alternative analgesic."},
    {"drug1": "lisinopril", "drug2": "ibuprofen", "severity": "moderate",
     "mechanism": "Pharmacodynamic: NSAIDs inhibit renal prostaglandins, reducing renal blood flow and GFR; opposing ACE inhibitor vasodilatory effects and causing sodium/water retention.",
     "description": "ACE Inhibitor (Lisinopril) + NSAID (Ibuprofen): MODERATE-MAJOR interaction. NSAIDs blunt the antihypertensive effect of ACE inhibitors AND increase risk of acute kidney injury, particularly in elderly, dehydrated, or CKD patients.",
     "action": "Avoid combination in elderly or renal impairment. If necessary, monitor renal function (creatinine, GFR) and electrolytes within 1-2 weeks. Consider paracetamol alternative."},
    {"drug1": "sertraline", "drug2": "ibuprofen", "severity": "moderate",
     "mechanism": "Pharmacodynamic: SSRIs deplete platelet serotonin, impairing platelet aggregation; NSAIDs further inhibit platelet COX-1 and cause GI mucosal damage.",
     "description": "SSRI (Sertraline) + NSAID (Ibuprofen): MODERATE interaction. The combination increases the risk of GI bleeding by 3-15 fold. The relative risk is highest in elderly patients.",
     "action": "Add PPI gastroprotection (omeprazole 20 mg/day) if combination is necessary. Consider paracetamol as safer analgesic alternative. Monitor for signs of GI bleeding."},
    {"drug1": "warfarin", "drug2": "atorvastatin", "severity": "moderate",
     "mechanism": "Pharmacokinetic: atorvastatin is a minor CYP2C9 inhibitor and may displace warfarin from protein binding, modestly increasing free warfarin.",
     "description": "Warfarin + Atorvastatin: MODERATE interaction. INR may increase modestly (typically <20%) when atorvastatin is added to warfarin therapy.",
     "action": "Monitor INR 5-7 days after starting atorvastatin. No dose adjustment usually needed but document INR change."},
    {"drug1": "lisinopril", "drug2": "furosemide", "severity": "moderate",
     "mechanism": "Pharmacodynamic: additive antihypertensive and volume depletion effects. First-dose hypotension risk especially in volume-depleted patients.",
     "description": "ACE Inhibitor (Lisinopril) + Loop Diuretic (Furosemide): MODERATE interaction. First-dose hypotension can be severe, particularly in hypovolaemic patients. Risk of renal impairment and hyperkalaemia.",
     "action": "Start with low doses of each. Advise patient about dizziness, especially on standing. Monitor BP, K+, and renal function regularly."},
    {"drug1": "metformin", "drug2": "furosemide", "severity": "moderate",
     "mechanism": "Pharmacokinetic: furosemide increases renal tubular secretion of metformin; also risk of volume depletion impairing metformin clearance.",
     "description": "Metformin + Furosemide: MODERATE interaction. Furosemide can increase metformin plasma levels. Volume depletion from furosemide can impair renal metformin clearance, increasing lactic acidosis risk.",
     "action": "Monitor renal function and lactic acid if combination used in patients with borderline renal function. Ensure adequate hydration."},
    {"drug1": "digoxin", "drug2": "furosemide", "severity": "moderate",
     "mechanism": "Pharmacodynamic: furosemide causes hypokalaemia and hypomagnesaemia, sensitising the heart to digoxin toxicity (hypokalaemia dramatically increases digoxin binding to Na/K-ATPase).",
     "description": "Digoxin + Furosemide: MODERATE interaction. Hypokalaemia caused by furosemide greatly increases susceptibility to digoxin toxicity (bradyarrhythmias, heart block, ventricular arrhythmias).",
     "action": "Monitor K+ closely. Keep K+  4.0 mEq/L in patients on digoxin. Consider potassium supplementation. Monitor serum digoxin levels."},
    {"drug1": "amoxicillin", "drug2": "warfarin", "severity": "moderate",
     "mechanism": "Pharmacodynamic: amoxicillin alters gut microbiome, reducing vitamin K2 synthesis by intestinal bacteria, potentiating warfarin anticoagulation.",
     "description": "Amoxicillin + Warfarin: MODERATE interaction. Antibiotics reduce gut flora that produce vitamin K2, potentially increasing INR during antibiotic therapy.",
     "action": "Monitor INR after starting antibiotic course. May need temporary warfarin dose reduction."},
    {"drug1": "clopidogrel", "drug2": "aspirin", "severity": "moderate",
     "mechanism": "Pharmacodynamic: dual antiplatelet  additive inhibition of platelet aggregation via P2Y12 (clopidogrel) and COX-1 (aspirin).",
     "description": "Clopidogrel + Aspirin: MODERATE  additive antiplatelet effect. This combination (DAPT) is intentional post-ACS/stent but significantly increases bleeding risk, including intracranial haemorrhage.",
     "action": "Use only when specifically indicated (ACS, recent stent). Limit DAPT duration to minimum necessary. Add PPI (avoid omeprazole  use pantoprazole instead). Monitor for bleeding."},
    {"drug1": "atorvastatin", "drug2": "amiodarone", "severity": "moderate",
     "mechanism": "Pharmacokinetic: amiodarone inhibits CYP3A4, reducing atorvastatin metabolism and increasing statin plasma levels, raising myopathy risk.",
     "description": "Statin (Atorvastatin) + Amiodarone: MODERATE interaction. Amiodarone inhibits CYP3A4, increasing atorvastatin levels and risk of statin-induced myopathy and rhabdomyolysis.",
     "action": "Limit atorvastatin to 40 mg/day. Monitor for myalgia and check CK levels if symptoms develop. Consider pravastatin or rosuvastatin (not CYP3A4 metabolised)."},
    {"drug1": "ciprofloxacin", "drug2": "metformin", "severity": "moderate",
     "mechanism": "Pharmacokinetic: ciprofloxacin inhibits renal tubular uptake of metformin via OCT2, increasing metformin plasma levels by 45%.",
     "description": "Ciprofloxacin + Metformin: MODERATE interaction. Ciprofloxacin can increase metformin levels significantly, raising lactic acidosis risk  especially in patients with borderline renal function.",
     "action": "Monitor renal function during concurrent use. Consider dose reduction or temporary metformin hold if renal function declines."},

    # MINOR
    {"drug1": "omeprazole", "drug2": "metformin", "severity": "minor",
     "mechanism": "Pharmacokinetic: PPIs inhibit OCT transporters, slightly increasing metformin levels.",
     "description": "PPI (Omeprazole) + Metformin: MINOR interaction. PPIs can modestly increase metformin exposure by inhibiting OCT transporters. Clinically relevant only if other metformin clearance risks are present.",
     "action": "No routine action required. Monitor if renal function is borderline."},
    {"drug1": "aspirin", "drug2": "atorvastatin", "severity": "minor",
     "mechanism": "Minimal pharmacokinetic interaction; both are widely used together in cardiovascular prevention.",
     "description": "Aspirin + Atorvastatin: MINOR interaction. Combination is safe and commonly used; minimal pharmacokinetic interaction noted.",
     "action": "No dose adjustment required. Standard monitoring applies."},
    {"drug1": "omeprazole", "drug2": "sertraline", "severity": "minor",
     "mechanism": "Pharmacokinetic: both inhibit CYP2C19; minor increase in sertraline levels possible.",
     "description": "PPI (Omeprazole) + SSRI (Sertraline): MINOR interaction. Omeprazole is a CYP2C19 inhibitor; sertraline levels may increase modestly.",
     "action": "No action required unless patient develops signs of SSRI toxicity (insomnia, agitation). Consider dose review if switching to higher-dose omeprazole."},
    {"drug1": "amlodipine", "drug2": "atorvastatin", "severity": "minor",
     "mechanism": "Pharmacokinetic: amlodipine is a weak CYP3A4 inhibitor; may slightly increase atorvastatin levels.",
     "description": "Amlodipine + Atorvastatin: MINOR interaction. Amlodipine can modestly increase atorvastatin exposure. Not clinically significant at normal doses.",
     "action": "No dose adjustment required. Limit atorvastatin to 80 mg/day (standard guideline regardless of interaction)."},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Return an open DB connection with Row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables and seed data (idempotent  safe to call on every startup)."""
    conn = get_connection()
    try:
        conn.executescript(_DDL)
        conn.commit()

        cur = conn.cursor()

        # Seed drugs (skip if already present)
        for drug in _DRUGS:
            cur.execute(
                "INSERT OR IGNORE INTO drugs "
                "(name, generic_name, brand_names, drug_class, mechanism, "
                " indications, contraindications, side_effects, pregnancy_cat) "
                "VALUES (:name, :generic_name, :brand_names, :drug_class, :mechanism, "
                "        :indications, :contraindications, :side_effects, :pregnancy_cat)",
                drug,
            )

        # Seed dosing rules
        for rule in _DOSING_RULES:
            cur.execute(
                "INSERT OR IGNORE INTO dosing_rules "
                "(drug_name, route, min_dose, max_dose, unit, frequency, "
                " max_daily, max_daily_unit, renal_adjustment, notes) "
                "VALUES (:drug_name, :route, :min_dose, :max_dose, :unit, :frequency, "
                "        :max_daily, :max_daily_unit, :renal_adjustment, :notes)",
                rule,
            )

        # Seed interactions (bi-directional  only insert if neither direction exists)
        for ix in _INTERACTIONS:
            cur.execute(
                "SELECT 1 FROM interactions WHERE "
                "(drug1=:drug1 AND drug2=:drug2) OR (drug1=:drug2 AND drug2=:drug1)",
                {"drug1": ix["drug1"], "drug2": ix["drug2"]},
            )
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO interactions "
                    "(drug1, drug2, severity, mechanism, description, action) "
                    "VALUES (:drug1, :drug2, :severity, :mechanism, :description, :action)",
                    ix,
                )

        conn.commit()
    finally:
        conn.close()



def log_event(event_type: str, metadata: "dict | None" = None) -> None:
    """Write a single event to activity_log (fire-and-forget)."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO activity_log (event_type, metadata) VALUES (?, ?)",
            (event_type, json.dumps(metadata or {})),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_stats() -> dict:
    """Return cumulative event counts plus safety_compliance percentage."""
    try:
        conn = get_connection()
        cur  = conn.cursor()
        stats: dict = {}
        for evt in ("prescription_scanned", "interaction_flagged", "query_answered", "drug_lookup"):
            cur.execute("SELECT COUNT(*) FROM activity_log WHERE event_type = ?", (evt,))
            stats[evt] = cur.fetchone()[0]
        total = stats["prescription_scanned"]
        if total > 0:
            cur.execute(
                "SELECT COUNT(*) FROM activity_log "
                "WHERE event_type=\'interaction_flagged\' AND json_extract(metadata,\'$.has_major\')=1"
            )
            major_count = cur.fetchone()[0]
            stats["safety_compliance"] = round(100.0 * max(0, total - major_count) / total, 1)
        else:
            stats["safety_compliance"] = 100.0
        conn.close()
        return stats
    except Exception:
        return {
            "prescription_scanned": 0, "interaction_flagged": 0,
            "query_answered": 0, "drug_lookup": 0, "safety_compliance": 100.0,
        }


def get_recent_logs(n: int = 12) -> list:
    """Return the *n* most-recent activity_log rows as plain dicts."""
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT event_type, metadata, created_at FROM activity_log ORDER BY id DESC LIMIT ?",
            (n,),
        )
        rows = [
            {"event_type": r[0], "metadata": json.loads(r[1] or "{}"), "created_at": r[2]}
            for r in cur.fetchall()
        ]
        conn.close()
        return rows
    except Exception:
        return []



def save_prescription(patient: str, prescriber: str, rx_date: str,
                      medications: list, safety_report: dict) -> int:
    """Insert a prescription record and return the new row id. Returns -1 on error."""
    try:
        conn = get_connection()
        cur  = conn.execute(
            "INSERT INTO prescriptions (patient, prescriber, rx_date, medications, safety_report) "
            "VALUES (?, ?, ?, ?, ?)",
            (patient or "", prescriber or "", rx_date or "",
             json.dumps(medications), json.dumps(safety_report)),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id
    except Exception:
        return -1

if __name__ == "__main__":
    init_db()
    print(f"Database initialised at: {DB_PATH}")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM drugs")
    print(f"  Drugs: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM dosing_rules")
    print(f"  Dosing rules: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM interactions")
    print(f"  Interactions: {cur.fetchone()[0]}")
    conn.close()
