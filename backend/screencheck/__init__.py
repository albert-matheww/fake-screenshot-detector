"""screencheck: type-aware, fail-safe screenshot checking (v3).

Pipeline: capture profile -> two independent type routers -> checks (each may say "not applicable")
-> calibration gates -> verdict policy that can only move towards "inconclusive" when unsure.
"""


def analyze_bytes(*args, **kwargs):
    from .pipeline import analyze_bytes as _f
    return _f(*args, **kwargs)


def model_info():
    from .pipeline import model_info as _f
    return _f()
