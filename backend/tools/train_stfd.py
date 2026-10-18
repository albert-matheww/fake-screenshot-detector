"""Train the word-level rendering model on REAL edits (STFD) and test it on screenshots it has never seen.

  python tools/train_stfd.py featurize --root data/stfd/extracted/STFD_ICASSP2023 --out data/stfd/feats.npz
  python tools/train_stfd.py train --feats data/stfd/feats.npz --out-dir model_data_stfd [--real data/realset]

Labels come from STFD's pixel masks: an OCR word is "edited" if >= 25% of its box lies inside the mask, "unedited" if its
box (plus a margin) touches no mask pixel; ambiguous words are dropped. The split is by SOURCE SCREENSHOT: perceptual
hashing groups near-identical base screenshots (the same screen edited in several ways) so they never straddle train/test.
STFD has no genuine whole images, so image-level false alarms are measured on the project owner's own genuine screenshots.
"""
import argparse, json, os, sys, time
from multiprocessing import Pool

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import textforensics as tf  # noqa: E402

POS_COVER = 0.25
MARGIN = 8


def dhash(img, size=16):
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.float32)
    return (g[:, 1:] > g[:, :-1]).flatten()


def work(args):
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    from scipy import ndimage as ndi
    path, mpath, etype = args
    img = Image.open(path).convert("RGB")
    mask = np.asarray(Image.open(mpath).convert("L")) > 127
    if mask.shape != (img.height, img.width):
        return None
    words = tf.ocr_words(img)
    X, kept, info = tf.image_word_features(img, words)
    h = dhash(img)
    if X.shape[0] == 0:
        return {"path": path, "etype": etype, "hash": h, "X": X, "y": np.zeros(0, np.int8), "n_words": 0, "text": []}
    near = ndi.binary_dilation(mask, iterations=MARGIN)
    y = np.full(len(kept), -1, np.int8)
    for i, w in enumerate(kept):
        x0, y0, x1, y1 = int(w["left"]), int(w["top"]), int(w["left"] + w["width"]), int(w["top"] + w["height"])
        cov = mask[max(y0, 0):y1, max(x0, 0):x1].mean() if (y1 > y0 and x1 > x0) else 0.0
        if cov >= POS_COVER:
            y[i] = 1
        elif not near[max(y0, 0):y1, max(x0, 0):x1].any():
            y[i] = 0
    return {"path": path, "etype": etype, "hash": h, "X": X, "y": y, "n_words": len(kept)}


