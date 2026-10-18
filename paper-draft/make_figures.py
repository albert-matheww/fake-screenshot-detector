"""Generates every figure of the report from the saved evidence files (paper-draft/evidence). Pillow only."""
import json, os, re, statistics as st, textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector"
EV = f"{ROOT}/paper-draft/evidence"
OUT = f"{ROOT}/paper-draft/figures"
os.makedirs(OUT, exist_ok=True)
BLUE, ORANGE, GREY, DARK, LIGHT, AQUA, PURPLE = (42, 120, 214), (235, 104, 52), (120, 130, 145), (17, 24, 39), (238, 242, 247), (27, 175, 122), (74, 58, 167)
S = 2  # supersampling


def font(px, bold=False):
    p = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
    return ImageFont.truetype(p, int(px * S))


def canvas(w, h):
    im = Image.new("RGB", (w * S, h * S), "white")
    return im, ImageDraw.Draw(im)


def save(im, name):
    w, h = im.size
    im.resize((w // S, h // S), Image.LANCZOS).save(f"{OUT}/{name}.png", dpi=(300, 300))
    print("wrote", name)


def tw(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0], b[3] - b[1]


def ctext(d, cx, cy, t, f, fill=DARK):
    w, h = tw(d, t, f)
    d.text((cx * S - w / 2, cy * S - h / 2 - f.size * 0.08), t, font=f, fill=fill)


def wrap(d, t, f, maxw):
    words, lines, cur = t.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if tw(d, trial, f)[0] <= maxw * S or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w_
    lines.append(cur)
    return lines


def box(d, x, y, w, h, title, body, fill, tcol=(255, 255, 255), bsize=30, tsize=36):
    d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=18 * S, fill=fill)
    ft, fb = font(tsize, True), font(bsize)
    ctext(d, x + w / 2, y + 36, title, ft, tcol)
    yy = y + 78
    for ln in wrap(d, body, fb, w - 36):
        ctext(d, x + w / 2, yy, ln, fb, tcol)
        yy += bsize * 1.25


def arrow(d, x1, y1, x2, y2, col=GREY, wd=5):
    d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=col, width=wd * S)
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    L = 22
    for s in (-0.45, 0.45):
        d.line([x2 * S, y2 * S, (x2 - L * math.cos(a + s)) * S, (y2 - L * math.sin(a + s)) * S], fill=col, width=wd * S)


def bars(name, cats, series, ymax, w=1900, h=1000, yfmt="{:.2f}", ylabel="", legend=True, vlabel_fmt=None, tick=None):
    im, d = canvas(w, h)
    L, R, T, B = 190, 60, 70, 190
    fa, fl, fv = font(40), font(38), font(36)
    n, m = len(cats), len(series)
    top = T + (60 if legend and m > 1 else 0)
    ph = h - top - B
    pw = w - L - R
    tk = tick or ymax / 5
    v = 0.0
    while v <= ymax + 1e-9:
        y = top + ph - ph * v / ymax
        d.line([L * S, y * S, (w - R) * S, y * S], fill=(220, 225, 232), width=2 * S)
        lab = yfmt.format(v)
        tw_, _ = tw(d, lab, fa)
        d.text(((L - 18) * S - tw_, y * S - fa.size * 0.55), lab, font=fa, fill=GREY)
        v += tk
    d.line([L * S, top * S, L * S, (top + ph) * S], fill=DARK, width=3 * S)
    d.line([L * S, (top + ph) * S, (w - R) * S, (top + ph) * S], fill=DARK, width=3 * S)
    gw = pw / n
    bw = gw * 0.72 / m
    for i, c in enumerate(cats):
        x0 = L + gw * i + gw * 0.14
        for j, (nm, vals, col) in enumerate(series):
            val = vals[i]
            bh = ph * min(val, ymax) / ymax
            xa = x0 + bw * j
            d.rectangle([xa * S, (top + ph - bh) * S, (xa + bw - 6) * S, (top + ph) * S], fill=col)
            lab = (vlabel_fmt or yfmt).format(val)
            ctext(d, xa + (bw - 6) / 2, top + ph - bh - 28, lab, fv, DARK)
        for k, ln in enumerate(wrap(d, c, fl, gw - 20)):
            ctext(d, L + gw * i + gw / 2, top + ph + 42 + k * 42, ln, fl, DARK)
    if ylabel:
        t = Image.new("RGBA", (700 * S, 80 * S), (255, 255, 255, 0))
        td = ImageDraw.Draw(t)
        td.text((0, 0), ylabel, font=fa, fill=DARK)
        t = t.rotate(90, expand=True)
        im.paste(t, (10 * S, int((top + ph / 2) * S - t.size[1] / 2)), t)
    if legend and m > 1:
        x = L + 20
        for nm, vals, col in series:
            d.rectangle([x * S, 24 * S, (x + 34) * S, 58 * S], fill=col)
            d.text(((x + 46) * S, 18 * S), nm, font=fl, fill=DARK)
            x += 46 + tw(d, nm, fl)[0] / S + 60
    save(im, name)


