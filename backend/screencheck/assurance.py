"""Assurance levels: how much independent evidence supports a screenshot, instead of a yes/no verdict.

  Level 0  Unverified            the screenshot alone, or a contradiction / conflict was found
  Level 1  No contradiction      what the screenshot says is consistent with itself (still unverified)
  Level 2  Consistent with an independent source   a second source (bank SMS, statement, the receiver's app) agrees
  Level 3  Confirmed by signed data            not available yet (needs a signature or QR that can be checked)

The tool never says 'genuine'. A forger can make one screenshot agree with itself, which is why level 1 is not proof.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

LADDER = [
    {"level": 0, "label": "Unverified", "requirement": "The screenshot alone."},
    {"level": 1, "label": "No contradiction found (still unverified)", "requirement": "What it says is consistent with itself."},
    {"level": 2, "label": "Consistent with an independent source",
     "requirement": "A second source you did not get from the sender (the receiver's bank SMS, a statement line, the issuer's e-mail) agrees on the reference, or on the amount and the date."},
    {"level": 3, "label": "Confirmed by signed data", "requirement": "A digital signature or signed QR code that can be checked. Not available yet."},
]

NEXT_STEP = {
    0: "Add a second source you did not get from the sender (reconcile mode), or ask the issuer to confirm the transaction.",
    1: "Add a second source you did not get from the sender (reconcile mode). A screenshot that agrees with itself can still be forged.",
    2: "For high-value cases, ask the issuer for a signed document or confirm directly with them.",
}


def _content_checks(checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [c for c in checks if c.get("category") == "content"]


def assess(verdict: str, checks: List[Dict[str, Any]], words_read: int, reconcile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    reasons: List[str] = []
    content = _content_checks(checks)
    live_find = [c for c in checks if c["gate"]["status"] == "live" and c["status"] == "finding"]
    content_find = [c for c in content if c["status"] == "finding"]
    content_clear = [c for c in content if c["status"] == "clear"]

    status, level = None, None
    if verdict in ("evidence_of_editing", "suspicious") or live_find:
        status, level = "contradiction", 0
        reasons += [f["message"] for c in live_find for f in c["findings"]][:3]
    elif content_find:
        status, level = "possible_issue", 0
        reasons += [f["message"] for c in content_find for f in c["findings"]][:3]
        reasons.append("These checks are rule-based but not yet measured on enough genuine screenshots, so they lower the assurance without deciding the verdict.")
    if reconcile and reconcile.get("status") == "conflict":
        status, level = "conflict", 0
        reasons.insert(0, "The second source and the screenshot disagree on: " + ", ".join(reconcile["differs"]) + ".")
    if status is None and reconcile and reconcile.get("status") == "review":
        status, level = "review", 0
        reasons.append("A reference number in the second source differs from the screenshot by one digit. Compare it by eye before relying on either.")
    if status is None:
        if reconcile and reconcile.get("status") == "corroborated":
            status, level = "corroborated", 2
            reasons.append("The second source agrees with the screenshot on: " + ", ".join(reconcile["matched"]) + ".")
        elif content_clear and words_read >= 15:
            status, level = "consistent", 1
            reasons.append(f"{len(content_clear)} content check(s) examined the text and found no contradiction.")
            if reconcile and reconcile.get("status") in ("partial", "nothing_matched", "no_facts"):
                reasons.append("The second source did not match enough facts to count as corroboration.")
        else:
            status, level = "unverified", 0
            reasons.append("Too little could be examined to say anything about the content.")
    top = LADDER[level]
    blocked = status in ("contradiction", "possible_issue", "conflict", "review")
    return {"level": level, "label": top["label"], "status": status, "reasons": reasons, "next_step": NEXT_STEP.get(level),
            "ladder": [{**r, "reached": r["level"] == 0 or (not blocked and r["level"] <= level)} for r in LADDER],
            "never_genuine": "No level proves the screenshot is untouched. Level 2 only means an independent source agrees with it."}
