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

def build_cnf(d, version):
    d = Path(d)
    f_food = find_file(d, r"^foodname", r"foodname")
    f_amt = find_file(d, r"^nutrientamount", r"nutrientamount")
    f_nn = find_file(d, r"^nutrientname", r"nutrientname")
    f_grp = find_file(d, r"^foodgroup", r"foodgroup")
    f_conv = find_file(d, r"measureweightconversion", r"^conversionfactor", r"conversionfactor", r"measureweight")
    f_mn = find_file(d, r"^measurename", r"measurename")
    print("Files:")
    for lbl, f in [("food name", f_food), ("nutrient amount", f_amt), ("nutrient name", f_nn), ("food group", f_grp), ("conversion", f_conv), ("measure name", f_mn)]:
        print(f"  {lbl:16s} {f.name if f else '-- NOT FOUND --'}")
    if not (f_food and f_amt and f_nn):
        sys.exit("Missing a required file")

    foods = read_csv(f_food)
    c_fid = col(foods, "FoodID", "Food ID", label="food id")
    c_fdesc = col(foods, "FoodDescription", "FoodDescriptionE", "Food Description English", "FoodNameE", "FoodDescriptionEnglish", label="food description")
    c_fgrp = col(foods, "FoodGroupID", "Food Group ID", required=False)
    c_alt = col(foods, "AlternateFoodDescription", "AlternateDescription", "AlternateFoodDescriptionE", "AltFoodDescription", required=False)
    c_fcode = col(foods, "FoodCode", "Food Code", required=False)

    groups = {}
    if f_grp:
        g = read_csv(f_grp)
        gid = col(g, "FoodGroupID", label="group id")
        gname = col(g, "FoodGroupName", "FoodGroupNameE", "Food Group Name English", label="group name")
        groups = {r[gid].strip(): r[gname].strip() for r in g}

    nn = read_csv(f_nn)
    c_nid = col(nn, "NutrientID", "NutrientNameID", "Nutrient ID", label="nutrient id")
    c_nname = col(nn, "NutrientName", "NutrientNameE", "Nutrient Name English", label="nutrient name")
    c_nunit = col(nn, "NutrientUnit", "Unit", required=False)
    c_nsym = col(nn, "NutrientSymbol", "Symbol", required=False)

    print("\nNutrient matching (CHECK THIS):")
    key_to_nid, problems = {}, []
    for key, unit, inc, exc in NUTRIENTS:
        hits = []
        for r in nn:
            name = r[c_nname].strip().lower()
            if re.search(inc, name) and not (exc and re.search(exc, name)):
                hits.append(r)
        if not hits:
            problems.append(key)
            print(f"  {key:8s} -- NO MATCH --")
            continue
        r = hits[0]
        key_to_nid[key] = r[c_nid].strip()
        u = r[c_nunit].strip() if c_nunit else "?"
        extra = f"   (also matched: {'; '.join(h[c_nname].strip() for h in hits[1:4])})" if len(hits) > 1 else ""
        flag = "" if unit_norm(u) == unit_norm(unit) else f"  <-- UNIT CHECK: expected {unit}"
        print(f"  {key:8s} id={key_to_nid[key]:>5s}  {r[c_nname].strip()} [{u}]{extra}{flag}")

    amt = read_csv(f_amt)
    a_fid = col(amt, "FoodID", label="amount food id")
    a_nid = col(amt, "NutrientID", "NutrientNameID", label="amount nutrient id")
    a_val = col(amt, "NutrientValue", "NutrientAmount", "Value", label="amount value")
    keys = [k for k, *_ in NUTRIENTS]
    nid_to_idx = {nid: keys.index(k) for k, nid in key_to_nid.items()}
    vals = {}
    for r in amt:
        i = nid_to_idx.get(r[a_nid].strip())
        if i is None:
            continue
        v = num(r[a_val])
        if v is None:
            continue
        vals.setdefault(r[a_fid].strip(), [None] * len(NUTRIENTS))[i] = round(v, 4)

    measures = {}
    if f_conv:
        conv = read_csv(f_conv)
        m_fid = col(conv, "FoodID", label="conv food id")
        m_mid = col(conv, "MeasureID", required=False)
        m_fac = col(conv, "ConversionFactorValue", "ConversionFactor", "MeasureWeightConversionFactor", "Factor", label="conversion factor")
        m_g = col(conv, "MeasureWeight", "Weight", "Grams", "WeightGrams", required=False)
        m_desc = col(conv, "MeasureDescription", "MeasureDescriptionE", "MeasureName", required=False)
        mnames = {}
        if f_mn:
            mn = read_csv(f_mn)
            mn_id = col(mn, "MeasureID", label="measure id")
            mn_d = col(mn, "MeasureDescription", "MeasureDescriptionE", "MeasureName", "MeasureNameE", label="measure description")
            mnames = {r[mn_id].strip(): r[mn_d].strip() for r in mn}
        for r in conv:
            fid = r[m_fid].strip()
            name = (r[m_desc].strip() if m_desc and r.get(m_desc) else mnames.get(r[m_mid].strip(), "") if m_mid else "")
            g = num(r[m_g]) if m_g else None
            if g is None:
                fac = num(r[m_fac])
                g = fac * 100 if fac is not None else None
            if not name or not g or g <= 0:
                continue
            lst = measures.setdefault(fid, [])
            if all(n != name for n, _ in lst):
                lst.append([name, round(g, 1)])

    out_foods = []
    for r in foods:
        fid = r[c_fid].strip()
        if fid not in vals:
            continue
        name = re.sub(r"\s+", " ", r[c_fdesc]).strip()
        grp = groups.get(r[c_fgrp].strip(), "") if c_fgrp else ""
        alt = r[c_alt].strip() if c_alt and r.get(c_alt) else ""
        rec = [int(fid) if fid.isdigit() else fid, name, grp, vals[fid], measures.get(fid, [])]
        if alt:
            rec.append(alt)
        out_foods.append(rec)
    out_foods.sort(key=lambda x: x[1].lower())

    n_meas = sum(1 for f in out_foods if f[4])
    print(f"\nFoods with nutrient values: {len(out_foods)}; with household measures: {n_meas}")
    for key, *_ in NUTRIENTS:
        i = [k for k, *_ in NUTRIENTS].index(key)
        have = sum(1 for f in out_foods if f[3][i] is not None)
        print(f"  {key:8s} values for {have:5d} foods ({have / max(1, len(out_foods)):.0%})")
    if problems:
        print("\nWARNING: unmatched nutrients:", ", ".join(problems))
    return {
        "meta": {"demo": False, "source": "Health Canada, Canadian Nutrient File", "version": version,
                 "built": datetime.date.today().isoformat(), "unmatched": problems},
        "nutrients": [k for k, *_ in NUTRIENTS],
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
        foods = []
        for code, name, brand, vals, measures in off["foods"]:
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
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (HERE / "template.html").read_text(encoding="utf-8").replace("/*__CNF_DATA__*/", blob)
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"\nWrote {a.out} ({len(html) / 1e6:.2f} MB)")

if __name__ == "__main__":
    main()
