"""Final pipeline on the nine e-statement pages (five PDFs, rendered at 150 dpi) with the type chosen. Prints statuses and ids only.
   python ../paper-draft/evidence/v3_statements.py ../data/realset/statements   (run from backend/ with its venv)"""
import collections, glob, os, sys
sys.path.insert(0, os.getcwd())
from screencheck.pipeline import analyze_bytes
rows = []
for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.png"))):
    r = analyze_bytes(open(p, "rb").read(), forced_type="bank_statement")
    by = {c["id"]: c for c in r["checks"]}
    live = [f["id"] for c in r["checks"] if c["gate"]["status"] == "live" and c["status"] == "finding" for f in c["findings"]]
    rows.append((os.path.basename(p), r["verdict"], r["assurance"]["level"], r["assurance"]["status"], by["typed.bank_statement"]["status"],
                 [f["id"] for f in by["typed.bank_statement"]["findings"]], live, by["content_logic"]["status"]))
print("pages", len(rows))
print("verdict", dict(collections.Counter(x[1] for x in rows)))
print("assurance", dict(collections.Counter((x[2], x[3]) for x in rows)))
print("running-balance rule", dict(collections.Counter(x[4] for x in rows)))
print("live findings", dict(collections.Counter(i for x in rows for i in x[6])))
for x in rows:
    print("  ", *x)
