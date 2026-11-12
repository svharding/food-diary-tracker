#!/usr/bin/env python3
"""Download the 2024 Adult Compendium of Physical Activities (PDF) and extract
activity code, major heading, MET value and description to data/compendium_2024.json.

Source: Herrmann SD, Willis EA, Ainsworth BE, et al. 2024 Adult Compendium of Physical
Activities: A third update of the energy costs of human activities. J Sport Health Sci
2024;13(1):6-12. https://pacompendium.com/  MET values are used unchanged.
"""
import json, os, re, urllib.request
import pdfplumber

URL = "https://pacompendium.com/wp-content/uploads/2024/02/1_2024-adult-compendium_1_2024.pdf"
os.makedirs("data", exist_ok=True)
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (food-diary-tracker data job)"})
open("/tmp/compendium.pdf", "wb").write(urllib.request.urlopen(req, timeout=120).read())

import statistics
rows, raw, bad = [], [], []
with pdfplumber.open("/tmp/compendium.pdf") as pdf:
    for page in pdf.pages:
        raw.extend((page.extract_text() or "").splitlines())
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
        codes = [w for w in words if re.fullmatch(r"\d{5}", w["text"])]
        if not codes:
            continue
        code_x = statistics.median(w["x0"] for w in codes)
        code_x1 = statistics.median(w["x1"] for w in codes)
        mets = [w for w in words if re.fullmatch(r"\d{1,2}\.\d", w["text"]) and code_x1 < w["x0"] < code_x1 + 80]
        met_x1 = statistics.median(w["x1"] for w in mets) if mets else code_x1 + 40
        # group words into lines
        lines = {}
        for w in words:
            key = round(w["top"] / 2)
            lines.setdefault(key, []).append(w)
        recs, others = [], []
        for key in sorted(lines):
            ws = sorted(lines[key], key=lambda w: w["x0"])
            top = statistics.mean(w["top"] for w in ws)
            head = " ".join(w["text"] for w in ws if w["x1"] < code_x - 2)
            code = [w["text"] for w in ws if abs(w["x0"] - code_x) < 6 and re.fullmatch(r"\d{5}", w["text"])]
            met = [w["text"] for w in ws if code_x1 < w["x0"] and w["x1"] <= met_x1 + 6 and re.fullmatch(r"\d{1,2}(\.\d+)?", w["text"])]
            desc = " ".join(w["text"] for w in ws if w["x0"] > met_x1 + 2)
            full = " ".join(w["text"] for w in ws)
            if re.search(r"Major Heading|Activity Code|Adult Compendium|Page \d", full):
                continue
            if code and met:
                recs.append({"top": top, "code": code[0], "met": float(met[0]), "head": [head] if head else [], "desc": [(top, desc)] if desc else []})
            else:
                others.append((top, head, desc))
        for top, head, desc in others:
            if not recs:
                continue
            r = min(recs, key=lambda r: abs(r["top"] - top))
            if abs(r["top"] - top) > 22:
                bad.append(f"{head} | {desc}"); continue
            if desc:
                r["desc"].append((top, desc))
            if head:
                r["head"].append(head)
        for r in recs:
            heads = [h for h in r["head"] if h]
            rows.append({"code": r["code"], "heading": " ".join(dict.fromkeys(heads)), "met": r["met"],
                         "desc": " ".join(d for _, d in sorted(r["desc"]))})
unmatched = bad
seen, out = set(), []
for r in rows:
    if r["code"] in seen:
        continue
    seen.add(r["code"]); out.append(r)
json.dump({"source": "2024 Adult Compendium of Physical Activities (pacompendium.com)", "activities": out},
          open("data/compendium_2024.json", "w"), ensure_ascii=False, indent=0)
with open("data/compendium_2024_summary.txt", "w") as fh:
    fh.write(f"Lines read: {len(raw)}; activities parsed: {len(out)}\n")
    heads = {}
    for r in out: heads[r["heading"]] = heads.get(r["heading"], 0) + 1
    fh.write("Headings:\n" + "\n".join(f"  {h}: {n}" for h, n in sorted(heads.items())) + "\n")
    fh.write("\nFirst 40 raw lines:\n" + "\n".join(raw[:40]) + "\n")
    fh.write(f"\nContinuation/unmatched lines ({len(unmatched)}), first 40:\n" + "\n".join(unmatched[:40]) + "\n")
print(open("data/compendium_2024_summary.txt").read())