# ----------------------------------------------------------------------------- parse evidence
def parse_final_log():
    sec, res = None, {}
    for ln in open(f"{EV}/train_final_v6.log"):
        if ln.startswith("-- by "):
            sec = ln[6:].split("(")[0].strip()
            continue
        m = re.match(r"\s+(\S+)\s+n=\s*(\d+) edits=\s*(\d+) AUC=([\d.]+) TPR@1%=([\d.]+)\(FPR ([\d.]+)\) TPR@5%=([\d.]+)\(FPR ([\d.]+)\)", ln)
        if m and sec:
            res.setdefault(sec, {})[m.group(1)] = dict(n=int(m.group(2)), edits=int(m.group(3)), auc=float(m.group(4)), tpr1=float(m.group(5)), fpr1=float(m.group(6)), tpr5=float(m.group(7)), fpr5=float(m.group(8)))
        m2 = re.match(r"\s+test all\s+n=\s*(\d+) edits=\s*(\d+) AUC=([\d.]+) TPR@1%=([\d.]+)\(FPR ([\d.]+)\) TPR@5%=([\d.]+)\(FPR ([\d.]+)\)", ln)
        if m2:
            res["test_all"] = dict(n=int(m2.group(1)), edits=int(m2.group(2)), auc=float(m2.group(3)), tpr1=float(m2.group(4)), fpr1=float(m2.group(5)), tpr5=float(m2.group(6)), fpr5=float(m2.group(7)))
    return res


final = parse_final_log()
json.dump(final, open(f"{EV}/final_log_parsed.json", "w"), indent=1)

# ----------------------------------------------------------------------------- Fig: architecture
im, d = canvas(1900, 760)
box(d, 40, 60, 330, 220, "Browser UI", "React app: upload, image overlay, verdict, reasons", BLUE)
box(d, 470, 60, 330, 220, "Flask API", "POST /analyze  GET /status; image kept in memory", (51, 65, 85))
box(d, 900, 60, 420, 220, "OCR", "Tesseract: word boxes, confidence, line ids", (51, 65, 85))
box(d, 1420, 60, 440, 220, "Word features", "95 rendering and layout measurements per word", BLUE)
box(d, 900, 420, 420, 240, "Rule checks", "metadata, watermarks, arithmetic, dates, checksums, layout grid", PURPLE)
box(d, 1420, 420, 440, 240, "Classifier", "boosted trees: P(word edited); thresholds from real validation", BLUE)
box(d, 470, 420, 330, 240, "Verdict", "four tiers, marked words, reasons, limitations", ORANGE)
arrow(d, 370, 170, 470, 170); arrow(d, 800, 170, 900, 170); arrow(d, 1320, 170, 1420, 170)
arrow(d, 1640, 280, 1640, 420)
d.line([1640 * S, 660 * S, 1640 * S, 715 * S], fill=GREY, width=5 * S); d.line([1640 * S, 715 * S, 635 * S, 715 * S], fill=GREY, width=5 * S)
arrow(d, 635, 715, 635, 662)
arrow(d, 1110, 280, 1110, 420); arrow(d, 900, 540, 800, 540)
arrow(d, 635, 420, 635, 280); arrow(d, 470, 150, 370, 150)
save(im, "fig_architecture")

# ----------------------------------------------------------------------------- Fig: word analysis idea
im, d = canvas(1900, 640)
box(d, 40, 70, 400, 220, "1  Words", "OCR gives a box for every word of the screenshot", (51, 65, 85))
box(d, 520, 70, 460, 220, "2  Measure", "edges, strokes, colour fringes, background seam, noise, JPEG grid, size, baseline", BLUE)
box(d, 1060, 70, 360, 220, "3  Compare", "each value against the other words of its line and image", BLUE)
box(d, 1500, 70, 360, 220, "4  Score", "boosted trees: probability the word was edited", ORANGE)
arrow(d, 440, 180, 520, 180); arrow(d, 980, 180, 1060, 180); arrow(d, 1420, 180, 1500, 180)
f = font(40)
ctext(d, 950, 420, "An edit is an outlier among its own neighbours, whatever the style of the app.", f, DARK)
ctext(d, 950, 480, "Image score = the highest word probability; two thresholds give the \"suspicious\" and \"evidence\" tiers.", font(36), GREY)
save(im, "fig_word_idea")

