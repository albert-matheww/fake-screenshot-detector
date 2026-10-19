"""Reconcile mode under OCR noise, with ground truth that is NOT derived from the OCR output.

  python tools/eval_reconcile_synthetic.py --n 100 --out results.json

Payment-receipt screenshots are rendered from known facts (payee, amount, date, time, 12-digit reference) in six fonts, light and
dark themes, with and without the rupee sign, then saved as PNG, as a shared copy (down-scaled 0.75, JPEG q75) and as a heavily
shared copy (0.5, JPEG q60). The second source is the bank-SMS text written from the SAME known facts, so a faithful source is
faithful by construction. Each screenshot is reconciled with (a) the faithful source and (b) four altered sources (one digit of the
reference, two digits of the reference, the amount, the date), using either a single OCR read or the two-read consensus.
Question: does the two-read consensus reduce false conflicts and keep altered sources from being corroborated?
"""
import argparse, datetime as dt, json, os, random, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FONTS = ["Arial", "Verdana", "Tahoma", "Trebuchet MS", "Georgia", "Times New Roman"]
FDIR = "/System/Library/Fonts/Supplemental/"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NAMES = ["Alex Morgan", "Priya Nair", "Daniel Okafor", "Maria Silva", "Kenji Sato", "Sara Haddad", "Tom Becker", "Anita Rao"]


def render(rng, facts):
    size = rng.choice([26, 30, 34, 40])
    f = ImageFont.truetype(FDIR + rng.choice(FONTS) + ".ttf", size)
    fb = ImageFont.truetype(FDIR + "Arial.ttf", size)
    dark = rng.random() < 0.5
    bg, fg, dim = ((18, 18, 20), (240, 240, 240), (160, 160, 165)) if dark else ((255, 255, 255), (20, 20, 25), (110, 110, 120))
    rupee = "₹" if rng.random() < 0.5 else "Rs "
    lines = [("Payment successful", fb, fg), (f"Paid to {facts['payee']}", f, fg), (f"{rupee}{facts['amount']}", fb, fg),
             (f"{facts['date'].day} {MON[facts['date'].month - 1]} {facts['date'].year}, {facts['time12']}", f, dim),
             (f"UPI transaction ID", f, dim), (facts["ref"], f, fg), ("Banking name: " + facts["payee"].upper(), f, dim),
             ("Powered by UPI", f, dim)]
    w, h = 900, 80 + len(lines) * (size + 34)
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    center = rng.random() < 0.5
    for i, (t, ft, col) in enumerate(lines):
        y = 50 + i * (size + 34)
        if center:
            d.text((w // 2, y), t, font=ft, fill=col, anchor="ma")
        else:
            d.text((60, y), t, font=ft, fill=col)
    return im


def degrade(im, cond):
    import io
    if cond == "png":
        return im
    k, q = (0.75, 75) if cond == "shared" else (0.5, 60)
    im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue())).convert("RGB")


def bump(s, rng, n):
    s = list(s)
    for i in rng.sample(range(len(s)), n):
        s[i] = str((int(s[i]) + rng.randrange(1, 9)) % 10)
    return "".join(s)


