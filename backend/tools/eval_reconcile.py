"""Mutation test of reconcile mode on real screenshots (no new data needed).

For each screenshot: build a 'second source' from its own facts (what a faithful bank SMS would say), check it is not reported
as a conflict (OCR noise must not create false conflicts); then change ONE fact in the source (a digit of the reference, the
amount, or the date) and check the change is noticed.

  python tools/eval_reconcile.py DIR [DIR ...]
"""
import glob, os, random, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screencheck import fields as F, pipeline, reconcile as R  # noqa: E402


def src_text(f, ref=None, amount=None, date=None):
    parts = []
    if amount is not None:
        parts.append(f"Rs {amount:,.2f}")
    if date:
        parts.append(f"on {date[8:10]}/{date[5:7]}/{date[:4]}")
    if ref:
        parts.append(f"Ref {ref}")
    return " ".join(parts)


def main():
    rng = random.Random(0)
    files = [p for d in sys.argv[1:] for p in sorted(glob.glob(os.path.join(d, "*"))) if p.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    faithful, mutated, usable = Counter(), Counter(), 0
    for p in files:
        ctx = pipeline.build_context(open(p, "rb").read())
        shot = F.extract_consensus(ctx["rgb_img"], ctx["words"])
        f = F.extract_words(ctx["words"])           # single read: the 'sender' side of the truth
        ref = f["refs"][0] if f["refs"] else None
        amount = f["amounts"][0] if f["amounts"] else None
        date = next((d for d in f["dates"] if not d.startswith("--")), None)   # a full date; day-and-month-only dates cannot build a source
        if not (ref or (amount is not None and date)):
            continue                                # nothing to build a source from
        usable += 1
        r0 = R.reconcile(shot, src_text(f, ref, amount, date))
        faithful[r0["status"]] += 1
        # mutate one fact
        options = []
        if ref:
            d = list(ref); i = rng.randrange(len(d)); d[i] = str((int(d[i]) + rng.randrange(1, 9)) % 10); options.append(("ref digit", src_text(f, "".join(d), amount, date)))
        if amount is not None:
            options.append(("amount", src_text(f, ref, amount + rng.choice([10, 100, 500]), date)))
        if date:
            y, m, dd = date.split("-"); nd = f"{y}-{m}-{(int(dd) % 27) + 1:02d}"; options.append(("date", src_text(f, ref, amount, nd)))
        kind, txt = rng.choice(options)
        r1 = R.reconcile(shot, txt)
        mutated[(kind, r1["status"])] += 1
    print(f"{len(files)} screenshots, {usable} had facts to build a source from")
    print("faithful source ->", dict(faithful))
    print("one fact changed ->", dict(mutated))


if __name__ == "__main__":
    main()
