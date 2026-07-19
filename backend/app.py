"""Flask API for the fake-screenshot detector."""
import logging
import os

from flask import Flask, jsonify

from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fake_screenshot_detector")

app = Flask(__name__)
app.config.from_object(Config)


@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "ok", "service": "fake-screenshot-detector"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
