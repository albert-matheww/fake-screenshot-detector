"""Reproduces the rejected column-peer experiments with the saved scratch artefacts (v7 feature code + model)."""
import sys, json, importlib.util, pickle, joblib, numpy as np
ROOT = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector"
S = "/private/tmp/claude-501/-Users-albertmathew-Desktop-projects-fake-screenshot-detector/dd5abb74-8524-43e1-980c-664131e23a6d/scratchpad"
sys.path.insert(0, ROOT + "/backend")
from PIL import Image
spec = importlib.util.spec_from_file_location("tf7", S + "/textforensics_v7_column_peers.py"); tf7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(tf7)
import textforensics as tf6
IMG = S + "/images"
IMG = "/private/tmp/claude-501/-Users-albertmathew-Desktop-projects-fake-screenshot-detector/dd5abb74-8524-43e1-980c-664131e23a6d/images"
models = {"shipped model (95 features)": (tf6, joblib.load(ROOT + "/backend/model_data/word_gbm.joblib"), json.load(open(ROOT + "/backend/model_data/word_gbm_meta.json"))),
          "column-peer model (117 features)": (tf7, joblib.load(S + "/model_v7/word_gbm.joblib"), json.load(open(S + "/model_v7/word_gbm_meta.json")))}
print("== A. top word probability on the eight hand-collected images")
for name, (tf, m, meta) in models.items():
    thr = meta["thresholds"]
    print(f"{name}: suspicious >= {thr['5%']:.3f}, evidence >= {thr['1%']:.3f}")
    for n, lab in [("3.jpg","edited"),("4.jpg","edited"),("5.jpg","edited"),("6.jpg","edited"),("7.webp","real"),("8.webp","real"),("9.webp","real"),("10.webp","real")]:
        im = Image.open(f"{IMG}/{n}").convert("RGB"); X, kept, _ = tf.image_word_features(im)
        p = m.predict_proba(X)[:, 1]; i = int(p.argmax())
        tier = "EVIDENCE" if p[i] >= thr["1%"] else ("suspicious" if p[i] >= thr["5%"] else "none")
        print(f"   {n:8s} {lab:6s} top p={p[i]:.3f} -> {tier}")
print("== B. column z-scores on the corpus (forge_v7 features): saturation and a numeric-column rule")
col = {n: i for i, n in enumerate(tf7.FEATURE_NAMES)}
recs = []
for sp in ("val", "test"): recs += pickle.load(open(f"{ROOT}/data/forge_v7/feat_{sp}.pkl", "rb"))
def stats(r):
    X = r["X"]
    if X.shape[0] == 0 or X.shape[0] != len(r["y"]): return None
    m = X[:, col["col_n"]] >= 4
    if m.sum() < 4: return None
    return float(np.abs(X[m, col["z_col_stroke_w2"]]).max()), float(np.abs(X[m, col["z_col_sharp_hi"]]).max())
A = [(r, stats(r)) for r in recs if r["label"] == 0]; E = [(r, stats(r)) for r in recs if r["label"] == 1]
A = [(r, s) for r, s in A if s]; E = [(r, s) for r, s in E if s]
for nm, idx in (("stroke_w2", 0), ("sharp_hi", 1)):
    a = np.array([s[idx] for _, s in A]); e = np.array([s[idx] for _, s in E])
    print(f"max |z_col_{nm}| per image: genuine median {np.median(a):.1f}, p90 {np.percentile(a, 90):.1f}; simulated-edited median {np.median(e):.1f}, p90 {np.percentile(e, 90):.1f}  (z clipped at 12; {len(A)} genuine, {len(E)} edited images with a usable column)")
def rz(vals, own):
    med = np.median(vals); mad = np.median(np.abs(vals - med)) * 1.4826; sc = max(mad, 0.05 * abs(med), 1e-3); return abs((own - med) / sc)
def numeric(t): return len(t) >= 2 and sum(c.isdigit() for c in t) / len(t) >= 0.5
def img_stats(r):
    X = r["X"]; W = r["words"]
    if X.shape[0] == 0 or X.shape[0] != len(W): return None
    num = [i for i, w in enumerate(W) if numeric(w[0]) and 10 <= w[4] <= 120]
    if len(num) < 5: return None
    right = np.array([W[i][1] + W[i][3] for i in num], float); hh = np.array([W[i][4] for i in num], float); cy = np.array([W[i][2] + W[i][4] / 2 for i in num])
    bs = bh = None; ne = 0
    for a, i in enumerate(num):
        m = (np.abs(right - right[a]) <= 0.4 * hh[a] + 6) & (hh / hh[a] >= 0.7) & (hh / hh[a] <= 1.4) & (np.abs(cy - cy[a]) > 0.8 * hh[a]); m[a] = False
        if m.sum() < 4: continue
        peers = [num[b] for b in np.where(m)[0]]
        zs = rz(X[peers, col["stroke_w2"]], X[i, col["stroke_w2"]]); zh = rz(X[peers, col["sharp_hi"]], X[i, col["sharp_hi"]]); ne += 1
        bs = zs if bs is None or zs > bs else bs; bh = zh if bh is None or zh > bh else bh
    return None if ne == 0 else (bs, bh)
A = [(r, img_stats(r)) for r in recs if r["label"] == 0]; E = [(r, img_stats(r)) for r in recs if r["label"] == 1]
A = [(r, s) for r, s in A if s]; E = [(r, s) for r, s in E if s]
print(f"numeric-column rule evaluated on {len(A)} genuine and {len(E)} edited images that have a numeric column")
for ts, th in ((3, 6), (3, 8), (4, 8), (3, 12)):
    line = f"  rule stroke z>={ts} and sharp z>={th}:"
    for src in ("real", "chrome", "pillow"):
        a = [s for r, s in A if r["source"] == src]; e = [s for r, s in E if r["source"] == src]
        if a: line += f" {src} genuine {np.mean([(s[0] >= ts and s[1] >= th) for s in a]):.1%} (n={len(a)}) / edited {np.mean([(s[0] >= ts and s[1] >= th) for s in e]):.1%} (n={len(e)});"
    print(line)
