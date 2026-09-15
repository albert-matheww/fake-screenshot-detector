"""Synthetic corpus generator + calibration report for the forensic cues.

No real labeled dataset exists for this project (see README). This script
generates a diverse set of synthetic "authentic" screenshots and several
distinct, plausible tamper types, runs the real forensic pipeline
(backend/forensic.py) against paired authentic/tampered versions of the
*same* underlying content, and reports how each cue's score moves between
the two — which is what the current WEIGHTS in config.py were tuned against.

Run from the backend/ directory (or inside the backend Docker image):
    python3 tools/calibrate.py

This is a development/calibration tool, not part of the served API.
"""
import io
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from forensic import analyze_image_bytes


def _chat_screenshot(seed, size=None):
    random.seed(seed)
    size = size or random.choice([(480, 700), (600, 400), (390, 844)])
    img = Image.new("RGB", size, color=(245, 245, 248))
    d = ImageDraw.Draw(img)
    y = 20
    for i in range(random.randint(4, 9)):
        w = random.randint(120, size[0] - 60)
        h = random.randint(30, 60)
        x = 20 if i % 2 == 0 else size[0] - w - 20
        color = (220, 230, 255) if i % 2 == 0 else (200, 250, 210)
        d.rounded_rectangle([x, y, x + w, y + h], radius=12, fill=color)
        for _ in range(random.randint(10, 30)):
            tx, ty = x + random.randint(5, max(6, w - 10)), y + random.randint(5, max(6, h - 10))
            d.line([tx, ty, tx + random.randint(2, 6), ty], fill=(70, 70, 70))
        y += h + 20
    return img


def _bank_screenshot(seed, size=None):
    random.seed(seed)
    size = size or (480, 760)
    img = Image.new("RGB", size, (245, 246, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size[0], 90], fill=(0, 90, 60))
    d.rounded_rectangle([20, 110, size[0] - 20, 210], radius=14, fill="white", outline=(220, 220, 220))
    for i in range(random.randint(15, 25)):
        d.line([40 + i * 3, 150, 42 + i * 3, 150], fill=(30, 30, 30))
    y = 250
    for _ in range(random.randint(4, 8)):
        d.rounded_rectangle([20, y, size[0] - 20, y + 60], radius=10, fill="white", outline=(230, 230, 230))
        for _ in range(random.randint(8, 20)):
            d.line([40 + random.randint(0, 150), y + 20, 42 + random.randint(0, 150), y + 20],
                   fill=(30, 30, 30))
        y += 70
        if y > size[1] - 80:
            break
    return img


def make_authentic(seed):
    kind = seed % 2
    img = _chat_screenshot(seed) if kind == 0 else _bank_screenshot(seed)
    quality = random.choice([85, 88, 90, 92, 95])
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def make_tampered_from(authentic_bytes, seed):
    """Paired variant: decode the *same* authentic bytes and apply a tamper,
    isolating the tamper's effect from incidental content/quality
    differences between independently generated samples."""
    random.seed(seed)
    img = Image.open(io.BytesIO(authentic_bytes)).convert("RGB")
    w, h = img.size
    tamper_type = seed % 4

    if tamper_type == 0:
        # Edit a textured region, recompress just that patch at a different
        # quality, paste it back, resave the whole image.
        px, py = w // 3, h // 3
        pw, ph = min(120, w // 3), min(50, h // 6)
        patch = img.crop((px, py, px + pw, py + ph)).convert("RGB")
        arr = np.array(patch).astype(np.int16)
        arr[:, :, 0] = np.clip(arr[:, :, 0] + 35, 0, 255)
        patch = Image.fromarray(arr.astype("uint8"))
        pbuf = io.BytesIO()
        patch.save(pbuf, format="JPEG", quality=random.choice([40, 50, 60]))
        pbuf.seek(0)
        patch = Image.open(pbuf).convert("RGB")
        tampered = img.copy()
        tampered.paste(patch, (px, py))
        resave_q = random.choice([80, 85, 88])

    elif tamper_type == 1:
        # Copy-move: duplicate a textured block elsewhere.
        tampered = img.copy()
        src_box = (10, 10, 10 + min(100, w // 4), 10 + min(50, h // 8))
        clone = tampered.crop(src_box)
        dst = (max(0, w - (src_box[2] - src_box[0]) - 10), max(0, h - (src_box[3] - src_box[1]) - 10))
        tampered.paste(clone, dst)
        resave_q = random.choice([85, 90])

    elif tamper_type == 2:
        # Sloppy flat overwrite: a solid box with new content, low texture
        # (the hardest case for compression-artifact-based cues).
        tampered = img.copy()
        d = ImageDraw.Draw(tampered)
        bx, by = w // 4, h // 4
        bw_, bh_ = min(160, w // 3), min(40, h // 10)
        d.rectangle([bx, by, bx + bw_, by + bh_], fill=(250, 250, 250))
        for i in range(8):
            d.line([bx + 10 + i * 8, by + 10, bx + 12 + i * 8, by + bh_ - 10], fill=(20, 20, 20))
        resave_q = random.choice([75, 80, 85])

    else:
        # Editing-tool fingerprint left in EXIF, otherwise untouched.
        tampered = img.copy()
        resave_q = 92

    out = io.BytesIO()
    if tamper_type == 3:
        from PIL.ExifTags import Base
        exif = Image.Exif()
        exif[Base.Software.value] = random.choice(["Adobe Photoshop 25.0", "GIMP 2.10", "Pixelmator Pro"])
        tampered.save(out, format="JPEG", quality=resave_q, exif=exif)
    else:
        tampered.save(out, format="JPEG", quality=resave_q)
    return out.getvalue()


def main():
    n = 25
    tamper_names = {0: "patch-recompress", 1: "copy-move", 2: "flat-edit", 3: "exif-only"}
    cues = ["ela_score", "ghost_score", "quant_score", "noise_score", "clone_score", "metadata_score",
            "font_score", "edge_score", "chrome_score", "arithmetic_score"]

    rows = []
    for i in range(n):
        authentic_bytes = make_authentic(seed=i)
        tampered_bytes = make_tampered_from(authentic_bytes, seed=i)
        r1 = analyze_image_bytes(authentic_bytes, Config)
        r2 = analyze_image_bytes(tampered_bytes, Config)
        rows.append({
            "tamper_type": i % 4,
            "authentic": r1["features"], "tampered": r2["features"],
            "authentic_fake_score": r1["fake_score"], "tampered_fake_score": r2["fake_score"],
            "authentic_is_fake": r1["is_fake"], "tampered_is_fake": r2["is_fake"],
        })

    print(f"Paired authentic/tampered win-rate per cue (n={n}):")
    for cue in cues:
        wins = sum(1 for r in rows if r["tampered"][cue] > r["authentic"][cue])
        print(f"  {cue:15s} {wins}/{n}")

    print("\nPer tamper type:")
    for t, name in tamper_names.items():
        trows = [r for r in rows if r["tamper_type"] == t]
        caught = sum(1 for r in trows if r["tampered_is_fake"])
        fp = sum(1 for r in trows if r["authentic_is_fake"])
        print(f"  type {t} ({name}): n={len(trows)}, tampered caught={caught}, "
              f"authentic false-positives={fp}")

    overall_caught = sum(1 for r in rows if r["tampered_is_fake"])
    overall_fp = sum(1 for r in rows if r["authentic_is_fake"])
    print(f"\nOverall: tampered caught {overall_caught}/{n}, "
          f"authentic false-positives {overall_fp}/{n}")


if __name__ == "__main__":
    main()