def featurize(a):
    jobs = []
    for t in sorted(d for d in os.listdir(a.root) if d[:1].isdigit()):
        for f in sorted(os.listdir(os.path.join(a.root, t, "tamper"))):
            jobs.append((os.path.join(a.root, t, "tamper", f), os.path.join(a.root, t, "masks", f), t))
    if a.limit:
        jobs = jobs[:: max(1, len(jobs) // a.limit)]
    t0 = time.time()
    with Pool(a.workers) as p:
        res = [r for r in p.map(work, jobs, chunksize=2) if r is not None]
    X = np.concatenate([r["X"] for r in res if len(r["y"])])
    y = np.concatenate([r["y"] for r in res if len(r["y"])])
    img_idx = np.concatenate([np.full(len(r["y"]), i) for i, r in enumerate(res) if len(r["y"])])
    np.savez_compressed(a.out, X=X, y=y, img_idx=img_idx, hashes=np.stack([r["hash"] for r in res]),
                        paths=np.array([r["path"] for r in res]), etypes=np.array([r["etype"] for r in res]))
    print(f"{len(res)} images, {len(y)} words ({int((y == 1).sum())} edited, {int((y == 0).sum())} unedited, "
          f"{int((y == -1).sum())} ambiguous) in {time.time() - t0:.0f}s")


def groups_from_hashes(H, thr=20):
    n = len(H)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    Hp = np.packbits(H, axis=1)
    pop = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)
    for i in range(n):
        d = pop[np.bitwise_xor(Hp[i + 1:], Hp[i])].sum(axis=1)
        for j in np.nonzero(d <= thr)[0]:
            ri, rj = find(i), find(i + 1 + j)
            if ri != rj:
                parent[ri] = rj
    return np.array([find(i) for i in range(n)])


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def train(a):
    from sklearn.ensemble import HistGradientBoostingClassifier
    import joblib
    z = np.load(a.feats, allow_pickle=True)
    X, y, idx, H = z["X"], z["y"], z["img_idx"], z["hashes"]
    grp = groups_from_hashes(H)
    ug = np.unique(grp)
    print(f"{len(H)} images fall into {len(ug)} source groups (largest {np.bincount(np.unique(grp, return_inverse=True)[1]).max()})")
    rng = np.random.RandomState(0)
    perm = rng.permutation(ug)
    tr_g, va_g, te_g = set(perm[: int(.7 * len(perm))]), set(perm[int(.7 * len(perm)): int(.85 * len(perm))]), set(perm[int(.85 * len(perm)):])
    part = np.array([0 if grp[i] in tr_g else (1 if grp[i] in va_g else 2) for i in idx])
    keep = y >= 0
    sets = {k: keep & (part == v) for k, v in (("train", 0), ("val", 1), ("test", 2))}
    for k, m in sets.items():
        print(f"{k}: {int(m.sum())} words, {int((y[m] == 1).sum())} edited")
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=15, class_weight="balanced", random_state=0)
    m.fit(X[sets["train"]], y[sets["train"]])
    pv, pt = m.predict_proba(X[sets["val"]])[:, 1], m.predict_proba(X[sets["test"]])[:, 1]
    out = {"word_auc_val": auc(y[sets["val"]], pv), "word_auc_test": auc(y[sets["test"]], pt)}
    # thresholds: the false-alarm points on UNEDITED validation words (word level, so conservative at image level)
    neg = np.sort(pv[y[sets["val"]] == 0])
    thr = {"5%": float(np.quantile(neg, .95)), "1%": float(np.quantile(neg, .99)), "0.1%": float(np.quantile(neg, .999))}
    out["thresholds"] = thr
    yt = y[sets["test"]]
    out["test_word_tpr_at"] = {k: float((pt[yt == 1] >= v).mean()) for k, v in thr.items()}
    out["test_word_fpr_at"] = {k: float((pt[yt == 0] >= v).mean()) for k, v in thr.items()}
    # per edit type on test
    et = z["etypes"][idx]
    out["test_word_auc_by_edit_type"] = {}
    for t in sorted(set(et)):
        mm = sets["test"] & (et == t)
        if (y[mm] == 1).sum() >= 5 and (y[mm] == 0).sum() >= 5:
            out["test_word_auc_by_edit_type"][t] = auc(y[mm], m.predict_proba(X[mm])[:, 1])
    # baseline: the shipped (generated-data) model on the same test words
    try:
        import analysis_model as am
        if am.MODEL is not None:
            ps = am.MODEL.predict_proba(X[sets["test"]])[:, 1]
            out["shipped_model_word_auc_test"] = auc(yt, ps)
    except Exception as e:  # noqa: BLE001
        out["shipped_model_error"] = str(e)
    os.makedirs(a.out_dir, exist_ok=True)
    joblib.dump(m, os.path.join(a.out_dir, "word_stfd.joblib"))
    json.dump({"feature_names": tf.FEATURE_NAMES, "thresholds": thr, "trained_on": "STFD (real edits), source-grouped split", **out},
              open(os.path.join(a.out_dir, "word_stfd_meta.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    if a.real:
        real(a, m, thr)


def _img_max(m, img):
    words = tf.ocr_words(img)
    X, kept, _ = tf.image_word_features(img, words)
    if X.shape[0] < 6:
        return None
    p = m.predict_proba(X)[:, 1]
    return float(p.max())


def real(a, m, thr):
    import glob
    res = {"authentic": [], "edited": []}
    for k in res:
        for p in sorted(glob.glob(os.path.join(a.real, k, "*"))):
            if p.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                res[k].append((os.path.basename(p), _img_max(m, Image.open(p).convert("RGB"))))
    for k, v in res.items():
        scored = [s for _, s in v if s is not None]
        line = {t: int(sum(s >= th for s in scored)) for t, th in thr.items()}
        print(f"owner's {k}: {len(v)} images, {len(scored)} scorable; flagged at thresholds {line}")
        print("  scores:", [round(s, 3) if s is not None else None for _, s in v])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("featurize"); f.add_argument("--root", required=True); f.add_argument("--out", required=True)
    f.add_argument("--workers", type=int, default=6); f.add_argument("--limit", type=int, default=0)
    t = sub.add_parser("train"); t.add_argument("--feats", required=True); t.add_argument("--out-dir", default="model_data_stfd"); t.add_argument("--real")
    a = ap.parse_args()
    featurize(a) if a.cmd == "featurize" else train(a)
