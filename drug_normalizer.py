from __future__ import annotations
from dataclasses import dataclass
import re
from difflib import SequenceMatcher


@dataclass
class NormResult:
    generic: str
    brand_matched: str | None = None
    confidence: float = 0.0
    match_type: str = "not_found"
    notes: str = ""


# (brand_lower, generic_INN, notes)
_CATALOG: list[tuple[str, str, str]] = [
    # Antibiotics
    ("augmentin",        "Amoxicillin + Clavulanic Acid", "Co-amoxiclav"),
    ("co-amoxiclav",     "Amoxicillin + Clavulanic Acid", ""),
    ("hi-biotic",        "Amoxicillin",                   "Egyptian brand"),
    ("hibiotic",         "Amoxicillin",                   "Egyptian brand"),
    ("amoxil",           "Amoxicillin",                   ""),
    ("amoxicare",        "Amoxicillin",                   ""),
    ("trimox",           "Amoxicillin",                   ""),
    ("ciproxin",         "Ciprofloxacin",                 ""),
    ("ciprobay",         "Ciprofloxacin",                 ""),
    ("cipro",            "Ciprofloxacin",                 ""),
    ("normacin",         "Norfloxacin",                   "Egyptian brand"),
    ("floxin",           "Ofloxacin",                     ""),
    ("tavanic",          "Levofloxacin",                  ""),
    ("levaquin",         "Levofloxacin",                  ""),
    ("zithromax",        "Azithromycin",                  ""),
    ("zithrax",          "Azithromycin",                  "Egyptian brand"),
    ("sumamed",          "Azithromycin",                  ""),
    ("klacid",           "Clarithromycin",                ""),
    ("novaclar",         "Clarithromycin",                "Egyptian brand"),
    ("biaxin",           "Clarithromycin",                ""),
    ("flagyl",           "Metronidazole",                 ""),
    ("rozex",            "Metronidazole",                 ""),
    ("fasigyn",          "Tinidazole",                    ""),
    ("zinnat",           "Cefuroxime",                    ""),
    ("keflex",           "Cefalexin",                     ""),
    ("ceclor",           "Cefaclor",                      ""),
    ("suprax",           "Cefixime",                      ""),
    ("rocephin",         "Ceftriaxone",                   ""),
    ("doxin",            "Doxycycline",                   ""),
    ("vibramycin",       "Doxycycline",                   ""),
    ("erythrocin",       "Erythromycin",                  ""),
    ("macrobid",         "Nitrofurantoin",                 ""),
    ("meronem",          "Meropenem",                     ""),
    # GI
    ("colovatil",        "Trimebutine",                   "Egyptian GI brand"),
    ("colospas",         "Trimebutine",                   "Egyptian GI brand"),
    ("antinal",          "Nifuroxazide",                  "Egyptian antidiarrheal"),
    ("smecta",           "Diosmectite",                   ""),
    ("lacilac",          "Lactulose",                     "Egyptian brand"),
    ("duphalac",         "Lactulose",                     ""),
    ("lactulax",         "Lactulose",                     ""),
    ("buscopan",         "Hyoscine Butylbromide",         ""),
    ("duspatalin",       "Mebeverine",                    ""),
    ("nexium",           "Esomeprazole",                  ""),
    ("mesopral",         "Esomeprazole",                  "Egyptian brand"),
    ("losec",            "Omeprazole",                    ""),
    ("prilosec",         "Omeprazole",                    ""),
    ("omez",             "Omeprazole",                    "Egyptian brand"),
    ("pantoloc",         "Pantoprazole",                  ""),
    ("controloc",        "Pantoprazole",                  ""),
    ("pantozol",         "Pantoprazole",                  ""),
    ("zoton",            "Lansoprazole",                  ""),
    ("prevacid",         "Lansoprazole",                  ""),
    ("normix",           "Rifaximin",                     ""),
    ("xifaxan",          "Rifaximin",                     ""),
    ("motilium",         "Domperidone",                   ""),
    ("kloft",            "Itopride",                      "Egyptian brand"),
    ("gaviscon",         "Alginate Antacid",              ""),
    # Analgesics
    ("panadol",          "Paracetamol",                   ""),
    ("tylenol",          "Paracetamol",                   ""),
    ("adol",             "Paracetamol",                   "Egyptian brand"),
    ("acetaminophen",    "Paracetamol",                   "USAN name"),
    ("perfalgan",        "Paracetamol",                   "IV form"),
    ("brufen",           "Ibuprofen",                     ""),
    ("advil",            "Ibuprofen",                     ""),
    ("nurofen",          "Ibuprofen",                     ""),
    ("ibufen",           "Ibuprofen",                     "Egyptian brand"),
    ("motrin",           "Ibuprofen",                     ""),
    ("voltaren",         "Diclofenac Sodium",             ""),
    ("cataflam",         "Diclofenac Potassium",          ""),
    ("celebrex",         "Celecoxib",                     ""),
    ("arcoxia",          "Etoricoxib",                    ""),
    ("dolowin",          "Aceclofenac",                   "Egyptian brand"),
    ("mobic",            "Meloxicam",                     ""),
    ("movalis",          "Meloxicam",                     ""),
    ("aleve",            "Naproxen",                      ""),
    ("naprosyn",         "Naproxen",                      ""),
    ("tramal",           "Tramadol",                      ""),
    ("ultram",           "Tramadol",                      ""),
    ("ultracet",         "Tramadol + Paracetamol",        ""),
    # Cardiovascular
    ("norvasc",          "Amlodipine",                    ""),
    ("istin",            "Amlodipine",                    ""),
    ("amlopres",         "Amlodipine",                    ""),
    ("concor",           "Bisoprolol",                    ""),
    ("emconcor",         "Bisoprolol",                    ""),
    ("inderal",          "Propranolol",                   ""),
    ("tenormin",         "Atenolol",                      ""),
    ("seloken",          "Metoprolol",                    ""),
    ("betaloc",          "Metoprolol",                    ""),
    ("zestril",          "Lisinopril",                    ""),
    ("prinivil",         "Lisinopril",                    ""),
    ("coversyl",         "Perindopril",                   ""),
    ("prestarium",       "Perindopril",                   ""),
    ("tritace",          "Ramipril",                      ""),
    ("cozaar",           "Losartan",                      ""),
    ("hyzaar",           "Losartan + Hydrochlorothiazide",""),
    ("micardis",         "Telmisartan",                   ""),
    ("diovan",           "Valsartan",                     ""),
    ("atacand",          "Candesartan",                   ""),
    ("aldactone",        "Spironolactone",                ""),
    ("lasix",            "Furosemide",                    ""),
    ("plavix",           "Clopidogrel",                   ""),
    ("iscover",          "Clopidogrel",                   ""),
    ("aspocid",          "Aspirin",                       "Low-dose Egyptian brand"),
    ("cardiprin",        "Aspirin",                       ""),
    ("coumadin",         "Warfarin",                      ""),
    ("jantoven",         "Warfarin",                      ""),
    ("warfant",          "Warfarin",                      "Egyptian brand"),
    ("lanoxin",          "Digoxin",                       ""),
    ("digacin",          "Digoxin",                       "Egyptian brand"),
    ("cordarone",        "Amiodarone",                    ""),
    ("pacerone",         "Amiodarone",                    ""),
    ("lipitor",          "Atorvastatin",                  ""),
    ("sortis",           "Atorvastatin",                  ""),
    ("zocor",            "Simvastatin",                   ""),
    ("crestor",          "Rosuvastatin",                  ""),
    ("xarelto",          "Rivaroxaban",                   ""),
    ("eliquis",          "Apixaban",                      ""),
    ("pradaxa",          "Dabigatran",                    ""),
    ("clexane",          "Enoxaparin",                    "LMWH"),
    ("lovenox",          "Enoxaparin",                    "LMWH"),
    # Diabetes
    ("glucophage",       "Metformin",                     ""),
    ("fortamet",         "Metformin",                     ""),
    ("glucomet",         "Metformin",                     "Egyptian brand"),
    ("amaryl",           "Glimepiride",                   ""),
    ("gliasave",         "Glimepiride",                   "Egyptian brand"),
    ("diamicron",        "Gliclazide",                    ""),
    ("glizid",           "Gliclazide",                    "Egyptian brand"),
    ("daonil",           "Glibenclamide",                 ""),
    ("januvia",          "Sitagliptin",                   ""),
    ("galvus",           "Vildagliptin",                  ""),
    ("jardiance",        "Empagliflozin",                 ""),
    ("invokana",         "Canagliflozin",                 ""),
    ("forxiga",          "Dapagliflozin",                 ""),
    ("lantus",           "Insulin Glargine",              ""),
    ("basaglar",         "Insulin Glargine",              ""),
    ("levemir",          "Insulin Detemir",               ""),
    ("novorapid",        "Insulin Aspart",                ""),
    ("actrapid",         "Insulin Regular",               ""),
    # Thyroid
    ("euthyrox",         "Levothyroxine",                 ""),
    ("synthroid",        "Levothyroxine",                 ""),
    ("eltroxin",         "Levothyroxine",                 ""),
    ("thyrax",           "Levothyroxine",                 "Egyptian brand"),
    ("neomercazole",     "Carbimazole",                   ""),
    ("tapazole",         "Methimazole",                   ""),
    # Asthma/COPD
    ("ventolin",         "Salbutamol",                    ""),
    ("salbutol",         "Salbutamol",                    "Egyptian brand"),
    ("seretide",         "Fluticasone + Salmeterol",      ""),
    ("advair",           "Fluticasone + Salmeterol",      ""),
    ("symbicort",        "Budesonide + Formoterol",       ""),
    ("pulmicort",        "Budesonide",                    ""),
    ("flixotide",        "Fluticasone",                   ""),
    ("atrovent",         "Ipratropium",                   ""),
    ("spiriva",          "Tiotropium",                    ""),
    ("singulair",        "Montelukast",                   ""),
    ("zaditen",          "Ketotifen",                     "Egyptian brand"),
    # Psychiatric/Neuro
    ("zoloft",           "Sertraline",                    ""),
    ("lustral",          "Sertraline",                    ""),
    ("prozac",           "Fluoxetine",                    ""),
    ("cipralex",         "Escitalopram",                  ""),
    ("lexapro",          "Escitalopram",                  ""),
    ("effexor",          "Venlafaxine",                   ""),
    ("cymbalta",         "Duloxetine",                    ""),
    ("xanax",            "Alprazolam",                    ""),
    ("valium",           "Diazepam",                      ""),
    ("rivotril",         "Clonazepam",                    ""),
    ("ativan",           "Lorazepam",                     ""),
    ("stilnox",          "Zolpidem",                      ""),
    ("risperdal",        "Risperidone",                   ""),
    ("zyprexa",          "Olanzapine",                    ""),
    ("seroquel",         "Quetiapine",                    ""),
    ("tegretol",         "Carbamazepine",                 ""),
    ("depakine",         "Sodium Valproate",              ""),
    ("keppra",           "Levetiracetam",                 ""),
    ("neurontin",        "Gabapentin",                    ""),
    ("lyrica",           "Pregabalin",                    ""),
    # Antihistamines
    ("clarityne",        "Loratadine",                    ""),
    ("claritin",         "Loratadine",                    ""),
    ("lorfast",          "Loratadine",                    "Egyptian brand"),
    ("zyrtec",           "Cetirizine",                    ""),
    ("virlix",           "Cetirizine",                    ""),
    ("xyzal",            "Levocetirizine",                ""),
    ("telfast",          "Fexofenadine",                  ""),
    ("allegra",          "Fexofenadine",                  ""),
    ("polaramine",       "Dexchlorpheniramine",           ""),
    ("periactin",        "Cyproheptadine",                "Appetite use in Egypt"),
    ("phenergan",        "Promethazine",                  ""),
    ("atarax",           "Hydroxyzine",                   ""),
    # Steroids
    ("medrol",           "Methylprednisolone",            ""),
    ("prednol",          "Methylprednisolone",            "Egyptian brand"),
    ("decadron",         "Dexamethasone",                 ""),
    ("dexacort",         "Dexamethasone",                 "Egyptian brand"),
    ("ultralan",         "Fluocortolone",                 ""),
    ("betnovate",        "Betamethasone",                 "Topical"),
    ("fucidin",          "Fusidic Acid",                  "Topical"),
    ("bactroban",        "Mupirocin",                     "Topical"),
    # Gout/Rheumatology
    ("zyloric",          "Allopurinol",                   "Egyptian brand"),
    ("zyloprim",         "Allopurinol",                   ""),
    ("uloric",           "Febuxostat",                    ""),
    ("fosamax",          "Alendronate",                   ""),
    # Urology
    ("flomax",           "Tamsulosin",                    "BPH"),
    ("proscar",          "Finasteride",                   "BPH"),
    # Antivirals/Antiparasitics
    ("tamiflu",          "Oseltamivir",                   ""),
    ("zovirax",          "Aciclovir",                     ""),
    ("valtrex",          "Valaciclovir",                  ""),
    ("vermox",           "Mebendazole",                   ""),
    ("zentel",           "Albendazole",                   ""),
    # Egyptian paediatric vitamins
    ("v-drop",           "Vitamin D3 Drops",              "Egyptian pediatric brand"),
    ("v drop",           "Vitamin D3 Drops",              "Egyptian pediatric brand"),
    ("vdrop",            "Vitamin D3 Drops",              "Egyptian pediatric brand"),
    ("sanso immune",     "Multivitamin + Zinc",           "Egyptian pediatric brand"),
    ("sanso",            "Multivitamin + Zinc",           "Egyptian pediatric brand"),
    ("eubion",           "Vitamins B1 + B6 + B12",       "B-complex"),
    ("eulicon",          "Vitamins B1 + B6 + B12",       "Egyptian variant spelling"),
    ("limotal kids",     "L-Carnitine",                   "Egyptian pediatric brand"),
    ("limotal",          "L-Carnitine",                   "Egyptian brand"),
    ("kidssi appetite",  "Multivitamin + Cyproheptadine", "Egyptian pediatric brand"),
    ("kidssi",           "Multivitamin + Cyproheptadine", "Egyptian pediatric brand"),
    ("ferose",           "Ferrous Sulphate + Folic Acid", "Egyptian iron supplement"),
    ("ferrogradumet",    "Ferrous Sulphate",              "SR form"),
    ("vitacal",          "Calcium + Vitamin D3",          "Egyptian brand"),
]

