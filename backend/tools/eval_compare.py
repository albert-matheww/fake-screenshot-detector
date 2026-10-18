"""Evaluate compare mode: do real edits show up, and do harmless re-saves stay quiet?

  python tools/eval_compare.py --pairs pairs.json
pairs.json: [["original path", "edited path"], ...]. Controls re-save each original as JPEG q80, JPEG q60 and
down-scaled 0.75 + JPEG q85; none of those should produce marked regions.
"""
import argparse
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screencheck.compare import compare_bytes  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    a = ap.parse_args()
    pairs = json.load(open(a.pairs))
    found = 0
    for o, e in pairs:
        r = compare_bytes(open(o, "rb").read(), open(e, "rb").read())
        ok = r["status"] == "differences_found"
        found += ok
        print(f"edit     {os.path.basename(e):14s} {r['status']:18s} regions={len(r.get('regions', [])):2d} text_changes={len(r.get('text_changes', [])):2d}")
    print(f"edits with differences found: {found} of {len(pairs)}")
    bad = tot = 0
    for o, _ in pairs:
        raw = open(o, "rb").read()
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        for name, tf, q in (("jpeg q80", lambda x: x, 80), ("jpeg q60", lambda x: x, 60),
                            ("scale .75 + jpeg q85", lambda x: x.resize((int(x.width * .75), int(x.height * .75)), Image.BILINEAR), 85)):
            b = io.BytesIO()
            tf(im).save(b, "JPEG", quality=q)
            r = compare_bytes(raw, b.getvalue())
            tot += 1
            flag = r["status"] != "no_difference"
            bad += flag
            if flag:
                print(f"control  {os.path.basename(o):14s} {name:20s} {r['status']} regions={len(r['regions'])} area%={r['changed_area_percent']}")
    print(f"harmless re-saves wrongly flagged: {bad} of {tot}")


if __name__ == "__main__":
    main()
