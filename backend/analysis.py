"""Entry points of the analysis service (v3).

The implementation lives in the `screencheck` package: capture profile -> type routing -> calibration-gated checks ->
fail-safe verdict. The previous single-model analyser (v2) is kept as `analysis_v2.py` only so that the evaluations
reported for it can be reproduced.
"""
from analysis_model import MODEL as _MODEL, THR_HI, THR_LO  # noqa: F401
from screencheck import analyze_bytes, model_info  # noqa: F401
from screencheck.verdict import LIMITATIONS  # noqa: F401


def analyze_image_bytes(raw_bytes: bytes, config=None, forced_type=None):
    return analyze_bytes(raw_bytes, config, forced_type=forced_type)
