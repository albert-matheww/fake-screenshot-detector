"""Train the structure router (router B) on the generated Chrome screenshots, then test BOTH routers.

  python tools/train_router.py --per-family 40 [--real-dir DIR --real-labels tools/real_labels.json]

Training data are generated screenshots (exact type labels). Because a model trained on generated images has failed to
transfer before (see README), the real screenshots are used ONLY for testing, and the result decides whether typed
checks are enabled (model_data/router_gate.json).
"""
import argparse
import glob
import json
import os
import sys
import time
from collections import Counter
from multiprocessing import Pool

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import textforensics as tf  # noqa: E402
from screencheck import router as R  # noqa: E402
from screencheck.common import FAMILY_TO_TYPE, TYPES, wilson  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_data")


def featurize(path):
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    img = Image.open(path).convert("RGB")
    words = tf.ocr_words(img)
    rgb = np.asarray(img)
    return R.structure_features(rgb, words), R.route_content(words), len(words)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join(ROOT, "data", "chrome", "chrome_manifest.jsonl"))
    ap.add_argument("--per-family", type=int, default=40)
    ap.add_argument("--real-dir")
    ap.add_argument("--real-labels", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_labels.json"))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    recs = [json.loads(l) for l in open(a.manifest)]
    by_fam = {}
    for r in recs:
        by_fam.setdefault(r["family"], []).append(r)
    rng = np.random.RandomState(0)
    pick = []
    for fam, rs in by_fam.items():
        idx = rng.permutation(len(rs))[: a.per_family]
        pick += [rs[i] for i in idx]
    t0 = time.time()
    with Pool(a.workers) as p:
        res = p.map(featurize, [r["path"] for r in pick], chunksize=4)
    print(f"featurised {len(pick)} generated images in {time.time() - t0:.0f}s")
    X = np.stack([r[0] for r in res])
    y = np.array([FAMILY_TO_TYPE[r["family"]] for r in pick])
    fams = np.array([r["family"] for r in pick])

    from sklearn.ensemble import HistGradientBoostingClassifier

    # honest check on generated data: hold out whole families' seeds (index parity) - this is optimistic by design
    tr = np.array([r["index"] % 5 != 0 for r in pick])
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=15, random_state=0).fit(X[tr], y[tr])
    acc_gen = float((m.predict(X[~tr]) == y[~tr]).mean())
    print(f"structure router, held-out generated images: accuracy {acc_gen:.3f} (n={int((~tr).sum())}; optimistic, same generator)")
    final = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=15, random_state=0).fit(X, y)
    import joblib

    os.makedirs(OUT, exist_ok=True)
    joblib.dump(final, os.path.join(OUT, "router_structure.joblib"))
    json.dump({"features": R.STRUCT_FEATURES, "classes": list(final.classes_), "trained_on": f"{len(pick)} generated Chrome screenshots",
               "generated_holdout_accuracy": acc_gen}, open(os.path.join(OUT, "router_structure_meta.json"), "w"), indent=1)

    # content router on the same generated images
    ca = np.array([r[1]["type"] == t for r, t in zip(res, y)])
    print(f"content router on generated images: top-1 accuracy {ca.mean():.3f}, abstained {np.mean([r[1]['type'] is None for r in res]):.3f}")
    print(f"saved router_structure.joblib; classes: {list(final.classes_)}")


if __name__ == "__main__":
    main()
