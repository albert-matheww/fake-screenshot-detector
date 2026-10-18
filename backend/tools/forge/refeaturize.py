"""Recompute word features for an existing ScreenForge corpus WITHOUT re-running OCR.

Feature engineering changes (textforensics.py) only need pixels + the saved OCR boxes, so
this is several times faster than rebuilding. Output goes to a new directory whose `img/`
is a symlink to the source corpus.

  python tools/forge/refeaturize.py --src data/forge_v1 --dst data/forge_v2
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor

os.environ.setdefault("OMP_THREAD_LIMIT", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402


def one(args):
    src, rec = args
    import textforensics as tf
    from build_dataset import word_labels
    img = Image.open(os.path.join(src, rec["path"])).convert("RGB")
    words = [{"text": t, "left": l, "top": tp, "width": w, "height": h, "conf": c, "line": ""}
             for (t, l, tp, w, h, c) in rec["words"]]
    X, kept, info = tf.image_word_features(img, words)
    r = dict(rec)
    r["X"] = X.astype(np.float32)
    r["y"] = word_labels(kept, rec["boxes"])
    r["words"] = [(w["text"], w["left"], w["top"], w["width"], w["height"], w["conf"]) for w in kept]
    r["info"] = info
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4) - 1))
    a = ap.parse_args()
    src, dst = os.path.abspath(a.src), os.path.abspath(a.dst)
    os.makedirs(dst, exist_ok=True)
    link = os.path.join(dst, "img")
    if not os.path.exists(link):
        os.symlink(os.path.join(src, "img"), link)
    for split in ("train", "val", "test"):
        recs = pickle.load(open(os.path.join(src, f"feat_{split}.pkl"), "rb"))
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            out = list(ex.map(one, [(src, r) for r in recs], chunksize=8))
        pickle.dump(out, open(os.path.join(dst, f"feat_{split}.pkl"), "wb"), protocol=4)
        print(split, len(out), flush=True)


if __name__ == "__main__":
    main()
