"""Wall-clock latency of analysis.analyze_image_bytes on test-split images of the final corpus (this machine)."""
import sys, pickle, os, statistics as st, time
sys.path.insert(0, "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend")
import analysis
from PIL import Image
D = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/data"
recs = pickle.load(open(f"{D}/forge_v6/feat_test.pkl", "rb"))
import random; random.Random(0).shuffle(recs)
rows = []
for r in recs[:80]:
    p = r["path"] if os.path.isabs(r["path"]) else f"{D}/forge_v6/{r['path']}"
    raw = open(p, "rb").read(); t = time.time(); res = analysis.analyze_image_bytes(raw); ms = (time.time() - t) * 1000
    w, h = res["image"]["width"], res["image"]["height"]
    rows.append((w * h / 1e6, ms, res["stats"]["measured_words"]))
rows.sort()
ms = [r[1] for r in rows]
print(f"n={len(rows)} images; median {st.median(ms):.0f} ms; p90 {sorted(ms)[int(0.9*len(ms))]:.0f} ms; max {max(ms):.0f} ms")
q = len(rows) // 3
for name, part in (("smallest third", rows[:q]), ("middle third", rows[q:2*q]), ("largest third", rows[2*q:])):
    print(f"{name}: {part[0][0]:.2f}-{part[-1][0]:.2f} megapixels, median {st.median(r[1] for r in part):.0f} ms, median measured words {st.median(r[2] for r in part):.0f}")
