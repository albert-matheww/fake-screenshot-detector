"""Flask API for the fake-screenshot detector.

Endpoints:
  POST /analyze  - multipart/form-data upload under field "image"; returns
                    forensic analysis JSON (fake_score, verdict, ELA image, cue
                    breakdown).
  GET  /status   - health check.

Images are processed entirely in memory and are never written to disk or
logged; only a SHA-256 hash and a size are logged for traceability.
"""
import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import UnidentifiedImageError

from config import Config
from forensic import analyze_image_bytes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fake_screenshot_detector")

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, resources={r"/*": {"origins": Config.CORS_ORIGINS}})


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "ok", "service": "fake-screenshot-detector"})


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No 'image' file part in request."}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({
            "error": f"Unsupported file type. Allowed: {sorted(Config.ALLOWED_EXTENSIONS)}"
        }), 400

    raw_bytes = file.read()
    if not raw_bytes:
        return jsonify({"error": "Uploaded file is empty."}), 400

    logger.info("Received image for analysis (%d bytes)", len(raw_bytes))

    try:
        result = analyze_image_bytes(raw_bytes, config=Config)
    except UnidentifiedImageError:
        return jsonify({"error": "File could not be read as an image."}), 400
    except Exception:
        logger.exception("Analysis failed")
        return jsonify({"error": "Internal error during analysis."}), 500
    finally:
        raw_bytes = None

    logger.info("Analysis complete: fake_score=%s is_fake=%s",
                result.get("fake_score"), result.get("is_fake"))
    return jsonify(result), 200


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
