"""Leave-files-out evaluation on FULL-SIZE genuine screenshots.

For every genuine screenshot file, a model that never saw ANY window of that file (nor edits
derived from it) scores (a) the untouched full-size image and (b) K edited copies (realistic
edits from tools/forge/tamper.py using held-out fonts, with a random re-share degradation).
Thresholds follow the SHIPPED rule: calibrated on VALIDATION real-screenshot authentic windows
(files outside the held-out fold), and the model is trained on the TRAIN split only, so the
calibration data is never trained on. Reports the false-positive rate on genuine screenshots
(the number v1 failed: 20%) and the detection rate on edits. Aggregates only - no content.

  python tools/forge/eval_real_cv.py --data ../data/forge_v5 --real-glob "~/Desktop/Screenshot*.png" ... --folds 5
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import random
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

os.environ.setdefault("OMP_THREAD_LIMIT", "1")
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "tools"))
import textforensics as tf  # noqa: E402
import train_text_model as T  # noqa: E402
from forge import tamper  # noqa: E402


def fid(rec_id: str) -> str:
    return rec_id.split("w")[0]  # real<md5>w<k>_... -> real<md5>


def run_fold(job) -> List[Dict[str, Any]]:
    k, data, key, fold_of, edits_per_file, seed = job
    recs = []
    for s in ("train", "val"):
        recs += [dict(r, _split=s) for r in T.load(data, s)]
    held = {f for f, v in fold_of.items() if v == k}
    keep = [r for r in recs if not (r["source"] == "real" and fid(r["id"]) in held)]
    train = [r for r in keep if r["_split"] == "train"]                       # model sees TRAIN only
    cal = [r for r in keep if r["_split"] == "val" and r["source"] == "real"]  # thresholds from unseen real val
    X, y, w = T.word_table_w(train)
    model = T.fit(X, y, sample_weight=w)
    vs, vl = T.image_scores(model, cal), T.edit_labels(cal)
    thr = {"1%": T.thr_for_fpr(vs, vl, 0.01), "5%": T.thr_for_fpr(vs, vl, 0.05)}
    print(f"fold {k}: held-out files {len(held)}, thresholds {thr}", flush=True)
    rows = []
    for f in sorted(held):
        path = key.get(f)
        if not path:
            continue
        base = Image.open(path).convert("RGB")
        words = tf.ocr_words(base)

        def score(img: Image.Image) -> float:
            w_ = tf.ocr_words(img)
            Xi, kept, _ = tf.image_word_features(img, w_)
            return float(model.predict_proba(Xi)[:, 1].max()) if len(Xi) >= 3 else 0.0

        row = {"file": f, "auth": score(base), "edits": [], "thr": thr}
        frng = random.Random(seed * 7919 + int(f[4:], 16) % 100000)
        for _ in range(edits_per_file):
            res = tamper.edit_word(base, words, frng, [0], None)
            if res is None:
                continue
            raw, ext, _, dmeta = tamper.degrade(res["image"], [res["box"]], frng)
            row["edits"].append((score(Image.open(io.BytesIO(raw)).convert("RGB")), dmeta["degrade"], res["meta"]["op"]))
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--real-glob", action="append", default=[])
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--edits-per-file", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", help="write aggregated results here")
    args = ap.parse_args()

    files = []
    for pat in args.real_glob:
        files += sorted(glob.glob(os.path.expanduser(pat), recursive=True))
    key = {f"real{hashlib.md5(p.encode()).hexdigest()[:8]}": p for p in files}
    real_ids = sorted({fid(r["id"]) for s in ("train", "val", "test") for r in T.load(args.data, s) if r["source"] == "real"})
    rng = random.Random(args.seed)
    rng.shuffle(real_ids)
    fold_of = {f: i % args.folds for i, f in enumerate(real_ids)}
    print(f"{len(real_ids)} real files, {args.folds} folds (parallel)", flush=True)

    with ProcessPoolExecutor(max_workers=args.folds) as ex:
        per_file = [r for rows in ex.map(run_fold, [(k, args.data, key, fold_of, args.edits_per_file, args.seed)
                                                    for k in range(args.folds)]) for r in rows]

    auth = np.array([r["auth"] for r in per_file])
    out: Dict[str, Any] = {"n_files": len(auth)}
    print(f"\n== genuine full-size screenshots (never seen by the model that scored them): n={len(auth)}")
    for lab, name in (("5%", "suspicious"), ("1%", "evidence")):
        fp_n = int(sum(r["auth"] >= r["thr"][lab] for r in per_file))
        tp_all, n_all = 0, 0
        by = defaultdict(lambda: [0, 0])
        for r in per_file:
            for s, deg, op in r["edits"]:
                hit = s >= r["thr"][lab]
                tp_all += hit
                n_all += 1
                by[deg][0] += hit
                by[deg][1] += 1
        out[name] = {"fp": fp_n, "fpr": fp_n / len(auth), "tp": int(tp_all), "n_edits": n_all, "tpr": tp_all / max(1, n_all),
                     "by_degrade": {d: a / b for d, (a, b) in by.items()}}
        print(f"{name:10s} threshold {lab}: false-positive rate {fp_n / len(auth):.3f} ({fp_n}/{len(auth)})   "
              f"edit detection rate {tp_all / max(1, n_all):.3f} ({tp_all}/{n_all})   by degradation: "
              + ", ".join(f"{d} {a / b:.2f} (n={b})" for d, (a, b) in sorted(by.items())))
    pos = [s for r in per_file for s, _, _ in r["edits"]]
    from sklearn.metrics import roc_auc_score
    out["auc"] = float(roc_auc_score([1] * len(pos) + [0] * len(auth), pos + list(auth)))
    print(f"image-level AUC (edited vs genuine, full-size real screenshots): {out['auc']:.3f}")
    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)


if __name__ == "__main__":
    main()
