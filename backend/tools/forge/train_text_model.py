"""Train + evaluate the word-level text-edit classifier on a ScreenForge corpus.

  python tools/forge/train_text_model.py --data data/forge --model-dir model_data

Image score = max over words of P(edited). Operating thresholds are chosen on the
VALIDATION split's authentic images (target false-positive rates), then reported on
the TEST split, which uses unseen base images AND unseen edit fonts.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND)
import textforensics as tf  # noqa: E402

NEG_PER_IMAGE = 0  # 0 = use every word (hard negatives: the edited word's own neighbours)


def load(data: str, split: str) -> List[Dict[str, Any]]:
    with open(os.path.join(data, f"feat_{split}.pkl"), "rb") as fh:
        return pickle.load(fh)


def word_table(recs: List[Dict[str, Any]], neg_per_image: int, seed: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    Xs, ys = [], []
    for r in recs:
        X, y = r["X"], r["y"]
        if len(y) == 0 or X.shape[0] != len(y):
            continue
        pos = np.where(y == 1)[0]
        neg = np.where(y == 0)[0]
        if neg_per_image and len(neg) > neg_per_image:
            neg = rng.choice(neg, neg_per_image, replace=False)
        idx = np.concatenate([pos, neg]).astype(int)
        Xs.append(X[idx])
        ys.append(y[idx])
    return np.concatenate(Xs), np.concatenate(ys)


REAL_WEIGHT = 3.0   # genuine screenshots are the target domain and the scarcest data


def word_table_w(recs: List[Dict[str, Any]], neg_per_image: int = 0, seed: int = 0):
    """Like word_table but also returns per-word sample weights (real screenshots up-weighted)."""
    Xs, ys, ws = [], [], []
    for r in recs:
        X, y = r["X"], r["y"]
        if len(y) == 0 or X.shape[0] != len(y):
            continue
        keep = y >= 0
        Xs.append(X[keep])
        ys.append(y[keep])
        ws.append(np.full(int(keep.sum()), REAL_WEIGHT if r["source"] == "real" else 1.0))
    return np.concatenate(Xs), np.concatenate(ys), np.concatenate(ws)


def fit(X: np.ndarray, y: np.ndarray, seed: int = 0, sample_weight=None) -> HistGradientBoostingClassifier:
    m = HistGradientBoostingClassifier(
        max_iter=1500, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=40, l2_regularization=2.0,
        random_state=seed, early_stopping=True, validation_fraction=0.1,
        n_iter_no_change=25)
    m.fit(X, y, sample_weight=sample_weight)
    return m


def image_scores(model, recs: List[Dict[str, Any]]) -> np.ndarray:
    out = np.zeros(len(recs))
    for i, r in enumerate(recs):
        if len(r["y"]) == 0 or r["X"].shape[0] != len(r["y"]):
            out[i] = 0.0
        else:
            out[i] = float(model.predict_proba(r["X"])[:, 1].max())
    return out


def tpr_at_fpr(scores: np.ndarray, labels: np.ndarray, thr: float) -> Tuple[float, float]:
    pos, neg = scores[labels == 1], scores[labels == 0]
    return float((pos >= thr).mean()) if len(pos) else float("nan"), float((neg >= thr).mean()) if len(neg) else float("nan")


def thr_for_fpr(scores: np.ndarray, labels: np.ndarray, fpr: float) -> float:
    neg = np.sort(scores[labels == 0])
    if len(neg) == 0:
        return 0.5
    k = int(np.ceil((1 - fpr) * len(neg))) - 1
    return float(min(1.0, neg[min(max(k, 0), len(neg) - 1)] + 1e-6))


def edit_labels(recs):
    return np.array([r["label"] for r in recs])


def report(name: str, model, recs, thr: Dict[str, float], verbose=True) -> Dict[str, Any]:
    s, y = image_scores(model, recs), edit_labels(recs)
    out: Dict[str, Any] = {"n": len(recs), "n_edit": int(y.sum())}
    if len(set(y)) == 2:
        out["auc"] = float(roc_auc_score(y, s))
    for k, t in thr.items():
        tpr, fpr = tpr_at_fpr(s, y, t)
        out[f"tpr@{k}"], out[f"fpr@{k}"] = tpr, fpr
    if verbose:
        print(f"  {name:34s} n={out['n']:5d} edits={out['n_edit']:5d} AUC={out.get('auc', float('nan')):.3f} " +
              " ".join(f"TPR@{k}={out[f'tpr@{k}']:.2f}(FPR {out[f'fpr@{k}']:.3f})" for k in thr))
    return out


def breakdown(model, recs, thr, key_fn, title, min_n=15):
    print(title)
    groups = defaultdict(lambda: ([], []))
    for r in recs:
        g = key_fn(r)
        if g is not None:
            groups[g][r["label"]].append(r)
    auth_all = [r for r in recs if r["label"] == 0]
    res = {}
    for g, (auth_g, edits) in sorted(groups.items(), key=lambda kv: str(kv[0])):
        if len(edits) < min_n:
            continue
        auth = auth_g if len(auth_g) >= 20 else auth_all   # same-group authentic when the key applies to both
        res[str(g)] = report(f"{g}", model, auth + edits, thr)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model-dir", default=os.path.join(BACKEND, "model_data"))
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--calibrate-on", choices=["all", "real"], default="real",
                    help="which validation authentic images set the 1%%/5%% alert thresholds (default: genuine "
                         "real screenshots, the target domain and the hardest one)")
    ap.add_argument("--compare-old", action="store_true", help="score the legacy ELA/RF pipeline on the test images")
    args = ap.parse_args()

    train, val, test = (load(args.data, s) for s in ("train", "val", "test"))
    print(f"train {len(train)}  val {len(val)}  test {len(test)} samples")
    Xtr, ytr, wtr = word_table_w(train)
    print(f"train words: {len(ytr)} ({int(ytr.sum())} edited)")
    model = fit(Xtr, ytr, sample_weight=wtr)
    print(f"boosting iterations used: {model.n_iter_}")

    cal = [r for r in val if args.calibrate_on == "all" or r["source"] == "real"]
    vs, vy = image_scores(model, cal), edit_labels(cal)
    thr = {"1%": thr_for_fpr(vs, vy, 0.01), "5%": thr_for_fpr(vs, vy, 0.05)}
    print(f"thresholds (from {int((vy == 0).sum())} val authentic images, calibrate-on={args.calibrate_on}):",
          {k: round(v, 3) for k, v in thr.items()})

    print("\n== VALIDATION (seen fonts)")
    results: Dict[str, Any] = {"val": report("val all", model, val, thr)}
    print("\n== TEST (unseen base images AND unseen edit fonts)")
    results["test"] = report("test all", model, test, thr)
    results["test_by_source"] = breakdown(model, test, thr, lambda r: r["source"], "-- by base source (same-source authentic)")
    results["test_by_op"] = breakdown(model, test, thr, lambda r: r["meta"].get("op") if r["label"] else None,
                                      "-- by edit operation")
    results["test_by_degrade"] = breakdown(model, test, thr, lambda r: r["meta"].get("degrade"), "-- by re-share degradation (same-degradation authentic)")
    results["test_by_fill"] = breakdown(model, test, thr, lambda r: r["meta"].get("fill") if r["label"] else None,
                                        "-- by background fill")
    results["test_by_aa"] = breakdown(model, test, thr, lambda r: r["meta"].get("aa") if r["label"] else None,
                                      "-- by anti-aliasing of inserted text")

    # authentic-only false-positive picture by number of words (max over many words inflates FPR)
    auth = [r for r in test if r["label"] == 0]
    if auth:
        sc = image_scores(model, auth)
        nw = np.array([len(r["y"]) for r in auth])
        print("\n-- authentic test images: median max-word-prob %.3f, p95 %.3f; FPR by #words:" %
              (np.median(sc), np.percentile(sc, 95)))
        for lo, hi in [(0, 30), (30, 80), (80, 200), (200, 10**6)]:
            m = (nw >= lo) & (nw < hi)
            if m.sum():
                print(f"   words {lo:3d}-{hi if hi < 10**6 else 'inf':>3}: n={int(m.sum()):4d} "
                      f"FPR@1%={(sc[m] >= thr['1%']).mean():.3f}  FPR@5%={(sc[m] >= thr['5%']).mean():.3f}")

    # word-level
    Xv, yv = word_table(test, 0)
    keep = yv >= 0
    pw = model.predict_proba(Xv[keep])[:, 1]
    results["test_word"] = {"auc": float(roc_auc_score(yv[keep], pw)), "ap": float(average_precision_score(yv[keep], pw))}
    print(f"\nword-level (test, all words): AUC={results['test_word']['auc']:.3f} AP={results['test_word']['ap']:.3f}")

    if args.compare_old:
        import io
        from PIL import Image
        from legacy.config import Config
        from legacy.forensic import analyze_image_bytes
        sub = test[:: max(1, len(test) // 300)]
        old = np.array([analyze_image_bytes(open(os.path.join(args.data, r["path"]), "rb").read(), Config)["fake_score"]
                        for r in sub])
        lab = edit_labels(sub)
        results["old_pipeline_on_test_subset"] = {"n": len(sub), "auc": float(roc_auc_score(lab, old))}
        new_s = image_scores(model, sub)
        results["new_pipeline_on_same_subset"] = {"n": len(sub), "auc": float(roc_auc_score(lab, new_s))}
        print(f"\nlegacy ELA/RF pipeline AUC on {len(sub)} test images: {results['old_pipeline_on_test_subset']['auc']:.3f}"
              f"   |  new: {results['new_pipeline_on_same_subset']['auc']:.3f}")

    if not args.no_save:
        os.makedirs(args.model_dir, exist_ok=True)
        joblib.dump(model, os.path.join(args.model_dir, "word_gbm.joblib"))
        with open(os.path.join(args.model_dir, "word_gbm_meta.json"), "w") as fh:
            json.dump({"feature_names": tf.FEATURE_NAMES, "thresholds": thr, "metrics": results,
                       "train_words": int(len(ytr)), "train_images": len(train)}, fh, indent=1)
        print("saved", args.model_dir)


if __name__ == "__main__":
    main()
