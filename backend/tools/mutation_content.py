"""Mutation test of the content rules: how often does each rule catch the contradiction it is written for, and how often does it
stay silent on a clean document?

  python tools/mutation_content.py --per-mutation 30 --clean 40 --out results.json

Documents are rendered with Pillow (several fonts, sizes and layouts) from a consistent set of facts. A *mutation* changes one
fact so that exactly one rule's invariant is broken (a weekday, a total, a balance, a checksum digit, ...). Every document is
run through the real pipeline, OCR included, as a lossless PNG and again as a shared copy (down-scaled 0.75, JPEG quality 75),
so the numbers include OCR errors. The recall measured here is an UPPER BOUND on what the rules do against real forgers: it
shows the rules fire on the contradictions they were written for, and says nothing about how often a real forger leaves one.
"""
import argparse, datetime as dt, io, json, os, random, sys, time
from collections import Counter, defaultdict
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FONTS = ["Arial", "Verdana", "Tahoma", "Trebuchet MS", "Georgia", "Times New Roman"]
FDIR = "/System/Library/Fonts/Supplemental/"
WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
NAMES = ["Alex Morgan", "Priya Nair", "Daniel Okafor", "Maria Silva", "Kenji Sato", "Sara Haddad", "Tom Becker", "Anita Rao"]
THINGS = ["Coffee beans", "Notebook", "USB cable", "Desk lamp", "Phone case", "Tea box", "Pen set", "Water bottle", "Backpack", "Headphones"]


def font(rng, size):
    return ImageFont.truetype(FDIR + rng.choice(FONTS) + ".ttf", size)


def money(v):
    return f"{v:,.2f}"


def iban(rng):
    bban = "WEST" + "".join(str(rng.randrange(10)) for _ in range(14))
    r = bban + "GB00"
    n = int("".join(str(int(c, 36)) for c in r))
    cd = 98 - n % 97
    return f"GB{cd:02d}{bban}"


def fmt_iban(s):
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


def card(rng):
    ds = [4] + [rng.randrange(10) for _ in range(14)]
    s = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2 == 0:
            d *= 2
            d -= 9 if d > 9 else 0
        s += d
    ds.append((10 - s % 10) % 10)
    t = "".join(map(str, ds))
    return " ".join(t[i:i + 4] for i in range(0, 16, 4))


def bump_digit(s, rng):
    idx = [i for i, c in enumerate(s) if c.isdigit()]
    i = rng.choice(idx)
    d = str((int(s[i]) + rng.randrange(1, 9)) % 10)
    return s[:i] + d + s[i + 1:]


def date_line(d, wd_override=None):
    wd = WEEK[d.weekday()] if wd_override is None else wd_override
    return f"{wd}, {d.day} {MON[d.month - 1]} {d.year}"


def draw_lines(rows, rng, w=1000, size=None, right_cols=None):
    size = size or rng.choice([26, 30, 34])
    f = font(rng, size)
    h = 40 + (size + 26) * (len(rows) + 1)
    im = Image.new("RGB", (w, h), (255, 255, 255) if rng.random() < 0.8 else (245, 247, 250))
    d = ImageDraw.Draw(im)
    for i, r in enumerate(rows):
        y = 30 + i * (size + 26)
        if isinstance(r, tuple):
            d.text((40, y), r[0], font=f, fill=(15, 15, 25))
            for j, cell in enumerate(r[1:]):
                d.text((w - 40 - j * 230, y), cell, font=f, fill=(15, 15, 25), anchor="ra")
        else:
            d.text((40, y), r, font=f, fill=(15, 15, 25))
    return im


