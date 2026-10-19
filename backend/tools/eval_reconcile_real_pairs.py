"""Reconcile mode on REAL data: bank SMS texts against Google Pay transaction-list screenshots.

  python tools/eval_reconcile_real_pairs.py --pairs ../data/realset/sms_pairs.json --lists ../data/realset/new15

Every SMS is reconciled with every list screenshot. The truth (which list shows the payment, if any) was judged by eye and is stored
with the SMS texts. A pair is CORRECT if the status is corroborated exactly when the payment is in that list. Counts of how many
present payments are corroborated, how many absent ones are wrongly corroborated, and the status distribution are printed.
"""
import argparse, json, os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
import textforensics as tf
from screencheck import fields as F, reconcile as R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True); ap.add_argument("--lists", required=True)
    a = ap.parse_args()
    sms = json.load(open(a.pairs))["sms"]
    lists = sorted(f for f in os.listdir(a.lists) if f.startswith("payment_gpay_list"))
    shots = {}
    for f in lists:
        im = Image.open(os.path.join(a.lists, f)).convert("RGB")
        shots[f] = F.extract_consensus(im, tf.ocr_words(im))
    present, absent = [], []
    rows = []
    for s in sms:
        for f in lists:
            st = R.reconcile(shots[f], s["text"])["status"]
            is_present = (s["present_in"] == f)
            (present if is_present else absent).append((s["id"], f, st))
            rows.append((s["id"], f, is_present, st))
    print(f"{len(sms)} SMS texts x {len(lists)} list screenshots = {len(rows)} pairs; {len(present)} true pairs, {len(absent)} pairs where the payment is not in that list")
    print("true pairs  (payment IS in the list):", dict(Counter(st for _, _, st in present)))
    print("other pairs (payment is NOT in the list):", dict(Counter(st for _, _, st in absent)))
    print("true pairs corroborated:", sum(st == "corroborated" for _, _, st in present), "of", len(present),
          "| false corroborations among other pairs:", sum(st == "corroborated" for _, _, st in absent), "of", len(absent),
          "| false conflicts among other pairs:", sum(st == "conflict" for _, _, st in absent))
    print("\nper true pair:")
    for i, f, st in present:
        print(f"  {i:18s} {f:26s} {st}")


if __name__ == "__main__":
    main()
