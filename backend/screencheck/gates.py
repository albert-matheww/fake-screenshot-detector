"""Calibration gates: a check may influence the verdict only if its false-alarm rate on GENUINE real screenshots has been
measured with enough images and an acceptable upper bound. Everything else is shown as "advisory" and cannot raise or
lower the verdict. Gates are written by tools/calibrate_gates.py; with no gate file every check is advisory.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

GATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_data", "gates.json")
MIN_GENUINE = 20            # genuine real screenshots on which the check was applicable
MAX_UPPER95 = 0.15          # Wilson upper bound of the false-alarm rate must not exceed this


def load() -> Dict[str, Any]:
    try:
        with open(GATE_FILE) as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {"checks": {}, "criteria": {"min_genuine": MIN_GENUINE, "max_upper95": MAX_UPPER95}}


_CACHE: Dict[str, Any] = {}


def gate_for(check_id: str) -> Dict[str, Any]:
    g = _CACHE.get("g") or load()
    _CACHE["g"] = g
    return g.get("checks", {}).get(check_id) or {
        "status": "advisory", "n": 0, "flagged": 0,
        "reason": f"not calibrated yet: needs at least {MIN_GENUINE} genuine real screenshots on which it applies"}


def is_live(check_id: str) -> bool:
    return gate_for(check_id).get("status") == "live"


def decide(n: int, flagged: int):
    """Gate decision from calibration counts: (live, wilson_upper95, reason)."""
    from .common import wilson

    _, hi = wilson(flagged, n)
    if n < MIN_GENUINE:
        return False, hi, f"applicable on only {n} genuine real screenshots (need {MIN_GENUINE}); {MIN_GENUINE - n} more needed"
    if hi > MAX_UPPER95:
        return False, hi, f"false-alarm rate {flagged}/{n} with upper bound {hi:.2f} above {MAX_UPPER95}"
    return True, hi, None


def reload() -> None:
    _CACHE.clear()
