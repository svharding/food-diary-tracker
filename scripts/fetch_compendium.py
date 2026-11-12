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

rows, raw, bad = [], [], []
HEAD_OK = re.compile(r"^[A-Za-z][A-Za-z ,&/'-]+$")
with pdfplumber.open("/tmp/compendium.pdf") as pdf:
    for page in pdf.pages:
        raw.extend((page.extract_text() or "").splitlines())
        for table in page.extract_tables():
            for cells in table:
                cells = [" ".join((c or "").split()) for c in cells]
                if len(cells) < 4:
                    bad.append(" | ".join(cells)); continue
                head, code, met, desc = cells[0], cells[1], cells[2], " ".join(cells[3:]).strip()
                if not re.fullmatch(r"\d{5}", code):
                    if not re.search(r"Activity Code", code, re.I):
                        bad.append(" | ".join(cells))
                    continue
                try:
                    m = float(met)
                except ValueError:
                    bad.append(" | ".join(cells)); continue
                rows.append({"code": code, "heading": head, "met": m, "desc": desc})
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
