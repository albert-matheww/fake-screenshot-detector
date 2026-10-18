"""Build the ScreenForge corpus: authentic vs. realistically edited screenshots with
exact edit masks, plus word-level feature matrices ready for training.

Authentic base sources
  real    genuine screenshots taken on a real device (glob; cropped to random windows;
          NEVER committed - they stay on this machine)
  chrome  UI pages rendered by Chrome (tools/forge/render_chrome.py)
  pillow  UI renders from tools/synthesize_dataset.py using a random system font

Every base yields authentic samples (label 0) and edited samples (label 1). Both
classes go through the SAME random "re-share" degradation (PNG / JPEG q55-98 /
downscale), so compression is not a label shortcut.

Splits are by base image (hash), never by sample. The test split uses ONLY fonts from
hash-fold 0 for its edits; train/val edits never use fold 0 -> test fonts are unseen.

Usage:
  python tools/forge/build_dataset.py --out data/forge --real-glob "~/Desktop/**/Screenshot*.png" \
      --chrome-dir data/chrome --pillow 900 --workers 8
"""
from __future__ import annotations

import os as _os
_os.environ.setdefault('OMP_THREAD_LIMIT', '1')   # Tesseract spawns OpenMP threads; N workers x 4 threads thrash the CPU
import argparse
import glob
import hashlib
import io
import json
import os
import pickle
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "tools"))

TRAIN_FOLDS = [1, 2, 3, 4]
TEST_FOLDS = [0]


def split_of(key: str) -> str:
    h = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
    return "train" if h < 70 else ("val" if h < 85 else "test")


