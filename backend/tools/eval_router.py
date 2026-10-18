"""Measure the type routers on labelled REAL screenshots and write model_data/router_gate.json.

  python tools/eval_router.py --real-dir DIR --real-labels tools/real_labels.json [--write-gate]

DIR holds the genuine screenshots whose sanitised file names are keys (folder/basename) in the labels file (the keys
use the owner's category folder, which the 'authentic' staging directory prefixes to each name with '__').
The router is declared validated only with at least MIN_N labelled real screenshots and fused accuracy >= MIN_ACC
on the ones it is confident about, and a wrong-confident rate <= MAX_WRONG.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import textforensics as tf  # noqa: E402
from screencheck import router as R  # noqa: E402
from screencheck.common import TYPES, wilson  # noqa: E402

MIN_N, MIN_ACC, MAX_WRONG = 60, 0.85, 0.05


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real-dir", required=True)
    ap.add_argument("--real-labels", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_labels.json"))
    ap.add_argument("--write-gate", action="store_true")
    a = ap.parse_args()
    labels = json.load(open(a.real_labels))["labels"]
    rows = []
    for p in sorted(glob.glob(os.path.join(a.real_dir, "*"))):
        parts = os.path.basename(p).split("__")
        key = parts[0] + "/" + parts[-1]
        if key not in labels:
            key = os.path.basename(p)      # plain file names work too
        if key not in labels:
            continue
        img = Image.open(p).convert("RGB")
        words = tf.ocr_words(img)
        r = R.route(np.asarray(img), words)
        rows.append((labels[key], r))
    n = len(rows)
    print(f"{n} labelled real screenshots")
    conf = defaultdict(Counter)
    for t, r in rows:
        conf[t][r["type"]] += 1
    print("\ntruth -> fused router output (type counts)")
    for t in TYPES:
        if conf[t]:
            print(f"  {t:16s}", dict(conf[t]))
    for name, key in (("content router A", lambda r: r["content"]["type"]), ("structure router B", lambda r: r["structure"]["type"]),
                      ("fused", lambda r: None if r["type"] == "unknown" else r["type"])):
        out = [(t, key(r)) for t, r in rows]
        ans = [(t, p) for t, p in out if p is not None]
        acc = np.mean([t == p for t, p in ans]) if ans else 0.0
        print(f"{name:20s} answered {len(ans)}/{n}, accuracy when answered {acc:.2f}")
    def stats(sel):
        out = [(tr, sel(r)) for tr, r in rows]
        ans = [(tr, p) for tr, p in out if p is not None]
        correct = sum(tr == p for tr, p in ans)
        acc = correct / len(ans) if ans else 0.0
        wrong = (len(ans) - correct) / max(1, n)
        ok = n >= MIN_N and len(ans) >= 0.5 * n and acc >= MIN_ACC and wrong <= MAX_WRONG
        lo, hi = wilson(correct, len(ans))
        return {"validated": bool(ok), "n": n, "answered": len(ans), "accuracy": round(acc, 3), "accuracy_interval": [round(lo, 3), round(hi, 3)],
                "wrong_answer_rate": round(wrong, 3),
                "reason": None if ok else f"needs n >= {MIN_N}, answers on at least half, accuracy >= {MIN_ACC}, wrong-answer rate <= {MAX_WRONG}; got n={n}, answered {len(ans)}, accuracy {acc:.2f}"}
    gate = {"content": stats(lambda r: r["content"]["type"]), "structure": stats(lambda r: r["structure"]["type"])}
    print("\ngate:", json.dumps(gate, indent=1))
    if a.write_gate:
        out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_data", "router_gate.json")
        json.dump(gate, open(out, "w"), indent=1)
        print("wrote", out)


if __name__ == "__main__":
    main()
