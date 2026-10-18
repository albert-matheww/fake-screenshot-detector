"""Configuration for the fake-screenshot-detector backend."""
import os


class Config:
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
