"""End-to-end analysis of one screenshot."""
from __future__ import annotations

import hashlib
import io
import time
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageOps

import analysis_model as am
import textforensics as tf

from . import assurance, capture, checks, fields, gates, router, verdict


def model_info() -> Dict[str, Any]:
    g = gates.load()
    info = {
        "loaded": am.MODEL is not None,
        "error": am.LOAD_ERROR,
        "feature_count": len(tf.FEATURE_NAMES),
        "train_images": am.META.get("train_images"),
        "test_auc": am.META.get("metrics", {}).get("test", {}).get("auc"),
        "thresholds": {"suspicious": am.THR_LO, "evidence": am.THR_HI},
        "version": "v3 (type router + calibration-gated checks)",
        "router": router.router_gate(),
        "gates": {k: gates.gate_for(k).get("status") for k in g.get("checks", {})},
    }
    return info


def _run(check_fn, ctx) -> Dict[str, Any]:
    try:
        res = check_fn(ctx)
    except Exception as exc:  # noqa: BLE001  a crashing check must never turn into a "clear"
        res = checks.result(getattr(check_fn, "__name__", "check"), getattr(check_fn, "__name__", "check"), "not_applicable",
                            why=f"The check failed to run ({type(exc).__name__}).")
    res["gate"] = gates.gate_for(res["id"])
    return res


def build_context(raw_bytes: bytes) -> Dict[str, Any]:
    image = Image.open(io.BytesIO(raw_bytes))
    image.load()
    rgb_img = ImageOps.exif_transpose(image).convert("RGB")
    cap = capture.profile(image, image.format)
    words = tf.ocr_words(rgb_img)
    rgb = np.asarray(rgb_img)
    return {"image": image, "rgb_img": rgb_img, "rgb": rgb, "words": words, "capture": cap, "route": router.route(rgb, words)}


def forced_route(typ: str, route: Dict[str, Any]) -> Dict[str, Any]:
    """The person chose the type: use it. The automatic guess stays in the result for comparison."""
    from .common import TYPE_LABELS

    return {**route, "type": typ, "label": TYPE_LABELS.get(typ, typ), "status": "confident", "confidence": 1.0,
            "typed_checks_enabled": True, "source": "user", "automatic_guess": route.get("type")}


def analyze_bytes(raw_bytes: bytes, config=None, forced_type: Optional[str] = None, ctx_out: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t0 = time.time()
    ctx = build_context(raw_bytes)
    if forced_type:
        ctx["route"] = forced_route(forced_type, ctx["route"])
    if ctx_out is not None:
        ctx_out.update(ctx)
    image, fmt = ctx["image"], ctx["image"].format
    W, H = ctx["rgb_img"].size
    cap, words, route = ctx["capture"], ctx["words"], ctx["route"]
    results: List[Dict[str, Any]] = [_run(fn, ctx) for fn in checks.GENERIC]
    for t, fn in checks.TYPED.items():
        cid = f"typed.{t}"
        if route["type"] == t and route["typed_checks_enabled"]:
            results.append(_run(fn, ctx))
        elif route["type"] == t:
            why = "The type router is not validated on real screenshots yet." if not route["router_validated"] else \
                "The type is not confident enough to apply type-specific checks."
            r = checks.result(cid, fn.__name__, "not_applicable", why=why)
            r["gate"] = gates.gate_for(cid)
            results.append(r)

    decision = verdict.decide(route, results, len(words))
    regions, findings = [], []
    for c in results:
        live = c["gate"]["status"] == "live"
        for r in c["regions"]:
            rr = dict(r)
            if not live:
                rr["level"] = "weak"
            rr["check"] = c["id"]
            regions.append(rr)
        for f in c["findings"]:
            findings.append({**f, "check": c["id"], "counted": live})
    regions.sort(key=lambda r: -r.get("score", 0.0))
    top_render = next((c["detail"].get("top_probability") for c in results if c["id"] == "rendering"), None)

    return {
        "verdict": decision["verdict"], "verdict_label": decision["verdict_label"], "risk_score": decision["risk_score"],
        "reasons": decision["reasons"], "regions": regions[:10], "findings": findings,
        "limitations": verdict.LIMITATIONS, "verify_steps": verdict.VERIFY_STEPS,
        "assurance": assurance.assess(decision["verdict"], results, len(words)),
        "fields": fields.display(fields.extract_words(words)),
        "routing": route, "capture": cap, "checks": results, "coverage": decision["coverage"],
        "image": {"width": W, "height": H, "format": fmt},
        "stats": {"ocr_words": len(words), "measured_words": next((c["detail"].get("measured_words", 0) for c in results if c["id"] == "rendering"), 0),
                  "top_word_probability": top_render or 0.0, "thresholds": {"suspicious": am.THR_LO, "evidence": am.THR_HI}},
        "meta": {"sha256": hashlib.sha256(raw_bytes).hexdigest(), "processing_ms": round((time.time() - t0) * 1000, 1),
                 "model": "v3: type router + calibration-gated checks (rendering model advisory)"},
    }
