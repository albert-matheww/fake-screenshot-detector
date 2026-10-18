"""Run the v3 pipeline on a stratified sample of STFD (tampered screenshots with pixel masks).

  python tools/eval_stfd.py --root data/stfd/extracted/STFD_ICASSP2023 --per-type 40 --out results.json

STFD has no genuine originals, so this measures only what the pipeline says about KNOWN edits (detection / abstention);
false alarms must be measured on genuine screenshots (tools/calibrate_gates.py).
"""
import argparse, json, os, sys, time, collections
from multiprocessing import Pool

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def work(args):
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    from screencheck.pipeline import analyze_bytes
    path, mpath = args
    raw = open(path, "rb").read()
    r = analyze_bytes(raw)
    mask = np.asarray(Image.open(mpath).convert("L")) > 127
    hit = False
    for g in r.get("regions", []):
        x, y, w, h = g["x"], g["y"], g["w"], g["h"]
        if mask[max(y, 0):y + h, max(x, 0):x + w].any():
            hit = True
    adv = {c["id"]: c["status"] for c in r.get("checks", [])}
    live_find = [c["id"] for c in r.get("checks", []) if c["status"] == "finding" and (c.get("gate") or {}).get("status") == "live"]
    adv_find = [c["id"] for c in r.get("checks", []) if c["status"] == "finding" and (c.get("gate") or {}).get("status") != "live"]
    return {"file": path, "verdict": r["verdict"], "type": (r.get("routing") or {}).get("type"), "live_findings": live_find,
            "advisory_findings": adv_find, "region_overlaps_mask": hit, "mask_frac": float(mask.mean()),
            "pixel_reliability": (r.get("capture") or {}).get("pixel_reliability")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--per-type", type=int, default=40)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    rng = np.random.RandomState(0)
    jobs = []
    for t in sorted(d for d in os.listdir(a.root) if d[:1].isdigit()):
        fs = sorted(os.listdir(os.path.join(a.root, t, "tamper")))
        for i in rng.permutation(len(fs))[: a.per_type]:
            jobs.append((os.path.join(a.root, t, "tamper", fs[i]), os.path.join(a.root, t, "masks", fs[i])))
    t0 = time.time()
    with Pool(a.workers) as p:
        res = p.map(work, jobs, chunksize=2)
    for r, (pth, _) in zip(res, jobs):
        r["edit_type"] = pth.split(os.sep)[-3]
    json.dump(res, open(a.out, "w"), indent=1)
    print(f"{len(res)} images in {time.time() - t0:.0f}s")
    by = collections.defaultdict(collections.Counter)
    for r in res:
        by[r["edit_type"]][r["verdict"]] += 1
        by[r["edit_type"]]["live_finding"] += bool(r["live_findings"])
        by[r["edit_type"]]["advisory_finding"] += bool(r["advisory_findings"])
        by[r["edit_type"]]["overlap"] += bool(r["region_overlaps_mask"])
    for t, c in by.items():
        print(t, dict(c))


if __name__ == "__main__":
    main()
