"""Calibrate the gates: measure each check's false-alarm rate on GENUINE real screenshots.

  python tools/calibrate_gates.py --real-dir DIR --real-labels tools/real_labels.json [--write]

A check becomes "live" (allowed to move the verdict) only if it was applicable on at least MIN_GENUINE genuine real
screenshots and the Wilson 95% upper bound of its false-alarm rate is at most MAX_UPPER95. Type-specific checks are
calibrated on the screenshots of their own type (taken from the labels). The output lists what is missing.
"""
import argparse
import glob
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screencheck import checks, pipeline  # noqa: E402
from screencheck.common import wilson  # noqa: E402
from screencheck.gates import GATE_FILE, MAX_UPPER95, MIN_GENUINE, decide  # noqa: E402


def flagged(res):
    return res["status"] == "finding" and res["severity"] in ("medium", "high")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real-dir", required=True)
    ap.add_argument("--real-labels", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_labels.json"))
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    labels = json.load(open(a.real_labels))["labels"]
    stats = defaultdict(lambda: {"n": 0, "flagged": 0, "na": 0, "low": 0})
    count_by_type = defaultdict(int)
    for p in sorted(glob.glob(os.path.join(a.real_dir, "*"))):
        parts = os.path.basename(p).split("__")
        key = parts[0] + "/" + parts[-1]
        if key not in labels:
            key = os.path.basename(p)      # plain file names work too
        if key not in labels:
            continue
        typ = labels[key]
        count_by_type[typ] += 1
        ctx = pipeline.build_context(open(p, "rb").read())
        fns = list(checks.GENERIC) + ([checks.TYPED[typ]] if typ in checks.TYPED else [])
        for fn in fns:
            res = fn(ctx)
            s = stats[res["id"]]
            if res["status"] == "not_applicable":
                s["na"] += 1
                continue
            s["n"] += 1
            s["flagged"] += int(flagged(res))
            s["low"] += int(res["status"] == "finding" and not flagged(res))
    out = {"criteria": {"min_genuine": MIN_GENUINE, "max_upper95": MAX_UPPER95},
           "calibrated_on": time.strftime("%Y-%m-%d"), "genuine_by_type": dict(count_by_type), "checks": {}}
    for cid in checks.ALL_IDS:
        s = stats[cid]
        live, hi, why = decide(s["n"], s["flagged"])
        out["checks"][cid] = {"status": "live" if live else "advisory", "n": s["n"], "flagged": s["flagged"], "low_severity_findings": s["low"],
                              "not_applicable": s["na"], "upper95": round(hi, 3), "reason": why}
        print(f"{cid:28s} {'LIVE    ' if live else 'advisory'} n={s['n']:3d} flagged={s['flagged']:2d} upper95={hi:.2f}  {why or ''}")
    print("genuine screenshots by type:", dict(count_by_type))
    if a.write:
        json.dump(out, open(GATE_FILE, "w"), indent=1)
        print("wrote", GATE_FILE)


if __name__ == "__main__":
    main()