def work(job):
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    cond, seed = job
    import textforensics as tf
    from screencheck import fields as F, reconcile as R
    rng = random.Random(seed)
    d0 = dt.date(2025, 1, 1) + dt.timedelta(days=rng.randrange(0, 600))
    hh, mm = rng.randrange(0, 24), rng.randrange(0, 60)
    amt = round(rng.uniform(20, 9000), 2)
    facts = {"payee": rng.choice(NAMES), "amount": f"{amt:,.2f}", "date": d0, "ref": "".join(str(rng.randrange(10)) for _ in range(12)),
             "time12": f"{(hh % 12) or 12}:{mm:02d} {'pm' if hh >= 12 else 'am'}"}
    img = degrade(render(rng, facts), cond)
    words = tf.ocr_words(img)
    single = F.extract_words(words)
    cons = F.extract_consensus(img, words)
    shot = {"single read": {"any": single, "confident": single}, "two-read consensus": cons}

    def sms(ref=facts["ref"], amount=amt, date=d0):
        return f"Rs.{amount:,.2f} debited from A/c XX1234 on {date.day:02d}-{date.month:02d}-{date.year} at {hh:02d}:{mm:02d}. UPI Ref No {ref}. -Bank"
    sources = {"faithful": sms(), "ref, one digit": sms(ref=bump(facts["ref"], rng, 1)), "ref, two digits": sms(ref=bump(facts["ref"], rng, 2)),
               "amount": sms(amount=round(amt + rng.choice([10, 50, 200, 500]), 2)), "date": sms(date=d0 + dt.timedelta(days=rng.randrange(1, 20)))}
    out = {"cond": cond, "seed": seed, "exact": {}, "status": {}}
    for m, sh in shot.items():
        out["exact"][m] = {"ref": facts["ref"] in sh["any"]["refs"], "ref_confident": facts["ref"] in sh["confident"]["refs"],
                           "amount": round(amt, 2) in sh["any"]["amounts"], "amount_confident": round(amt, 2) in sh["confident"]["amounts"],
                           "date": d0.isoformat() in sh["any"]["dates"], "date_confident": d0.isoformat() in sh["confident"]["dates"]}
        out["status"][m] = {k: R.reconcile(sh, txt)["status"] for k, txt in sources.items()}
    return out


def wilson(k, n, z=1.96):
    import math
    if n == 0:
        return 0.0, 1.0
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100); ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    conds = ["png", "shared", "heavy"]
    jobs = [(c, 7000 + s) for c in conds for s in range(a.n)]
    t0 = time.time()
    with Pool(a.workers) as p:
        res = p.map(work, jobs, chunksize=2)
    json.dump(res, open(a.out, "w"))
    print(f"{len(res)} rendered receipts in {time.time() - t0:.0f}s ({a.n} per condition)")
    print("\nOCR exactness: the true fact is among the values read (any read) / read by both reads (confident)")
    for c in conds:
        rs = [r for r in res if r["cond"] == c]
        cells = []
        for k in ("ref", "amount", "date"):
            n = len(rs)
            ka = sum(r["exact"]["two-read consensus"][k] for r in rs); kc = sum(r["exact"]["two-read consensus"][k + "_confident"] for r in rs)
            ks = sum(r["exact"]["single read"][k] for r in rs)
            cells.append(f"{k}: single {ks}/{n}, either {ka}/{n}, both {kc}/{n}")
        print(f"  {c:7s} " + " | ".join(cells))
    print("\nFAITHFUL second source: status counts")
    for m in ("single read", "two-read consensus"):
        for c in conds:
            cnt = Counter(r["status"][m]["faithful"] for r in res if r["cond"] == c)
            print(f"  {m:20s} {c:7s} {dict(cnt)}")
    print("\nALTERED second source: share NOT corroborated / share called conflict or review")
    for kind in ("ref, one digit", "ref, two digits", "amount", "date"):
        for m in ("single read", "two-read consensus"):
            row = []
            for c in conds:
                rs = [r for r in res if r["cond"] == c]
                nc = sum(r["status"][m][kind] != "corroborated" for r in rs)
                fl = sum(r["status"][m][kind] in ("conflict", "review") for r in rs)
                lo, hi = wilson(nc, len(rs))
                row.append(f"{c}: {nc}/{len(rs)} ({lo:.0%}-{hi:.0%}) flagged {fl}")
            print(f"  {kind:16s} {m:20s} " + " | ".join(row))
    print("\nFalse conflict on a FAITHFUL source (status conflict):")
    for m in ("single read", "two-read consensus"):
        for c in conds:
            rs = [r for r in res if r["cond"] == c]
            k = sum(r["status"][m]["faithful"] == "conflict" for r in rs)
            print(f"  {m:20s} {c:7s} {k}/{len(rs)}")


if __name__ == "__main__":
    main()
