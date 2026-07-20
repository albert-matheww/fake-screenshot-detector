"""Core forensic analysis functions.

Implements Error Level Analysis (ELA) plus complementary cues: EXIF/metadata
inspection, JPEG quantization-table checks, OCR-based document text
forensics, and block-wise noise consistency analysis. Each cue returns a
bounded 0-1 "score" (higher = more suspicious) plus the raw evidence used
to compute it, so results stay explainable.
"""
import base64
import io
import math
import re
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ExifTags

try:
    import pytesseract
except ImportError:
    pytesseract = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _largest_connected_component(mask: np.ndarray) -> int:
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


# ---------------------------------------------------------------------------
# Error Level Analysis
# ---------------------------------------------------------------------------

def compute_ela(image: Image.Image, quality: int = 90) -> Tuple[Image.Image, np.ndarray]:
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

GHOST_QUALITIES: List[int] = list(range(50, 100, 5))
GHOST_MAX_DIM = 700


def compute_jpeg_ghost(image: Image.Image, block_size: int = 16,
                        qualities: List[int] = None) -> Dict[str, Any]:
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
    span = block_diffs.max(axis=0) - block_diffs.min(axis=0)

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

    informative = (dip_idx >= 0) & (dip_depth > 0.15) & (span > 1.5)
    if not informative.any():
        return {"score": 0.0, "note": "No blocks showed a conclusive native-quality dip."}

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
        suspicious.append(f"Software tag indicates an editing tool was used: {software}")
        weight += 1.0

    has_gps = any(k.lower().startswith("gps") for k in fields)
    if has_gps:
        suspicious.append("GPS metadata present (stripped before any storage/response logging)")
        weight += 0.5

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

_GENERATOR_WATERMARKS = [
    "bankstatements.net", "bank statements.net", "thepaystubs", "paystubcreator",
    "stubcreator", "makereceipt", "receiptmakerly", "docutemplates",
    "specimen", "sample statement", "not a real bank statement",
    "for novelty purposes only", "for entertainment purposes only",
    "this is not a real", "template only", "demo purposes only",
    "not a real document", "not an official document",
]

_PLACEHOLDER_NAMES = ["john doe", "jane doe", "john smith", "test user", "sample name"]

_PLACEHOLDER_NUMBER_RE = re.compile(r"(\d)\1{5,}|123456789|987654321")


def check_document_text(image: Image.Image) -> Dict[str, Any]:
    if pytesseract is None:
        return {"score": 0.0, "note": "OCR not available in this environment.", "matched_flags": []}

    try:
        text = pytesseract.image_to_string(image.convert("RGB"))
    except Exception as exc:
        return {"score": 0.0, "note": f"OCR failed: {exc}", "matched_flags": []}

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

    score = min(1.0, 0.9 * len(flags)) if flags else 0.0
    return {
        "score": round(score, 4),
        "matched_flags": flags,
        "extracted_text_length": len(text.strip()),
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
