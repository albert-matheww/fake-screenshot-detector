"""Compare mode: when a genuine copy exists, show exactly what differs.

Needs no learned model and no assumptions about how the edit was made, so it also finds edits typed in the matching font.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage as ndi

import textforensics as tf


def _load(raw: bytes):
    im = Image.open(io.BytesIO(raw))
    im.load()
    lossy = (im.format == "JPEG") or (im.format == "WEBP" and not im.info.get("lossless"))
    return ImageOps.exif_transpose(im).convert("RGB"), lossy


def _norm(t: str) -> str:
    return re.sub(r"[^\w]", "", t.lower())


def _iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a["left"], a["top"], a["left"] + a["width"], a["top"] + a["height"]
    bx0, by0, bx1, by1 = b["left"], b["top"], b["left"] + b["width"], b["top"] + b["height"]
    iw, ih = max(0, min(ax1, bx1) - max(ax0, bx0)), max(0, min(ay1, by1) - max(ay0, by0))
    inter = iw * ih
    return inter / float(a["width"] * a["height"] + b["width"] * b["height"] - inter + 1e-9)


def compare_bytes(original: bytes, suspect: bytes) -> Dict[str, Any]:
    (a, a_lossy), (b, b_lossy) = _load(original), _load(suspect)
    if abs(a.height / a.width - b.height / b.width) > 0.03:
        return {"status": "layout_mismatch",
                "message": "The two images have different proportions, so they cannot be compared position by position "
                           "(different crop, device or window size)."}
    rescaled = a.size != b.size
    if rescaled:
        b = b.resize(a.size, Image.LANCZOS)
    # blur both before differencing: compression noise lives at the glyph edges, real edits change whole glyphs
    A = ndi.gaussian_filter(np.asarray(a, np.float32), sigma=(1.4, 1.4, 0))
    B = ndi.gaussian_filter(np.asarray(b, np.float32), sigma=(1.4, 1.4, 0))
    diff = np.abs(A - B).max(2)
    thr = 38.0 if rescaled else 30.0
    mask = ndi.binary_opening(diff > thr, structure=np.ones((3, 3)))
    mask = ndi.binary_dilation(mask, iterations=5)
    lab, n = ndi.label(mask)
    min_area = max(60, int(0.00005 * a.width * a.height))
    regions: List[Dict[str, Any]] = []
    for i, sl in enumerate(ndi.find_objects(lab)):
        area = int((lab[sl] == i + 1).sum())
        if area < min_area:
            continue
        regions.append({"x": int(sl[1].start), "y": int(sl[0].start), "w": int(sl[1].stop - sl[1].start),
                        "h": int(sl[0].stop - sl[0].start), "area": area, "text": "", "score": 0.0, "level": "evidence",
                        "reasons": ["pixels differ from the original here"]})
    ow, sw = tf.ocr_words(a), tf.ocr_words(b)
    changes: List[Dict[str, Any]] = []
    for w in sw:
        best = max(ow, key=lambda o: _iou(w, o), default=None)
        if best is not None and _iou(w, best) >= 0.3:
            if _norm(w["text"]) != _norm(best["text"]) and min(w["conf"], best["conf"]) >= 40:
                changes.append({"type": "changed", "original": best["text"], "suspect": w["text"],
                                "box": [w["left"], w["top"], w["width"], w["height"]]})
        elif w["conf"] >= 60 and len(_norm(w["text"])) >= 2:
            changes.append({"type": "added", "original": "", "suspect": w["text"], "box": [w["left"], w["top"], w["width"], w["height"]]})
    for o in ow:
        if o["conf"] >= 60 and len(_norm(o["text"])) >= 2 and max((_iou(o, w) for w in sw), default=0.0) < 0.3:
            changes.append({"type": "removed", "original": o["text"], "suspect": "", "box": [o["left"], o["top"], o["width"], o["height"]]})
    # OCR is unstable under compression, so a text difference only counts where the pixels differ too
    def inside_region(c):
        cx, cy = c["box"][0] + c["box"][2] / 2, c["box"][1] + c["box"][3] / 2
        return any(r["x"] <= cx <= r["x"] + r["w"] and r["y"] <= cy <= r["y"] + r["h"] for r in regions)
    changes = [c for c in changes if inside_region(c)]
    for r in regions:
        inside = [c for c in changes if r["x"] <= c["box"][0] + c["box"][2] / 2 <= r["x"] + r["w"] and r["y"] <= c["box"][1] + c["box"][3] / 2 <= r["y"] + r["h"]]
        if inside:
            r["text"] = " / ".join(f'{c["original"] or "-"} -> {c["suspect"] or "-"}' for c in inside[:3])
    changed_pct = round(100.0 * float(mask.sum()) / mask.size, 3)
    found = bool(regions or changes)
    return {
        "status": "differences_found" if found else "no_difference",
        "message": ("The suspect image differs from the original; the marked regions and text changes show where."
                    if found else "No visible difference above the noise level. This does not cover edits made before the original was saved."),
        "rescaled": rescaled, "caution": ("One of the images is lossy-compressed; small marked areas can be compression noise, so confirm each region by eye." if (a_lossy or b_lossy) else ""), "changed_area_percent": changed_pct, "regions": regions[:30], "text_changes": changes[:60],
        "image": {"width": a.width, "height": a.height},
    }
