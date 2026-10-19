"""Final pipeline on the 15 further genuine screenshots (11 chats, 4 payment-history lists), with the type chosen as a person would.
   python ../paper-draft/evidence/v3_new15.py ../data/realset/new15    (run from backend/ with its venv; prints verdicts and ids only)"""
import collections, glob, json, os, sys, time
sys.path.insert(0, os.getcwd())
from screencheck.pipeline import analyze_bytes
labels = json.load(open("tools/real_labels.json"))["labels"]
rows = []
for p in sorted(glob.glob(os.path.join(sys.argv[1], "*"))):
    n = os.path.basename(p); t = time.time()
    r = analyze_bytes(open(p, "rb").read(), forced_type=labels[n])
    by = {c["id"]: c for c in r["checks"]}
    typed = next((c for c in r["checks"] if c["id"].startswith("typed.")), None)
    rows.append((n, labels[n], r["verdict"], r["assurance"]["level"], by["content_logic"]["status"], by["rendering"]["status"], typed["status"] if typed else None, time.time() - t))
print("images", len(rows))
for key, name in ((2, "verdict"), (3, "assurance level"), (4, "content rules"), (5, "word-rendering model"), (6, "type-specific rule")):
    for typ in ("chat", "payment_receipt"):
        sub = [r for r in rows if r[1] == typ]
        print(f"{typ:16s} {name:22s} n={len(sub)}", dict(collections.Counter(r[key] for r in sub)))
print("seconds per image: median %.2f max %.2f" % (sorted(r[7] for r in rows)[len(rows) // 2], max(r[7] for r in rows)))
for r in rows:
    print("  ", r[0], *r[2:7])
