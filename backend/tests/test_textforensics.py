"""Feature extractor + edit simulator tests (no trained model needed)."""
import random

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

import textforensics as tf
from tools.forge import tamper


def _page(seed=0, w=520, h=320):
    """A small genuine-looking page: several lines of text in one font (so line-mates are comparable)."""
    img = Image.new("RGB", (w, h), (250, 250, 252))
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=22)
    rows = ["Payment received from Alex", "Amount 1,284.19 USD", "Reference 88231907 completed",
            "Status Paid on Monday", "Balance 5,402.77 available", "Thank you for banking with us"]
    for i, r in enumerate(rows):
        d.text((24, 20 + i * 44), r, font=f, fill=(20, 20, 30))
    return img


def test_ocr_and_features_shape():
    img = _page()
    words = tf.ocr_words(img)
    assert len(words) >= 10
    X, kept, info = tf.image_word_features(img, words)
    assert X.shape == (len(kept), len(tf.FEATURE_NAMES))
    assert np.isfinite(X).all()
    assert info["measured_words"] == len(kept)


def test_blank_image_has_no_measurable_words():
    img = Image.new("RGB", (300, 200), "white")
    X, kept, info = tf.image_word_features(img, [])
    assert X.shape[0] == 0 and kept == []


def test_edit_simulator_changes_only_the_target_box():
    img = _page()
    words = tf.ocr_words(img)
    res = tamper.edit_word(img, words, random.Random(1), [1, 2, 3, 4])
    assert res is not None
    a, b = np.asarray(img).astype(int), np.asarray(res["image"]).astype(int)
    diff = np.abs(a - b).sum(axis=2) > 0
    ys, xs = np.where(diff)
    x0, y0, x1, y1 = res["box"]
    assert diff.any()
    assert xs.min() >= x0 - 1 and xs.max() <= x1 + 1 and ys.min() >= y0 - 1 and ys.max() <= y1 + 1


def test_edited_word_is_a_stronger_outlier_than_untouched_words():
    """Averaged over edits, the replaced word deviates more from its neighbours than untouched words do."""
    img = _page()
    words = tf.ocr_words(img)
    cols = {n: j for j, n in enumerate(tf.FEATURE_NAMES)}
    z_cols = [cols[n] for n in tf.FEATURE_NAMES if n.startswith("z_img_")]
    edited, other = [], []
    for seed in range(12):
        res = tamper.edit_word(img, words, random.Random(seed), [1, 2, 3, 4])
        if res is None:
            continue
        w2 = tf.ocr_words(res["image"])
        X, kept, _ = tf.image_word_features(res["image"], w2)
        bx = res["box"]
        for i, wd in enumerate(kept):
            cx, cy = wd["left"] + wd["width"] / 2, wd["top"] + wd["height"] / 2
            inside = bx[0] <= cx <= bx[2] and bx[1] <= cy <= bx[3]
            (edited if inside else other).append(float(np.abs(X[i, z_cols]).mean()))
    assert edited and other
    assert np.mean(edited) > np.mean(other)


def test_font_bank_has_unseen_test_fold():
    bank = tamper.font_bank()
    assert len(bank) > 50
    assert {f["fold"] for f in bank} == {0, 1, 2, 3, 4}


def test_degrade_scales_boxes():
    img = _page()
    raw, ext, boxes, meta = tamper.degrade(img, [(100, 100, 200, 140)], random.Random(5))
    assert ext in ("png", "jpg") and len(raw) > 100
    assert len(boxes) == 1
    if "scale" in meta:
        assert boxes[0][2] <= 200 * meta["scale"] + 2
