import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from forensic import (
    compute_ela,
    ela_feature_score,
    compute_jpeg_ghost,
    check_metadata,
    check_document_text,
    check_quantization_tables,
    estimate_noise_inconsistency,
    detect_clone_regions,
    analyze_image_bytes,
)
from model_loader import predict_fake, predict_fake_heuristic


def test_compute_ela_returns_image_and_array(authentic_image):
    ela_image, diff_arr = compute_ela(authentic_image, quality=90)
    assert isinstance(ela_image, Image.Image)
    assert diff_arr.shape[2] == 3
    assert diff_arr.dtype == np.uint8


def test_ela_feature_score_bounded(authentic_image):
    _, diff_arr = compute_ela(authentic_image, quality=90)
    features = ela_feature_score(diff_arr)
    assert 0.0 <= features["score"] <= 1.0
    assert set(features) == {
        "mean_diff", "std_diff", "hotspot_ratio", "cluster_ratio", "cluster_size", "score",
    }


def test_jpeg_ghost_bounded(authentic_image):
    # NOTE: JPEG Ghost is deliberately excluded from config.WEIGHTS (see the
    # comment there) — testing against a synthetic corpus (backend/tools/
    # calibrate.py) showed it unreliable on flat/vector-UI screenshot content
    # (it sometimes scored an untouched image *higher* than its tampered
    # counterpart). It's kept computed and shown in the per-cue breakdown for
    # transparency/debugging, so this test only checks it stays well-formed,
    # not that it's directionally correct.
    result = compute_jpeg_ghost(authentic_image)
    assert 0.0 <= result["score"] <= 1.0


def test_check_metadata_no_exif_is_not_flagged(authentic_image):
    result = check_metadata(authentic_image)
    assert result["has_exif"] is False
    assert result["suspicious_flags"] == []
    assert result["score"] == 0.0


def test_check_document_text_flags_generator_watermark():
    img = Image.new("RGB", (600, 200), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Regions Bank Statement", fill="black")
    d.text((20, 60), "Account Holder: John Doe", fill="black")
    d.text((20, 100), "Account # 123456789", fill="black")
    d.text((20, 140), "BankStatements.net", fill="black")

    result = check_document_text(img)
    if result.get("note", "").startswith("OCR not available"):
        return  # environment has no tesseract binary; nothing to assert
    assert result["score"] > 0.0
    assert len(result["matched_flags"]) >= 1


def test_check_document_text_clean_image_not_flagged(authentic_image):
    result = check_document_text(authentic_image)
    assert result["score"] == 0.0
    assert result["matched_flags"] == []


def test_check_quantization_tables_handles_missing_tables():
    # A freshly created PIL image with no `.quantization` attr (e.g. PNG-like)
    img = Image.new("RGB", (50, 50))
    result = check_quantization_tables(img)
    assert result["present"] is False
    assert result["score"] == 0.0


def test_noise_estimate_bounded(authentic_image):
    result = estimate_noise_inconsistency(authentic_image)
    assert 0.0 <= result["score"] <= 1.0


def test_clone_detection_bounded(authentic_image):
    result = detect_clone_regions(authentic_image)
    assert 0.0 <= result["score"] <= 1.0
    assert result["blocks_checked"] > 0


def test_predict_fake_heuristic_weighted_average():
    # predict_fake_heuristic is the pure weighted-average fallback used when
    # no trained model is bundled/loadable — tested directly here since
    # predict_fake() itself now prefers the trained model when available
    # (see test_trained_model_is_loaded_and_used below).
    features = {
        "ela_score": 1.0, "quant_score": 1.0, "noise_score": 1.0,
        "clone_score": 1.0, "metadata_score": 1.0,
    }
    assert predict_fake_heuristic(features, Config.WEIGHTS) == 1.0

    zero_features = {k: 0.0 for k in features}
    assert predict_fake_heuristic(zero_features, Config.WEIGHTS) == 0.0


def test_predict_fake_override_forces_is_fake_despite_low_composite_score(monkeypatch):
    # The actual bug report this guards against: several noisy cues (ELA,
    # noise) can dilute a genuinely conclusive single cue below threshold in
    # a plain weighted average. A high-confidence override must catch this
    # regardless of what the other cues say. Forces the heuristic path via
    # monkeypatch so this test exercises that exact dilution scenario
    # regardless of whether a trained model happens to be bundled.
    import model_loader
    monkeypatch.setattr(model_loader, "_MODEL", None)

    features = {
        "ela_score": 0.1, "quant_score": 0.0, "noise_score": 0.1,
        "clone_score": 0.0, "metadata_score": 0.9, "text_score": 0.0,
    }
    result = model_loader.predict_fake(features, Config.WEIGHTS, Config.FAKE_THRESHOLD,
                                        overrides=Config.OVERRIDE_CUES)
    assert result["fake_score"] < Config.FAKE_THRESHOLD  # composite alone wouldn't cross
    assert result["is_fake"] is True                     # but the override still fires
    assert result["override_reason"] == "metadata_score"

    # No override cue is high enough: the composite score alone decides.
    clean_features = {**features, "metadata_score": 0.3}
    clean_result = model_loader.predict_fake(clean_features, Config.WEIGHTS, Config.FAKE_THRESHOLD,
                                              overrides=Config.OVERRIDE_CUES)
    assert clean_result["is_fake"] is False
    assert clean_result["override_reason"] is None


def test_trained_model_is_loaded_and_used():
    # Guards the wiring described in the README's "Upgrading to a trained
    # model" section: backend/model_data/rf_model.joblib should load at
    # import time and be preferred over the heuristic.
    import model_loader
    assert model_loader._MODEL is not None, "expected the bundled RandomForest model to load"
    assert "randomforest" in model_loader.MODEL_NAME.lower()

    features = {
        "ela_score": 0.5, "ghost_score": 0.0, "quant_score": 0.0,
        "noise_score": 0.5, "clone_score": 0.0, "metadata_score": 0.0, "text_score": 0.0,
    }
    result = predict_fake(features, Config.WEIGHTS, Config.FAKE_THRESHOLD, overrides=Config.OVERRIDE_CUES)
    assert 0.0 <= result["fake_score"] <= 1.0


def test_analyze_image_bytes_end_to_end_authentic(authentic_image_bytes):
    result = analyze_image_bytes(authentic_image_bytes, Config)
    assert 0.0 <= result["fake_score"] <= 1.0
    assert result["verdict"] in {"Likely Authentic", "Possible Fake"}
    assert result["ela_image"].startswith("data:image/png;base64,")
    assert "ela" in result["details"]
    assert "quantization" in result["details"]
    assert "metadata" in result["details"]
    assert "noise" in result["details"]
    assert "clone_detection" in result["details"]
    assert "document_text" in result["details"]
    assert len(result["meta"]["sha256"]) == 64


def test_analyze_image_bytes_runs_on_tampered_fixture(tampered_image_bytes):
    # Smoke test: the pipeline should run end-to-end on a tampered image
    # without error and produce the same well-formed result shape.
    result = analyze_image_bytes(tampered_image_bytes, Config)
    assert 0.0 <= result["fake_score"] <= 1.0
    assert "clone_detection" in result["details"]
    assert "jpeg_ghost" in result["details"]


def test_editing_tool_exif_fixture_is_reliably_flagged(authentic_image_bytes):
    # This is the actual accuracy regression test, using the one tamper type
    # that testing against a synthetic corpus (backend/tools/calibrate.py)
    # showed is *reliably* caught end-to-end: an editing-tool fingerprint
    # left in EXIF. Compression/noise-artifact cues (ELA, JPEG ghost, block
    # noise) turned out to be much weaker signals on flat/vector-UI
    # screenshots than on natural photographs — see the README's "Known
    # limitations" — so this test intentionally targets the tamper class the
    # pipeline can actually be trusted on, rather than asserting a blanket
    # "any edit crosses the threshold" claim the evidence doesn't support.
    img = Image.open(io.BytesIO(authentic_image_bytes)).convert("RGB")
    from PIL.ExifTags import Base
    exif = Image.Exif()
    exif[Base.Software.value] = "Adobe Photoshop 25.0"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, exif=exif)
    tampered_bytes = buf.getvalue()

    authentic_result = analyze_image_bytes(authentic_image_bytes, Config)
    tampered_result = analyze_image_bytes(tampered_bytes, Config)

    assert tampered_result["fake_score"] > authentic_result["fake_score"]
    assert authentic_result["is_fake"] is False
    assert tampered_result["is_fake"] is True