# ---------------------------------------------------------------- documents: (clean builder, mutation builders)
def invoice(rng, mut=None):
    d0 = dt.date(2024, 1, 1) + dt.timedelta(days=rng.randrange(0, 700))
    items = [(rng.choice(THINGS), round(rng.uniform(4, 90), 2)) for _ in range(rng.randrange(3, 6))]
    sub = round(sum(p for _, p in items), 2)
    tax = round(sub * 0.05, 2)
    tot = round(sub + tax, 2)
    name = rng.choice(NAMES)
    ib, cd = fmt_iban(iban(rng)), card(rng)
    wd_over, date_ = None, d0
    if mut == "weekday":
        wd_over = rng.choice([w for w in WEEK if w != WEEK[d0.weekday()]])
    if mut == "future_date":
        date_ = dt.date.today() + dt.timedelta(days=rng.randrange(40, 300))
    if mut == "total_below_subtotal":
        tot = round(sub - rng.uniform(5, 30), 2)
    if mut == "items_vs_subtotal":
        k = rng.randrange(len(items))
        items[k] = (items[k][0], round(items[k][1] + rng.choice([-1, 1]) * rng.uniform(3, 25), 2))
    if mut == "iban":
        ib = bump_digit(ib, rng)
    if mut == "card":
        cd = bump_digit(cd, rng)
    if mut == "placeholder_name":
        name = "John Doe"
    rows = ["Order Invoice", f"Customer: {name}", f"Date: {date_line(date_, wd_over)}", f"Time: {rng.randrange(8, 22)}:{rng.randrange(0, 60):02d}"]
    rows += [(n, money(p)) for n, p in items]
    rows += [("Subtotal", money(sub)), ("Tax (5%)", money(tax)), ("Total", money(tot))]
    rows += [f"IBAN: {ib}", f"Card: {cd}"]
    if mut == "watermark":
        rows.append("SAMPLE STATEMENT - for novelty purposes only")
    if mut == "time":
        rows[3] = f"Time: {rng.choice([25, 27, 31])}:{rng.randrange(0, 60):02d}"
    return draw_lines(rows, rng), "order_invoice"


def statement(rng, mut=None):
    bal = round(rng.uniform(800, 5000), 2)
    rows = [("Account statement", "Balance", "Amount")]
    balances, amts = [], []
    for _ in range(8):
        a = round(rng.uniform(3, 220), 2)
        bal = round(bal + (a if rng.random() < 0.4 else -a), 2)
        balances.append(bal); amts.append(a)
    k = rng.randrange(2, 6)
    if mut == "balance":
        balances[k] = round(balances[k] + rng.choice([-1, 1]) * rng.uniform(10, 300), 2)
    if mut == "amount":
        amts[k] = round(amts[k] + rng.uniform(10, 90), 2)
    d0 = dt.date(2025, 1, 5)
    for i in range(8):
        dd = d0 + dt.timedelta(days=3 * i)
        rows.append((f"{dd.day} {MON[dd.month - 1][:3]}  {rng.choice(THINGS)}", money(balances[i]), money(amts[i])))
    return draw_lines(rows, rng, w=1100), "bank_statement"


def payment(rng, mut=None):
    ref = "".join(str(rng.randrange(10)) for _ in range(12))
    if mut == "ref_digits":
        ref = ref[:11] if rng.random() < 0.5 else ref + str(rng.randrange(10))
    rows = ["Payment Successful", f"Paid to {rng.choice(NAMES)}", f"Rs {money(rng.uniform(50, 9000))}",
            f"{rng.randrange(1, 28)} {rng.choice(MON)[:3]} 2025, {rng.randrange(1, 12)}:{rng.randrange(0, 60):02d} pm",
            f"UPI transaction ID {ref}", "Status: Completed"]
    if mut == "status":
        rows.insert(3, "Payment failed")
    return draw_lines(rows, rng), "payment_receipt"


def chat(rng, mut=None):
    t = rng.randrange(1 * 60, 10 * 60)             # between 01:00 and 10:00, so 12-hour times never cross noon
    ts = []
    for _ in range(8):
        t += rng.randrange(1, 7)
        ts.append(t)
    if mut == "time_order":
        j = rng.randrange(2, 6)
        ts[j] = ts[j - 1] - 45
    style = rng.choice(["glued", "spaced", "bare"])   # "8:43PM", "8:43 PM" (as WhatsApp prints it) or a 24-hour "8:43"
    pm = rng.random() < 0.5

    def fmt(m):
        h, mi = m // 60, m % 60
        if style == "bare":
            return f"{h}:{mi:02d}"
        return f"{h}:{mi:02d}{'' if style == 'glued' else ' '}{'PM' if pm else 'AM'}"
    msgs = ["Hey, are you coming?", "On my way", "Great see you soon", "Did you get the tickets?", "Yes, two seats", "Perfect",
            "Bring the charger", "Will do"]
    rows = [(m, fmt(ts[i])) for i, m in enumerate(msgs)]
    return draw_lines(rows, rng), "chat"


