#!/usr/bin/env python3
"""Stream the Open Food Facts CSV export and keep Canadian products with
complete core Nutrition Facts data. Writes data/off_canada.json and a summary.

Open Food Facts data: (c) Open Food Facts contributors, Open Database License (ODbL).
"""
import csv, gzip, io, json, os, statistics, sys, urllib.request, datetime

URL = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
OUT = "data/off_canada.json"
SUMMARY = "data/off_canada_summary.txt"

# app key -> (OFF column, multiplier from OFF unit (g, kcal) to app unit)
FIELDS = {
    "energy": ("energy-kcal_100g", 1),
    "protein": ("proteins_100g", 1),
    "fat": ("fat_100g", 1),
    "sfa": ("saturated-fat_100g", 1),
    "carb": ("carbohydrates_100g", 1),
    "sugars": ("sugars_100g", 1),
    "fibre": ("fiber_100g", 1),
    "chol": ("cholesterol_100g", 1000),    # g -> mg
    "na": ("sodium_100g", 1000),           # g -> mg
    "k": ("potassium_100g", 1000),
    "ca": ("calcium_100g", 1000),
    "fe": ("iron_100g", 1000),
    "vita": ("vitamin-a_100g", 1e6),       # g -> µg
    "vitd": ("vitamin-d_100g", 1e6),       # g -> µg
    "vitc": ("vitamin-c_100g", 1000),      # g -> mg
}
REQUIRED = ["energy", "protein", "fat", "carb"]

def num(s):
    if s is None or s == "":
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v == v and v >= 0 else None

def main():
    csv.field_size_limit(sys.maxsize)
    print("Downloading", URL, flush=True)
    resp = urllib.request.urlopen(URL, timeout=600)
    text = io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8", errors="replace", newline="")
    reader = csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE)
    header = next(reader)
    idx = {h: i for i, h in enumerate(header)}
    missing = [c for c, _ in FIELDS.values() if c not in idx]
    print("Columns missing from export:", missing, flush=True)
    need = ["code", "product_name", "brands", "countries_tags", "serving_size", "serving_quantity"]
    for c in need:
        if c not in idx:
            sys.exit(f"Required column {c} not in export")
    keys = list(FIELDS)
    seen, out, total, canada = set(), [], 0, 0
    raw_samples = {k: [] for k in keys}
    for row in reader:
        total += 1
        if total % 500000 == 0:
            print(f"  scanned {total:,} rows, kept {len(out):,}", flush=True)
        if len(row) < len(header):
            continue
        if "en:canada" not in row[idx["countries_tags"]]:
            continue
        canada += 1
        name = row[idx["product_name"]].strip()
        if not name:
            continue
        vals = []
        for k in keys:
            col, mult = FIELDS[k]
            v = num(row[idx[col]]) if col in idx else None
            vals.append(None if v is None else round(v * mult, 4))
        d = dict(zip(keys, vals))
        if any(d[k] is None for k in REQUIRED):
            continue
        if not (0 <= d["energy"] <= 900) or d["protein"] > 100 or d["fat"] > 100 or d["carb"] > 100:
            continue
        if d["protein"] + d["fat"] + d["carb"] > 105:
            continue
        brand = row[idx["brands"]].split(",")[0].strip()
        key = (name.lower(), brand.lower())
        if key in seen:
            continue
        seen.add(key)
        sq = num(row[idx["serving_quantity"]])
        ss = row[idx["serving_size"]].strip()[:40]
        measures = [["1 serving" + (f" ({ss})" if ss else ""), round(sq, 1)]] if sq and 0 < sq <= 2000 else []
        for k in keys:
            if d[k] is not None and len(raw_samples[k]) < 20000:
                raw_samples[k].append(d[k])
        out.append([row[idx["code"]], name[:120], brand[:60], vals, measures])
    meta = {
        "source": "Open Food Facts (Canada)",
        "licence": "ODbL; (c) Open Food Facts contributors",
        "fetched": datetime.date.today().isoformat(),
        "keys": keys,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "foods": out}, fh, ensure_ascii=False, separators=(",", ":"))
    lines = [f"Fetched {meta['fetched']}", f"Rows scanned: {total:,}", f"Tagged Canada: {canada:,}",
             f"Kept (complete core label data, deduplicated): {len(out):,}", "",
             "Median per 100 g among products with a value (sanity check units):"]
    for k in keys:
        s = raw_samples[k]
        cov = sum(1 for f in out if f[3][keys.index(k)] is not None)
        med = statistics.median(s) if s else None
        lines.append(f"  {k:7s} median={med}  values for {cov:,} products ({cov / max(1, len(out)):.0%})")
    open(SUMMARY, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
