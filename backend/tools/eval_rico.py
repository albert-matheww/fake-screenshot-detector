"""False alarms on GENUINE public app screens (Rico, CC-BY-4.0) for the STFD-trained word models and the live checks.

  python tools/eval_rico.py --parquet data/rico/test.parquet --n 300 --out results.json

Rico screens are genuine Android app screenshots from 2017 (JPEG, English mostly). They are NOT the project's target
screens (shared bank/payment/order screenshots), so this measures false alarms on a different genuine population.
"""
import argparse, io, json, os, sys, time
from multiprocessing import Pool

import joblib
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import textforensics as tf  # noqa: E402

MD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_data_stfd")
_M = {}


def work(raw):
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    if not _M:
        _M["A"] = joblib.load(os.path.join(MD, "word_stfd.joblib"))
        _M["C"] = joblib.load(os.path.join(MD, "word_stfd_mixed.joblib"))
        import analysis_model as am
        _M["S"] = am.MODEL
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    X, _, _ = tf.image_word_features(img)
    out = {"scorable": bool(X.shape[0] >= 6), "n_words": int(X.shape[0])}
    if out["scorable"]:
        for k, m in _M.items():
            if m is not None:
                out[k] = float(m.predict_proba(X)[:, 1].max())
    from screencheck.pipeline import analyze_bytes
    r = analyze_bytes(raw)
    out["live_findings"] = [c["id"] for c in r["checks"] if c["status"] == "finding" and (c.get("gate") or {}).get("status") == "live"]
    out["layout_grid"] = next((c["status"] for c in r["checks"] if c["id"] == "layout_grid"), None)
    out["verdict"] = r["verdict"]
    return out


def main():
    import pyarrow.parquet as pq
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True); ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    t = pq.read_table(a.parquet, columns=["image"])
    idx = np.random.RandomState(0).permutation(t.num_rows)[: a.n]
    raws = [t.column("image")[int(i)].as_py()["bytes"] for i in idx]
    t0 = time.time()
    with Pool(a.workers) as p:
        res = p.map(work, raws, chunksize=2)
    json.dump(res, open(a.out, "w"), indent=1)
    sc = [r for r in res if r["scorable"]]
    cm = json.load(open(os.path.join(MD, "compare.json")))
    print(f"{len(res)} genuine Rico screens, {len(sc)} scorable, {time.time() - t0:.0f}s")
    for key, name in (("A", "A clean only"), ("C", "C clean + shared")):
        for th_name, th in cm[name]["thresholds_from_shared_val"].items():
            n = sum(r[key] >= th for r in sc)
            print(f"model {key} threshold {th_name} ({th:.3f}): flags {n} of {len(sc)} genuine screens")
    import analysis_model as am
    if am.MODEL is not None:
        for th_name, th in (("THR_LO", am.THR_LO), ("THR_HI", am.THR_HI)):
            print(f"shipped model {th_name} ({th:.3f}): flags {sum(r['S'] >= th for r in sc)} of {len(sc)}")
    print("live-check findings:", sum(bool(r["live_findings"]) for r in res), "of", len(res),
          "| verdicts", {v: sum(r["verdict"] == v for r in res) for v in {r["verdict"] for r in res}},
          "| layout_grid applicable on", sum(r["layout_grid"] != "not_applicable" for r in res))


if __name__ == "__main__":
    main()
