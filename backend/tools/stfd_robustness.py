"""Robustness of the STFD word-model result: several grouped splits (seeds), bootstrap intervals over source groups,
feature-family ablation, and a random-choice baseline for 'does a flagged word land on the edit?'.

  python tools/stfd_robustness.py --feats data/stfd/feats.npz --feats-shared data/stfd/feats_shared.npz --out results.json

Uses the cached word features of tools/train_stfd.py (nothing is re-read from images). Splits are by source-screenshot group
(perceptual hash), exactly as in train_stfd.py; the seed only changes which groups fall in train, validation and test.
"""
import argparse, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import textforensics as tf  # noqa: E402

NAMES = list(tf.FEATURE_NAMES)
REL = set(tf.REL)
FAMILY_RAW = {
    "edge and contrast": ["aa_ratio", "edge95", "ink_q25", "ink_q50", "ink_q75", "ink_sd", "contrast", "sharp_hi", "exey"],
    "colour": ["ink_chroma", "edge_chroma", "lcd_fringe"],
    "strokes": ["stroke_w", "stroke_w2", "ink_frac"],
    "background": ["bg_noise_in", "bg_noise_out", "noise_ratio", "bg_shift"],
    "seam": ["seam_max", "seam_pos", "seam_sides"],
    "JPEG grid": ["grid_strength", "grid_phase_mismatch"],
    "histograms": [f"h{i}" for i in range(8)] + [f"o{i}" for i in range(8)] + ["hist_d_img", "hist_d_line", "ori_d_img", "ori_d_line"],
    "geometry": ["h", "w", "char_w", "conf", "n_chars", "digit_frac"],
    "line context": ["rel_h_line", "base_off_line", "top_off_line", "ink_dist_line", "bg_dist_line", "line_n", "n_words_img"],
}


def family_indices(fam):
    raws = set(FAMILY_RAW[fam])
    idx = [i for i, n in enumerate(NAMES) if n in raws or (n.startswith(("z_img_", "z_line_")) and n.split("_", 2)[2] in raws)]
    return idx


def groups():
    from tools.train_stfd import groups_from_hashes  # noqa: E402
    return groups_from_hashes


def split(z, paths, seed, gmap, ug):
    perm = np.random.RandomState(seed).permutation(ug)
    c1, c2 = int(.7 * len(perm)), int(.85 * len(perm))
    part_of = {g: (0 if i < c1 else (1 if i < c2 else 2)) for i, g in enumerate(perm)}
    gi = np.array([part_of[gmap[paths[i]]] for i in z["img_idx"]])
    k = z["y"] >= 0
    return {n: k & (gi == v) for n, v in (("train", 0), ("val", 1), ("test", 2))}


def fit_eval(args):
    name, seed, cols, shared = args
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    G = _G
    z1, z2, gmap, ug, p1, p2 = G["z1"], G["z2"], G["gmap"], G["ug"], G["p1"], G["p2"]
    s1, s2 = split(z1, p1, seed, gmap, ug), split(z2, p2, seed, gmap, ug)
    X1, y1, X2, y2 = z1["X"][:, cols], z1["y"], z2["X"][:, cols], z2["y"]
    tr = s1["train"] if not shared else s2["train"]
    Xtr, ytr = (X1[tr], y1[tr]) if not shared else (X2[tr], y2[tr])
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=15, class_weight="balanced", random_state=0).fit(Xtr, ytr)
    out = {"name": name, "seed": seed, "trained_on": "degraded" if shared else "clean", "n_features": len(cols)}
    for tag, X, y, s, z, paths in (("clean_test", X1, y1, s1, z1, p1), ("degraded_test", X2, y2, s2, z2, p2)):
        te = s["test"]
        p = m.predict_proba(X[te])[:, 1]
        out[tag] = float(roc_auc_score(y[te], p))
        if name == "all features" and seed == 0 and not shared and tag == "clean_test":
            # bootstrap over source groups
            gt = np.array([gmap[paths[i]] for i in z["img_idx"][te]])
            ug_t = np.unique(gt)
            rng = np.random.RandomState(1)
            idx_by = {g: np.nonzero(gt == g)[0] for g in ug_t}
            aucs = []
            yt = y[te]
            for _ in range(200):
                pick = rng.choice(ug_t, len(ug_t))
                ii = np.concatenate([idx_by[g] for g in pick])
                if yt[ii].min() == yt[ii].max():
                    continue
                aucs.append(roc_auc_score(yt[ii], p[ii]))
            out["bootstrap_clean_test_auc_95"] = [float(np.quantile(aucs, .025)), float(np.quantile(aucs, .975))]
    return out


