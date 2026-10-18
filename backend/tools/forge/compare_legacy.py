"""Score the legacy v1 pipeline and the current model on the same test images (reproduces the v1-vs-v2 table).
   python tools/forge/compare_legacy.py --data ../data/forge_v5 --n 400"""
import argparse, os, sys
import numpy as np
from sklearn.metrics import roc_auc_score
HERE = os.path.dirname(os.path.abspath(__file__)); BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND); sys.path.insert(0, HERE)
import joblib, json  # noqa: E402
import train_text_model as T  # noqa: E402
from legacy.config import Config  # noqa: E402
from legacy.forensic import analyze_image_bytes  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--n", type=int, default=400)
a = ap.parse_args()
model = joblib.load(os.path.join(BACKEND, "model_data", "word_gbm.joblib"))
thr = json.load(open(os.path.join(BACKEND, "model_data", "word_gbm_meta.json")))["thresholds"]
test = T.load(a.data, "test")
rng = np.random.default_rng(0)
sub = [test[i] for i in rng.choice(len(test), min(a.n, len(test)), replace=False)]
def path(r): return r["path"] if os.path.isabs(r["path"]) else os.path.join(a.data, r["path"])
old = [analyze_image_bytes(open(path(r), "rb").read(), Config) for r in sub]
y = T.edit_labels(sub)
old_s = np.array([o["fake_score"] for o in old]); old_f = np.array([o["is_fake"] for o in old])
new_s = T.image_scores(model, sub)
print(f"n={len(sub)} ({int(y.sum())} edited)")
print(f"legacy v1: AUC {roc_auc_score(y, old_s):.3f}   flagged-fake rate on AUTHENTIC {old_f[y==0].mean():.3f}   on EDITED {old_f[y==1].mean():.3f}")
for k, t in thr.items():
    f = new_s >= t
    print(f"v2 @ {k:>3} target: AUC {roc_auc_score(y, new_s):.3f}   flagged rate on AUTHENTIC {f[y==0].mean():.3f}   on EDITED {f[y==1].mean():.3f}")
