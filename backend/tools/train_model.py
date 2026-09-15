"""Trains the RandomForest classifier bundled at backend/model_data/.

Combines multiple real, labeled image-forgery datasets so the model
generalizes beyond one narrow document type (the original version of this
script trained on receipts alone). Each dataset contributes a different kind
of forgery/content domain:

  --findit2 PATH   "Find it again!" receipt-forgery dataset (ICDAR 2023, L3i
                    lab, Univ. of La Rochelle) — 988 scanned receipts, 163
                    forged (copy-paste, text imitation, deletion, pixel
                    edits). Ships its own train/val/test CSV split, which is
                    used as-is. https://l3i-share.univ-lr.fr/2023Finditagain/

  --casia2 PATH     CASIA v2.0 tampering dataset — 12,614 general photos
                    (animals, architecture, nature, indoor scenes, textures,
                    documents...), 5,123 spliced/copy-moved. The classic
                    classical-forensics benchmark; broadens training beyond
                    documents to arbitrary photographic content. No
                    pre-defined split, so one is created here (stratified,
                    seeded). Expects the extracted `CASIA2.0_revised/Au/` and
                    `CASIA2.0_revised/Tp/` layout.

  --imd2020 PATH    IMD2020 "real-life" manipulated-image set (Novozamsky et
                    al., WACVW 2020) — ~2,010 pairs of genuinely manipulated
                    images collected from the internet (i.e. real forgeries
                    made and shared by unknown people, not lab-generated)
                    alongside their authentic originals. Closest available
                    analogue to "someone faked a screenshot and posted it".
                    No pre-defined split; created here. Expects each example
                    pair as a subdirectory containing one authentic and one
                    manipulated image.

  --synthetic PATH  Procedurally generated screenshot corpus (chat, bank,
                    payment, social, ecommerce categories) built by
                    tools/synthesize_dataset.py — see that file for why:
                    no public dataset of labeled real/fake *screenshots*
                    exists, so this fills that specific gap rather than
                    relying solely on document/photo forgery datasets from
                    adjacent domains. Reads the manifest.csv that tool
                    writes; run it first if PATH doesn't have one yet. No
                    pre-defined split; created here, per category, so every
                    category is represented proportionally.

Any subset of the four flags may be given; each dataset that ships without
a pre-defined split is capped and split independently (see --casia-cap),
then all datasets' train/val/test portions are pooled before training so no
single dataset dominates the final split proportions.

This will:
  1. Build a combined manifest of (path, label, split, source_dataset).
  2. Run the real forensic pipeline (forensic.analyze_image_bytes) over
     every image, in parallel across CPU cores, to extract the same feature
     vector the served API produces.
  3. Train a RandomForestClassifier (class_weight="balanced") on the pooled
     train split.
  4. Report accuracy/precision/recall/F1 on val/test overall AND broken
     down per source dataset, so a regression on one domain (e.g. documents)
     hiding behind a good overall number is visible.
  5. Overwrite backend/model_data/rf_model.joblib and
     backend/model_data/rf_model_meta.json — model_loader.py picks this up
     automatically on the next process start. rf_model_meta.json also
     records the dataset composition and a human-readable model
     description, which model_loader.py surfaces as MODEL_NAME.

Usage (run inside the backend Docker image, or any environment with the
project's requirements installed):

    python3 tools/train_model.py \
        --findit2 /path/to/findit2 \
        --casia2 /path/to/CASIA2.0_revised \
        --imd2020 /path/to/IMD2020
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FEATURE_KEYS = ["ela_score", "ghost_score", "quant_score", "noise_score",
                "clone_score", "metadata_score", "text_score",
                # font_score/edge_score are here despite NOT being in
                # config.WEIGHTS (see that file) — same treatment as
                # ghost_score already got: let the RandomForest see them
                # and empirically learn their (possibly ~0) importance,
                # rather than a hand-set heuristic weight that can't be
                # justified for a cue calibration testing didn't validate.
                "font_score", "edge_score", "chrome_score", "arithmetic_score"]
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model_data")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


@dataclass
class Record:
    path: str
    label: int  # 1 = forged/tampered, 0 = authentic
    split: str  # "train" | "val" | "test"
    source: str


def _stratified_split(paths_by_label: dict, source: str, seed: int,
                       ratios=(0.7, 0.15, 0.15)) -> List[Record]:
    """Assigns each (label -> [paths]) group independently into
    train/val/test so both classes are represented in every split."""
    rng = random.Random(seed)
    records = []
    for label, paths in paths_by_label.items():
        paths = list(paths)
        rng.shuffle(paths)
        n = len(paths)
        n_train = int(n * ratios[0])
        n_val = int(n * ratios[1])
        for i, p in enumerate(paths):
            split = "train" if i < n_train else ("val" if i < n_train + n_val else "test")
            records.append(Record(p, label, split, source))
    return records


# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------

def load_findit2(data_dir: str) -> List[Record]:
    """Uses the dataset's own train.txt/val.txt/test.txt CSV split (columns
    `image`, `forged`) and matching train/ val/ test/ image folders."""
    records = []
    for split in ("train", "val", "test"):
        csv_path = os.path.join(data_dir, f"{split}.txt")
        img_dir = os.path.join(data_dir, split)
        if not os.path.exists(csv_path):
            print(f"  [findit2] WARNING: {csv_path} not found, skipping split")
            continue
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                path = os.path.join(img_dir, row["image"])
                if not os.path.exists(path):
                    continue
                label = 1 if row["forged"].strip() == "1" else 0
                records.append(Record(path, label, split, "findit2"))
    return records


def load_casia2(data_dir: str, cap_per_class: Optional[int], seed: int) -> List[Record]:
    """CASIA2.0_revised/Au/*  = authentic (label 0)
    CASIA2.0_revised/Tp/*    = tampered  (label 1)
    No official split, so one is created here (stratified, seeded)."""
    au_dir = os.path.join(data_dir, "Au")
    tp_dir = os.path.join(data_dir, "Tp")
    if not os.path.isdir(au_dir) or not os.path.isdir(tp_dir):
        raise FileNotFoundError(
            f"Expected {au_dir} and {tp_dir} (CASIA2.0_revised layout) — got data_dir={data_dir}")

    rng = random.Random(seed)

    def _list(d):
        files = [os.path.join(d, f) for f in os.listdir(d)
                 if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
        rng.shuffle(files)
        return files[:cap_per_class] if cap_per_class else files

    paths_by_label = {0: _list(au_dir), 1: _list(tp_dir)}
    print(f"  [casia2] authentic={len(paths_by_label[0])} tampered={len(paths_by_label[1])}"
          f"{f' (capped at {cap_per_class}/class)' if cap_per_class else ''}")
    return _stratified_split(paths_by_label, "casia2", seed)


def load_imd2020(data_dir: str, seed: int) -> List[Record]:
    """IMD2020 real-life set: each example is a subdirectory (named by the
    original Reddit post id, since this set is sourced from r/photoshopbattles-
    style "spot the edit" threads) containing:
      <dirname>_orig.<ext>   — the authentic original (exactly one)
      <hash>_0.<ext>         — one or more real-world manipulated versions
      <hash>_0_mask.png      — a diff mask per manipulated image (not a photo; skipped)
    No official split, so one is created here (stratified, seeded)."""
    paths_by_label = {0: [], 1: []}

    for root, _dirs, files in os.walk(data_dir):
        for f in files:
            if os.path.splitext(f)[1].lower() not in IMAGE_EXTS:
                continue
            stem = os.path.splitext(f)[0]
            if stem.endswith("_mask"):
                continue
            label = 0 if stem.endswith("_orig") else 1
            paths_by_label[label].append(os.path.join(root, f))

    print(f"  [imd2020] authentic={len(paths_by_label[0])} manipulated={len(paths_by_label[1])}")
    return _stratified_split(paths_by_label, "imd2020", seed)


def load_synthetic(data_dir: str, seed: int) -> List[Record]:
    """Reads the manifest.csv produced by tools/synthesize_dataset.py —
    procedurally generated chat/bank/payment/social/ecommerce screenshots,
    the one category of training data no public dataset provides (see that
    file's docstring). No pre-defined split; one is created here per
    (category, label) rather than per label alone, so every category is
    represented proportionally in train/val/test instead of a numerically
    larger category dominating the split."""
    manifest_path = os.path.join(data_dir, "manifest.csv")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"Expected {manifest_path} — run tools/synthesize_dataset.py --out {data_dir} first")

    by_category = defaultdict(lambda: defaultdict(list))
    with open(manifest_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            by_category[row["category"]][int(row["label"])].append(row["path"])

    records: List[Record] = []
    for category, paths_by_label in sorted(by_category.items()):
        records += _stratified_split(paths_by_label, f"synthetic:{category}", seed)

    n_forged = sum(r.label for r in records)
    print(f"  [synthetic] {len(records)} images across {len(by_category)} categories "
          f"({n_forged} tampered)")
    return records


# ---------------------------------------------------------------------------
# Feature extraction (parallel)
# ---------------------------------------------------------------------------

def _extract_one(path: str):
    # Imported inside the worker so each process pool member does its own
    # import (config/forensic pull in PIL/numpy; cheaper than pickling them).
    from config import Config
    from forensic import analyze_image_bytes
    try:
        with open(path, "rb") as f:
            raw = f.read()
        result = analyze_image_bytes(raw, Config)
        return path, [result["features"].get(k, 0.0) for k in FEATURE_KEYS], None
    except Exception as exc:  # corrupt/unreadable images shouldn't kill the run
        return path, None, str(exc)


def extract_features(records: List[Record], workers: int) -> List[Record]:
    """Extracts feature vectors for every record in parallel, attaching them
    in-place, and dropping records that failed to load/analyze."""
    ok_records = []
    total = len(records)
    by_path = {r.path: r for r in records}
    start = time.time()
    done = 0
    errors = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_extract_one, r.path) for r in records]
        for fut in as_completed(futures):
            path, features, error = fut.result()
            done += 1
            if error is not None:
                errors += 1
            else:
                rec = by_path[path]
                rec.features = features
                ok_records.append(rec)
            if done % 200 == 0 or done == total:
                elapsed = time.time() - start
                rate = done / elapsed if elapsed else 0.0
                print(f"  extracted {done}/{total} ({errors} errors) "
                      f"— {rate:.1f} img/s, ~{(total - done) / rate if rate else 0:.0f}s left")
    return ok_records


# ---------------------------------------------------------------------------
# Reporting / training
# ---------------------------------------------------------------------------

def _to_xy(records: List[Record]):
    X = np.array([r.features for r in records])
    y = np.array([r.label for r in records])
    return X, y


def report(name, model, records: List[Record]):
    if not records:
        print(f"  {name}: (no records)")
        return
    X, y = _to_xy(records)
    pred = model.predict(X)
    print(f"  {name}: n={len(y)} accuracy={accuracy_score(y, pred):.4f} "
          f"precision={precision_score(y, pred, zero_division=0):.4f} "
          f"recall={recall_score(y, pred, zero_division=0):.4f} "
          f"f1={f1_score(y, pred, zero_division=0):.4f} "
          f"confusion_matrix={confusion_matrix(y, pred).tolist()}")

    by_source = defaultdict(list)
    for r in records:
        by_source[r.source].append(r)
    if len(by_source) > 1:
        for source, recs in sorted(by_source.items()):
            Xs, ys = _to_xy(recs)
            preds = model.predict(Xs)
            print(f"    {source}: n={len(ys)} "
                  f"accuracy={accuracy_score(ys, preds):.4f} "
                  f"precision={precision_score(ys, preds, zero_division=0):.4f} "
                  f"recall={recall_score(ys, preds, zero_division=0):.4f} "
                  f"f1={f1_score(ys, preds, zero_division=0):.4f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--findit2", help="Path to extracted findit2 dataset directory")
    parser.add_argument("--casia2", help="Path to extracted CASIA2.0_revised directory")
    parser.add_argument("--imd2020", help="Path to extracted IMD2020 real-life directory")
    parser.add_argument("--synthetic", help="Path to a corpus generated by tools/synthesize_dataset.py "
                                             "(directory containing manifest.csv)")
    parser.add_argument("--casia-cap", type=int, default=1500,
                         help="Max images per class sampled from CASIA v2 (default 1500/class, "
                              "since it's much larger than the other datasets). 0 = no cap.")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4,
                         help="Parallel worker processes for feature extraction")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model-dir", default=MODEL_DIR,
                         help="Output directory for rf_model.joblib/rf_model_meta.json (default: "
                              "backend/model_data/, i.e. the bundled production model). Override this "
                              "for a test/demo run — e.g. a synthetic-only retrain — so it doesn't "
                              "overwrite the real model, which was trained on real labeled data.")
    args = parser.parse_args()

    if not any([args.findit2, args.casia2, args.imd2020, args.synthetic]):
        parser.error("pass at least one of --findit2 / --casia2 / --imd2020 / --synthetic")

    records: List[Record] = []
    dataset_names = []

    if args.findit2:
        print("Loading findit2...")
        recs = load_findit2(args.findit2)
        print(f"  [findit2] {len(recs)} images")
        records += recs
        dataset_names.append("findit2")

    if args.casia2:
        print("Loading casia2...")
        cap = args.casia_cap or None
        recs = load_casia2(args.casia2, cap, args.seed)
        records += recs
        dataset_names.append("casia2")

    if args.imd2020:
        print("Loading imd2020...")
        recs = load_imd2020(args.imd2020, args.seed)
        records += recs
        dataset_names.append("imd2020")

    if args.synthetic:
        print("Loading synthetic...")
        recs = load_synthetic(args.synthetic, args.seed)
        records += recs
        dataset_names.append("synthetic")

    for r in records:
        r.features = None  # type: ignore[attr-defined]

    print(f"\nTotal manifest: {len(records)} images "
          f"({sum(1 for r in records if r.label == 1)} forged) across {dataset_names}")

    print("\nExtracting features (this is the slow part — parallel across "
          f"{args.workers} workers)...")
    records = extract_features(records, args.workers)

    train = [r for r in records if r.split == "train"]
    val = [r for r in records if r.split == "val"]
    test = [r for r in records if r.split == "test"]
    print(f"\ntrain n={len(train)} (forged={sum(r.label for r in train)}), "
          f"val n={len(val)} (forged={sum(r.label for r in val)}), "
          f"test n={len(test)} (forged={sum(r.label for r in test)})")

    X_train, y_train = _to_xy(train)

    print("\nTraining RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=300, class_weight="balanced", max_depth=6, random_state=0)
    model.fit(X_train, y_train)

    print("\nResults:")
    report("train", model, train)
    report("val", model, val)
    report("test", model, test)
    print("\nFeature importances:", dict(zip(FEATURE_KEYS, model.feature_importances_.round(4).tolist())))

    os.makedirs(args.model_dir, exist_ok=True)
    joblib.dump(model, os.path.join(args.model_dir, "rf_model.joblib"))

    # Keyed off each record's actual `source` rather than `dataset_names`:
    # synthetic images carry a per-category source ("synthetic:chat", etc.,
    # see load_synthetic) so a category breakdown falls out of this for free
    # instead of collapsing to one "synthetic" bucket.
    composition = {}
    for source in sorted(set(r.source for r in records)):
        composition[source] = {
            "total": sum(1 for r in records if r.source == source),
            "forged": sum(1 for r in records if r.source == source and r.label == 1),
        }
    description = (
        "randomforest-v2 (trained on " + " + ".join(dataset_names) +
        " — see README's 'Trained model' section for composition and caveats)"
    )
    with open(os.path.join(args.model_dir, "rf_model_meta.json"), "w") as f:
        json.dump({
            "feature_keys": FEATURE_KEYS,
            "model_description": description,
            "dataset_composition": composition,
            "casia_cap_per_class": args.casia_cap,
            "seed": args.seed,
        }, f, indent=2)
    print(f"\nSaved model to {args.model_dir}/rf_model.joblib")
    print(f"Dataset composition: {json.dumps(composition, indent=2)}")


if __name__ == "__main__":
    main()
