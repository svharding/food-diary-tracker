#!/usr/bin/env python3
"""Build the single-page nutrient tracker.

Usage
  python3 build.py --demo                 # placeholder demo data -> index.html
  python3 build.py --cnf path/to/cnf_dir  # Canadian Nutrient File CSVs -> index.html

The CNF reader auto-detects file and column names so it works with the 2015
layout (Food Name / Nutrient Amount / Nutrient Name / Conversion Factor /
Measure Name) and should work with the 2026 layout (Measure Weight Conversion).
It prints a nutrient-matching report: check it before using the output.
"""
import argparse, csv, json, re, sys, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Order must match NUTRIENTS in template.html
# key: (expected unit, include regex, exclude regex)
NUTRIENTS = [
    ("energy", "kcal", r"energy.*(kilocal|kcal)", None),
    ("protein", "g", r"^protein\b", r"amino"),
    ("fat", "g", r"^fat\b.*total|^total lipid|^fat \(total", None),
    ("sfa", "g", r"saturated.*total|total.*saturated", r"mono|poly"),
    ("carb", "g", r"carbohydrate.*total.*difference|carbohydrate, total|^carbohydrate", None),
    ("sugars", "g", r"^sugars?,? total|total sugars", None),
    ("fibre", "g", r"fib(re|er).*total.*dietary|total dietary fib", None),
    ("alcohol", "g", r"^alcohol", None),
    ("chol", "mg", r"^cholesterol", None),
    ("ala", "g", r"18:3.*(c,c,c|ala\b|alpha|linolenic).*n-3|18:3.*n-3.*(c,c,c|linolenic)|alpha-linolenic", r"n-6|gamma"),
    ("na", "mg", r"^sodium", None),
    ("k", "mg", r"^potassium", None),
    ("ca", "mg", r"^calcium", None),
    ("fe", "mg", r"^iron", None),
    ("mg", "mg", r"^magnesium", None),
    ("zn", "mg", r"^zinc", None),
    ("p", "mg", r"^phosphorus", None),
    ("vita", "µg", r"retinol activity equivalent|vitamin a.*rae", None),
    ("vitd", "µg", r"vitamin d.*(d2 ?\+ ?d3|µg|ug|mcg)|vitamin d \(d2", r"\biu\b|international"),
    ("vite", "mg", r"alpha-tocopherol|vitamin e.*alpha", r"added|beta|gamma|delta"),
    ("vitk", "µg", r"^vitamin k\b|phylloquinone", r"dihydro|menaquinone"),
    ("vitc", "mg", r"^vitamin c\b|ascorbic", None),
    ("thia", "mg", r"^thiamin", None),
    ("ribo", "mg", r"^riboflavin", None),
    ("nia", "mg", r"niacin.*equiv|equiv.*niacin|niacin \(ne\)|total niacin", r"preformed"),
    ("b6", "mg", r"vitamin b-?6", None),
    ("fol", "µg", r"dietary folate equiv|folate.*dfe", None),
    ("b12", "µg", r"vitamin b-?12", r"added"),
]

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

def unit_norm(u):
    u = u.strip().lower().replace("µ", "u").replace("μ", "u")
    return {"mcg": "ug", "ne": "mg", "dfe": "ug"}.get(u, u)

def read_csv(path):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
    sys.exit(f"Could not decode {path}")

def find_file(d, *patterns):
    files = [p for p in d.rglob("*") if p.suffix.lower() == ".csv"]
    for pat in patterns:
        for p in files:
            if re.search(pat, norm(p.stem)):
                return p
    return None

def col(rows, *cands, required=True, label=""):
    if not rows:
        sys.exit(f"Empty file for {label}")
    keys = {norm(k): k for k in rows[0].keys()}
    for c in cands:
        if norm(c) in keys:
            return keys[norm(c)]
    for c in cands:  # partial match
        for nk, k in keys.items():
            if norm(c) in nk:
                return k
    if required:
        sys.exit(f"Column not found for {label}: tried {cands}; have {list(rows[0].keys())}")
    return None

