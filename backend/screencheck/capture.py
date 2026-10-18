"""Capture-path profile: what happened to the file after the screenshot was taken.

Everything here comes from the file itself, not from the filename. The profile decides how much weight
pixel-level checks deserve: a re-compressed or down-scaled image has lost most of the evidence they need.
"""
from __future__ import annotations

from typing import Any, Dict

from PIL import Image


def _jpeg_quality(img: Image.Image) -> float | None:
    """Rough JPEG quality estimate from the luminance quantisation table (None if not a JPEG)."""
    q = getattr(img, "quantization", None)
    if not q:
        return None
    table = q.get(0) or next(iter(q.values()))
    avg = sum(table) / len(table)
    # libjpeg: scale = 5000/Q (Q<50) or 200-2Q; base table average is ~57.6 (luminance)
    scale = avg / 57.6 * 100
    quality = (5000 / scale) if scale > 100 else (200 - scale) / 2
    return round(max(1.0, min(100.0, quality)), 1)


def profile(img: Image.Image, fmt: str | None) -> Dict[str, Any]:
    w, h = img.size
    fmt = (fmt or "").upper()
    quality = _jpeg_quality(img) if fmt == "JPEG" else None
    info = getattr(img, "info", {}) or {}
    lossless = fmt == "PNG" or (fmt == "WEBP" and bool(info.get("lossless")))
    lossy_webp = fmt == "WEBP" and not lossless
    aspect = h / w if w else 0.0
    phone_like = aspect >= 1.6 and w <= 1500
    desktop_like = w > h or w >= 1100
    notes = []
    reliability = "high"
    if fmt == "JPEG":
        reliability = "reduced" if (quality or 100) >= 85 else "low"
        notes.append(f"JPEG file (estimated quality {quality}); pixel-level evidence is partly destroyed by compression.")
    elif lossy_webp:
        reliability = "reduced"
        notes.append("Lossy WebP file; pixel-level evidence is partly destroyed by compression.")
    elif lossless:
        notes.append("Lossless file; pixel-level evidence is preserved, but it may still be a re-save of a compressed image.")
    return {
        "format": fmt or None, "width": w, "height": h, "aspect": round(aspect, 3),
        "megapixels": round(w * h / 1e6, 2), "lossless": lossless, "jpeg_quality": quality,
        "phone_like": phone_like, "desktop_like": desktop_like,
        "pixel_reliability": reliability, "notes": notes,
    }
