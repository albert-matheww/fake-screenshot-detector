"""Core forensic analysis functions.

Implements Error Level Analysis (ELA) plus complementary cues described in
the design doc: EXIF/metadata inspection, JPEG quantization-table checks,
block-noise-consistency analysis, and a lightweight copy-move (clone)
detector — all techniques from photograph forensics. On top of those,
"Screenshot-specific rendering cues" below adds signal classes specific to
*rendered UI* rather than photographs: text-rendering (font/anti-aliasing)
consistency, resampling/edge-sharpness consistency, duplicated-device-chrome
detection, and printed-number arithmetic consistency. Each cue returns a
bounded 0-1 "score" (higher = more suspicious) plus the raw evidence used to
compute it, so results stay explainable.

`analyze_image_bytes` is the single entry point used by the Flask API: it
runs every cue and hands the resulting feature vector to
`model_loader.predict_fake` for a final verdict.
"""
import base64
import hashlib
import io
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ExifTags

try:
    import pytesseract
except ImportError:  # pragma: no cover - OCR is optional at import time
    pytesseract = None

from model_loader import predict_fake


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _largest_connected_component(mask: np.ndarray) -> int:
    """Size of the largest 4-connected True-region in a 2D boolean grid.

    Used to distinguish a compact, localized anomaly (consistent with a
    pasted-in region) from the same number of flagged blocks scattered
    diffusely across the image (usually just content complexity or JPEG
    noise, not tampering).
    """
    bh, bw = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    best = 0
    for i in range(bh):
        for j in range(bw):
            if mask[i, j] and not visited[i, j]:
                stack = [(i, j)]
                visited[i, j] = True
                size = 0
                while stack:
                    y, x = stack.pop()
                    size += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < bh and 0 <= nx < bw and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                best = max(best, size)
    return best


def _local_outlier_mask(values: np.ndarray, neighborhood: int = 3, z_thresh: float = 5.0) -> np.ndarray:
    """Flag cells that are strong statistical outliers relative to their own
    local spatial neighborhood, rather than the whole image's distribution.

    A global threshold (comparing every block against the image-wide median)
    conflates "this block has real content" with "this block was tampered
    with": on mostly-flat UI screenshots, any block that merely contains an
    edge, icon, or line of text already looks like an outlier next to a
    sea of flat background blocks, regardless of whether it was edited. A
    local baseline fixes this: a block in a naturally detailed area isn't
    flagged, because its *neighbors* are similarly elevated. Only a block
    that disagrees with its immediate surroundings — the actual signature
    of a localized splice — gets flagged.
    """
    bh, bw = values.shape
    mask = np.zeros((bh, bw), dtype=bool)
    pad = neighborhood
    padded = np.pad(values.astype(np.float64), pad, mode="edge")
    for i in range(bh):
        for j in range(bw):
            window = padded[i:i + 2 * pad + 1, j:j + 2 * pad + 1].flatten()
            cy, cx = pad, pad
            center_idx = cy * (2 * pad + 1) + cx
            center_val = window[center_idx]
            local_vals = np.delete(window, center_idx)
            median = np.median(local_vals)
            mad = np.median(np.abs(local_vals - median)) or 1e-6
            z = (center_val - median) / (1.4826 * mad)
            mask[i, j] = z > z_thresh
    return mask


def _ocr_data(image: Image.Image) -> Dict[str, Any]:
    """Runs Tesseract once and returns plain text, per-word bounding boxes,
    and per-line groupings — enough for check_document_text,
    check_font_consistency, check_chrome_consistency, and
    check_amount_consistency to all share a single OCR pass instead of
    running Tesseract redundantly, since it's one of the more expensive
    steps in this pipeline. Every one of those cues also accepts a plain
    `image` and computes this internally if not given one, so each stays
    independently callable/testable like every other cue in this module —
    only analyze_image_bytes bothers to share a single call.
    """
    if pytesseract is None:
        return {"text": "", "words": [], "lines": [], "available": False}
    try:
        data = pytesseract.image_to_data(image.convert("RGB"), output_type=pytesseract.Output.DICT)
    except Exception:
        return {"text": "", "words": [], "lines": [], "available": False}

    words: List[Dict[str, Any]] = []
    texts: List[str] = []
    line_order: List[Tuple[int, int, int]] = []
    line_words: Dict[Tuple[int, int, int], List[str]] = {}

    for i in range(len(data.get("text", []))):
        text = data["text"][i].strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not text or conf < 0:
            continue  # Tesseract emits empty/-1-conf rows for structural (block/line) entries

        words.append({
            "text": text, "left": int(data["left"][i]), "top": int(data["top"][i]),
            "width": int(data["width"][i]), "height": int(data["height"][i]), "conf": conf,
        })
        texts.append(text)

        line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if line_key not in line_words:
            line_words[line_key] = []
            line_order.append(line_key)
        line_words[line_key].append(text)

    lines = [" ".join(line_words[k]) for k in line_order]
    return {"text": " ".join(texts), "words": words, "lines": lines, "available": True}


# ---------------------------------------------------------------------------
# Error Level Analysis
# ---------------------------------------------------------------------------

