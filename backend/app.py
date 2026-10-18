"""Flask API for the screenshot forensics service (v2).

Endpoints:
  POST /analyze  - multipart/form-data upload under field "image"; returns the analysis JSON
                    (three-tier verdict, edited-word regions with reasons, rule-based findings,
                    limitations). See analysis.analyze_image_bytes.
  GET  /status   - health check + model info.

Images are processed entirely in memory: the upload parser is configured to keep
every upload in memory too (see InMemoryUploadRequest - Werkzeug would otherwise
spool uploads above 500 KB to a temporary file). Only the byte count and the
verdict are logged; the SHA-256 of the image is returned in the response.
"""
import io
import logging
import os

from flask import Flask, Request, jsonify, request
from flask_cors import CORS
from PIL import UnidentifiedImageError

from config import Config
from analysis import analyze_image_bytes, model_info

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fake_screenshot_detector")

class InMemoryUploadRequest(Request):
    """Werkzeug spools multipart file parts larger than 500 KB to a temporary file on disk. Screenshots are
    private, so every upload part is kept in memory instead (size is bounded by MAX_CONTENT_LENGTH)."""

    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        return io.BytesIO()


app = Flask(__name__)
app.request_class = InMemoryUploadRequest
app.config.from_object(Config)
CORS(app, resources={r"/*": {"origins": Config.CORS_ORIGINS}})


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "ok", "service": "screenshot-forensics", "model": model_info()})


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

    logger.info("Analysis complete: verdict=%s risk=%s regions=%d",
                result.get("verdict"), result.get("risk_score"), len(result.get("regions", [])))
    return jsonify(result), 200


@app.route("/compare", methods=["POST"])
def compare():
    """Compare a suspect screenshot with a genuine copy (multipart fields `original` and `suspect`)."""
    from screencheck.compare import compare_bytes

    for field in ("original", "suspect"):
        if field not in request.files:
            return jsonify({"error": f"Missing '{field}' file part."}), 400
    raws = {}
    for field in ("original", "suspect"):
        f = request.files[field]
        if f.filename == "" or not _allowed_file(f.filename):
            return jsonify({"error": f"'{field}' must be a png, jpg, jpeg or webp file."}), 400
        raws[field] = f.read()
        if not raws[field]:
            return jsonify({"error": f"'{field}' is empty."}), 400
    logger.info("Received images for comparison (%d and %d bytes)", len(raws["original"]), len(raws["suspect"]))
    try:
        result = compare_bytes(raws["original"], raws["suspect"])
    except UnidentifiedImageError:
        return jsonify({"error": "A file could not be read as an image."}), 400
    except Exception:
        logger.exception("Comparison failed")
        return jsonify({"error": "Internal error during comparison."}), 500
    finally:
        raws = None
    return jsonify(result), 200


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
