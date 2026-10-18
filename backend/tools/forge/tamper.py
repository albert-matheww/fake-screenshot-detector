"""Realistic screenshot text-edit simulator (ground-truth masks included).

The edits mimic what people actually do to fake a screenshot with a raster
editor: pick a word (usually a number, name or status), paint over it, and
type a replacement - in a *different* font engine than the one that drew the
rest of the screen, with varying care:

  fill   flat colour | row-gradient | noise-matched | clone-stamp of nearby background
  text   Pillow/FreeType, many system fonts; grayscale AA, no AA, or simulated
         LCD sub-pixel AA; size and baseline jitter; optional blur / noise /
         local JPEG recompression of the patch
  splice a word crop taken from a *different* screenshot, resized to fit

Each operation returns the exact edit rectangle, so training/eval labels are
exact. Edits from the same engine as the base image (a DOM edit in browser
devtools, a generator site that renders natively) are *not* simulated: they
leave no rendering inconsistency and are outside what this method can see -
that limit is reported, not hidden (see README "What it cannot detect").
"""
from __future__ import annotations

import glob
import io
import os
import random
import zlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIRS = ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts"]
SKIP_NAMES = ("braille", "symbol", "emoji", "lastresort", "keyboard", "webdings", "wingdings", "dingbat",
              "ornament", "zapf", "kohinoor", "noto", "myanmar", "sf arabic", "sfarabic", "hebrew", "armenian",
              "georgian", "ethiopic", "geeza", "diwan", "nastaleeq", "baghdad", "beirut", "damascus", "farah",
              "nadeem", "muna", "sana", "adtnumeric", "aquakana", "hiragino", "cjk", "applesdgothic", "stheit",
              "songti", "pingfang", "heiti", "kaiti", "lantinghei", "hannotate", "hanzipen", "yuppy", "wawati",
              "libian", "weibei", "xingkai", "yuanti", "baoli", "lisong", "mshtakan", "gurmukhi", "gujarati",
              "devanagari", "bangla", "kannada", "malayalam", "oriya", "tamil", "telugu", "thonburi", "ayuthaya",
              "krungthep", "sukhumvit", "silom", "kokonor", "tibetan", "plantagenet", "mishafi", "sathu", "waseem",
              "al bayan", "al nile", "al tarikh", "corsiva", "decotype", "mukta", "euphemia", "khmer", "lao", "sinhala")


def _renders_latin(path: str, index: int) -> bool:
    try:
        f = ImageFont.truetype(path, 40, index=index)
        def sig(s: str):
            im = Image.new("L", (120, 70), 0)
            ImageDraw.Draw(im).text((8, 4), s, font=f, fill=255)
            return np.asarray(im).tobytes()
        sigs = {sig(c) for c in ("A", "B", "0", "8", "e", "$")}
        return len(sigs) == 6 and max(f.getbbox("Hello 123")[2:]) > 20
    except Exception:
        return False


_FONT_BANK: Optional[List[Dict[str, Any]]] = None


def font_bank() -> List[Dict[str, Any]]:
    """Usable Latin fonts on this machine. `fold` (0-4) is a stable hash of the font name:
    fold 0 is reserved for the unseen-font test set."""
    global _FONT_BANK
    if _FONT_BANK is not None:
        return _FONT_BANK
    bank: List[Dict[str, Any]] = []
    seen = set()
    for d in FONT_DIRS:
        for p in sorted(glob.glob(os.path.join(d, "*"))):
            base = os.path.basename(p)
            if not base.lower().endswith((".ttf", ".ttc", ".otf")):
                continue
            if any(s in base.lower() for s in SKIP_NAMES):
                continue
            for index in range(0, 6 if base.lower().endswith(".ttc") else 1):
                try:
                    f = ImageFont.truetype(p, 20, index=index)
                    name = "/".join(f.getname())
                except Exception:
                    break
                if name in seen:
                    continue
                if not _renders_latin(p, index):
                    continue
                seen.add(name)
                bank.append({"path": p, "index": index, "name": name, "fold": zlib.crc32(name.encode()) % 5})
    _FONT_BANK = bank
    return bank


# ---------------------------------------------------------------------------
# Text rendering
# ---------------------------------------------------------------------------

def _size_for_height(font_path: str, index: int, text: str, target_h: int) -> int:
    best, best_err = 8, 1e9
    for s in range(9, 260):  # tiny sizes give erratic hinted bboxes in some fonts
        f = ImageFont.truetype(font_path, s, index=index)
        b = f.getbbox(text)
        err = abs((b[3] - b[1]) - target_h)
        if err < best_err:
            best, best_err = s, err
        elif (b[3] - b[1]) > target_h + 3:
            break
    return best


