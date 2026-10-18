"""Classification stage: turns forensic feature scores into a final verdict.

Loads a trained RandomForest classifier from `model_data/` if present. Falls
back to a transparent weighted-average heuristic (`predict_fake_heuristic`)
if no trained model is bundled or scikit-learn/joblib aren't installed, so
the service still works in a minimal environment.

Either way, a small set of high-confidence overrides is applied on top: a
cue that's genuinely conclusive on its own (an editing-tool EXIF tag, an
OCR-caught document-generator watermark) forces `is_fake=True` regardless of
what the underlying classifier says.
"""
import json
import os
from typing import Dict, Optional

_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_data")
_MODEL = None
_MODEL_FEATURE_KEYS = None
_MODEL_LOAD_ERROR = None
_MODEL_DESCRIPTION = None

try:
    import joblib

    _model_path = os.path.join(_MODEL_DIR, "rf_model.joblib")
    _meta_path = os.path.join(_MODEL_DIR, "rf_model_meta.json")
    if os.path.exists(_model_path) and os.path.exists(_meta_path):
        with open(_meta_path) as _f:
            _meta = json.load(_f)
        _MODEL_FEATURE_KEYS = _meta["feature_keys"]
        _MODEL_DESCRIPTION = _meta.get("model_description")
        _MODEL = joblib.load(_model_path)
except Exception as exc:
    _MODEL = None
    _MODEL_LOAD_ERROR = str(exc)

MODEL_NAME = (
    (_MODEL_DESCRIPTION or "randomforest (trained model; see rf_model_meta.json for details)")
    if _MODEL is not None else
    "heuristic-v0 (rule-based weighted average; not yet trained on labeled data)"
) + " + high-confidence overrides"


def predict_fake_heuristic(features: Dict[str, float], weights: Dict[str, float]) -> float:
    weighted_sum = 0.0
    total_weight = 0.0
    for key, weight in weights.items():
        if key in features:
            weighted_sum += features[key] * weight
            total_weight += weight

    fake_score = weighted_sum / total_weight if total_weight else 0.0
    return max(0.0, min(1.0, fake_score))


def _override_reason(features: Dict[str, float], overrides: Optional[Dict[str, float]]) -> Optional[str]:
    for key, min_score in (overrides or {}).items():
        if features.get(key, 0.0) >= min_score:
            return key
    return None


def predict_fake(features: Dict[str, float], weights: Dict[str, float],
                  threshold: float = 0.5, overrides: Optional[Dict[str, float]] = None) -> Dict:
    if _MODEL is not None:
        vector = [[features.get(key, 0.0) for key in _MODEL_FEATURE_KEYS]]
        fake_score = float(_MODEL.predict_proba(vector)[0][1])
    else:
        fake_score = predict_fake_heuristic(features, weights)

    fake_score = max(0.0, min(1.0, fake_score))
    override_reason = _override_reason(features, overrides)

    return {
        "fake_score": round(fake_score, 4),
        "is_fake": (fake_score >= threshold) or (override_reason is not None),
        "override_reason": override_reason,
        "model_name": MODEL_NAME,
    }