def num(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None

# CNF 2026 nutrient codes (Nutrient_Name.csv). Checked against the 2026 release.
CNF_CODES = {
    "energy": ["208"], "protein": ["203"], "fat": ["204"], "sfa": ["606"], "carb": ["205"],
    "sugars": ["269"], "fibre": ["291"], "alcohol": ["221"], "chol": ["601"],
    "ala": ["851", "619"],  # 18:3 n-3 (ALA); falls back to 18:3 undifferentiated
    "na": ["307"], "k": ["306"], "ca": ["301"], "fe": ["303"], "mg": ["304"], "zn": ["309"], "p": ["305"],
    "vita": ["320"], "vitd": ["328"], "vite": ["323"], "vitk": ["430"], "vitc": ["401"],
    "thia": ["404"], "ribo": ["405"], "nia": ["409"], "b6": ["415"], "fol": ["435"], "b12": ["418"],
}
MEASURE_TYPE_HOUSEHOLD = "6"   # 3 = refuse, 9 = yield (not portion sizes)

def measure_sort_key(name):
    n = name.lower()
    if re.match(r"^1 [a-z]", n):       # "1 medium fruit", "1 slice"; medium first
        return (0, 0 if "medium" in n else 1, n)
    m = re.match(r"^([\d.]+)\s*ml", n)
    if m:                               # 250 ml first among volumes
        v = float(m.group(1))
        return (1, -v if v >= 250 else 1000 - v, n)
    return (2, n)

# ---- Plausibility checks for crowd-sourced label data ----
# Typical energy (kcal/100 g) ranges for foods students log often. A product
# outside its range usually has per-serving values typed into per-100 g fields.
MILK_WORDS = r"(organic|partly|skimmed|skim|homogeni[sz]ed|whole|fine[- ]?filtered|ultra[- ]?filtered|lactose[- ]free|grass[- ]fed|fresh|dairy|cow'?s?|\d+(\.\d+)?\s*%|m\.?f\.?|percent|milk|and|plus|natrel|[\s,.\-()])+"
JUICE_WORDS = r"(100\s*%|pure|organic|not from concentrate|from concentrate|unsweetened|no pulp|pulp|with|calcium|fresh|squeezed|apple|orange|grape|grapefruit|cranberry|pineapple|mango|tomato|vegetable|lemon|lime|carrot|juice|cocktail|blend|[\s,.\-()&])+"
NAME_RANGES = [   # whole-name patterns: only plain products are checked
    (MILK_WORDS, r"\bmilk\b", 25, 80),
    (JUICE_WORDS, r"\bjuice\b", 5, 75),
]

def plausibility_reference(off):
    import math, statistics as st
    keys = off["meta"]["keys"]; ie = keys.index("energy")
    by = {}
    for rec in off["foods"]:
        if len(rec) > 5 and rec[5] and rec[3][ie]:
            by.setdefault(rec[5], []).append(math.log(rec[3][ie]))
    ref = {}
    for c, xs in by.items():
        if len(xs) >= 15:
            med = st.median(xs)
            mad = st.median([abs(x - med) for x in xs]) or 0.1
            ref[c] = (med, mad)
    return ref

def implausible(name, cat, v, ref):
    import math
    e, p, f, c = v["energy"], v["protein"], v["fat"], v["carb"]
    atw = 4 * p + 4 * c + 9 * f + 7 * (v.get("alcohol") or 0)
    if e > 40 and atw > 0 and abs(e - atw) > max(40, 0.35 * e):
        return "energy does not match protein, fat and carbohydrate"
    if e == 0 and atw > 20:
        return "energy does not match protein, fat and carbohydrate"
    n = name.lower().strip()
    for whole, must, lo, hi in NAME_RANGES:
        if re.fullmatch(whole, n) and re.search(must, n) and not (lo <= e <= hi):
            return "energy outside the usual range for this kind of food"
    return None

def build_cnf(d, version):
    d = Path(d)
    def rows(name):
        p = next((x for x in d.rglob(name)), None)
        if not p:
            sys.exit(f"Missing {name}")
        return read_csv(p)
    names = {r["Nutrient_Code"].strip(): (r["Nutrient_Name_EN"].strip(), r["Nutrient_Unit"].strip()) for r in rows("Nutrient_Name.csv")}
    print("Nutrient mapping (CNF 2026 codes):")
    for k, codes in CNF_CODES.items():
        print(f"  {k:8s} " + " | ".join(f"{c} {names.get(c, ('MISSING', ''))[0]} [{names.get(c, ('', '?'))[1]}]" for c in codes))
        for c in codes:
            if c not in names:
                sys.exit(f"Nutrient code {c} not in Nutrient_Name.csv")
    keys = [k for k, *_ in NUTRIENTS]
    code_to = {}
    for k, codes in CNF_CODES.items():
        for rank, c in enumerate(codes):
            code_to[c] = (keys.index(k), rank)
    vals, ranks = {}, {}
    for r in rows("Nutrient_Amount.csv"):
        c = r["Nutrient_Code"].strip()
        if c not in code_to:
            continue
        v = num(r["Nutrient_Amount"])
        if v is None:
            continue
        fid = r["Food_Code"].strip()
        i, rank = code_to[c]
        vv = vals.setdefault(fid, [None] * len(keys))
        rr = ranks.setdefault(fid, [99] * len(keys))
        if rank < rr[i]:
            vv[i] = round(v, 4); rr[i] = rank
    groups = {r["CNF_Food_Group_Code"].strip(): r["CNF_Food_Group_Description_EN"].strip() for r in rows("CNF_Food_Group.csv")}
    mnames = {r["Measure_Code"].strip(): r["Measure_Description_and_Unit_EN"].strip() for r in rows("Measure_Name.csv")}
    measures = {}
    for r in rows("Measure_Weight_Conversion.csv"):
        if r["Measure_Type_Code"].strip() != MEASURE_TYPE_HOUSEHOLD:
            continue
        g = num(r["Measure_Weight_Conversion"])
        name = mnames.get(r["Measure_Code"].strip(), "")
        if not name or not g or g <= 0:
            continue
        lst = measures.setdefault(r["Food_Code"].strip(), [])
        if all(n != name for n, _ in lst):
            lst.append([name, round(g, 1)])
    for lst in measures.values():
        lst.sort(key=lambda x: measure_sort_key(x[0]))
    out_foods = []
    for r in rows("Food_Name.csv"):
        fid = r["Food_Code"].strip()
        if fid not in vals or vals[fid][keys.index("energy")] is None:
            continue
        name = " ".join(r["Food_Description_EN"].split())
        alt = (r.get("Alternate_Description_EN") or "").strip()
        rec = [int(fid), name, groups.get(r["CNF_Food_Group_Code"].strip(), ""), vals[fid], measures.get(fid, [])]
        if alt:
            rec.append(alt)
        out_foods.append(rec)
    out_foods.sort(key=lambda x: x[1].lower())
    print(f"\nFoods: {len(out_foods)}; with household measures: {sum(1 for f in out_foods if f[4])}")
    for i, k in enumerate(keys):
        have = sum(1 for f in out_foods if f[3][i] is not None)
        print(f"  {k:8s} values for {have:5d} foods ({have / max(1, len(out_foods)):.0%})")
    return {
        "meta": {"demo": False, "source": "Health Canada, Canadian Nutrient File", "version": version,
                 "built": datetime.date.today().isoformat()},
        "nutrients": keys,
        "foods": out_foods,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--cnf", help="folder with CNF CSV files")
    ap.add_argument("--version", default="CNF 2026")
    ap.add_argument("--out", default=str(HERE / "index.html"))
    ap.add_argument("--off", help="Open Food Facts extract (data/off_canada.json)")
    a = ap.parse_args()
    if a.demo:
        data = json.loads((HERE / "demo_data.json").read_text())
        data["nutrients"] = [k for k, *_ in NUTRIENTS]
    elif a.cnf:
        data = build_cnf(a.cnf, a.version)
    else:
        ap.error("use --demo or --cnf DIR")
    if a.off:
        off = json.loads(Path(a.off).read_text(encoding="utf-8"))
        keys = off["meta"]["keys"]
        drop = {"vita", "vitd", "vitc"}  # sparse and unreliable unit handling in label data
        keep = [i for i, k in enumerate(keys) if k not in drop]
        def sig(v):
            if v is None: return None
            if v == 0: return 0
            r = float(f"{v:.3g}")
            return int(r) if r == int(r) else r
        foods, dropped = [], {}
        cats = None
        for rec in off["foods"]:
            code, name, brand, vals, measures = rec[:5]
            cat = rec[5] if len(rec) > 5 else ""
            why = implausible(name, cat, dict(zip(keys, vals)), cats)
            if why:
                dropped.setdefault(why, []).append(f"{name} – {brand}")
                continue
            if not brand.strip():
                continue  # unbranded entries duplicate generic CNF foods and are less reliable
            clean = lambda t: " ".join(t.replace("\ufffd", "").split())
            measures = [[clean(m), g] for m, g in measures]
            foods.append([code, clean(name), clean(brand), [sig(vals[i]) for i in keep], measures])
        off["meta"]["keys"] = [keys[i] for i in keep]
        off["foods"] = foods
        data["extra"] = [{
            "id": "off", "short": "Label", "label": "Packaged products, label data (Open Food Facts)",
            "credit": "Packaged products: (c) Open Food Facts contributors, ODbL. Label data only; entries may contain errors.",
            "fetched": off["meta"].get("fetched"), "keys": off["meta"]["keys"], "foods": off["foods"],
        }]
        print(f"Added {len(off['foods']):,} Open Food Facts products")
        for why, lst in dropped.items():
            print(f"  dropped {len(lst):5d} ({why})")
            import random; random.seed(1)
            for x in random.sample(lst, min(12, len(lst))): print("      ", x)
    comp, cur = HERE / "data" / "compendium_2024.json", HERE / "data" / "activities_curated.json"
    if comp.exists() and cur.exists():
        acts = json.loads(comp.read_text(encoding="utf-8"))["activities"]
        curated = json.loads(cur.read_text(encoding="utf-8"))
        codes = {x["code"] for x in acts}
        missing = [c for _, items in curated for c, _ in items if c not in codes]
        if missing:
            sys.exit(f"Curated activity codes not in compendium: {missing}")
        data["activities"] = {"all": [[x["code"], x["met"], x["heading"], x["desc"]] for x in acts], "curated": curated}
        print(f"Added {len(acts):,} compendium activities ({sum(len(i) for _, i in curated)} curated)")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (HERE / "template.html").read_text(encoding="utf-8").replace("/*__CNF_DATA__*/", blob)
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"\nWrote {a.out} ({len(html) / 1e6:.2f} MB)")

if __name__ == "__main__":
    main()