_G = {}


def init(feats, feats_shared):
    from tools.train_stfd import groups_from_hashes
    z1, z2 = dict(np.load(feats, allow_pickle=True)), dict(np.load(feats_shared, allow_pickle=True))
    p1, p2 = list(z1["paths"]), list(z2["paths"])
    grp1 = groups_from_hashes(z1["hashes"])
    _G.update(z1=z1, z2=z2, p1=p1, p2=p2, gmap=dict(zip(p1, grp1)), ug=np.unique(grp1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", required=True); ap.add_argument("--feats-shared", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    init(a.feats, a.feats_shared)
    allc = list(range(len(NAMES)))
    jobs = [("all features", s, allc, False) for s in range(5)]
    for fam in FAMILY_RAW:
        keep = [i for i in allc if i not in set(family_indices(fam))]
        jobs.append((f"without {fam}", 0, keep, False))
    rel_idx = [i for i, n in enumerate(NAMES) if n.startswith(("z_img_", "z_line_")) or n in FAMILY_RAW["line context"]]
    jobs.append(("no comparison with neighbours (raw and geometry only)", 0, [i for i in allc if i not in set(rel_idx)], False))
    jobs.append(("comparison with neighbours only", 0, rel_idx, False))
    jobs.append(("all features", 0, allc, True))
    jobs.append(("no comparison with neighbours (raw and geometry only)", 0, [i for i in allc if i not in set(rel_idx)], True))
    t0 = time.time()
    with ProcessPoolExecutor(a.workers, initializer=init, initargs=(a.feats, a.feats_shared)) as ex:
        res = list(ex.map(fit_eval, jobs))
    json.dump(res, open(a.out, "w"), indent=1)
    print(f"{len(jobs)} fits in {time.time() - t0:.0f}s")
    full = [r for r in res if r["name"] == "all features" and r["trained_on"] == "clean"]
    cs = [r["clean_test"] for r in full]
    ds = [r["degraded_test"] for r in full]
    print(f"all features, clean-trained, 5 grouped splits: clean-test word AUC mean {np.mean(cs):.3f} sd {np.std(cs, ddof=1):.3f} (min {min(cs):.3f}, max {max(cs):.3f}); degraded-test mean {np.mean(ds):.3f} sd {np.std(ds, ddof=1):.3f}")
    b = next((r for r in full if "bootstrap_clean_test_auc_95" in r), None)
    if b:
        print("bootstrap over source groups, seed 0, clean test AUC 95% interval:", [round(x, 3) for x in b["bootstrap_clean_test_auc_95"]])
    print("\nablation (seed 0, trained on clean images): clean-test AUC, degraded-test AUC")
    base = next(r for r in full if r["seed"] == 0)
    for r in res:
        if r["seed"] == 0 and r["trained_on"] == "clean":
            print(f"  {r['name']:62s} features={r['n_features']:3d} clean {r['clean_test']:.3f} ({r['clean_test'] - base['clean_test']:+.3f}) degraded {r['degraded_test']:.3f}")
    print("\ntrained on degraded images (seed 0):")
    for r in res:
        if r["trained_on"] == "degraded":
            print(f"  {r['name']:62s} clean {r['clean_test']:.3f} degraded {r['degraded_test']:.3f}")
    # random-choice baseline
    z1 = _G["z1"]; y = z1["y"]
    lab = y >= 0
    print(f"\nrandom-word baseline: {int((y == 1).sum())} of {int(lab.sum())} labelled words are edited words ({(y == 1).sum() / lab.sum():.3%}); "
          f"per image, a random measurable word is an edited word with probability averaging "
          f"{np.mean([ (y[z1['img_idx'] == i] == 1).mean() for i in np.unique(z1['img_idx']) if (z1['img_idx'] == i).sum() > 0]):.3%}")


if __name__ == "__main__":
    main()
