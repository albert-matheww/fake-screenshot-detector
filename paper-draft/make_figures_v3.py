"""Figures for the version-3 chapters. Numbers are copied from evidence/stfd_compare_run.txt, evidence/rico_genuine_run.txt and
evidence/v3_real_set.txt; the UI figure is a headless-Chrome capture of the demo page (placeholder content)."""
import json, os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_figures.py")).read()
exec(src.split("# ----------------------------------------------------------------------------- parse evidence")[0], globals())
from PIL import Image

# ------------------------------------------------------------------ pipeline
def pipeline():
    W, H = 1900, 1120
    im, d = canvas(W, H)
    f = font(34, True)
    # row 1
    box(d, 30, 30, 400, 190, "1 Upload", "one screenshot, and the type the person chooses", BLUE, bsize=30)
    box(d, 500, 30, 420, 190, "2 Capture profile", "format, JPEG quality, how much pixel evidence can survive", BLUE, bsize=30)
    box(d, 990, 30, 420, 190, "3 Read the text", "OCR twice; amounts, dates, times, reference numbers", BLUE, bsize=30)
    arrow(d, 430, 125, 495, 125); arrow(d, 920, 125, 985, 125)
    # row 2: checks (grouped, one arrow in from row 1, one bar out to the gates)
    d.rounded_rectangle([10 * S, 250 * S, (W - 10) * S, 600 * S], radius=24 * S, outline=GREY, width=3 * S)
    d.text((30 * S, 262 * S), "4 Checks: each returns found something / found nothing / could not examine", font=font(34, True), fill=DARK)
    arrow(d, 1300, 222, 1300, 305, wd=4)
    box(d, 30, 330, 430, 250, "File and content rules", "metadata tags, dates, totals, checksums count; the rules written for the chosen type are shown, not counted", AQUA, bsize=29)
    box(d, 490, 330, 430, 250, "Layout", "evenly spaced number columns: one number off the grid; advisory", GREY, bsize=30)
    box(d, 950, 330, 430, 250, "Word rendering model", "trained on generated edits; advisory only", GREY, bsize=30)
    box(d, 1410, 330, 460, 250, "Version-1 cues", "error level, JPEG ghost, noise, copy-move, quantisation tables: hints only", GREY, bsize=30)
    # row 3
    box(d, 30, 650, 560, 220, "5 Calibration gates", "a check counts only if measured on enough genuine screenshots; otherwise it is shown, not counted", PURPLE, bsize=30)
    box(d, 650, 650, 560, 220, "6 Verdict policy", "contradiction = flagged; any doubt = inconclusive; never called authentic", PURPLE, bsize=30)
    box(d, 1270, 650, 600, 220, "7 Assurance level 0, 1 or 2", "what independent evidence supports the screenshot", ORANGE, bsize=30)
    arrow(d, 590, 760, 645, 760); arrow(d, 1210, 760, 1265, 760)
    arrow(d, 310, 603, 310, 645, wd=4)
    # side inputs
    box(d, 780, 960, 520, 130, "Second source", "bank SMS, statement line, issuer e-mail", AQUA, bsize=28, tsize=34)
    box(d, 1340, 960, 530, 130, "Genuine copy", "compare mode: a separate result that marks every difference", AQUA, bsize=26, tsize=34)
    arrow(d, 1040, 955, 1480, 875, wd=4)
    save(im, "fig_v3_pipeline")

# ------------------------------------------------------------------ assurance ladder
def ladder():
    W, H = 1900, 860
    im, d = canvas(W, H)
    steps = [("Level 0  Unverified", "The screenshot alone, or a contradiction or conflict was found.", GREY),
             ("Level 1  No contradiction found (still unverified)", "What it says is consistent with itself. A careful forgery reaches this level too.", BLUE),
             ("Level 2  Consistent with an independent source", "A second source that did not come from the sender agrees on the reference, or on the amount and the date.", AQUA),
             ("Level 3  Confirmed by signed data", "A digital signature or signed QR code that can be checked. Not built yet.", (190, 196, 206))]
    for i, (t, b, col) in enumerate(steps):
        x = 40 + i * 70
        y = 40 + i * 195
        d.rounded_rectangle([x * S, y * S, (W - 40) * S, (y + 160) * S], radius=20 * S, fill=col)
        tc = (255, 255, 255) if i < 3 else DARK
        d.text(((x + 30) * S, (y + 24) * S), t, font=font(40, True), fill=tc)
        for k, ln in enumerate(wrap(d, b, font(33), W - x - 120)):
            d.text(((x + 30) * S, (y + 82 + k * 40) * S), ln, font=font(33), fill=tc)
    save(im, "fig_assurance")

# ------------------------------------------------------------------ reconcile flow
def reconcile():
    W, H = 1900, 780
    im, d = canvas(W, H)
    box(d, 30, 40, 520, 200, "Screenshot", "text read twice (as is and enlarged 2x): a value both reads agree on is confident", BLUE, bsize=29)
    box(d, 30, 330, 520, 200, "Second source", "pasted text or an image: amounts, dates, times, reference numbers", AQUA, bsize=29)
    box(d, 680, 170, 520, 250, "Look every fact up", "each fact in the second source is searched for in the screenshot", PURPLE, bsize=30)
    arrow(d, 550, 140, 675, 260); arrow(d, 550, 430, 675, 330)
    outs = [("matched", "same value present", AQUA), ("differs", "the screenshot confidently shows other values", ORANGE),
            ("near", "reference off by one digit, or an amount with one extra leading digit: look by eye", (214, 160, 40)), ("unclear", "no value of that kind found", GREY)]
    for i, (t, b, col) in enumerate(outs):
        y = 20 + i * 175
        box(d, 1330, y, 540, 150, t, b, col, bsize=27, tsize=34)
        arrow(d, 1200, 295, 1325, y + 75, wd=4)
    d.text((30 * S, 590 * S), "Corroborated: no difference, no near miss, every supplied fact", font=font(31), fill=DARK)
    d.text((30 * S, 635 * S), "matched, and the reference matches (or both amount and date match).", font=font(31), fill=DARK)
    d.text((30 * S, 695 * S), "Any 'differs' on reference, amount or date is a conflict.", font=font(31), fill=DARK)
    save(im, "fig_reconcile")

# ------------------------------------------------------------------ pixel model: STFD and Rico
def stfd():
    bars("fig_stfd_auc", ["Trained on clean STFD", "Trained on degraded STFD", "Trained on both"],
         [("tested on clean STFD", [0.806, 0.694, 0.793], BLUE), ("tested on degraded STFD", [0.6648, 0.733, 0.732], ORANGE)],
         1.0, yfmt="{:.2f}", ylabel="word-level AUC", tick=0.2, h=900)
    bars("fig_rico_fa", ["Trained on clean STFD", "Trained on clean and degraded STFD", "Second version (generated edits)"],
         [("lower threshold (about 5% false alarms)", [215 / 276, 221 / 276, 74 / 276], ORANGE), ("higher threshold (about 1%)", [139 / 276, 111 / 276, 40 / 276], BLUE)],
         1.0, yfmt="{:.2f}", ylabel="share of genuine screens flagged", tick=0.2, h=900)

# ------------------------------------------------------------------ UI capture
def ui():
    src = "/tmp/ui_noev.png"
    if os.path.exists(src):
        im = Image.open(src).convert("RGB").crop((100, 172, 1180, 960))
        im.save(f"{OUT}/fig_ui_v3.png", dpi=(200, 200)); print("wrote fig_ui_v3")

pipeline(); ladder(); reconcile(); stfd(); ui()