def render_coverage(text: str, font_path: str, index: int, size: int, mode: str) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Return (coverage [H,W] or [H,W,3] in 0..1, (left_offset, top_offset) of the ink box
    relative to the drawing origin). mode: gray | none | lcd."""
    f = ImageFont.truetype(font_path, size, index=index)
    l, t, r, b = f.getbbox(text)
    W, H = r - l + 6, b - t + 6
    if mode == "lcd":
        f3 = ImageFont.truetype(font_path, size * 3, index=index)
        l3, t3, r3, b3 = f3.getbbox(text)
        W3 = (r3 - l3 + 18)
        W3 += (-W3) % 3
        H3 = (b3 - t3 + 18)
        H3 += (-H3) % 3
        im = Image.new("L", (W3, H3), 0)
        ImageDraw.Draw(im).text((9 - l3, 9 - t3), text, font=f3, fill=255)
        a = np.asarray(im, dtype=np.float32) / 255.0
        a = a.reshape(H3 // 3, 3, W3).mean(axis=1)                      # vertical box filter
        k = np.array([1, 2, 3, 2, 1], np.float32) / 9.0                # FIR across sub-pixels
        pad = np.pad(a, ((0, 0), (2, 2)), mode="constant")
        a = sum(k[i] * pad[:, i:i + W3] for i in range(5))
        cov = a.reshape(H3 // 3, W3 // 3, 3)                           # (R,G,B) sub-pixel coverage
        return cov, (0, 0)  # caller trims to the ink box
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1" if mode == "none" else "L"
    d.text((3 - l, 3 - t), text, font=f, fill=255)
    return np.asarray(im, dtype=np.float32) / 255.0, (3, 3)


def _trim(cov: np.ndarray) -> np.ndarray:
    m = cov.max(axis=2) if cov.ndim == 3 else cov
    ys, xs = np.where(m > 0.02)
    if len(ys) == 0:
        return cov
    return cov[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


# ---------------------------------------------------------------------------
# Edit operations
# ---------------------------------------------------------------------------

_VOCAB = ["Paid", "Sent", "Received", "Success", "Failed", "Pending", "Refund", "Total", "Credit", "Debit", "Done",
          "Approved", "Today", "Order", "Delivered", "Online", "Verified", "Amount", "Balance", "Account", "Online",
          "Cancelled", "Seen", "Read", "Yes", "Confirmed", "Transfer", "Deposit", "Salary", "Rent", "Gift"]


def _mutate_text(text: str, rng: random.Random) -> str:
    digits = [i for i, ch in enumerate(text) if ch.isdigit()]
    if digits and rng.random() < 0.75:
        s = list(text)
        for i in rng.sample(digits, min(len(digits), rng.choice([1, 1, 2, 3]))):
            s[i] = str((int(s[i]) + rng.randint(1, 9)) % 10)
        out = "".join(s)
        if rng.random() < 0.25 and len(digits) >= 2:  # add/remove a digit group
            out = out + rng.choice("0123456789") if rng.random() < 0.5 else out[:-1] or out
        return out if out != text else text[::-1]
    alpha = text.strip(".,:;!?()")
    cands = [w for w in _VOCAB if abs(len(w) - len(alpha)) <= 2 and w.lower() != alpha.lower()]
    if cands and rng.random() < 0.8:
        w = rng.choice(cands)
        if alpha.isupper():
            w = w.upper()
        elif alpha[:1].islower():
            w = w.lower()
        return text.replace(alpha, w) if alpha else w
    s = list(alpha)
    rng.shuffle(s)
    return "".join(s) or text


def _ring_stats(arr: np.ndarray, x0: int, y0: int, x1: int, y1: int, m: int = 4):
    H, W, _ = arr.shape
    X0, Y0, X1, Y1 = max(0, x0 - m), max(0, y0 - m), min(W, x1 + m), min(H, y1 + m)
    mask = np.ones((Y1 - Y0, X1 - X0), bool)
    mask[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = False
    ring = arr[Y0:Y1, X0:X1][mask]
    return np.median(ring, axis=0), ring.std(axis=0)


def _fill_rect(arr: np.ndarray, rect: Tuple[int, int, int, int], mode: str, rng: random.Random) -> None:
    x0, y0, x1, y1 = rect
    H, W, _ = arr.shape
    med, sd = _ring_stats(arr, x0, y0, x1, y1)
    if mode == "flat":
        arr[y0:y1, x0:x1] = med
    elif mode == "noisy":
        n = np.random.default_rng(rng.randint(0, 2**31)).normal(0, max(0.5, float(sd.mean()) * 0.5),
                                                             (y1 - y0, x1 - x0, 1))
        arr[y0:y1, x0:x1] = np.clip(med + n, 0, 255)
    elif mode == "gradient":
        left = arr[y0:y1, max(0, x0 - 3):x0].mean(axis=1) if x0 > 0 else np.tile(med, (y1 - y0, 1))
        right = arr[y0:y1, x1:min(W, x1 + 3)].mean(axis=1) if x1 < W else left
        t = np.linspace(0, 1, x1 - x0)[None, :, None]
        arr[y0:y1, x0:x1] = left[:, None, :] * (1 - t) + right[:, None, :] * t
    else:  # clone stamp: copy a same-size block of nearby background
        h, w = y1 - y0, x1 - x0
        for dy in (-(h + 2), h + 2, -(2 * h + 4), 2 * h + 4):
            ys = y0 + dy
            if 0 <= ys and ys + h <= H:
                blk = arr[ys:ys + h, x0:x1]
                if blk.std() < max(4.0, float(sd.mean()) * 2):
                    arr[y0:y1, x0:x1] = blk
                    return
        arr[y0:y1, x0:x1] = med


def _composite(arr: np.ndarray, cov: np.ndarray, x: int, y: int, ink: np.ndarray) -> None:
    H, W, _ = arr.shape
    ch, cw = cov.shape[:2]
    xs0, ys0 = max(0, x), max(0, y)
    xs1, ys1 = min(W, x + cw), min(H, y + ch)
    if xs1 <= xs0 or ys1 <= ys0:
        return
    c = cov[ys0 - y:ys1 - y, xs0 - x:xs1 - x]
    if c.ndim == 2:
        c = c[..., None]
    reg = arr[ys0:ys1, xs0:xs1]
    arr[ys0:ys1, xs0:xs1] = reg * (1 - c) + ink[None, None, :] * c


def _ink_color(arr: np.ndarray, box: Tuple[int, int, int, int], bg: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = box
    reg = arr[y0:y1, x0:x1].reshape(-1, 3)
    d = np.abs(reg - bg[None, :]).sum(axis=1)
    k = max(3, int(0.05 * len(d)))
    return reg[np.argsort(d)[-k:]].mean(axis=0)


def pick_target(words: Sequence[Dict[str, Any]], rng: random.Random, img_w: int, img_h: int
                ) -> Optional[Dict[str, Any]]:
    cands = [w for w in words if w["conf"] >= 70 and 12 <= w["height"] <= 90 and w["width"] >= 14
             and w["left"] > 4 and w["top"] > 4 and w["left"] + w["width"] < img_w - 4
             and w["top"] + w["height"] < img_h - 4 and any(ch.isalnum() for ch in w["text"])]
    if not cands:
        return None
    digit = [w for w in cands if any(ch.isdigit() for ch in w["text"])]
    pool = digit if (digit and rng.random() < 0.6) else cands
    return rng.choice(pool)


def edit_word(img: Image.Image, words: Sequence[Dict[str, Any]], rng: random.Random,
              allowed_folds: Sequence[int], donors: Optional[Sequence[Tuple[Image.Image, Dict[str, Any]]]] = None,
              target: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Apply one realistic edit. Returns {"image","box":(x0,y0,x1,y1),"meta":{...}} or None."""
    rgb = img.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32).copy()
    H, W, _ = arr.shape
    t = target or pick_target(words, rng, W, H)
    if t is None:
        return None
    x, y, w, h = t["left"], t["top"], t["width"], t["height"]
    old_box = (x, y, x + w, y + h)
    bg, _ = _ring_stats(arr, *old_box)
    ink = _ink_color(arr, old_box, bg)

    op = rng.choices(["replace", "splice", "blur"], weights=[0.62, 0.14, 0.24])[0]
    if op == "splice" and not donors:
        op = "replace"
    fills = ["flat", "noisy", "gradient", "clonestamp"]
    fill = rng.choices(fills, weights=[0.35, 0.2, 0.2, 0.25])[0]
    pad = rng.choice([0, 1, 2, 3, 4])
    meta: Dict[str, Any] = {"op": op, "fill": fill, "pad": pad, "orig_text": t["text"]}

    if op == "splice":
        dimg, dw = rng.choice(list(donors))
        crop = dimg.convert("RGB").crop((dw["left"] - 2, dw["top"] - 2, dw["left"] + dw["width"] + 2,
                                         dw["top"] + dw["height"] + 2))
        scale = (h + 4) / crop.height
        # keep the spliced crop a plausible size for the slot it replaces (and inside the image)
        new_w = int(min(max(4, crop.width * scale), max(w * 2.0, 24), W - 8))
        crop = crop.resize((max(4, new_w), h + 4), Image.BICUBIC if rng.random() < .5 else Image.LANCZOS)
        nx1 = min(W, x + crop.width)
        rect = (max(0, min(x, W - crop.width) - pad), max(0, y - 2 - pad), min(W, max(x + w, nx1) + pad), min(H, y + h + 2 + pad))
        _fill_rect(arr, rect, fill, rng)
        px = min(x, W - crop.width)
        arr[max(0, y - 2):max(0, y - 2) + crop.height, px:px + crop.width] = np.asarray(crop, np.float32)[
            :min(crop.height, H - max(0, y - 2)), :min(crop.width, W - px)]
        meta.update({"donor_text": dw["text"]})
        box = rect
    else:
        new_text = _mutate_text(t["text"], rng)
        fonts = [f for f in font_bank() if f["fold"] in allowed_folds]
        font = rng.choice(fonts)
        aa = rng.choices(["gray", "none", "lcd"], weights=[0.65, 0.12, 0.23])[0]
        size = _size_for_height(font["path"], font["index"], new_text, max(6, h + rng.choice([0, 0, 0, 1, -1, 2])))
        cov, _off = render_coverage(new_text, font["path"], font["index"], size, aa)
        cov = _trim(cov)
        ch, cw = cov.shape[:2]
        right_aligned = (x + w) > 0.72 * W and rng.random() < 0.8
        nx = (x + w - cw) if right_aligned else x
        ny = y + h - ch + rng.choice([0, 0, 0, 1, -1, 2]) if rng.random() < 0.7 else y + (h - ch) // 2
        nx, ny = int(max(0, min(W - cw, nx))), int(max(0, min(H - ch, ny)))
        rx0 = max(0, min(x, nx) - pad)
        ry0 = max(0, min(y, ny) - pad)
        rx1 = min(W, max(x + w, nx + cw) + pad)
        ry1 = min(H, max(y + h, ny + ch) + pad)
        rect = (rx0, ry0, rx1, ry1)
        _fill_rect(arr, rect, fill, rng)
        jitter = np.array([rng.uniform(-6, 6) for _ in range(3)]) if rng.random() < 0.3 else 0
        _composite(arr, cov, nx, ny, np.clip(ink + jitter, 0, 255))
        meta.update({"new_text": new_text, "font": font["name"], "font_fold": font["fold"], "aa": aa, "size": size})
        box = rect

    out = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8))
    # optional patch post-processing
    if op == "blur" or rng.random() < 0.12:
        r = rng.uniform(0.35, 0.9)
        pr = out.crop(box).filter(ImageFilter.GaussianBlur(r))
        out.paste(pr, box[:2])
        meta["blur"] = round(r, 2)
    if rng.random() < 0.15:
        b = io.BytesIO()
        pr = out.crop(box)
        pr.save(b, "JPEG", quality=rng.randint(60, 90))
        out.paste(Image.open(b).convert("RGB"), box[:2])
        meta["patch_jpeg"] = True
    return {"image": out, "box": tuple(int(v) for v in box), "meta": meta}


