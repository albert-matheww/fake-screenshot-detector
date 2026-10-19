"""Score the 23 genuine and 9 edited real screenshots with the version-3 pipeline (run from backend/ with its venv).
   python ../paper-draft/evidence/v3_real_set.py ../data/realset > ../paper-draft/evidence/v3_real_set.txt
Private screenshots: only verdicts, assurance levels and check ids are printed, never words."""
import collections, glob, os, sys, time
sys.path.insert(0, os.getcwd())
from screencheck.pipeline import analyze_bytes

root = sys.argv[1]
for kind in ("authentic", "edited"):
    rows = []
    lat = []
    for p in sorted(glob.glob(os.path.join(root, kind, "*"))):
        t = time.time()
        r = analyze_bytes(open(p, "rb").read())
        lat.append(time.time() - t)
        live = [c["id"] for c in r["checks"] if c["status"] == "finding" and c["gate"]["status"] == "live"]
        adv = [c["id"] for c in r["checks"] if c["status"] == "finding" and c["gate"]["status"] != "live" and not c["gate"].get("uninformative")]
        rows.append((os.path.basename(p), r["verdict"], r["assurance"]["level"], r["assurance"]["status"], live, adv, r["routing"]["type"], r["routing"]["status"]))
    print(f"[{kind}] {len(rows)} images")
    print("  verdicts:", dict(collections.Counter(x[1] for x in rows)))
    print("  assurance level:", dict(collections.Counter(x[2] for x in rows)), "status:", dict(collections.Counter(x[3] for x in rows)))
    print("  live findings:", sum(bool(x[4]) for x in rows), "| advisory findings per check:",
          dict(collections.Counter(c for x in rows for c in x[5])))
    print("  automatic type:", dict(collections.Counter(f"{x[6]}/{x[7]}" for x in rows)))
    print(f"  seconds per image: median {sorted(lat)[len(lat)//2]:.2f}, max {max(lat):.2f}")
    for x in rows:
        print("   ", x[0][:70], x[1], f"L{x[2]}", x[3], x[4], x[5])