def test_generator_watermark_document_is_flagged_despite_clean_pixels():
    # Directly reproduces a real false-negative found in manual testing: a
    # fake bank statement (from a real fake-statement-generator site) that
    # read as "Likely Authentic" because its pixel-level cues (ELA, noise)
    # were unremarkable for a dense, text-heavy document — nothing about the
    # image *bytes* looked tampered. What gave it away was the document's
    # actual text: a third-party generator's watermark and placeholder
    # customer/account data, which no pixel-forensics cue can see. This test
    # is the regression guard for that exact gap.
    img = Image.new("RGB", (700, 500), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Regions Bank", fill="black")
    d.text((20, 60), "Mr John Doe", fill="black")
    d.text((20, 100), "ACCOUNT # 123456789", fill="black")
    d.text((20, 400), "BankStatements.net", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    raw_bytes = buf.getvalue()

    result = analyze_image_bytes(raw_bytes, Config)
    if result["details"]["document_text"].get("note", "").startswith("OCR not available"):
        return  # environment has no tesseract binary; nothing to assert

    assert result["details"]["document_text"]["score"] > 0.0
    assert result["is_fake"] is True


def _flat_image_with_patch(size=(300, 300), patch_size=48, patch_pos=(24, 24),
                            duplicate_at=None, seed=42) -> Image.Image:
    """A clean synthetic image isolating the copy-move signal: a flat
    background with one randomly-textured patch, optionally duplicated
    elsewhere. Used to unit-test detect_clone_regions() without the
    confounding sparse noise of the full chat-screenshot fixture.

    `patch_pos` / `duplicate_at` are chosen as multiples of the detector's
    default stride (12px) so the block-sampling grid captures pixel-identical
    crops of the patch at both locations.
    """
    img = Image.new("RGB", size, (250, 250, 250))
    rng = np.random.default_rng(seed)
    patch = Image.fromarray(
        rng.integers(0, 255, size=(patch_size, patch_size, 3), dtype=np.uint8)
    )
    img.paste(patch, patch_pos)
    if duplicate_at is not None:
        img.paste(patch, duplicate_at)
    return img


def test_clone_detection_finds_duplicated_patch():
    original = _flat_image_with_patch(duplicate_at=None)
    with_clone = _flat_image_with_patch(duplicate_at=(216, 216))

    result_original = detect_clone_regions(original)
    result_clone = detect_clone_regions(with_clone)

    assert result_clone["duplicate_pairs"] > result_original["duplicate_pairs"]
    assert result_clone["duplicate_pairs"] > 0
    assert result_clone["score"] > result_original["score"]
