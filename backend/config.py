"""Configuration for the fake-screenshot-detector backend."""
import os


class Config:
    ELA_QUALITY = int(os.environ.get("ELA_QUALITY", 90))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    ANALYSIS_MAX_DIM = int(os.environ.get("ANALYSIS_MAX_DIM", 1600))
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