# ----------------------------------------------------------------------------- Fig: corpus construction
im, d = canvas(1900, 820)
box(d, 40, 40, 420, 200, "Genuine bases", "real device screenshots, Chrome-rendered app UIs, Pillow-rendered UIs", (51, 65, 85))
box(d, 560, 40, 420, 200, "Edit simulator", "Pillow engine (many fonts) and Chrome-rasterised patches", BLUE)
box(d, 1080, 40, 380, 200, "Sharing", "PNG, JPEG q55-98, or down-scaled 0.5-0.85x", ORANGE)
box(d, 1560, 40, 300, 200, "OCR + features", "word-level labels from exact masks", (51, 65, 85))
arrow(d, 460, 140, 560, 140); arrow(d, 980, 140, 1080, 140); arrow(d, 1460, 140, 1560, 140)
box(d, 40, 400, 540, 260, "Split by base image", "hash of the base file: 70 % train, 15 % validation, 15 % test; windows of one file never straddle splits", PURPLE)
box(d, 680, 400, 540, 260, "Held-out fonts", "test-split edits only use fonts from hash fold 0 (Pillow) or four held-out Chrome fonts", PURPLE)
box(d, 1320, 400, 540, 260, "Same degradation", "genuine and edited images get the same random sharing step, so compression is not a label", PURPLE)
arrow(d, 1710, 240, 1710, 330); arrow(d, 1710, 330, 310, 330); arrow(d, 310, 330, 310, 400); arrow(d, 950, 330, 950, 400); arrow(d, 1590, 330, 1590, 400)
save(im, "fig_corpus")

# ----------------------------------------------------------------------------- Fig: v1 cue saturation
fp = json.load(open(f"{EV}/fp_results.json"))
cues = [("ela_score", "ELA"), ("noise_score", "Noise"), ("edge_score", "Edge"), ("ghost_score", "JPEG ghost"), ("clone_score", "Clone"), ("font_score", "Font"), ("metadata_score", "Metadata"), ("text_score", "OCR text")]
vals = [st.mean(x["features"][k] for x in fp) for k, _ in cues]
bars("fig_v1_cues", [c for _, c in cues], [("mean score on 60 genuine screenshots", vals, ORANGE)], 1.0, legend=False, ylabel="Mean cue score (0-1)", tick=0.2, w=1900, h=900)

# ----------------------------------------------------------------------------- Fig: v1 vs v2
cl = open(f"{EV}/compare_legacy.txt").read()
leg = re.search(r"legacy v1: AUC ([\d.]+)\s+flagged-fake rate on AUTHENTIC ([\d.]+)\s+on EDITED ([\d.]+)", cl)
v2 = re.search(r"v2 @\s*5% target: AUC ([\d.]+)\s+flagged rate on AUTHENTIC ([\d.]+)\s+on EDITED ([\d.]+)", cl)
v2s = re.search(r"v2 @\s*1% target: AUC ([\d.]+)\s+flagged rate on AUTHENTIC ([\d.]+)\s+on EDITED ([\d.]+)", cl)
bars("fig_v1_v2", ["Edited images flagged (%)", "Genuine images flagged (%)"],
     [("v1 pipeline", [float(leg.group(3)) * 100, float(leg.group(2)) * 100], ORANGE),
      ("v2 evidence tier", [float(v2s.group(3)) * 100, float(v2s.group(2)) * 100], PURPLE),
      ("v2 suspicious tier", [float(v2.group(3)) * 100, float(v2.group(2)) * 100], BLUE)],
     50, yfmt="{:.0f}", vlabel_fmt="{:.1f}", ylabel="Share of 500 test images (%)", tick=10)

# ----------------------------------------------------------------------------- Fig: AUC by sharing condition
dg = final["re-share degradation"]
order = [("png", "Lossless (PNG)"), ("jpeg", "Shared as JPEG"), ("resize_png", "Down-scaled, PNG"), ("resize_jpeg", "Down-scaled, JPEG")]
bars("fig_degrade", [l for _, l in order], [("AUC", [dg[k]["auc"] for k, _ in order], BLUE)], 1.0, legend=False, ylabel="Image-level AUC", tick=0.2)
bars("fig_degrade_tpr", [l for _, l in order], [("Edits caught, suspicious tier", [dg[k]["tpr5"] * 100 for k, _ in order], BLUE), ("Edits caught, evidence tier", [dg[k]["tpr1"] * 100 for k, _ in order], PURPLE)], 100, yfmt="{:.0f}", vlabel_fmt="{:.0f}", ylabel="Edited images caught (%)", tick=20)