def _ov(word: Dict[str, Any], box) -> float:
    x0, y0 = max(word["left"], box[0]), max(word["top"], box[1])
    x1 = min(word["left"] + word["width"], box[2])
    y1 = min(word["top"] + word["height"], box[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / float(word["width"] * word["height"])


def word_labels(words, boxes) -> np.ndarray:
    y = np.zeros(len(words), np.int8)
    for i, w in enumerate(words):
        ov = max((_ov(w, b) for b in boxes), default=0.0)
        y[i] = 1 if ov >= 0.3 else (-1 if ov > 0.02 else 0)
    return y


# --------------------------------------------------------------------------- bases

def load_base(spec: Dict[str, Any], rng: random.Random) -> Image.Image:
    if spec["source"] == "real":
        im = Image.open(spec["path"]).convert("RGB")
        if spec.get("full"):
            return im   # whole screenshot: 300-500 words on a Retina capture, the case windows under-represent
        w, h = im.size
        cw, ch = min(w, rng.randint(700, 1500)), min(h, rng.randint(500, 1100))
        x0, y0 = rng.randint(0, w - cw), rng.randint(0, h - ch)
        return im.crop((x0, y0, x0 + cw, y0 + ch))
    if spec["source"] == "chrome":
        return Image.open(spec["path"]).convert("RGB")
    import synthesize_dataset as S
    from PIL import ImageFont
    from forge import tamper as T
    f = rng.choice(T.font_bank())
    S._font = lambda size, f=f: ImageFont.truetype(f["path"], size, index=f["index"])
    return S.RENDERERS[spec["category"]](rng).convert("RGB")


# --------------------------------------------------------------------------- worker

_DONORS: List[Any] = []
_BANK = None


def _bank(path):
    global _BANK
    if _BANK is None:
        import patchbank
        _BANK = patchbank.Bank(path)
    return _BANK


def work(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    import textforensics as tf
    from forge import tamper as T

    spec, split, out_dir = task["spec"], task["split"], task["out_dir"]
    rng = random.Random(task["seed"])
    folds = TEST_FOLDS if split == "test" else TRAIN_FOLDS
    try:
        base = load_base(spec, rng)
        words = tf.ocr_words(base)
    except Exception as e:  # noqa: BLE001
        return [{"error": f'{spec.get("path", spec.get("category"))}: {e}'}]
    if len(words) < 6:
        return []

    donors = _DONORS if len(_DONORS) >= 3 else None
    records = []
    plan = [("auth", 0)] * task["n_auth"] + [("edit", 1)] * task["n_edit"]
    for k, (kind, label) in enumerate(plan):
        boxes: List = []
        meta: Dict[str, Any] = {}
        img = base
        if kind == "edit":
            try:
                if task.get("bank_dir"):   # out-of-distribution edits: text rasterised by Chrome, not Pillow
                    import patchbank
                    res = patchbank.edit_with_bank(img, words, rng, _bank(task["bank_dir"]), test_fonts=(split == "test"))
                else:
                    res = T.edit_word(img, words, rng, folds, donors)
            except Exception:  # noqa: BLE001 - a rare geometry edge case must not kill a long build
                res = None
            if res is None:
                continue
            img, boxes, meta = res["image"], [res["box"]], dict(res["meta"])
            if rng.random() < 0.2:  # second edit elsewhere
                rest = [w for w in words if _ov(w, boxes[0]) == 0]
                res2 = T.edit_word(img, rest, rng, folds, donors)
                if res2 is not None:
                    img = res2["image"]
                    boxes.append(res2["box"])
                    meta["second_edit"] = res2["meta"]
        raw, ext, sboxes, dmeta = T.degrade(img, boxes, rng)
        meta.update(dmeta)
        sid = f'{spec["id"]}_{task["seed"] % 100000}_{k}'
        rel = os.path.join("img", split, f"{sid}.{ext}")
        os.makedirs(os.path.join(out_dir, "img", split), exist_ok=True)
        with open(os.path.join(out_dir, rel), "wb") as fh:
            fh.write(raw)
        final = Image.open(io.BytesIO(raw)).convert("RGB")
        fw = tf.ocr_words(final)
        X, kept, info = tf.image_word_features(final, fw)
        y = word_labels(kept, sboxes)
        records.append({
            "id": sid, "path": rel, "split": split, "source": spec["source"],
            "category": spec.get("category") or spec.get("family", ""), "label": label, "boxes": sboxes,
            "meta": meta, "size": final.size, "ext": ext, "info": info,
            "X": X.astype(np.float32), "y": y,
            "words": [(w["text"], w["left"], w["top"], w["width"], w["height"], w["conf"]) for w in kept],
        })
    # keep a few clean words as donors for splice edits (per worker process)
    if len(words) >= 10 and len(_DONORS) < 12:
        good = [w for w in words if w["conf"] >= 85 and 12 <= w["height"] <= 60 and w["width"] >= 20]
        if good:
            _DONORS.append((base, rng.choice(good)))
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--real-glob", action="append", default=[])
    ap.add_argument("--real-windows", type=int, default=3, help="random crop windows per real screenshot")
    ap.add_argument("--real-full", action="store_true", help="use whole real screenshots instead of random windows")
    ap.add_argument("--chrome-dir", help="dir containing chrome/*.png from render_chrome.py")
    ap.add_argument("--pillow", type=int, default=0, help="number of Pillow-rendered bases (spread over 10 categories)")
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4) - 1))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="debug: cap number of bases")
    ap.add_argument("--bank", help="patchbank dir: make every edit with a Chrome-rendered patch (OOD test family)")
    ap.add_argument("--only-split", choices=["train", "val", "test"], help="only build bases belonging to this split")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    tasks: List[Dict[str, Any]] = []
    n = 0

    def add(spec, auth, edit):
        nonlocal n
        n += 1
        split = split_of(spec["split_key"])
        if args.only_split and split != args.only_split:
            return
        tasks.append({"spec": spec, "split": split, "out_dir": out, "seed": args.seed * 1000003 + n,
                      "n_auth": auth, "n_edit": edit, "bank_dir": args.bank})

    for pat in args.real_glob:
        for p in sorted(glob.glob(os.path.expanduser(pat), recursive=True)):
            for wi in range(args.real_windows):
                add({"source": "real", "path": p, "id": f'real{hashlib.md5(p.encode()).hexdigest()[:8]}w{wi}',
                     "split_key": p, "full": args.real_full}, 1, 3)  # split by *file* so windows of one screenshot never straddle splits
    if args.chrome_dir:
        man = os.path.join(args.chrome_dir, "chrome_manifest.jsonl")
        for line in open(man):
            r = json.loads(line)
            add({"source": "chrome", "path": r["path"] if os.path.isabs(r["path"]) else
                 os.path.join(args.chrome_dir, r["path"]), "id": r["id"], "family": r["family"],
                 "split_key": r["id"]}, 1, 2)
    cats = ["chat", "bank", "payment", "social", "ecommerce", "email", "notification", "crypto", "sms", "trading"]
    for i in range(args.pillow):
        add({"source": "pillow", "category": cats[i % len(cats)], "id": f"pil{i:05d}", "split_key": f"pil{i}"}, 1, 2)
    if args.limit:
        random.Random(1).shuffle(tasks)
        tasks = tasks[: args.limit]
    print(f"{len(tasks)} bases -> ~{sum(t['n_auth'] + t['n_edit'] for t in tasks)} samples, workers={args.workers}",
          flush=True)

    recs: List[Dict[str, Any]] = []
    errors: List[str] = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, rs in enumerate(ex.map(work, tasks, chunksize=2)):
            for r in rs:
                if "error" in r:
                    errors.append(r["error"])
                else:
                    recs.append(r)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(tasks)} bases, {len(recs)} samples, {time.time() - t0:.0f}s", flush=True)
            if (i + 1) % 500 == 0:
                _dump(out, recs)   # checkpoint: a long build must never lose its features
    _dump(out, recs, verbose=True)
    print(f"done in {time.time() - t0:.0f}s; {len(errors)} base errors", errors[:3])


def _dump(out: str, recs: List[Dict[str, Any]], verbose: bool = False) -> None:
    for split in ("train", "val", "test"):
        part = [r for r in recs if r["split"] == split]
        with open(os.path.join(out, f"feat_{split}.pkl"), "wb") as fh:
            pickle.dump(part, fh, protocol=4)
        by = {}
        for r in part:
            k = (r["source"], r["label"])
            by[k] = by.get(k, 0) + 1
        if verbose:
            print(split, len(part), "samples;", {f"{a}/{'edit' if b else 'auth'}": c for (a, b), c in sorted(by.items())})


if __name__ == "__main__":
    main()
