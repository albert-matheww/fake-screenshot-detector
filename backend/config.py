"""Configuration for the fake-screenshot-detector backend."""
import os


class Config:
    ELA_QUALITY = int(os.environ.get("ELA_QUALITY", 90))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    ANALYSIS_MAX_DIM = int(os.environ.get("ANALYSIS_MAX_DIM", 1600))

    WEIGHTS = {
        "text_score": 0.35,
        "metadata_score": 0.35,
        "clone_score": 0.15,
        "ela_score": 0.08,
        "noise_score": 0.05,
        "quant_score": 0.02,
    }
    FAKE_THRESHOLD = float(os.environ.get("FAKE_THRESHOLD", 0.5))

    OVERRIDE_CUES = {
        "metadata_score": 0.8,
        "text_score": 0.8,
    }

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
