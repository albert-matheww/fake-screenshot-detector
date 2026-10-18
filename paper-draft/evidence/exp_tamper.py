"""Experiment B: can the detector tell a realistically edited screenshot from the
genuine original?  For each genuine screenshot: OCR a word, paint over it with the
surrounding background colour and re-type a modified string in a different font
(what a person editing a number in Preview/Photoshop/Figma does).  Variants:
  orig_png   untouched PNG
  edit_png   edited, saved lossless PNG        (devtools / any lossless editor)
  orig_jpg85 untouched, shared as JPEG q85     (WhatsApp-style re-share)
  edit_jpg85 edited, then shared as JPEG q85
Only scores are recorded."""
import glob, io, json, os, random, sys, time
from concurrent.futures import ProcessPoolExecutor

BACKEND = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend"
sys.path.insert(0, BACKEND)
OUT = os.path.dirname(os.path.abspath(__file__))
FONT = "/System/Library/Fonts/Helvetica.ttc"


def edit_image(img, rng):
    import numpy as np, pytesseract
    from PIL import ImageDraw, ImageFont
    d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    cands = []
    for i, t in enumerate(d["text"]):
        t = t.strip()
        try:
            conf = float(d["conf"][i])
        except Exception:
            continue
        h = d["height"][i]
        if conf >= 85 and len(t) >= 4 and 12 <= h <= 60 and d["width"][i] > 20:
            cands.append((i, t))
    if not cands:
        return None
    digit_c = [c for c in cands if any(ch.isdigit() for ch in c[1])]
    i, t = rng.choice(digit_c or cands)
    x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
    arr = np.array(img)
    pad = 3
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(img.width, x + w + pad), min(img.height, y + h + pad)
    ring = np.concatenate([arr[y0:y1, x0:x0 + 1].reshape(-1, 3), arr[y0:y1, x1 - 1:x1].reshape(-1, 3),
                           arr[y0:y0 + 1, x0:x1].reshape(-1, 3), arr[y1 - 1:y1, x0:x1].reshape(-1, 3)])
    bg = tuple(int(v) for v in np.median(ring, axis=0))
    ink = tuple(int(v) for v in arr[y:y + h, x:x + w].reshape(-1, 3)[
        np.argmax(np.abs(arr[y:y + h, x:x + w].reshape(-1, 3).astype(int) - np.array(bg)).sum(axis=1))])
    new = "".join(str((int(ch) + 3) % 10) if ch.isdigit() else ch for ch in t)
    if new == t:
        new = t[::-1]
    out = img.copy()
    dr = ImageDraw.Draw(out)
    dr.rectangle([x0, y0, x1, y1], fill=bg)
    dr.text((x, y), new, fill=ink, font=ImageFont.truetype(FONT, int(h * 1.0)))
    return out


def analyze(img_or_bytes_fmt):
    from config import Config
    from forensic import analyze_image_bytes
    return analyze_image_bytes(img_or_bytes_fmt, Config)


def to_bytes(img, fmt, **kw):
    b = io.BytesIO()
    img.convert("RGB").save(b, format=fmt, **kw)
    return b.getvalue()


def work(path):
    from PIL import Image
    rng = random.Random(hash(os.path.basename(path)) & 0xFFFF)
    img = Image.open(path).convert("RGB")
    edited = edit_image(img, rng)
    if edited is None:
        return None
    variants = {
        "orig_png": to_bytes(img, "PNG"),
        "edit_png": to_bytes(edited, "PNG"),
        "orig_jpg85": to_bytes(img, "JPEG", quality=85),
        "edit_jpg85": to_bytes(edited, "JPEG", quality=85),
    }
    res = {"id": os.path.basename(path)[:40], "size": img.size}
    for k, raw in variants.items():
        r = analyze(raw)
        res[k] = {"fake_score": r["fake_score"], "is_fake": r["is_fake"], "ctype": r["meta"]["content_type"],
                  "features": r["features"]}
    return res


if __name__ == "__main__":
    home = os.path.expanduser("~")
    paths = []
    for pat in ("Desktop/Screenshot*.png", "Downloads/Screenshot*.png",
                "Desktop/untitled folder/Screenshot*.png", "Desktop/untitled folder/*/Screenshot*.png"):
        paths += glob.glob(os.path.join(home, pat))
    random.Random(1).shuffle(paths)
    paths = paths[:60]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=4) as ex:
        res = [r for r in ex.map(work, paths) if r]
    json.dump(res, open(os.path.join(OUT, "tamper_results.json"), "w"))
    print("done", len(res), "image-sets in", round(time.time() - t0), "s")