# ----------------------------------------------------------------------------- Fig: leave-files-out
cv = json.load(open(f"{EV}/cv_summary_v6.json"))
bars("fig_leave_out", ["Genuine screenshots flagged", "Edited copies caught"],
     [("Suspicious tier", [cv["suspicious"]["fpr"] * 100, cv["suspicious"]["tpr"] * 100], BLUE),
      ("Evidence tier", [cv["evidence"]["fpr"] * 100, cv["evidence"]["tpr"] * 100], PURPLE)], 60, yfmt="{:.0f}", vlabel_fmt="{:.1f}", ylabel="Share of images (%)", tick=10)

# ----------------------------------------------------------------------------- Fig: layout rule recall
rec = []
for ln in open(f"{EV}/layout_rule_eval.txt"):
    m = re.match(r"\s+shift ([\d.]+) x height: detected (\d+)/(\d+)", ln)
    if m:
        rec.append((m.group(1), 100.0 * int(m.group(2)) / int(m.group(3))))
bars("fig_layout", [f"{a} x height" for a, _ in rec], [("simulated misplaced number detected", [b for _, b in rec], BLUE)], 25, legend=False, yfmt="{:.0f}", vlabel_fmt="{:.1f}", ylabel="Detected (%)", tick=5, w=1900, h=900)

# ----------------------------------------------------------------------------- Fig: by edit operation (AUC)
op = final["edit operation"]
nm = {"replace": "Re-typed (Pillow)", "blur": "Re-typed + blur", "splice": "Spliced word crop", "chrome_patch": "Chrome-rendered patch"}
ks = [k for k in ("replace", "blur", "splice", "chrome_patch") if k in op]
bars("fig_ops", [nm[k] for k in ks], [("AUC", [op[k]["auc"] for k in ks], BLUE)], 1.0, legend=False, ylabel="Image-level AUC", tick=0.2)

# ----------------------------------------------------------------------------- Fig: cross-engine (needs cross_engine.txt)
ce = f"{EV}/cross_engine.txt"
if os.path.exists(ce) and os.path.getsize(ce) > 0:
    rows = {}
    for ln in open(ce):
        m = re.match(r"trained on (.+?)\s+-> test on\s+Pillow edits: AUC ([\d.]+)\s+\|\s+Chrome edits: AUC ([\d.]+)", ln.strip())
        if m:
            rows[m.group(1).strip()] = (float(m.group(2)), float(m.group(3)))
    if rows:
        cats = ["Pillow edits only", "Chrome edits only", "Both engines"]
        key = {"Pillow edits only": "Pillow only", "Chrome edits only": "Chrome only", "Both engines": "both engines"}
        bars("fig_cross", [f"Trained on: {c}" for c in cats],
             [("tested on Pillow edits", [rows[key[c]][0] for c in cats], BLUE), ("tested on Chrome edits", [rows[key[c]][1] for c in cats], ORANGE)],
             1.0, ylabel="Image-level AUC", tick=0.2)
# ----------------------------------------------------------------------------- Fig: sample pair (generated Chrome render, not private)
a = Image.open(f"{ROOT}/docs/samples/statement_original.png").convert("RGB")
b = Image.open(f"{ROOT}/docs/samples/statement_edited_detected.png").convert("RGB")
H = 1000
a2 = a.resize((int(a.size[0] * H / a.size[1]), H), Image.LANCZOS); b2 = b.resize((int(b.size[0] * H / b.size[1]), H), Image.LANCZOS)
W = a2.size[0] + b2.size[0] + 90
im = Image.new("RGB", (W, H + 70), "white")
im.paste(a2, (30, 60)); im.paste(b2, (60 + a2.size[0], 60))
dd = ImageDraw.Draw(im)
fnt = ImageFont.truetype("/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf", 34)
dd.text((30, 12), "(a) untouched", font=fnt, fill=DARK); dd.text((60 + a2.size[0], 12), "(b) one amount edited", font=fnt, fill=DARK)
im.save(f"{OUT}/fig_sample_pair.png", dpi=(300, 300)); print("wrote fig_sample_pair")
print("figures done")
