import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


def test_status_endpoint(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_analyze_missing_file(client):
    resp = client.post("/analyze", data={})
    assert resp.status_code == 400


def test_analyze_rejects_bad_extension(client):
    data = {"image": (io.BytesIO(b"not an image"), "malware.exe")}
    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_analyze_rejects_unreadable_file(client):
    data = {"image": (io.BytesIO(b"not a real jpeg"), "fake.jpg")}
    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_analyze_success(client, authentic_image_bytes):
    data = {"image": (io.BytesIO(authentic_image_bytes), "screenshot.jpg")}
    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "fake_score" in body
    assert "ela_image" in body
    assert "details" in body
