"""Score a saved model on a held-out corpus (e.g. edits rendered by a different text engine).
   python tools/forge/eval_ood.py --data ../data/forge_ood"""
import argparse, json, os, sys
import joblib, numpy as np
from sklearn.metrics import roc_auc_score
HERE = os.path.dirname(os.path.abspath(__file__)); BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND); sys.path.insert(0, HERE)
import train_text_model as T  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True)
ap.add_argument("--model-dir", default=os.path.join(BACKEND, "model_data")); a = ap.parse_args()
model = joblib.load(os.path.join(a.model_dir, "word_gbm.joblib"))
thr = json.load(open(os.path.join(a.model_dir, "word_gbm_meta.json")))["thresholds"]
recs = T.load(a.data, "test")
def rep(name, rs):
    s, y = T.image_scores(model, rs), T.edit_labels(rs)
    line = f"{name:22s} n={len(rs):5d} edits={int(y.sum()):5d} AUC={roc_auc_score(y, s):.3f}"
    for k, t in thr.items():
        tpr, fpr = T.tpr_at_fpr(s, y, t); line += f"  TPR@{k}={tpr:.2f} (FPR {fpr:.3f})"
    print(line)
rep("ALL (Chrome-engine edits)", recs)
for src in ("real", "chrome", "pillow"):
    rep(f"  base={src}", [r for r in recs if r["source"] == src])
for d in ("png", "jpeg", "resize_png", "resize_jpeg"):
    a_ = [r for r in recs if r["label"] == 0 and r["meta"].get("degrade") == d]
    e_ = [r for r in recs if r["label"] == 1 and r["meta"].get("degrade") == d]
    if len(e_) > 10: rep(f"  degrade={d}", a_ + e_)
