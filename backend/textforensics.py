"""Word-level text-edit forensics for screenshots.

Why this exists
---------------
Photograph forensics (ELA, noise maps, JPEG ghosts) carries no usable signal on
screenshots: measured on genuine, untouched screenshots those cues sit near
their maximum on *every* image, and they do not move when a word is edited.
What an edit to a screenshot does leave behind is a *local inconsistency of
text rendering*: the new glyphs were rasterised by a different engine, font,
size or anti-aliasing mode than their neighbours, they sit on a slightly
different baseline, and the background patch painted under them rarely
matches the surrounding background exactly (colour step along a rectangle,
different noise, different JPEG block-grid phase).

So this module treats the problem as outlier detection *within one image*:

  1. OCR gives word boxes (and line grouping).
  2. For every word we measure rendering features (anti-aliasing profile,
     stroke width, colour fringing, ink colour, background seam, residual
     noise, JPEG grid alignment, geometry).
  3. Each feature is also expressed relative to the other words of the same
     image / same line (robust z-scores) - an edit is an outlier among its
     own neighbours, whatever the absolute style of the app is.
  4. A gradient-boosted classifier (trained in tools/forge on edits made to
     real and browser-rendered screenshots) turns that into a per-word
     probability of being edited.

Everything here is deliberately explainable: each flagged word comes with the
features that deviate most from its neighbours.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage as ndi

try:  # OCR is required for inference; import lazily so tooling can import the file
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

EPS = 1e-6
MIN_WORD_H = 8          # words shorter than this (px) are too small to measure reliably
MAX_WORD_H = 220


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def ocr_words(img, min_conf: float = 0.0) -> List[Dict[str, Any]]:
    """Run Tesseract once; return word dicts with box, confidence and line id."""
    if pytesseract is None:
        return []
    try:
        d = pytesseract.image_to_data(img.convert("RGB"), output_type=pytesseract.Output.DICT)
    except Exception:
        return []
    words: List[Dict[str, Any]] = []
    for i in range(len(d["text"])):
        t = d["text"][i].strip()
        try:
            conf = float(d["conf"][i])
        except (TypeError, ValueError):
            continue
        if not t or conf < min_conf:
            continue
        w, h = int(d["width"][i]), int(d["height"][i])
        if h < 4 or w < 3:
            continue
        words.append({
            "text": t, "left": int(d["left"][i]), "top": int(d["top"][i]), "width": w, "height": h,
            "conf": conf, "line": f'{d["block_num"][i]}-{d["par_num"][i]}-{d["line_num"][i]}',
        })
    return words


# ---------------------------------------------------------------------------
# Per-word measurements
# ---------------------------------------------------------------------------

def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def _phase_profile(gray: np.ndarray, x0: int, y0: int) -> Tuple[float, int]:
    """JPEG 8x8 grid evidence in a crop expressed in absolute image coordinates:
    (strength, phase). Strength is how much stronger the best-aligned column/row
    boundary phase is than the median phase."""
    if gray.shape[0] < 9 or gray.shape[1] < 9:
        return 0.0, 0
    col = np.abs(np.diff(gray, axis=1)).mean(axis=0)
    row = np.abs(np.diff(gray, axis=0)).mean(axis=1)
    pc = np.array([col[((p - x0) % 8)::8].mean() if len(col[((p - x0) % 8)::8]) else 0.0 for p in range(8)])
    pr = np.array([row[((p - y0) % 8)::8].mean() if len(row[((p - y0) % 8)::8]) else 0.0 for p in range(8)])
    prof = pc / (pc.mean() + EPS) + pr / (pr.mean() + EPS)
    return float((prof.max() - np.median(prof)) / 2.0), int(prof.argmax())


FEATURE_BASE = [
    "aa_ratio", "edge95", "ink_q25", "ink_q50", "ink_q75", "ink_chroma", "edge_chroma", "lcd_fringe",
    "stroke_w", "stroke_w2", "ink_frac", "bg_noise_in", "bg_noise_out", "noise_ratio", "bg_shift",
    "seam_max", "seam_pos", "seam_sides", "grid_strength", "grid_phase_mismatch", "contrast", "sharp_hi",
]
DIST_BINS = 8
HIST_NAMES = [f"h{i}" for i in range(DIST_BINS)] + [f"o{i}" for i in range(DIST_BINS)]
FEATURE_BASE += ["exey", "ink_sd"] + HIST_NAMES
GEOM = ["h", "w", "char_w", "conf", "n_chars", "digit_frac"]
# base features that also get image-relative and line-relative z-scores
REL = ["exey", "ink_sd", "aa_ratio", "edge95", "ink_q50", "ink_chroma", "edge_chroma", "lcd_fringe", "stroke_w", "stroke_w2",
       "ink_frac", "bg_noise_in", "noise_ratio", "bg_shift", "seam_max", "grid_strength", "contrast", "sharp_hi",
       "char_w"]


def _seam(rgb: np.ndarray, x: int, y: int, w: int, h: int, max_d: int = 9) -> Tuple[float, int, int]:
    """Largest colour step, moving outward from the word box, that is *consistent along a whole side*
    (median over positions) - the signature of a rectangular background patch painted under an edit.
    Returns (max_step, distance_of_step, number_of_sides_with_step>2.5)."""
    H, W, _ = rgb.shape
    best, best_d, strong = 0.0, 0, 0
    sides = []
    # top / bottom strips: rows at distance d from the box edge, spanning the box width
    xs0, xs1 = max(0, x), min(W, x + w)
    ys0, ys1 = max(0, y), min(H, y + h)
    if xs1 - xs0 >= 4:
        top = [rgb[y - d, xs0:xs1] for d in range(0, max_d + 1) if y - d >= 0]
        bot = [rgb[y + h - 1 + d, xs0:xs1] for d in range(0, max_d + 1) if y + h - 1 + d < H]
        sides += [top, bot]
    if ys1 - ys0 >= 4:
        lef = [rgb[ys0:ys1, x - d] for d in range(0, max_d + 1) if x - d >= 0]
        rig = [rgb[ys0:ys1, x + w - 1 + d] for d in range(0, max_d + 1) if x + w - 1 + d < W]
        sides += [lef, rig]
    for lines in sides:
        if len(lines) < 3:
            continue
        side_best = 0.0
        for d in range(len(lines) - 1):
            step = np.median(np.linalg.norm(lines[d] - lines[d + 1], axis=1))
            if step > side_best:
                side_best = step
                if step > best:
                    best, best_d = float(step), d
        if side_best > 2.5:
            strong += 1
    return best, best_d, strong


def word_measurements(rgb: np.ndarray, gray: np.ndarray, word: Dict[str, Any],
                      global_phase: int) -> Optional[Dict[str, float]]:
    """Absolute rendering features for one word, or None if it cannot be measured."""
    H, W = gray.shape
    x, y, w, h = word["left"], word["top"], word["width"], word["height"]
    if h < MIN_WORD_H or h > MAX_WORD_H or w < 6:
        return None
    m = max(3, int(round(0.35 * h)))
    x0, y0, x1, y1 = max(0, x - m), max(0, y - m), min(W, x + w + m), min(H, y + h + m)
    xi0, yi0, xi1, yi1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if xi1 - xi0 < 6 or yi1 - yi0 < 6:
        return None
    crop_g = gray[y0:y1, x0:x1]
    inner_g = gray[yi0:yi1, xi0:xi1]
    inner_c = rgb[yi0:yi1, xi0:xi1]

    ring_mask = np.ones(crop_g.shape, bool)
    ring_mask[yi0 - y0:yi1 - y0, xi0 - x0:xi1 - x0] = False
    ring = crop_g[ring_mask]
    if ring.size < 10:
        return None
    ring_c = rgb[y0:y1, x0:x1][ring_mask]
    bg = float(np.median(ring))
    bg_c = np.median(ring_c, axis=0)

    dev = inner_g - bg
    adev = np.abs(dev)
    c = float(np.percentile(adev, 98))
    if c < 10:
        return None  # nothing to measure (OCR hallucination on a flat area)
    nd = adev / c
    ink = nd > 0.5
    aa = (nd > 0.12) & (nd <= 0.88)
    n_ink = int(ink.sum())
    if n_ink < 6:
        return None

    gy, gx = np.gradient(inner_g)
    gm = np.hypot(gx, gy) / c
    vals = nd[nd > 0.05]
    h8 = np.histogram(vals, bins=DIST_BINS, range=(0.05, 1.0))[0].astype(np.float64) if vals.size else np.zeros(DIST_BINS)
    h8 /= (h8.sum() + EPS)
    ang = np.arctan2(gy, gx) % np.pi
    o8 = np.histogram(ang.ravel(), bins=DIST_BINS, range=(0, np.pi), weights=gm.ravel())[0].astype(np.float64)
    o8 /= (o8.sum() + EPS)
    chroma = inner_c.max(axis=2) - inner_c.min(axis=2)
    bg_chroma = float(np.median(ring_c.max(axis=1) - ring_c.min(axis=1)))
    core = nd > 0.8
    ink_rgb = inner_c[core].mean(axis=0) if core.any() else inner_c[ink].mean(axis=0)

    # stroke width: 2*area/perimeter, and 2*median of distance-transform ridge
    er = ndi.binary_erosion(ink)
    perim = max(1, int((ink & ~er).sum()))
    sw = 2.0 * n_ink / perim
    dt = ndi.distance_transform_edt(ink)
    ridge = (dt >= ndi.maximum_filter(dt, size=3)) & ink & (dt > 0.9)
    sw2 = 2.0 * float(np.median(dt[ridge])) if ridge.any() else sw

    # background noise inside the box vs just outside it
    bgmask_in = nd < 0.1
    lap_in = ndi.laplace(inner_g)
    noise_in = float(lap_in[bgmask_in].std()) if bgmask_in.sum() > 12 else 0.0
    lap_crop = ndi.laplace(crop_g)
    noise_out = float(lap_crop[ring_mask].std()) if ring_mask.sum() > 12 else 0.0
    bg_in_mean = float(inner_g[bgmask_in].mean()) if bgmask_in.sum() > 12 else bg

    seam, seam_d, seam_sides = _seam(rgb.astype(np.float32), xi0, yi0, xi1 - xi0, yi1 - yi0)

    gs, gp = _phase_profile(crop_g, x0, y0)
    text = word["text"]
    n_chars = max(1, len(text))
    q = np.percentile(nd[nd > 0.05], [25, 50, 75]) if (nd > 0.05).sum() > 8 else np.zeros(3)
    out = {
        "exey": float((np.abs(gx).mean() + 1e-3) / (np.abs(gy).mean() + 1e-3)),
        "ink_sd": float(nd[ink].std()),
        "aa_ratio": float(aa.sum()) / (n_ink + 1.0),
        "edge95": float(np.percentile(gm, 95)),
        "ink_q25": float(q[0]), "ink_q50": float(q[1]), "ink_q75": float(q[2]),
        "ink_chroma": float(chroma[ink].mean() - bg_chroma),
        "edge_chroma": float(chroma[aa].mean() - bg_chroma) if aa.any() else 0.0,
        "lcd_fringe": float(np.abs(inner_c[..., 0] - inner_c[..., 2])[aa].mean() / c) if aa.any() else 0.0,
        "stroke_w": sw / h, "stroke_w2": sw2 / h,
        "ink_frac": n_ink / float(ink.size),
        "bg_noise_in": noise_in, "bg_noise_out": noise_out, "noise_ratio": noise_in / (noise_out + 0.25),
        "bg_shift": bg_in_mean - bg,
        "seam_max": seam, "seam_pos": float(seam_d), "seam_sides": float(seam_sides),
        "grid_strength": gs, "grid_phase_mismatch": float(gs > 0.15 and gp != global_phase),
        "contrast": c, "sharp_hi": float((gm > 0.6).mean()),
        "h": float(h), "w": float(w), "char_w": w / float(h * n_chars), "conf": float(word["conf"]),
        "n_chars": float(n_chars), "digit_frac": sum(ch.isdigit() for ch in text) / float(n_chars),
        "_ink_r": float(ink_rgb[0]), "_ink_g": float(ink_rgb[1]), "_ink_b": float(ink_rgb[2]),
        "_bg_r": float(bg_c[0]), "_bg_g": float(bg_c[1]), "_bg_b": float(bg_c[2]),
        "_bg_l": bg, "_cy": y + h / 2.0, "_bottom": float(y + h), "_top": float(y),
        "_h8": h8, "_o8": o8,
    }
    for i in range(DIST_BINS):
        out[f"h{i}"], out[f"o{i}"] = float(h8[i]), float(o8[i])
    return out


def _robust_z(vals: np.ndarray, own: float) -> float:
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med))) * 1.4826
    scale = max(mad, 0.05 * abs(med), 1e-3)
    return float(np.clip((own - med) / scale, -12, 12))


def _cluster_lines(ms: List[Dict[str, float]], words: List[Dict[str, Any]]) -> List[int]:
    """Own line grouping (words whose vertical centres coincide and heights agree) - more
    dependable on UI layouts than Tesseract's block/paragraph ids alone."""
    order = sorted(range(len(ms)), key=lambda i: ms[i]["_cy"])
    line_of = [-1] * len(ms)
    lines: List[List[int]] = []
    for i in order:
        placed = False
        for li in range(len(lines) - 1, max(-1, len(lines) - 6), -1):
            ref = lines[li]
            cy = np.mean([ms[j]["_cy"] for j in ref])
            hh = np.median([ms[j]["h"] for j in ref])
            if abs(ms[i]["_cy"] - cy) <= 0.45 * min(hh, ms[i]["h"]) and 0.6 < ms[i]["h"] / hh < 1.7:
                ref.append(i)
                line_of[i] = li
                placed = True
                break
        if not placed:
            lines.append([i])
            line_of[i] = len(lines) - 1
    return line_of


