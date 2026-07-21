"""Trains the RandomForest classifier bundled at backend/model_data/.

Uses the "Find it again!" receipt-forgery dataset (ICDAR 2023, L3i lab,
University of La Rochelle — https://l3i-share.univ-lr.fr/2023Finditagain/),
built from the public SROIE receipt-OCR dataset with 163 of 988 receipts
carrying realistic forgeries (copy-paste, text imitation, deletion, pixel
edits) and ground-truth labels/annotations for each. This is real labeled
forgery data — unlike backend/tools/calibrate.py's self-generated synthetic
corpus — but it's scanned paper receipts, not chat/bank-statement
screenshots, so there is a real domain gap; see the README's "Known
limitations" for what that means in practice and why the high-confidence
override in model_loader.py still matters even with this model active.

Usage (run inside the backend Docker image, or any environment with the
project's requirements installed):

    python3 tools/train_model.py /path/to/findit2

where /path/to/findit2 is the extracted dataset directory containing
train.txt / val.txt / test.txt and train/ / val/ / test/ image folders (the
CSV format the "Find it again!" dataset ships with: columns include
`image` and `forged`, the latter used as the label here).

This will:
  1. Run the real forensic pipeline (forensic.analyze_image_bytes) over
     every image to extract the same feature vector the served API
     produces, for train/val/test splits.
  2. Train a RandomForestClassifier (class_weight="balanced", since forged
     examples are a ~16% minority) on the train split.
  3. Report accuracy/precision/recall/F1 on val and test splits, and print
     feature importances.
  4. Overwrite backend/model_data/rf_model.joblib and
     backend/model_data/rf_model_meta.json with the newly trained model —
     model_loader.py picks this up automatically on the next process start.

Adapting this to a different/better dataset later: keep the same CSV shape
(an `image` filename column + a 0/1 `forged`-style label column) and this
script needs no changes beyond pointing it at the new directory.
"""
import csv
import json
import os
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from forensic import analyze_image_bytes

FEATURE_KEYS = ["ela_score", "ghost_score", "quant_score", "noise_score",
                "clone_score", "metadata_score", "text_score"]
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model_data")


def extract_split(data_dir: str, split: str):
    csv_path = os.path.join(data_dir, f"{split}.txt")
    img_dir = os.path.join(data_dir, split)
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)

    features, labels = [], []
    for i, row in enumerate(rows):
        path = os.path.join(img_dir, row["image"])
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            raw = f.read()
        result = analyze_image_bytes(raw, Config)
        features.append([result["features"].get(k, 0.0) for k in FEATURE_KEYS])
        labels.append(1 if row["forged"].strip() == "1" else 0)
        if (i + 1) % 100 == 0:
            print(f"  {split}: {i + 1}/{len(rows)}")
    return np.array(features), np.array(labels)


def report(name, model, X, y):
    pred = model.predict(X)
    print(f"  {name}: accuracy={accuracy_score(y, pred):.4f} "
          f"precision={precision_score(y, pred, zero_division=0):.4f} "
          f"recall={recall_score(y, pred, zero_division=0):.4f} "
          f"f1={f1_score(y, pred, zero_division=0):.4f} "
          f"confusion_matrix={confusion_matrix(y, pred).tolist()}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    data_dir = sys.argv[1]

    print("Extracting features...")
    X_train, y_train = extract_split(data_dir, "train")
    X_val, y_val = extract_split(data_dir, "val")
    X_test, y_test = extract_split(data_dir, "test")

    print(f"\ntrain n={len(y_train)} (forged={y_train.sum()}), "
          f"val n={len(y_val)} (forged={y_val.sum()}), "
          f"test n={len(y_test)} (forged={y_test.sum()})")

    print("\nTraining RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=300, class_weight="balanced", max_depth=6, random_state=0)
    model.fit(X_train, y_train)

    print("\nResults:")
    report("train", model, X_train, y_train)
    report("val", model, X_val, y_val)
    report("test", model, X_test, y_test)
    print("\nFeature importances:", dict(zip(FEATURE_KEYS, model.feature_importances_.round(4).tolist())))

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODEL_DIR, "rf_model.joblib"))
    with open(os.path.join(MODEL_DIR, "rf_model_meta.json"), "w") as f:
        json.dump({"feature_keys": FEATURE_KEYS}, f, indent=2)
    print(f"\nSaved model to {MODEL_DIR}/rf_model.joblib")


if __name__ == "__main__":
    main()
