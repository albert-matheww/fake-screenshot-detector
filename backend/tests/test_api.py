import io

import pytest
from PIL import Image, ImageDraw, ImageFont

import analysis
from app import app as flask_app


def _receipt_png(w=520, h=360, text_rows=None) -> bytes:
    img = Image.new("RGB", (w, h), (250, 250, 252))
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=22)
    rows = text_rows or ["Payment received from Alex", "Amount 1,284.19 USD", "Reference 88231907 completed",
                         "Status Paid on Monday", "Balance 5,402.77 available", "Thank you for banking with us"]
    for i, r in enumerate(rows):
        d.text((24, 20 + i * 44), r, font=f, fill=(20, 20, 30))
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_status_reports_model(client):
    body = client.get("/status").get_json()
    assert body["status"] == "ok"
    assert body["model"]["loaded"] is True
    # a version-1 cue is never live, whatever the stored gate file says
    gates = body["model"]["gates"]
    assert all(v != "live" for k, v in gates.items() if k.startswith("v1."))


def test_analyze_missing_file(client):
    assert client.post("/analyze", data={}).status_code == 400


def test_analyze_rejects_bad_extension(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(b"x"), "malware.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_analyze_rejects_unreadable_file(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(b"not a jpeg"), "fake.jpg")},
                    content_type="multipart/form-data")
    assert r.status_code == 400


def test_analyze_contract(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(_receipt_png()), "s.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    b = r.get_json()
    assert b["verdict"] in {"evidence_of_editing", "suspicious", "no_evidence", "inconclusive"}
    assert 0.0 <= b["risk_score"] <= 1.0
    assert isinstance(b["regions"], list) and isinstance(b["findings"], list)
    assert len(b["limitations"]) >= 2
    assert b["image"]["width"] == 520 and b["image"]["height"] == 360
    assert len(b["meta"]["sha256"]) == 64
    for region in b["regions"]:
        assert 0 <= region["x"] < 520 and 0 <= region["y"] < 360 and region["w"] > 0 and region["h"] > 0


def test_blank_image_is_inconclusive_not_authentic(client):
    img = Image.new("RGB", (400, 300), "white")
    b_ = io.BytesIO()
    img.save(b_, "PNG")
    b = client.post("/analyze", data={"image": (io.BytesIO(b_.getvalue()), "blank.png")},
                    content_type="multipart/form-data").get_json()
    assert b["verdict"] == "inconclusive"


def test_no_evidence_is_never_called_authentic(client):
    b = client.post("/analyze", data={"image": (io.BytesIO(_receipt_png()), "s.png")},
                    content_type="multipart/form-data").get_json()
    blob = (b["verdict_label"] + " ".join(b["reasons"])).lower()
    assert "authentic" not in blob and "genuine" not in blob


def test_semantic_contradiction_forces_evidence_tier(client):
    rows = ["Subtotal $120.00", "Tax $9.60", "Total $60.00", "Order placed Fri, 12 Jan 2026",
            "Thank you for shopping", "Receipt number 4412"]
    b = client.post("/analyze", data={"image": (io.BytesIO(_receipt_png(text_rows=rows)), "s.png")},
                    content_type="multipart/form-data").get_json()
    ids = {f["id"] for f in b["findings"]}
    assert "arith.total_below_subtotal" in ids
    assert b["verdict"] == "evidence_of_editing"


def test_editing_software_tag_forces_evidence_tier(client):
    img = Image.open(io.BytesIO(_receipt_png())).convert("RGB")
    ex = Image.Exif()
    ex[0x0131] = "Adobe Photoshop 25.0"
    b_ = io.BytesIO()
    img.save(b_, "JPEG", exif=ex, quality=95)
    b = client.post("/analyze", data={"image": (io.BytesIO(b_.getvalue()), "s.jpg")},
                    content_type="multipart/form-data").get_json()
    assert any(f["id"] == "metadata.editing_software" for f in b["findings"])
    assert b["verdict"] == "evidence_of_editing"


def test_model_feature_list_matches_code():
    assert analysis._MODEL is not None, analysis._LOAD_ERROR


def test_large_uploads_are_never_spooled_to_disk(client, monkeypatch):
    """Werkzeug's default parser rolls uploads above 500 KB over to a temporary file; ours must not."""
    import os
    import tempfile
    rolls = []
    original = tempfile.SpooledTemporaryFile.rollover
    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", lambda self: (rolls.append(1), original(self))[1])
    big = os.urandom(2 * 1024 * 1024)     # not an image: the point is the upload path, not the analysis
    client.post("/analyze", data={"image": (io.BytesIO(big), "big.png")}, content_type="multipart/form-data")
    assert rolls == []
