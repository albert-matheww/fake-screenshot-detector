"""Reconcile a screenshot with a second, independent source (a bank SMS, a statement line, the receiver's app).

A forged screenshot can be made to agree with itself, but it cannot change the other source. Every fact in the second source
is looked up in the screenshot:
  matched   the same value appears in the screenshot
  differs   the screenshot clearly shows other values of that kind and not this one (a conflict)
  unclear   the screenshot shows no value of that kind
  near      a reference differs by a single digit (a misread, or an edited digit): never counts as corroboration
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import fields as F

TIME_TOLERANCE_MIN = 5
HARD_KINDS = ("refs", "amounts", "dates")


def _edit_distance_le1(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def _compare_kind(kind: str, src: List[Any], shot_any: List[Any], shot_conf: List[Any]) -> Dict[str, Any]:
    if not src:
        return {"kind": kind, "status": "not_in_source", "source": [], "screenshot": shot_any}
    if kind == "times":
        close = [s for s in src for v in shot_any if abs(s - v) <= TIME_TOLERANCE_MIN]
        if close:
            return {"kind": kind, "status": "matched", "source": src, "screenshot": shot_any}
        if shot_conf:
            return {"kind": kind, "status": "differs", "source": src, "screenshot": shot_conf,
                    "note": f"The times differ by more than {TIME_TOLERANCE_MIN} minutes (clocks and apps can disagree a little)."}
        return {"kind": kind, "status": "unclear", "source": src, "screenshot": shot_any}
    shared = [s for s in src if s in shot_any]
    if shared:
        return {"kind": kind, "status": "matched", "source": src, "screenshot": shot_any}
    if kind == "refs" and any(_edit_distance_le1(s, v) for s in src for v in shot_any):
        return {"kind": kind, "status": "near", "source": src, "screenshot": shot_any,
                "note": "The reference differs by one digit. That may be a misread of the image, or an edited digit. Compare it by eye."}
    if shot_conf:
        return {"kind": kind, "status": "differs", "source": src, "screenshot": shot_conf}
    return {"kind": kind, "status": "unclear", "source": src, "screenshot": shot_any}


def compare_fields(source: Dict[str, List[Any]], shot: Dict[str, Dict[str, List[Any]]]) -> Dict[str, Any]:
    rows = [_compare_kind(k, source.get(k, []), shot["any"][k], shot["confident"][k]) for k in ("refs", "amounts", "dates", "times")]
    by = {r["kind"]: r["status"] for r in rows}
    hard_differs = [k for k in HARD_KINDS if by[k] == "differs"]
    matched_hard = [k for k in HARD_KINDS if by[k] == "matched"]
    near = by["refs"] == "near"
    # every hard fact the second source supplies must be found in the screenshot, not just some of them
    unmatched = [r["kind"] for r in rows if r["kind"] in HARD_KINDS and r["source"] and r["status"] != "matched"]
    corroborated = (not hard_differs and not near and not unmatched
                    and ("refs" in matched_hard or {"amounts", "dates"} <= set(matched_hard)))
    if hard_differs:
        status = "conflict"
    elif near:
        status = "review"
    elif corroborated:
        status = "corroborated"
    elif matched_hard:
        status = "partial"
    else:
        status = "nothing_matched"
    return {"status": status, "rows": rows, "matched": matched_hard, "differs": hard_differs,
            "needs": [] if corroborated else (["every fact in the second source found in the screenshot: " + ", ".join(unmatched)] if unmatched
                                              else ["a reference number match, or both an amount and a date match"])}


def reconcile(shot_consensus: Dict[str, Dict[str, List[Any]]], source_text: str = "", source_consensus=None) -> Dict[str, Any]:
    src = F.extract_text(source_text or "")
    if source_consensus is not None:          # the second source was an image: trust values both reads agree on, else any
        for k in src:
            vals = source_consensus["confident"][k] or source_consensus["any"][k]
            src[k] = src[k] + [v for v in vals if v not in src[k]]
    if not any(src.values()):
        return {"status": "no_facts", "rows": [], "matched": [], "differs": [], "needs": ["a source that contains an amount, date or reference"],
                "source_fields": F.display(src)}
    out = compare_fields(src, shot_consensus)
    out["source_fields"] = F.display(src)
    out["screenshot_fields"] = F.display(shot_consensus["any"])
    return out
