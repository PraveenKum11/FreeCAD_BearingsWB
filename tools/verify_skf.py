# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-check BRData/*.csv against SKF's public deep groove ball bearing table.

    python3 tools/verify_skf.py

The script fetches the table on each run and does not store or redistribute it. Only the
boundary dimensions (d, D, B) are compared. Rows are matched by (d, D) because SKF names
miniatures differently (688 = 618/8, MR105 has no SKF name).
"""

import csv
import glob
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = (
    "https://search.skf.com/prod/search-skfcom/rest/apps/skfcom/searchers/dynamic_table"
    "?system=metric&language=en&locale=en-in&category=Deep%20groove%20ball%20bearings"
    "&contentstack_taxonomy_uid=blt634a650a928c34a2&sort=PIM001%7CFloating%20point%7CASCENDING"
    "&offset={offset}&hits=1000"
)
CLOSED = re.compile(r"(2Z|2RS|2RZ|RSH|RSL|RZ|-Z|-RS|ZS|ZNR|Z$|RS1)")


def fetch():
    rows, offset, total = {}, 0, None
    while total is None or offset < total:
        # curl instead of urllib: python.org builds on macOS often lack CA certificates
        out = subprocess.run(
            ["curl", "-sfS", "-m", "120", "-A", "Mozilla/5.0", URL.format(offset=offset)],
            check=True,
            capture_output=True,
        ).stdout
        data = json.loads(out)
        total = data["documentList"]["numberOfHits"]
        docs = data["documentList"]["documents"]
        if not docs:
            break
        for doc in docs:
            name, d, D, B = doc["table_values"][:4]
            if None not in (d, D, B):
                rows[name] = (d, D, B)
        offset += len(docs)
    return rows


def main():
    skf = fetch()
    print("SKF rows:", len(skf))
    index = {}
    for name, (d, D, B) in skf.items():
        index.setdefault((d, D), []).append((name, B))
    mismatches = unverified = checked = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "BRData", "*.csv"))):
        with open(path) as f:
            rows = list(csv.DictReader([ln for ln in f if not ln.startswith("#")]))
        for r in rows:
            d, D, B = float(r["d"]), float(r["D"]), float(r["B"])
            Bs = float(r["B_shielded"]) if r["B_shielded"] else B
            tag = "%s %s %gx%gx%g" % (os.path.basename(path), r["Designation"], d, D, B)
            cands = index.get((d, D))
            if not cands:
                unverified += 1
                print("  unverified  %s: SKF has no bearing with this d x D" % tag)
                continue
            checked += 1
            opens = sorted({b for n, b in cands if not CLOSED.search(n)})
            closed = sorted({b for n, b in cands if CLOSED.search(n)})
            if opens and B not in opens:
                mismatches += 1
                print("  MISMATCH    %s: open width, SKF %s" % (tag, opens))
            if closed and Bs not in closed:
                mismatches += 1
                print("  MISMATCH    %s: closed width %g, SKF %s" % (tag, Bs, closed))
    print("checked %d rows, %d mismatches, %d not in SKF range" % (checked, mismatches, unverified))


if __name__ == "__main__":
    main()