def otp(rng, mut=None):
    n = rng.choice([4, 6, 8]) if mut is None else 7
    code = "".join(str(rng.randrange(1, 10)) for _ in range(n))
    rows = [f"Your OTP is {code}. Do not share it with anyone.", "Valid for 10 minutes.", "- Example Bank"]
    return draw_lines(rows, rng), "message_alert"


def layout(rng, mut=None):
    size = rng.choice([28, 32])
    f = font(rng, size)
    n, pitch = 10, size + 30
    h = 60 + pitch * (n + 1)
    im = Image.new("RGB", (900, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    k = rng.randrange(3, 7)
    for i in range(n):
        y = 30 + i * pitch
        if mut == "off_grid" and i == k:
            y += int(0.6 * size) if rng.random() < 0.5 else -int(0.6 * size)
        d.text((40, 30 + i * pitch), rng.choice(THINGS), font=f, fill=(15, 15, 25))
        d.text((860, y), money(rng.uniform(5, 950)), font=f, fill=(15, 15, 25), anchor="ra")
    return im, "bank_statement"


DOCS = {
    "invoice": (invoice, ["weekday", "future_date", "total_below_subtotal", "items_vs_subtotal", "iban", "card", "placeholder_name", "watermark", "time"]),
    "statement": (statement, ["balance", "amount"]),
    "payment": (payment, ["ref_digits", "status"]),
    "chat": (chat, ["time_order"]),
    "otp": (otp, ["otp_length"] if False else ["length7"]),
    "layout": (layout, ["off_grid"]),
}
# mutation id -> (document builder, builder's mutation name, expected finding id)
MUTS = {
    "weekday": ("invoice", "weekday", "date.weekday_mismatch"),
    "future_date": ("invoice", "future_date", "date.future"),
    "total_below_subtotal": ("invoice", "total_below_subtotal", "arith.total_below_subtotal"),
    "items_vs_subtotal": ("invoice", "items_vs_subtotal", "arith.items_vs_subtotal"),
    "iban_digit": ("invoice", "iban", "id.iban_checksum"),
    "card_digit": ("invoice", "card", "id.card_luhn"),
    "placeholder_name": ("invoice", "placeholder_name", "text.placeholder_name"),
    "generator_watermark": ("invoice", "watermark", "text.generator_marker"),
    "impossible_time": ("invoice", "time", "time.invalid"),
    "running_balance_balance": ("statement", "balance", "bank.running_balance"),
    "running_balance_amount": ("statement", "amount", "bank.running_balance"),
    "upi_ref_length": ("payment", "ref_digits", "pay.upi_ref_length"),
    "status_contradiction": ("payment", "status", "pay.status_contradiction"),
    "chat_time_order": ("chat", "time_order", "chat.time_order"),
    "otp_length": ("otp", "mut", "msg.otp_length"),
    "off_grid_number": ("layout", "off_grid", "layout.column_off_grid"),
}
BUILD = {"invoice": invoice, "statement": statement, "payment": payment, "chat": chat, "otp": otp, "layout": layout}
CONTENT_CHECKS = ("content_logic", "layout_grid")


def to_bytes(im, shared):
    if shared:
        im = im.resize((int(im.width * 0.75), int(im.height * 0.75)), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, "JPEG", quality=75)
    else:
        b = io.BytesIO(); im.save(b, "PNG")
    return b.getvalue()


def work(job):
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    from screencheck.pipeline import analyze_bytes
    if os.environ.get("MUT_OLD_ROWS") == "1":      # reproduce the behaviour before rows were rebuilt from word positions
        import semantic
        semantic.rows_from_words = semantic.lines_from_words
    mid, doc, mut, seed, shared = job
    rng = random.Random(seed)
    im, typ = BUILD[doc](rng, None if mut is None else ("mut" if doc == "otp" else mut))
    r = analyze_bytes(to_bytes(im, shared), forced_type=typ)
    fnd = [(f["check"], f["id"], f["severity"]) for f in r["findings"] if not f["check"].startswith(("rendering", "v1."))]
    return {"mid": mid, "doc": doc, "shared": shared, "seed": seed, "verdict": r["verdict"], "assurance": r["assurance"]["level"],
            "ids": sorted({i for _, i, _ in fnd}), "ids_mh": sorted({i for _, i, s in fnd if s in ("medium", "high")}),
            "words": r["stats"]["ocr_words"]}


def wilson(k, n, z=1.96):
    import math
    if n == 0:
        return 0.0, 1.0
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-mutation", type=int, default=30)
    ap.add_argument("--clean", type=int, default=40)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    jobs = []
    for shared in (False, True):
        for mid, (doc, mut, _) in MUTS.items():
            for s in range(a.per_mutation):
                jobs.append((mid, doc, mut, 1000 + s, shared))
        for doc in BUILD:
            for s in range(a.clean):
                jobs.append(("clean", doc, None, 5000 + s, shared))
    t0 = time.time()
    with Pool(a.workers) as p:
        res = p.map(work, jobs, chunksize=4)
    json.dump(res, open(a.out, "w"))
    print(f"{len(res)} documents scored in {time.time() - t0:.0f}s (per mutation {a.per_mutation}, clean per document type {a.clean})")
    print("\nRECALL: the rule written for the mutation fires (expected finding id present)")
    print(f"{'mutation':26s} {'expected id':30s} {'PNG':>14s} {'shared':>14s} {'verdict moves (PNG)':>20s}")
    for mid, (doc, mut, exp) in MUTS.items():
        row = []
        for shared in (False, True):
            rs = [r for r in res if r["mid"] == mid and r["shared"] == shared]
            k = sum(exp in r["ids"] for r in rs)
            lo, hi = wilson(k, len(rs))
            row.append(f"{k}/{len(rs)} ({lo:.0%}-{hi:.0%})")
        rs = [r for r in res if r["mid"] == mid and not r["shared"]]
        mv = sum(r["verdict"] in ("suspicious", "evidence_of_editing") for r in rs)
        print(f"{mid:26s} {exp:30s} {row[0]:>14s} {row[1]:>14s} {mv:>8d}/{len(rs)}")
    print("\nSILENCE on clean documents: any finding by a content, type-specific or layout check")
    print(f"{'document':12s} {'any finding PNG':>20s} {'any finding shared':>22s} {'medium/high PNG':>18s} {'medium/high shared':>20s}")
    for doc in BUILD:
        cells = []
        for key in ("ids", "ids_mh"):
            for shared in (False, True):
                rs = [r for r in res if r["mid"] == "clean" and r["doc"] == doc and r["shared"] == shared]
                k = sum(bool(r[key]) for r in rs)
                lo, hi = wilson(k, len(rs))
                cells.append(f"{k}/{len(rs)} ({lo:.0%}-{hi:.0%})")
        print(f"{doc:12s} {cells[0]:>20s} {cells[1]:>22s} {cells[2]:>18s} {cells[3]:>20s}")
    allc = [r for r in res if r["mid"] == "clean"]
    for shared in (False, True):
        rs = [r for r in allc if r["shared"] == shared]
        k = sum(bool(r["ids_mh"]) for r in rs)
        print(f"all clean documents, {'shared' if shared else 'PNG'}: medium/high finding on {k} of {len(rs)} ({wilson(k, len(rs))[0]:.1%} to {wilson(k, len(rs))[1]:.1%})")
    print("\nWhich clean documents raised a finding (id: count)")
    cnt = Counter(i for r in allc for i in r["ids"])
    print(dict(cnt))
    lv = Counter((r["mid"] == "clean", r["assurance"]) for r in res)
    print("\nassurance level of clean documents:", {k[1]: v for k, v in lv.items() if k[0]}, "| of mutated documents:", {k[1]: v for k, v in lv.items() if not k[0]})


if __name__ == "__main__":
    main()