# ---------------------------------------------------------------------------
# Distribution shift applied identically to authentic and edited images
# ---------------------------------------------------------------------------

def degrade(img: Image.Image, boxes: Sequence[Tuple[int, int, int, int]], rng: random.Random
            ) -> Tuple[bytes, str, List[Tuple[int, int, int, int]], Dict[str, Any]]:
    """Re-share simulation. Returns (file_bytes, extension, scaled_boxes, meta)."""
    mode = rng.choices(["png", "jpeg", "resize_png", "resize_jpeg"], weights=[0.34, 0.34, 0.14, 0.18])[0]
    meta: Dict[str, Any] = {"degrade": mode}
    scale = 1.0
    if mode.startswith("resize"):
        scale = rng.choice([0.5, 0.66, 0.75, 0.85])
        img = img.resize((max(8, int(img.width * scale)), max(8, int(img.height * scale))),
                         rng.choice([Image.BILINEAR, Image.LANCZOS, Image.BICUBIC]))
        meta["scale"] = scale
    buf = io.BytesIO()
    if mode.endswith("jpeg"):
        q = rng.randint(55, 98)
        img.convert("RGB").save(buf, "JPEG", quality=q, subsampling=rng.choice([0, 2]))
        meta["jpeg_q"] = q
        ext = "jpg"
    else:
        img.convert("RGB").save(buf, "PNG")
        ext = "png"
    sb = [(int(b[0] * scale), int(b[1] * scale), int(np.ceil(b[2] * scale)), int(np.ceil(b[3] * scale))) for b in boxes]
    return buf.getvalue(), ext, sb, meta
