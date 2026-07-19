"""Core forensic analysis functions.

Implements Error Level Analysis (ELA) and JPEG Ghost (multi-quality
recompression scan) as the first two forensic cues. Each cue returns a
bounded 0-1 "score" (higher = more suspicious) plus the raw evidence used
to compute it, so results stay explainable.
"""
import base64
import io
import math
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageFilter


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
