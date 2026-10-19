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


def share_degrade(img, mask, key):
    """Imitate sharing through a chat app: shrink so the long side is at most 1600 px and re-save as JPEG (quality 60-90)."""
    import io, zlib
    rng = np.random.RandomState(zlib.crc32(key.encode()) & 0xFFFFFFFF)
    q = int(rng.choice([60, 70, 80, 90]))
    long_side = max(img.size)
    if long_side > 1600:
        k = 1600 / long_side
        size = (max(1, round(img.width * k)), max(1, round(img.height * k)))
        img = img.resize(size, Image.LANCZOS)
        mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize(size, Image.NEAREST)) > 127
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), mask


def dhash(img, size=16):
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.float32)
    return (g[:, 1:] > g[:, :-1]).flatten()


def work(args):
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    from scipy import ndimage as ndi
    path, mpath, etype, degrade = args
    img = Image.open(path).convert("RGB")
    mask = np.asarray(Image.open(mpath).convert("L")) > 127
    if mask.shape != (img.height, img.width):
        return None
    if degrade:
        img, mask = share_degrade(img, mask, path)
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
            jobs.append((os.path.join(a.root, t, "tamper", f), os.path.join(a.root, t, "masks", f), t, a.degrade))
    if a.limit:
        jobs = jobs[:: max(1, len(jobs) // a.limit)]
    t0 = time.time()
    with Pool(a.workers) as p:
        res = []
        for k, r in enumerate(p.imap(work, jobs, chunksize=2)):
            if r is not None:
                res.append(r)
            if k % 500 == 0:
                print(f"  {k}/{len(jobs)} images, {time.time() - t0:.0f}s", flush=True)
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


# ---------------------------------------------------------------- clean vs "shared" (chat-app degraded) training comparison
def compare(a):
    import glob
    from sklearn.ensemble import HistGradientBoostingClassifier
    import joblib
    z1, z2 = np.load(a.feats, allow_pickle=True), np.load(a.feats_shared, allow_pickle=True)
    p1, p2 = list(z1["paths"]), list(z2["paths"])
    grp1 = groups_from_hashes(z1["hashes"])
    gmap = {p: g for p, g in zip(p1, grp1)}
    ug = np.unique(grp1)
    perm = np.random.RandomState(0).permutation(ug)
    cut1, cut2 = int(.7 * len(perm)), int(.85 * len(perm))
    part_of = {}
    for i, g in enumerate(perm):
        part_of[g] = 0 if i < cut1 else (1 if i < cut2 else 2)

    def split(z, paths):
        gi = np.array([part_of[gmap[paths[i]]] for i in z["img_idx"]])
        k = z["y"] >= 0
        return {n: k & (gi == v) for n, v in (("train", 0), ("val", 1), ("test", 2))}
    s1, s2 = split(z1, p1), split(z2, p2)
    X1, y1, X2, y2 = z1["X"], z1["y"], z2["X"], z2["y"]
    et1 = z1["etypes"][z1["img_idx"]]
    et2 = z2["etypes"][z2["img_idx"]]
    for nm, s, y in (("clean", s1, y1), ("shared", s2, y2)):
        print(f"{nm}: train {int(s['train'].sum())} words ({int((y[s['train']] == 1).sum())} edited), test {int(s['test'].sum())} ({int((y[s['test']] == 1).sum())} edited)")

    def fit(X, y):
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=15, class_weight="balanced", random_state=0).fit(X, y)
    models = {
        "A clean only": fit(X1[s1["train"]], y1[s1["train"]]),
        "B shared only": fit(X2[s2["train"]], y2[s2["train"]]),
        "C clean + shared": fit(np.concatenate([X1[s1["train"]], X2[s2["train"]]]), np.concatenate([y1[s1["train"]], y2[s2["train"]]])),
    }
    # owner's real screenshots, featurised once
    own = {"authentic": [], "edited": []}
    for k in own:
        for pth in sorted(glob.glob(os.path.join(a.real, k, "*"))):
            if pth.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                X, _, _ = tf.image_word_features(Image.open(pth).convert("RGB"))
                own[k].append(X if X.shape[0] >= 6 else None)
    out = {}
    for name, m in models.items():
        pv_shared = m.predict_proba(X2[s2["val"]])[:, 1]
        neg = np.sort(pv_shared[y2[s2["val"]] == 0])
        thr = {"5%": float(np.quantile(neg, .95)), "1%": float(np.quantile(neg, .99))}
        r = {"thresholds_from_shared_val": thr}
        for nm, X, y, s, et in (("clean_test", X1, y1, s1, et1), ("shared_test", X2, y2, s2, et2)):
            p = m.predict_proba(X[s["test"]])[:, 1]
            yy = y[s["test"]]
            r[nm] = {"word_auc": auc(yy, p), "tpr_at_5%": float((p[yy == 1] >= thr["5%"]).mean()), "fpr_at_5%": float((p[yy == 0] >= thr["5%"]).mean())}
            r[nm]["by_type"] = {}
            for t in sorted(set(et[s["test"]])):
                mm = et[s["test"]] == t
                if (yy[mm] == 1).sum() >= 5 and (yy[mm] == 0).sum() >= 5:
                    r[nm]["by_type"][t] = round(auc(yy[mm], p[mm]), 3)
        sc = {k: [float(m.predict_proba(X)[:, 1].max()) if X is not None else None for X in v] for k, v in own.items()}
        au = [s for s in sc["authentic"] if s is not None]
        ed = [s for s in sc["edited"] if s is not None]
        r["owner"] = {"n_authentic": len(au), "n_edited": len(ed),
                      "image_auc": float(sum((x > y) + 0.5 * (x == y) for x in ed for y in au) / (len(au) * len(ed))),
                      **{f"flagged_at_{t}": {"authentic": int(sum(s >= th for s in au)), "edited": int(sum(s >= th for s in ed))} for t, th in thr.items()}}
        out[name] = r
        print(f"\n== {name}\n{json.dumps(r, indent=1)}")
    os.makedirs(a.out_dir, exist_ok=True)
    json.dump(out, open(os.path.join(a.out_dir, "compare.json"), "w"), indent=1)
    joblib.dump(models["C clean + shared"], os.path.join(a.out_dir, "word_stfd_mixed.joblib"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("featurize"); f.add_argument("--root", required=True); f.add_argument("--out", required=True)
    f.add_argument("--workers", type=int, default=6); f.add_argument("--limit", type=int, default=0); f.add_argument("--degrade", action="store_true")
    t = sub.add_parser("train"); t.add_argument("--feats", required=True); t.add_argument("--out-dir", default="model_data_stfd"); t.add_argument("--real")
    c = sub.add_parser("compare"); c.add_argument("--feats", required=True); c.add_argument("--feats-shared", required=True)
    c.add_argument("--out-dir", default="model_data_stfd"); c.add_argument("--real", required=True)
    a = ap.parse_args()
    {"featurize": featurize, "train": train, "compare": compare}[a.cmd](a)
