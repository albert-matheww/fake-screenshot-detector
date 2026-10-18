"""Loads the word-level rendering model (shared by the pipeline and the tools)."""
import json
import os
from typing import Any, Dict, Optional

import textforensics as tf

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_data")
MODEL = None
META: Dict[str, Any] = {}
LOAD_ERROR: Optional[str] = None

try:
    import joblib

    _mp, _jp = os.path.join(_DIR, "word_gbm.joblib"), os.path.join(_DIR, "word_gbm_meta.json")
    if os.path.exists(_mp) and os.path.exists(_jp):
        MODEL = joblib.load(_mp)
        with open(_jp) as fh:
            META = json.load(fh)
        if META.get("feature_names") != tf.FEATURE_NAMES:
            raise RuntimeError("model feature list does not match textforensics.FEATURE_NAMES - retrain the model")
except Exception as exc:  # noqa: BLE001
    MODEL, LOAD_ERROR = None, str(exc)

THR_LO = float(META.get("thresholds", {}).get("5%", 0.4))
THR_HI = float(META.get("thresholds", {}).get("1%", 0.8))
MIN_MEASURED_WORDS = 6