FEATURE_NAMES: List[str] = (
    FEATURE_BASE + GEOM
    + [f"z_img_{k}" for k in REL] + [f"z_line_{k}" for k in REL]
    + ["rel_h_line", "base_off_line", "top_off_line", "ink_dist_line", "bg_dist_line", "line_n", "n_words_img",
       "hist_d_img", "hist_d_line", "ori_d_img", "ori_d_line"]
)


def image_word_features(img, words: Optional[List[Dict[str, Any]]] = None
                        ) -> Tuple[np.ndarray, List[Dict[str, Any]], Dict[str, Any]]:
    """Feature matrix for every measurable OCR word of `img` (PIL).

    Returns (X [n, len(FEATURE_NAMES)], words_kept, info)."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    gray = _luma(rgb)
    if words is None:
        words = ocr_words(img)
    # global JPEG grid phase from the whole image
    _, global_phase = _phase_profile(gray, 0, 0)

    ms: List[Dict[str, float]] = []
    kept: List[Dict[str, Any]] = []
    for wd in words:
        if len(wd["text"].strip()) < 2:
            continue  # single glyphs (icons, bullets, OCR noise) are too small to judge reliably
        m = word_measurements(rgb, gray, wd, global_phase)
        if m is not None:
            ms.append(m)
            kept.append(wd)
    info = {"ocr_words": len(words), "measured_words": len(ms), "global_phase": global_phase}
    if len(ms) < 3:
        return np.zeros((0, len(FEATURE_NAMES)), np.float32), kept, info

    n = len(ms)
    line_of = _cluster_lines(ms, kept)
    by_line: Dict[int, List[int]] = {}
    for i, li in enumerate(line_of):
        by_line.setdefault(li, []).append(i)

    allvals = {k: np.array([m[k] for m in ms]) for k in REL}
    H_all = np.array([m["_h8"] for m in ms])
    O_all = np.array([m["_o8"] for m in ms])
    H_med, O_med = np.median(H_all, axis=0), np.median(O_all, axis=0)

    def chi2(a, b):
        return float(0.5 * np.sum((a - b) ** 2 / (a + b + 1e-6)))
    X = np.zeros((n, len(FEATURE_NAMES)), np.float32)
    col = {name: j for j, name in enumerate(FEATURE_NAMES)}
    for i, m in enumerate(ms):
        for k in FEATURE_BASE + GEOM:
            X[i, col[k]] = m[k]
        mates = [j for j in by_line[line_of[i]] if j != i]
        for k in REL:
            others = np.delete(allvals[k], i)
            X[i, col[f"z_img_{k}"]] = _robust_z(others, m[k])
            if len(mates) >= 2:
                X[i, col[f"z_line_{k}"]] = _robust_z(allvals[k][mates], m[k])
        if mates:
            hs = np.array([ms[j]["h"] for j in mates])
            X[i, col["rel_h_line"]] = m["h"] / (np.median(hs) + EPS)
            X[i, col["base_off_line"]] = (m["_bottom"] - np.median([ms[j]["_bottom"] for j in mates])) / m["h"]
            X[i, col["top_off_line"]] = (m["_top"] - np.median([ms[j]["_top"] for j in mates])) / m["h"]
            ink_m = np.median([[ms[j]["_ink_r"], ms[j]["_ink_g"], ms[j]["_ink_b"]] for j in mates], axis=0)
            X[i, col["ink_dist_line"]] = float(np.linalg.norm(
                np.array([m["_ink_r"], m["_ink_g"], m["_ink_b"]]) - ink_m)) / 255.0
            bg_m = np.median([[ms[j]["_bg_r"], ms[j]["_bg_g"], ms[j]["_bg_b"]] for j in mates], axis=0)
            X[i, col["bg_dist_line"]] = float(np.linalg.norm(
                np.array([m["_bg_r"], m["_bg_g"], m["_bg_b"]]) - bg_m)) / 255.0
        X[i, col["line_n"]] = len(mates)
        X[i, col["n_words_img"]] = n
        X[i, col["hist_d_img"]] = chi2(H_all[i], H_med)
        X[i, col["ori_d_img"]] = chi2(O_all[i], O_med)
        if len(mates) >= 2:
            X[i, col["hist_d_line"]] = chi2(H_all[i], np.median(H_all[mates], axis=0))
            X[i, col["ori_d_line"]] = chi2(O_all[i], np.median(O_all[mates], axis=0))
    return X, kept, info


def explain_word(x: np.ndarray, top: int = 3) -> List[str]:
    """Human-readable reasons: which neighbour-relative measurements deviate most."""
    names = {
        "aa_ratio": "anti-aliasing profile", "edge95": "edge sharpness", "ink_q50": "glyph edge softness",
        "ink_chroma": "text colour saturation", "edge_chroma": "colour fringing on glyph edges",
        "lcd_fringe": "sub-pixel (LCD) fringing", "stroke_w": "stroke thickness", "stroke_w2": "stroke thickness",
        "ink_frac": "ink density", "bg_noise_in": "background noise", "noise_ratio": "noise vs surroundings",
        "bg_shift": "background brightness vs surroundings", "seam_max": "rectangular background seam",
        "grid_strength": "JPEG block-grid evidence", "contrast": "text contrast", "sharp_hi": "edge sharpness",
        "char_w": "character width/spacing",
    }
    col = {n: j for j, n in enumerate(FEATURE_NAMES)}
    cands: List[Tuple[float, str]] = []
    for k in REL:
        for pref, where in (("z_line_", "neighbouring words on the same line"), ("z_img_", "the rest of the image")):
            z = abs(float(x[col[pref + k]]))
            if z >= 3.0:
                cands.append((z, f"{names.get(k, k)} differs from {where} (z={z:.1f})"))
    if x[col["seam_sides"]] >= 3:
        cands.append((6.0, "a rectangular background patch outline surrounds the word"))
    if abs(x[col["rel_h_line"]] - 1) > 0.18 and x[col["line_n"]] >= 2:
        cands.append((5.0, "text height does not match the rest of its line"))
    if abs(x[col["base_off_line"]]) > 0.09 and x[col["line_n"]] >= 2:
        cands.append((5.0, "baseline is offset from the rest of its line"))
    if x[col["ink_dist_line"]] > 0.12 and x[col["line_n"]] >= 2:
        cands.append((4.5, "text colour differs from its line"))
    cands.sort(reverse=True)
    seen, out = set(), []
    for _, s in cands:
        key = s.split(" differs")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= top:
            break
    return out