def compute_ela(image: Image.Image, quality: int = 90) -> Tuple[Image.Image, np.ndarray]:
    """Recompress `image` at `quality` and diff it against the original.

    Returns (amplified ELA image for display, raw uint8 diff array for scoring).
    Regions that were edited after the image's last "true" JPEG save tend to
    re-compress differently than untouched regions, producing localized
    bright spots in the diff.
    """
    rgb = image.convert("RGB")
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer).convert("RGB")

    diff = ImageChops.difference(rgb, recompressed)
    diff_arr = np.array(diff, dtype=np.uint8)

    max_diff = int(diff_arr.max()) if diff_arr.size else 0
    scale = 255.0 / max_diff if max_diff != 0 else 1.0
    amplified = np.clip(diff_arr.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    ela_image = Image.fromarray(amplified, mode="RGB")

    return ela_image, diff_arr


def ela_feature_score(diff_arr: np.ndarray, block_size: int = 16) -> Dict[str, float]:
    """Turn a raw ELA diff array into bounded, interpretable features.

    Flags blocks whose recompression error is a statistical outlier
    relative to their *local neighborhood* (see `_local_outlier_mask`)
    rather than the image's global distribution — this is what lets the
    cue tell "a naturally detailed area of the screenshot" apart from "a
    small region that recompresses differently than everywhere around it",
    which a global mean/std or global-MAD threshold cannot distinguish on
    mostly-flat UI content. The size of the largest contiguous flagged
    cluster is the primary signal: a compact hot patch is the signature of
    a localized paste edit, while the same block count scattered around is
    ordinary content complexity.
    """
    gray = diff_arr.mean(axis=2)
    mean_diff = float(gray.mean())
    std_diff = float(gray.std())

    h, w = gray.shape
    bh, bw = h // block_size, w // block_size
    if bh >= 5 and bw >= 5:
        cropped = gray[: bh * block_size, : bw * block_size]
        block_means = cropped.reshape(bh, block_size, bw, block_size).mean(axis=(1, 3))
        hot_mask = _local_outlier_mask(block_means)
        hotspot_ratio = float(hot_mask.mean())
        cluster_size = _largest_connected_component(hot_mask)
        cluster_ratio = cluster_size / (bh * bw)
    else:
        hotspot_ratio = 0.0
        cluster_size = 0
        cluster_ratio = 0.0

    # NOTE: these constants were calibrated against a synthetically
    # generated real/tampered corpus (see backend/tools/calibrate.py) since
    # no real labeled dataset exists for this project (see README) — they
    # are not validated against real-world forgeries.
    #
    # Cluster size is scored as an *absolute* block count (saturating at a
    # handful of blocks), not as a fraction of the whole image: a real
    # tamper (e.g. one balance figure) is often only a few blocks even on a
    # large screenshot, so normalizing by total block count would make a
    # perfectly-localized detection score near zero simply because the
    # image is big.
    cluster_term = min(1.0, cluster_size / 4.0)
    score = min(1.0, (cluster_term * 0.85) + (hotspot_ratio * 0.3) + min(mean_diff / 80.0, 0.1))
    return {
        "mean_diff": round(mean_diff, 4),
        "std_diff": round(std_diff, 4),
        "hotspot_ratio": round(hotspot_ratio, 4),
        "cluster_ratio": round(cluster_ratio, 4),
        "cluster_size": int(cluster_size),
        "score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# JPEG Ghost — multi-quality recompression (double-compression detection)
# ---------------------------------------------------------------------------

GHOST_QUALITIES: List[int] = list(range(50, 100, 5))  # 50, 55, ..., 95
GHOST_MAX_DIM = 700


def compute_jpeg_ghost(image: Image.Image, block_size: int = 16,
                        qualities: List[int] = None) -> Dict[str, Any]:
    """JPEG Ghost analysis (Farid): recompress the image at a range of
    candidate qualities and, per block, look for a candidate quality where
    the recompression diff forms a genuine *local minimum* relative to its
    neighboring qualities in the scan.

    The naive version of this idea (just take argmin diff over the whole
    quality range) doesn't work: recompression diff decreases roughly
    monotonically as quality rises toward lossless for almost any content,
    so a plain argmin always lands on the highest quality tested regardless
    of tampering, producing no signal at all. The actual diagnostic (per
    Farid's original method) is a *local* dip in the diff curve at a block's
    own native compression quality — recompressing at the quality a block
    was already quantized to is closer to a no-op than compressing at any
    neighboring quality, on either side. Blocks whose curve never dips
    (monotonic across the whole tested range) are inconclusive and excluded
    rather than forced into a spurious answer.

    A region edited and re-saved at a different quality than the rest of
    the image (the single most common real-world screenshot tamper — change
    a number, export again) shows up as a cluster of blocks whose dip
    location disagrees with the rest of the frame.
    """
    qualities = qualities or GHOST_QUALITIES
    rgb = image.convert("RGB")
    w, h = rgb.size
    if max(w, h) > GHOST_MAX_DIM:
        scale = GHOST_MAX_DIM / max(w, h)
        rgb = rgb.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    w, h = rgb.size
    gray = np.array(rgb.convert("L"), dtype=np.float32)

    bh, bw = h // block_size, w // block_size
    if bh < 3 or bw < 3:
        return {"score": 0.0, "note": "Image too small for JPEG ghost analysis."}

    block_diffs = np.zeros((len(qualities), bh, bw), dtype=np.float32)
    for qi, q in enumerate(qualities):
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=q)
        buf.seek(0)
        recompressed = np.array(Image.open(buf).convert("L"), dtype=np.float32)
        diff = np.abs(gray - recompressed)
        cropped = diff[: bh * block_size, : bw * block_size]
        block_diffs[qi] = cropped.reshape(bh, block_size, bw, block_size).mean(axis=(1, 3))

    n_q = len(qualities)
    span = block_diffs.max(axis=0) - block_diffs.min(axis=0)  # (bh, bw)

    # For each interior quality index, is it a local minimum, and how deep
    # (relative to the block's own dynamic range) is the dip?
    dip_idx = np.full((bh, bw), -1, dtype=np.int64)
    dip_depth = np.zeros((bh, bw), dtype=np.float32)
    for qi in range(1, n_q - 1):
        center = block_diffs[qi]
        left = block_diffs[qi - 1]
        right = block_diffs[qi + 1]
        is_min = (center < left) & (center < right)
        neighbor_avg = (left + right) / 2.0
        depth = np.where(span > 1e-6, (neighbor_avg - center) / np.maximum(span, 1e-6), 0.0)
        better = is_min & (depth > dip_depth)
        dip_idx = np.where(better, qi, dip_idx)
        dip_depth = np.where(better, depth, dip_depth)

    # A block only "votes" if it has a real dip (not monotonic) with enough
    # relative depth to trust, on a curve with enough dynamic range to be
    # informative in the first place.
    informative = (dip_idx >= 0) & (dip_depth > 0.15) & (span > 1.5)
    if not informative.any():
        return {"score": 0.0, "note": "No blocks showed a conclusive native-quality dip."}

    # Compare each block's dip location to its *local* neighborhood rather
    # than a single whole-image dominant quality: a large region that's
    # legitimately more/less detailed than the rest (e.g. a card vs. plain
    # background) can consistently read a different "native quality" across
    # its whole area without being tampered, which a single global mode
    # would misflag wholesale. Non-informative blocks are filled with the
    # global median dip so they act as neutral filler in their neighbors'
    # local baselines instead of skewing them.
    fill_value = float(np.median(dip_idx[informative]))
    filled_dip_idx = np.where(informative, dip_idx, fill_value).astype(np.float64)
    local_outliers = _local_outlier_mask(filled_dip_idx)
    outlier_mask = informative & local_outliers
    total_informative = int(informative.sum())

    counts = np.bincount(dip_idx[informative].flatten(), minlength=n_q)
    dominant_idx = int(counts.argmax())
    outlier_ratio = float(outlier_mask.sum()) / total_informative
    cluster_size = _largest_connected_component(outlier_mask)
    cluster_ratio = cluster_size / (bh * bw)

    # Absolute block count, not a fraction of the whole image — see the
    # matching note in ela_feature_score for why.
    cluster_term = min(1.0, cluster_size / 3.0)
    score = min(1.0, (cluster_term * 0.85) + (outlier_ratio * 0.3))
    return {
        "dominant_quality": qualities[dominant_idx],
        "informative_block_ratio": round(total_informative / (bh * bw), 4),
        "outlier_block_ratio": round(outlier_ratio, 4),
        "largest_cluster_ratio": round(cluster_ratio, 4),
        "largest_cluster_size": int(cluster_size),
        "qualities_tested": qualities,
        "score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# Metadata / EXIF
# ---------------------------------------------------------------------------

def check_metadata(image: Image.Image) -> Dict[str, Any]:
    exif_raw = image.getexif()
    fields: Dict[str, str] = {}
    if exif_raw:
        for tag_id, value in exif_raw.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if isinstance(value, bytes):
                try:
                    value = value.decode(errors="replace")
                except Exception:
                    value = str(value)
            fields[str(tag)] = str(value)[:200]

    suspicious: List[str] = []
    weight = 0.0
    software = fields.get("Software", "")
    editing_tools = ["photoshop", "gimp", "paint.net", "pixelmator", "affinity", "canva"]
    if any(tool in software.lower() for tool in editing_tools):
        # An editing-tool fingerprint is close to a smoking gun for something
        # submitted as an untouched screenshot — a real phone/app screenshot
        # exporter never stamps this tag. Weighted much higher than the
        # other, more circumstantial flags below.
        suspicious.append(f"Software tag indicates an editing tool was used: {software}")
        weight += 1.0

    has_gps = any(k.lower().startswith("gps") for k in fields)
    if has_gps:
        suspicious.append("GPS metadata present (stripped before any storage/response logging)")
        weight += 0.5

    # Screenshots normally carry no EXIF at all. Camera-style tags (Make/Model)
    # on something submitted as a screenshot is a flag; total absence of EXIF
    # is the expected, unremarkable case and should NOT be treated as suspicious.
    has_camera_tags = "Make" in fields or "Model" in fields
    if has_camera_tags:
        suspicious.append("Camera EXIF (Make/Model) present on an image submitted as a screenshot")
        weight += 0.5

    metadata_score = min(1.0, weight)
    return {
        "has_exif": bool(fields),
        "fields": fields,
        "suspicious_flags": suspicious,
        "score": round(metadata_score, 4),
    }


# ---------------------------------------------------------------------------
# Document text (OCR) — watermark / placeholder-data detection
# ---------------------------------------------------------------------------

# Known fake-statement / fake-document generator brand markers and generic
# "this isn't real" disclaimers that such generators leave in the image
# itself (often as a watermark, sometimes removed only in a paid tier).
_GENERATOR_WATERMARKS = [
    "bankstatements.net", "bank statements.net", "thepaystubs", "paystubcreator",
    "stubcreator", "makereceipt", "receiptmakerly", "docutemplates",
    "specimen", "sample statement", "not a real bank statement",
    "for novelty purposes only", "for entertainment purposes only",
    "this is not a real", "template only", "demo purposes only",
    "not a real document", "not an official document",
]

# Placeholder names generators default to when the user hasn't customized them.
_PLACEHOLDER_NAMES = ["john doe", "jane doe", "john smith", "test user", "sample name"]

# Obviously fabricated account/routing numbers: 6+ repeated digits, or the
# textbook placeholder sequences "123456789" / "987654321".
_PLACEHOLDER_NUMBER_RE = re.compile(r"(\d)\1{5,}|123456789|987654321")


def check_document_text(image: Image.Image, ocr_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """OCR the image and check its actual text content for tampering signals
    that pixel-level forensics (ELA, noise, clone detection) cannot see at
    all: a known fake-statement-generator's own watermark, or an obviously
    placeholder name/account number. These are near-conclusive once read —
    a real financial institution never watermarks its own statements with a
    third-party generator's brand, and a real customer's statement doesn't
    say "John Doe" — but a purely pixel-based pipeline has no way to notice
    them, regardless of how much compression-artifact analysis it does.
    """
    if ocr_data is None:
        ocr_data = _ocr_data(image)
    if not ocr_data.get("available"):
        return {"score": 0.0, "note": "OCR not available in this environment.", "matched_flags": []}

    text = ocr_data["text"]
    lower = text.lower()
    flags: List[str] = []

    for marker in _GENERATOR_WATERMARKS:
        if marker in lower:
            flags.append(f'Text contains a known fake-document-generator marker: "{marker}"')

    for name in _PLACEHOLDER_NAMES:
        if name in lower:
            flags.append(f'Text contains a placeholder name: "{name}"')

    if _PLACEHOLDER_NUMBER_RE.search(lower.replace(" ", "")):
        flags.append("Text contains an obviously placeholder account/routing number "
                      "(repeated or sequential digits)")

    # Any single match here is close to conclusive, unlike the pixel-level
    # cues elsewhere in this module — score accordingly.
    score = min(1.0, 0.9 * len(flags)) if flags else 0.0
    return {
        "score": round(score, 4),
        "matched_flags": flags,
        "extracted_text_length": len(text.strip()),
    }


# ---------------------------------------------------------------------------
# Screenshot-specific rendering cues
#
# Every cue above this point comes from photograph forensics (ELA, JPEG
# Ghost, quantization, noise) or is agnostic to content type (EXIF, OCR
# text matching). Screenshots are *rendered UI*, not photographs, which
# opens up signal classes those techniques were never designed to see: how
# consistently the text itself was rasterized, whether a region was
# resampled at a different scale than its surroundings, whether a document's
# own printed numbers contradict each other, and whether device chrome
# looks duplicated. These are newer and less battle-tested than the cues
# above — see each docstring for how they're deliberately scoped to avoid
# false-positive-prone assumptions, and see calibrate.py for measured
# reliability before trusting any of them in fake_score.
# ---------------------------------------------------------------------------

def check_font_consistency(image: Image.Image, ocr_data: Optional[Dict[str, Any]] = None,
                            min_words: int = 6) -> Dict[str, Any]:
    """Flags text whose rendering (anti-aliasing / edge softness) is
    inconsistent with the rest of the document's text — the signature of
    text pasted in from a different rendering source (a different OS, a
    screenshot tool, or a photo editor) than whatever rendered the rest of
    the screen. The pixel-level cues elsewhere in this module look at
    compression/noise artifacts; this looks at how the *glyphs themselves*
    were drawn, a signal specific to rendered text that has no equivalent
    in photograph forensics.

    Unlike the block-grid cues (ELA, noise, edge-sharpness), OCR'd text
    regions are sparse and irregularly placed, so there's no dense spatial
    grid to build a *local* neighborhood baseline from (see
    _local_outlier_mask's docstring for why that matters elsewhere) —
    instead each region is compared against the robust median of every
    OTHER text region in the same image, the closest available equivalent
    baseline when regions aren't on a grid.

    STATUS: implemented but NOT validated — unlike check_amount_consistency
    and check_chrome_consistency below, direct testing could not confirm
    this cue actually fires on a genuine mismatch. A deliberately
    constructed test image (normal text next to a hard-thresholded,
    anti-aliasing-free copy of the same text) produced near-identical
    "sharpness" values for both, well under the outlier threshold — either
    Pillow's bundled default font doesn't carry enough anti-aliasing at
    typical sizes for gradient-based sharpness to distinguish, or the
    edge-steepness/contrast metric itself isn't sensitive enough. On real
    corpus data it also never fires (no false positives, but no evidence of
    true positives either). Computed and reported for transparency, same as
    ghost_score, but do not treat a nonzero value here as trustworthy until
    it's validated against genuinely different rendering sources (e.g. text
    rasterized by two different real font engines, not a synthetic proxy).
    """
    if ocr_data is None:
        ocr_data = _ocr_data(image)
    if not ocr_data.get("available") or len(ocr_data.get("words", [])) < min_words:
        return {"score": 0.0, "note": "Not enough OCR'd text to compare font rendering.", "region_count": 0}

    gray = np.array(image.convert("L"), dtype=np.float32)
    h, w = gray.shape

    sharpness: List[float] = []
    for word in ocr_data["words"]:
        if len(word["text"]) < 2:
            continue  # single characters are too small to measure reliably
        x0, y0 = max(0, word["left"] - 2), max(0, word["top"] - 2)
        x1, y1 = min(w, word["left"] + word["width"] + 2), min(h, word["top"] + word["height"] + 2)
        if x1 - x0 < 6 or y1 - y0 < 6:
            continue
        region = gray[y0:y1, x0:x1]

        # Edge steepness normalized by the region's own ink/background
        # contrast, so a naturally low-contrast region (e.g. light-gray
        # text) isn't penalized relative to a high-contrast one — only the
        # *shape* of the transition (hard vs. anti-aliased) should matter.
        contrast = float(region.max() - region.min())
        if contrast < 10:
            continue  # too flat to have measurable text edges (likely an OCR false positive)
        gx = np.abs(np.diff(region, axis=1))
        gy = np.abs(np.diff(region, axis=0))
        edge_energy = (float(gx.mean()) if gx.size else 0.0) + (float(gy.mean()) if gy.size else 0.0)
        sharpness.append(edge_energy / contrast)

    if len(sharpness) < min_words:
        return {"score": 0.0, "note": "Not enough measurable text regions to compare font rendering.",
                "region_count": len(sharpness)}

    values = np.array(sharpness)
    median = np.median(values)
    mad = np.median(np.abs(values - median)) or 1e-6
    z = (values - median) / (1.4826 * mad)
    outliers = z > 4.5

    outlier_ratio = float(outliers.mean())
    max_z = float(z.max())
    # A single wildly-inconsistent region matters more than a low ratio
    # across many regions — most screenshots only have a handful of
    # distinct text blocks, so this saturates on absolute deviation rather
    # than requiring many outliers before it fires at all.
    score = min(1.0, max(0.0, (max_z - 4.5) / 6.0) * 0.7 + outlier_ratio * 0.5)
    return {
        "region_count": len(sharpness),
        "outlier_region_count": int(outliers.sum()),
        "outlier_ratio": round(outlier_ratio, 4),
        "max_z_score": round(max_z, 4),
        "score": round(score, 4),
    }


def check_edge_sharpness_consistency(image: Image.Image, block_size: int = 16) -> Dict[str, Any]:
    """Flags a block whose UI-edge sharpness (how steep the transition is
    across a strong straight edge — a button border, a divider, a card
    outline) is a local outlier relative to its neighborhood.

    This is a deliberately narrower, implementable version of "does this
    region's content align with the rest of the UI" than literal pixel-grid/
    DPI-snap detection: different UI elements in a real screenshot
    legitimately don't all share one pixel grid, so grid-alignment isn't a
    reliable invariant across arbitrary UI frameworks. *Resampling blur* is
    a real, meaningful signal instead — a region pasted in at a different
    scale than its surroundings picks up interpolation blur that a
    natively-rendered, unscaled region doesn't have, and that shows up as a
    local dip in edge steepness. Same local-neighborhood rationale as
    ela_feature_score/estimate_noise_inconsistency (see
    _local_outlier_mask).

    STATUS: tested and found NOT reliable on this content type — same fate
    as ghost_score, for a related reason. Direct testing against real
    screenshot content (not just the synthetic corpus) showed this cue
    saturates near the top of its range (~0.84-0.95) on ordinary,
    untampered screenshots across every category tried, and does not
    increase — it slightly *decreased* in one direct test — when a genuine
    resampled/blurred patch is pasted in. Root cause: flat UI content
    legitimately has widely varying local edge sharpness block-to-block
    (a vector-rendered card border next to a soft drop-shadow next to
    dense small text), so "local outlier in edge sharpness" fires on
    ordinary layout structure almost everywhere, not just on tampering —
    a more severe version of the same flat-UI weakness ELA and JPEG Ghost
    already have (see README's "Known limitations"). A percentile-based
    fix (measuring the block's strongest edges rather than its mean, to
    remove the edge-density confound) was tried and did not resolve it.
    Kept computed and shown for transparency, exactly like ghost_score;
    excluded from fake_score, and should not be trusted without a
    fundamentally different approach (e.g. explicit periodic-artifact
    detection for resampling, rather than local sharpness variance).
    """
    gray = np.array(image.convert("L"), dtype=np.float32)
    h, w = gray.shape
    gx = np.abs(np.diff(gray, axis=1, append=gray[:, -1:]))
    gy = np.abs(np.diff(gray, axis=0, append=gray[-1:, :]))
    edge = gx + gy

    bh, bw = h // block_size, w // block_size
    if bh < 5 or bw < 5:
        return {"score": 0.0, "note": "Image too small for edge-sharpness analysis."}

    cropped_edge = edge[: bh * block_size, : bw * block_size]
    cropped_gray = gray[: bh * block_size, : bw * block_size]
    gray_blocks = cropped_gray.reshape(bh, block_size, bw, block_size)
    # transpose before collapsing the per-block pixels into one axis — a
    # plain .reshape(bh, bw, -1) here would NOT group each spatial block's
    # own pixels together (reshape reinterprets the flat buffer, it doesn't
    # reorder axes), silently computing the percentile over scrambled data.
    edge_blocks = cropped_edge.reshape(bh, block_size, bw, block_size).transpose(0, 2, 1, 3) \
        .reshape(bh, bw, block_size * block_size)

    # The 90th-percentile edge magnitude in a block (how steep its
    # *strongest* edges are), not the block mean: averaging over every
    # pixel conflates edge sharpness with edge *density* (a text-dense
    # block has many edge pixels diluting the mean differently than a
    # single card border does), which isn't what this cue is trying to
    # measure and made it fire almost everywhere on real screenshots
    # during smoke-testing — a block-density confound, not a real signal.
    block_edge_p90 = np.percentile(edge_blocks, 90, axis=2)
    block_contrast = gray_blocks.max(axis=(1, 3)) - gray_blocks.min(axis=(1, 3))

    # Only blocks with a real edge in them are informative — a flat block
    # has no edge to measure sharpness on (same rationale as the clone
    # detector skipping near-uniform blocks).
    informative = block_contrast > 20
    if int(informative.sum()) < 10:
        return {"score": 0.0, "note": "Not enough textured/edged blocks for edge-sharpness analysis."}

    sharpness = np.where(informative, block_edge_p90 / np.maximum(block_contrast, 1e-6), np.nan)
    fill_value = float(np.nanmedian(sharpness))
    filled = np.where(informative, sharpness, fill_value)

    outlier_mask = _local_outlier_mask(filled) & informative
    cluster_size = _largest_connected_component(outlier_mask)
    outlier_ratio = float(outlier_mask.sum()) / max(1, int(informative.sum()))

    cluster_term = min(1.0, cluster_size / 4.0)
    score = min(1.0, (cluster_term * 0.8) + (outlier_ratio * 0.3))
    return {
        "informative_block_ratio": round(float(informative.mean()), 4),
        "outlier_block_ratio": round(outlier_ratio, 4),
        "largest_cluster_size": int(cluster_size),
        "score": round(score, 4),
    }


_TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")


def check_chrome_consistency(image: Image.Image, ocr_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Flags the status-bar clock reading being repeated verbatim elsewhere
    in a phone-shaped screenshot — the signature of a screenshot-of-a-
    screenshot or a composite with two layers of device chrome, both real,
    low-effort ways to fake a screenshot.

    Deliberately narrow, twice over. First: without the submitter declaring
    which platform a screenshot claims to be from, there's no ground truth
    to validate a clock/battery/carrier readout *against* (this project's
    general stance on not forcing signal where there isn't a reliable
    invariant to check — see README's "Known limitations"), so this checks
    for literal duplication, not "wrong-looking" chrome. Second, and found
    empirically during this cue's own calibration: an earlier version
    flagged *any* H:MM-shaped text found outside the top strip, which
    false-positives constantly — most receipt/payment screenshots
    legitimately print their own transaction timestamp in the body, and
    that's a real time, just not the status bar's. Only an EXACT match
    between the top-strip reading and a reading elsewhere is a genuine
    invariant: a real transaction timestamp is essentially never the exact
    same minute as when the screenshot itself was taken, but a duplicated
    chrome layer reproduces the identical string.
    """
    if ocr_data is None:
        ocr_data = _ocr_data(image)
    w, h = image.size
    if h < w * 1.2:
        return {"score": 0.0, "applicable": False, "note": "Not a phone-shaped screenshot; chrome check skipped."}
    if not ocr_data.get("available"):
        return {"score": 0.0, "applicable": False, "note": "OCR not available."}

    top_strip_height = max(24, int(h * 0.06))
    top_matches: List[str] = []
    other_matches: List[str] = []
    for word in ocr_data["words"]:
        m = _TIME_PATTERN.search(word["text"])
        if not m:
            continue
        (top_matches if word["top"] < top_strip_height else other_matches).append(m.group(0))

    duplicates = sorted(set(top_matches) & set(other_matches))
    if not duplicates:
        return {
            "score": 0.0, "applicable": True, "top_strip_reading": top_matches[:1],
            "note": "No exact duplicate of the status-bar reading found elsewhere in the image.",
        }
    return {
        "score": 0.6, "applicable": True, "top_strip_reading": top_matches[:1],
        "duplicate_readings": duplicates,
        "note": "The status-bar clock reading is repeated verbatim elsewhere in the image — possible "
                "duplicated/composited device chrome (e.g. a screenshot of a screenshot).",
    }


_AMOUNT_RE = re.compile(r"\$\s?([\d][\d,]*\.\d{2})")


def _line_amount(line: str) -> Optional[float]:
    m = _AMOUNT_RE.search(line)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def check_amount_consistency(image: Image.Image, ocr_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Flags a document whose own printed numbers contradict each other —
    the one arithmetic invariant that's unambiguous regardless of layout: a
    "Subtotal"/"Total" pair where the total is LESS than the subtotal
    (impossible for any real order/statement, since tax/shipping/fees can
    only add to it), or the same total-style label printed twice with two
    materially different amounts. Pixel-level cues can't see this at all;
    like check_document_text, this reads what the document actually *says*.

    Deliberately narrow, for the same reason check_document_text's
    watermark list is a fixed set rather than a fuzzy match: a broader
    "does the itemized list sum to the total" check would false-positive
    constantly on real receipts (discounts, multiple tax lines, rounding,
    loyalty credits — none of which this pipeline can enumerate reliably),
    so this only fires on a contradiction with no legitimate explanation, at
    the cost of missing subtler tampering that doesn't leave one.
    """
    if ocr_data is None:
        ocr_data = _ocr_data(image)
    if not ocr_data.get("available"):
        return {"score": 0.0, "note": "OCR not available in this environment.", "matched_flags": []}

    totals: List[float] = []
    subtotals: List[float] = []
    for line in ocr_data.get("lines", []):
        amount = _line_amount(line)
        if amount is None:
            continue
        lower = line.lower()
        if "subtotal" in lower:
            subtotals.append(amount)
        elif "total" in lower or "balance" in lower:
            totals.append(amount)

    flags: List[str] = []
    if subtotals and totals and max(totals) < max(subtotals) - 0.01:
        flags.append(
            f"Total (${max(totals):.2f}) is less than Subtotal (${max(subtotals):.2f}) — "
            "not possible for a real order/statement."
        )
    unique_totals = sorted(set(round(v, 2) for v in totals))
    if len(unique_totals) > 1:
        flags.append(f"Multiple different Total/Balance amounts printed in the same document: {unique_totals}")

    score = min(1.0, 0.9 * len(flags)) if flags else 0.0
    return {
        "score": round(score, 4),
        "matched_flags": flags,
        "totals_found": totals,
        "subtotals_found": subtotals,
    }


# ---------------------------------------------------------------------------
# JPEG quantization tables
# ---------------------------------------------------------------------------

def check_quantization_tables(image: Image.Image) -> Dict[str, Any]:
    qtables = getattr(image, "quantization", None)
    if not qtables:
        return {
            "present": False,
            "num_tables": 0,
            "note": "No JPEG quantization tables found (not a native JPEG, e.g. a PNG screenshot).",
            "score": 0.0,
        }

    num_tables = len(qtables)
    # A standard single JPEG encode has at most 2 tables (luma + chroma).
    # More than that on a re-opened file suggests multiple/inconsistent
    # compression generations (i.e. the image was edited and re-saved).
    suspicious = num_tables > 2
    score = 0.6 if suspicious else 0.0
    return {
        "present": True,
        "num_tables": num_tables,
        "suspicious_multiple_tables": suspicious,
        "score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# Block-wise noise consistency
# ---------------------------------------------------------------------------

_HIGH_PASS_KERNEL = ImageFilter.Kernel((3, 3), [-1, -1, -1, -1, 8, -1, -1, -1, -1], scale=1)


def estimate_noise_inconsistency(image: Image.Image, block_size: int = 32) -> Dict[str, Any]:
    """Flag images whose local noise energy varies unusually across blocks —
    a common side effect of splicing in content with a different noise
    profile (e.g. a re-compressed or re-rendered patch) than the rest of the
    image.

    Combines the overall coefficient of variation (diffuse signal: is noise
    energy inconsistent at all?) with a robust-outlier cluster check (localized
    signal: is there a compact region whose noise energy doesn't belong?),
    since a real spliced patch produces the latter, not just generic spread.
    """
    gray = image.convert("L")
    w, h = gray.size
    hp = np.array(gray.filter(_HIGH_PASS_KERNEL), dtype=np.float32)

    bh, bw = h // block_size, w // block_size
    if bh < 2 or bw < 2:
        return {"score": 0.0, "note": "Image too small for reliable block noise analysis."}

    cropped = hp[: bh * block_size, : bw * block_size]
    block_stds = cropped.reshape(bh, block_size, bw, block_size).std(axis=(1, 3))

    overall_mean = float(block_stds.mean()) or 1e-6
    overall_std = float(block_stds.std())
    coefficient_of_variation = overall_std / overall_mean

    if bh >= 5 and bw >= 5:
        outlier_mask = _local_outlier_mask(block_stds)
        cluster_size = _largest_connected_component(outlier_mask)
    else:
        outlier_mask = np.zeros_like(block_stds, dtype=bool)
        cluster_size = 0
    outlier_ratio = float(outlier_mask.mean())
    cluster_ratio = cluster_size / (bh * bw)

    # NOTE: calibrated against the synthetic corpus in backend/tools/calibrate.py.
    # Absolute block count (see ela_feature_score) — blocks here are 32px
    # (vs. 16px elsewhere), so a small patch saturates at a lower count.
    cluster_term = min(1.0, cluster_size / 2.0)
    score = min(1.0, (cluster_term * 0.7) + max(0.0, (coefficient_of_variation - 0.6) / 2.5) * 0.5)
    return {
        "block_count": int(bh * bw),
        "noise_cv": round(coefficient_of_variation, 4),
        "outlier_block_ratio": round(outlier_ratio, 4),
        "largest_cluster_ratio": round(cluster_ratio, 4),
        "largest_cluster_size": int(cluster_size),
        "score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# Lightweight copy-move (clone) detection
# ---------------------------------------------------------------------------

def _block_hash(block: np.ndarray) -> int:
    small = Image.fromarray(block).resize((8, 8), Image.BILINEAR).convert("L")
    arr = np.array(small, dtype=np.float32)
    avg = arr.mean()
    bits = (arr > avg).flatten()
    h = 0
    for bit in bits:
        h = (h << 1) | int(bit)
    return h


def detect_clone_regions(image: Image.Image, block_size: int = 24, stride: int = 12,
                          max_blocks: int = 2000, flat_std_threshold: float = 15.0) -> Dict[str, Any]:
    """Hash overlapping blocks and look for a copy-move forgery signature
    using offset-vector voting (Fridrich/Popescu-style block matching): for
    every pair of near-duplicate blocks that are far apart, record the
    displacement vector between them. A real copy-paste rigidly shifts a
    whole rectangular region, so dozens of block-pairs across that region
    all share the *same* displacement vector, producing one dominant peak.

    Legitimately repeated UI elements (icons, bullet points, repeated dash
    decorations) also produce near-duplicate block pairs, but each repeated
    instance sits at its own, generally different, offset from the others —
    so their vote spreads across many different vectors instead of piling
    onto one. Requiring a dominant, sharply-peaked offset is what tells a
    real forgery apart from ordinary repeated design elements, which a
    naive "any two blocks matched" count cannot.

    Near-flat blocks (solid backgrounds, empty margins) are skipped: they
    trivially hash identically to every other flat block and would otherwise
    swamp the result with meaningless "matches".
    """
    rgb = np.array(image.convert("RGB"))
    h, w, _ = rgb.shape

    positions = [
        (x, y)
        for y in range(0, max(h - block_size, 0), stride)
        for x in range(0, max(w - block_size, 0), stride)
    ]

    if len(positions) > max_blocks:
        step = math.ceil(len(positions) / max_blocks)
        positions = positions[::step]

    buckets: Dict[int, List[Tuple[int, int]]] = {}
    textured_blocks = 0
    for (x, y) in positions:
        block = rgb[y:y + block_size, x:x + block_size]
        if block.std() < flat_std_threshold:
            continue  # skip near-uniform regions (backgrounds, margins)
        textured_blocks += 1
        h_val = _block_hash(block)
        buckets.setdefault(h_val, []).append((x, y))

    offset_votes: Dict[Tuple[int, int], int] = {}
    offset_source_points: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    matched_hashes = 0
    for h_val, pts in buckets.items():
        if len(pts) < 2:
            continue
        found_far_pair = False
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                (x1, y1), (x2, y2) = pts[i], pts[j]
                if math.hypot(x2 - x1, y2 - y1) <= block_size * 3:
                    continue
                found_far_pair = True
                dx, dy = x2 - x1, y2 - y1
                src = (x1, y1)
                if dx < 0 or (dx == 0 and dy < 0):
                    dx, dy = -dx, -dy  # canonicalize direction
                    src = (x2, y2)
                key = (round(dx / stride) * stride, round(dy / stride) * stride)
                offset_votes[key] = offset_votes.get(key, 0) + 1
                offset_source_points.setdefault(key, []).append(src)
        if found_far_pair:
            matched_hashes += 1

    unique_patterns = max(1, len(buckets))
    total_votes = sum(offset_votes.values())
    if offset_votes:
        dominant_offset, dominant_votes = max(offset_votes.items(), key=lambda kv: kv[1])
    else:
        dominant_offset, dominant_votes = (0, 0), 0

    # How concentrated the votes are onto the single most common offset
    # (peaked => real rigid copy-move) vs. how much of the textured image
    # that dominant offset's matches actually cover (a couple of blocks
    # sharing an offset by chance is not meaningful; a large contiguous
    # region shifted by one offset is).
    peak_ratio = dominant_votes / total_votes if total_votes else 0.0
    coverage_ratio = dominant_votes / max(1, textured_blocks)

    # Compactness gate: a real copy-paste's matched *source* blocks cluster
    # inside one localized patch. Regularly-spaced decorative content (e.g.
    # repeated bullet dashes) can coincidentally share a common small offset
    # too, but those matches scatter across most of the frame rather than
    # clustering — so gate on the bounding-box area of the dominant offset's
    # source points, not just how many blocks voted for it.
    compact_ratio = 0.0
    if dominant_votes >= 3:
        src_pts = offset_source_points[dominant_offset]
        xs = [p[0] for p in src_pts]
        ys = [p[1] for p in src_pts]
        bbox_area = (max(xs) - min(xs) + block_size) * (max(ys) - min(ys) + block_size)
        compact_ratio = 1.0 - min(1.0, bbox_area / (w * h))

    score = min(1.0, (peak_ratio * coverage_ratio * compact_ratio) * 20.0) if dominant_votes >= 3 else 0.0
    return {
        "blocks_checked": len(positions),
        "textured_blocks": textured_blocks,
        "unique_patterns": unique_patterns,
        "duplicate_pairs": matched_hashes,
        "dominant_offset": dominant_offset,
        "dominant_offset_votes": dominant_votes,
        "offset_peak_ratio": round(peak_ratio, 4),
        "source_compactness": round(compact_ratio, 4),
        "score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# Content-type classification (for per-domain thresholds, not scoring)
# ---------------------------------------------------------------------------

def classify_content_type(image: Image.Image, ocr_data: Optional[Dict[str, Any]] = None) -> str:
    """Buckets an image into a coarse content type using simple, explainable
    rules over its OCR'd text and shape — not a trained classifier — so a
    single global fake_score threshold isn't forced across visually
    incompatible domains. Directly motivated by this project's own measured
    finding (see README's "Trained model" per-source breakdown): the same
    threshold that gives CASIA's general photos 100% recall gives findit2's
    dense receipts only 28% precision, because one global cutoff can't suit
    both a nearly-textless photo and a dense financial document equally
    well.

    Deliberately simple and rule-based rather than a second trained model: a
    wrong bucket here only shifts which *threshold* applies (see
    config.CONTENT_TYPE_THRESHOLDS and analyze_image_bytes below) — it never
    changes fake_score itself or swaps in different cue weights — so a
    misclassification degrades gracefully to "uses the default threshold"
    rather than corrupting the underlying verdict.

    Buckets:
      financial_document  Dense $-amount content with balance/total/
                          transaction-style language — bank statements,
                          payment receipts, crypto wallets, e-commerce
                          orders, paper receipts (findit2).
      social_or_chat      An @handle pattern, or a phone-shaped image with
                          light, informal text — social posts, message
                          threads.
      photo               Little to no legible text — general photographs
                          (CASIA/IMD2020-style content), where this
                          pipeline's pixel-forensics cues are closest to the
                          conditions they were originally validated under.
      unknown             Doesn't clearly match any of the above; uses the
                          global default threshold.
    """
    if ocr_data is None:
        ocr_data = _ocr_data(image)
    text = ocr_data.get("text", "")
    lower = text.lower()
    word_count = len(ocr_data.get("words", []))
    w, h = image.size

    if word_count < 5:
        return "photo"

    financial_kw = any(kw in lower for kw in
                        ("balance", "total", "subtotal", "transaction", "payment",
                         "order", "amount", "account"))
    if text.count("$") >= 2 and financial_kw:
        return "financial_document"

    has_handle = bool(re.search(r"@\w{2,}", text))
    social_kw = any(kw in lower for kw in ("likes", "replies", "reposts", "comments", "shares"))
    phone_shaped = h > w * 1.3
    if has_handle or social_kw or (phone_shaped and word_count < 60):
        return "social_or_chat"

    return "unknown"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _resize_for_analysis(image: Image.Image, max_dim: int) -> Image.Image:
    w, h = image.size
    rgb = image.convert("RGB")
    if max(w, h) <= max_dim:
        return rgb
    scale = max_dim / max(w, h)
    return rgb.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def analyze_image_bytes(raw_bytes: bytes, config) -> Dict[str, Any]:
    """Run the full forensic pipeline on an in-memory image and return a
    JSON-serializable result dict. Nothing is written to disk."""
    start = time.time()

    image = Image.open(io.BytesIO(raw_bytes))
    image.load()
    original_format = image.format
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    # Cues that depend on the original file's own compression history (or,
    # for OCR, on maximum available text legibility) must run before any
    # resizing/re-encoding. OCR runs exactly once here (_ocr_data) and its
    # result is shared by every text-derived cue below, rather than each
    # running its own Tesseract pass.
    quant = check_quantization_tables(image)
    metadata = check_metadata(image)
    ocr_data = _ocr_data(image)
    doc_text = check_document_text(image, ocr_data)
    font_consistency = check_font_consistency(image, ocr_data)
    chrome = check_chrome_consistency(image, ocr_data)
    amount_consistency = check_amount_consistency(image, ocr_data)

    analysis_image = _resize_for_analysis(image, config.ANALYSIS_MAX_DIM)
    ela_image, diff_arr = compute_ela(analysis_image, quality=config.ELA_QUALITY)
    ela_features = ela_feature_score(diff_arr)
    ghost = compute_jpeg_ghost(analysis_image)
    noise = estimate_noise_inconsistency(analysis_image)
    clone = detect_clone_regions(analysis_image)
    edge_sharpness = check_edge_sharpness_consistency(analysis_image)

    features = {
        "ela_score": ela_features["score"],
        "ghost_score": ghost.get("score", 0.0),
        "quant_score": quant["score"],
        "noise_score": noise.get("score", 0.0),
        "clone_score": clone["score"],
        "metadata_score": metadata["score"],
        "text_score": doc_text["score"],
        # New screenshot-specific cues (see "Screenshot-specific rendering
        # cues" section above): computed and reported like ghost_score, but
        # NOT in config.WEIGHTS and not seen by the currently-bundled
        # trained model (it only reads the seven keys above — see
        # model_loader.predict_fake and rf_model_meta.json's feature_keys)
        # until calibration testing validates them, same bar ghost_score
        # itself didn't clear. Kept visible for transparency/debugging.
        "font_score": font_consistency["score"],
        "edge_score": edge_sharpness.get("score", 0.0),
        "chrome_score": chrome["score"],
        "arithmetic_score": amount_consistency["score"],
    }
    # Per-domain threshold (see classify_content_type's docstring): looked
    # up, not re-derived per request, so a misclassification degrades to
    # "uses the global default" rather than anything more surprising.
    content_type = classify_content_type(image, ocr_data)
    threshold_overrides = getattr(config, "CONTENT_TYPE_THRESHOLDS", {}) or {}
    effective_threshold = threshold_overrides.get(content_type) or config.FAKE_THRESHOLD

    prediction = predict_fake(features, config.WEIGHTS, effective_threshold,
                               overrides=getattr(config, "OVERRIDE_CUES", None))

    buf = io.BytesIO()
    ela_image.save(buf, format="PNG")
    ela_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    elapsed_ms = round((time.time() - start) * 1000, 1)

    return {
        "fake_score": prediction["fake_score"],
        "is_fake": prediction["is_fake"],
        "verdict": "Possible Fake" if prediction["is_fake"] else "Likely Authentic",
        "override_reason": prediction["override_reason"],
        "ela_image": f"data:image/png;base64,{ela_b64}",
        "features": features,
        "details": {
            "ela": ela_features,
            "jpeg_ghost": ghost,
            "quantization": quant,
            "metadata": metadata,
            "noise": noise,
            "clone_detection": clone,
            "document_text": doc_text,
            "font_consistency": font_consistency,
            "edge_sharpness": edge_sharpness,
            "chrome_consistency": chrome,
            "amount_consistency": amount_consistency,
        },
        "meta": {
            "original_format": original_format,
            "sha256": sha256,
            "processing_ms": elapsed_ms,
            "content_type": content_type,
            "effective_threshold": effective_threshold,
            "model": prediction["model_name"],
        },
    }
