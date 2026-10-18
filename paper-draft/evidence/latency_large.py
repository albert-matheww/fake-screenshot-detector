"""Latency on the largest full-size real screenshots of the final corpus (this machine)."""
import sys, pickle, time, statistics as st
sys.path.insert(0, "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend")
import analysis
D = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/data"
recs = pickle.load(open(f"{D}/forge_realfull/feat_test.pkl", "rb")) + pickle.load(open(f"{D}/forge_realfull/feat_train.pkl", "rb"))
recs = sorted((r for r in recs if r["label"] == 0), key=lambda r: -r["size"][0] * r["size"][1])[:8]
ms = []
for r in recs:
    raw = open(f"{D}/forge_realfull/{r['path']}", "rb").read(); t = time.time(); res = analysis.analyze_image_bytes(raw); ms.append((time.time() - t) * 1000)
    print(f"{r['size'][0]}x{r['size'][1]} ({r['size'][0]*r['size'][1]/1e6:.1f} MP): {ms[-1]:.0f} ms, measured words {res['stats']['measured_words']}")
print(f"largest {len(ms)} full-size genuine screenshots: median {st.median(ms):.0f} ms, max {max(ms):.0f} ms")
