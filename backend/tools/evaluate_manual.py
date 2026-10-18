"""Evaluate the analyser on hand-collected, personally verified screenshots.

This is the validation that matters most: every other number in this repo comes from edits
we simulated. Collect two folders:

  authentic/   screenshots you took yourself and did not touch
  edited/      screenshots you really edited with a real tool (Preview, Photoshop, Figma,
               Canva, Paint, a phone photo editor...) - one edit per image is fine

  python tools/evaluate_manual.py --authentic-dir ~/eval/authentic --edited-dir ~/eval/edited [--json out.json]

Reports, per verdict tier, how many images of each kind landed there, the false-alarm rate on
authentic images, the detection rate on edited ones, and lists every miss/false alarm with its
reasons. Either folder may be omitted. Images never leave this machine.
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analysis import analyze_image_bytes  # noqa: E402

EXTS = (".png", ".jpg", ".jpeg", ".webp")
TIERS = ["evidence_of_editing", "suspicious", "no_evidence", "inconclusive"]


def run(folder):
    rows = []
    for p in sorted(glob.glob(os.path.join(os.path.expanduser(folder), "*"))):
        if not p.lower().endswith(EXTS):
            continue
        with open(p, "rb") as fh:
            r = analyze_image_bytes(fh.read())
        rows.append({"file": os.path.basename(p), "verdict": r["verdict"], "risk": r["risk_score"],
                     "reasons": r["reasons"][:3], "regions": [(g["text"], g["score"]) for g in r["regions"][:3]]})
    return rows


def summarize(name, rows):
    c = Counter(r["verdict"] for r in rows)
    print(f"\n{name}: n={len(rows)}")
    for t in TIERS:
        print(f"   {t:22s} {c.get(t, 0):4d}  ({c.get(t, 0) / max(1, len(rows)):.0%})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--authentic-dir")
    ap.add_argument("--edited-dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    if not (a.authentic_dir or a.edited_dir):
        ap.error("pass --authentic-dir and/or --edited-dir")
    out = {}
    if a.authentic_dir:
        rows = run(a.authentic_dir)
        out["authentic"] = rows
        summarize("AUTHENTIC screenshots", rows)
        flagged = [r for r in rows if r["verdict"] in ("evidence_of_editing", "suspicious")]
        hard = [r for r in rows if r["verdict"] == "evidence_of_editing"]
        print(f"   false-alarm rate: evidence-tier {len(hard) / max(1, len(rows)):.1%}, "
              f"evidence+suspicious {len(flagged) / max(1, len(rows)):.1%}")
        for r in flagged:
            print(f"   FALSE ALARM {r['file']}: {r['verdict']} risk={r['risk']} {r['reasons']}")
    if a.edited_dir:
        rows = run(a.edited_dir)
        out["edited"] = rows
        summarize("EDITED screenshots", rows)
        det = [r for r in rows if r["verdict"] in ("evidence_of_editing", "suspicious")]
        hard = [r for r in rows if r["verdict"] == "evidence_of_editing"]
        print(f"   detection rate: evidence-tier {len(hard) / max(1, len(rows)):.1%}, "
              f"evidence+suspicious {len(det) / max(1, len(rows)):.1%}")
        for r in rows:
            if r["verdict"] in ("no_evidence", "inconclusive"):
                print(f"   MISSED {r['file']}: {r['verdict']} risk={r['risk']}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