# Build lookup (last entry wins for duplicate brands)
_BRAND_MAP: dict[str, tuple[str, str]] = {}
for _b, _g, _n in _CATALOG:
    _BRAND_MAP[_b.lower()] = (_g, _n)

# All known generics lower-cased for reverse lookup
_ALL_GENERICS: dict[str, str] = {v[0].lower(): v[0] for v in _BRAND_MAP.values()}

_DOSE_RE = re.compile(
    r"\s+[\d][\d.,/]*\s*(?:mg|mcg|g|ml|iu|tab(?:let)?s?|caps?(?:ule)?s?|sach(?:et)?s?).*$",
    re.IGNORECASE,
)


def normalize(name: str) -> NormResult:
    if not name or not name.strip():
        return NormResult(generic="", match_type="not_found", confidence=0.0, notes="Empty input.")
    clean = _DOSE_RE.sub("", name.strip())
    cl = clean.lower().strip()

    # 1. Exact brand match
    if cl in _BRAND_MAP:
        g, n = _BRAND_MAP[cl]
        return NormResult(generic=g, brand_matched=clean.strip(), confidence=0.97,
                          match_type="exact",
                          notes=("Exact brand match. " + n).strip(". "))

    # 2. Already a generic name
    if cl in _ALL_GENERICS:
        return NormResult(generic=_ALL_GENERICS[cl], brand_matched=None, confidence=0.95,
                          match_type="generic", notes="Input is already a generic (INN) name.")

    # 3. Prefix / alias match (>= 5 chars)
    for brand_l, (g, n) in _BRAND_MAP.items():
        k = min(len(cl), len(brand_l), 10)
        if k >= 5 and cl[:k] == brand_l[:k]:
            return NormResult(generic=g, brand_matched=brand_l.title(), confidence=0.82,
                              match_type="alias",
                              notes=(f"Prefix match to '{brand_l.title()}'. " + n).strip(". "))

    # 4. Fuzzy matching
    best_r, best_b, best_g, best_n = 0.0, "", "", ""
    for brand_l, (g, n) in _BRAND_MAP.items():
        r = SequenceMatcher(None, cl, brand_l).ratio()
        if r > best_r:
            best_r, best_b, best_g, best_n = r, brand_l, g, n

    if best_r >= 0.78:
        conf = min(0.91, round(0.50 + best_r * 0.45, 2))
        return NormResult(generic=best_g, brand_matched=best_b.title(), confidence=conf,
                          match_type="fuzzy",
                          notes=(f"Fuzzy match ({best_r:.0%}) to '{best_b.title()}'. " + best_n).strip(". "))

    if best_r >= 0.62:
        conf = round(0.35 + best_r * 0.35, 2)
        return NormResult(generic=clean.strip(), brand_matched=best_b.title(), confidence=conf,
                          match_type="fuzzy",
                          notes=f"Possible match ({best_r:.0%}) to '{best_b.title()}' - verify manually.")

    return NormResult(generic=clean.strip(), brand_matched=None, confidence=0.30,
                      match_type="not_found",
                      notes="Not found in normalisation database. Treating name as-is.")


def normalize_list(names: list[str]) -> list[NormResult]:
    return [normalize(n) for n in names]


def avg_confidence(results: list[NormResult]) -> float:
    if not results:
        return 0.80
    return round(sum(r.confidence for r in results) / len(results), 3)
