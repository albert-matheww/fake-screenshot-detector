"""Glue for /reconcile: one analysis of the screenshot, a double read of its facts, the comparison, and the assurance level."""
from __future__ import annotations

from typing import Any, Dict, Optional

from . import assurance, fields, pipeline, reconcile


def reconcile_bytes(raw: bytes, forced_type: Optional[str], source_text: str, source_raw: Optional[bytes]) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {}
    result = pipeline.analyze_bytes(raw, forced_type=forced_type, ctx_out=ctx)
    shot = fields.extract_consensus(ctx["rgb_img"], ctx["words"])
    src_consensus = None
    if source_raw:
        sctx = pipeline.build_context(source_raw)
        src_consensus = fields.extract_consensus(sctx["rgb_img"], sctx["words"])
    rec = reconcile.reconcile(shot, source_text, src_consensus)
    result["reconcile"] = rec
    result["assurance"] = assurance.assess(result["verdict"], result["checks"], len(ctx["words"]), rec)
    return result
