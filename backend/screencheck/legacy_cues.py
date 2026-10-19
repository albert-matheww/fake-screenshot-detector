"""The version-1 pixel cues (error-level analysis, JPEG ghost, noise, copy-move, quantisation tables) as checks.

They are kept as HINTS: measured on genuine real screenshots they raised false alarms (see README), so they pass through
the same calibration gate as every other check and stay "advisory" (shown, never counted) unless a gate says otherwise.
ELA, JPEG ghost and quantisation tables describe a file's compression history, so they say "could not examine" for a
lossless file, where that history does not exist.
"""
from __future__ import annotations

import base64
import io
from typing import Any, Dict

from . import checks

FLAG_AT = 0.5   # a v1 cue score at or above this is reported as a finding (severity medium)
ANALYSIS_MAX_DIM = 1600


def _v1(ctx) -> Dict[str, Any]:
    """Run the expensive v1 computations once per screenshot and share them between the five checks."""
    cache = ctx.setdefault("_v1", {})
    if "ready" in cache:
        return cache
    from legacy import forensic as F  # lazy: only imported when a v1 cue is asked for

    img = F._resize_for_analysis(ctx["rgb_img"], ANALYSIS_MAX_DIM)
    cache["image"] = img
    lossless = bool(ctx["capture"]["lossless"])
    if not lossless:
        ela_img, diff = F.compute_ela(img, quality=90)
        cache["ela"] = F.ela_feature_score(diff)
        buf = io.BytesIO()
        ela_img.save(buf, format="PNG")
        cache["ela_image"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        cache["ghost"] = F.compute_jpeg_ghost(img)
    cache["noise"] = F.estimate_noise_inconsistency(img)
    cache["clone"] = F.detect_clone_regions(img)
    cache["quant"] = F.check_quantization_tables(ctx["image"])
    cache["ready"] = True
    return cache


def _cue(ctx, cid: str, name: str, key: str, message: str, needs_compression_history: bool) -> Dict[str, Any]:
    if needs_compression_history and ctx["capture"]["lossless"]:
        return checks.result(cid, name, "not_applicable",
                             why="The file is lossless (for example PNG), so there is no compression history for this cue to read.")
    d = _v1(ctx)[key]
    score = float(d.get("score", 0.0))
    detail = {"score": score, **{k: v for k, v in d.items() if k != "score" and isinstance(v, (int, float, str, bool))}}
    if key == "ela":
        detail["ela_image"] = _v1(ctx).get("ela_image")
    if score >= FLAG_AT:
        f = [{"id": f"{cid}.high", "severity": "medium", "message": message, "evidence": {"score": round(score, 3)}}]
        return checks.result(cid, name, "finding", f, detail=detail)
    return checks.result(cid, name, "clear", detail=detail)


def ela(ctx):
    return _cue(ctx, "v1.ela", "Error-level analysis (hint)", "ela",
                "A region recompresses differently from the rest of the image (error-level analysis).", True)


def jpeg_ghost(ctx):
    return _cue(ctx, "v1.ghost", "JPEG ghost (hint)", "ghost",
                "Parts of the image show a different JPEG compression history from the rest.", True)


def quantisation(ctx):
    return _cue(ctx, "v1.quant", "JPEG quantisation tables (hint)", "quant",
                "The file carries more JPEG quantisation tables than a single save would leave.", True)


def noise(ctx):
    return _cue(ctx, "v1.noise", "Noise consistency (hint)", "noise",
                "A block of the image has a noise level that differs from its surroundings.", False)


def clone(ctx):
    return _cue(ctx, "v1.clone", "Copy-move / clone detection (hint)", "clone",
                "A patch of the image appears to be a copy of another patch.", False)


CHECKS = [ela, jpeg_ghost, quantisation, noise, clone]
IDS = ["v1.ela", "v1.ghost", "v1.quant", "v1.noise", "v1.clone"]
