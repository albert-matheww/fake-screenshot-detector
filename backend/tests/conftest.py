"""Test fixtures: build synthetic 'authentic' and 'tampered' screenshot-like
images so the pipeline can be exercised without a real labeled dataset.
"""
import io
import random

import numpy as np
import pytest
from PIL import Image, ImageDraw


def _make_base_screenshot(seed: int = 0, size=(600, 400)) -> Image.Image:
    """A synthetic 'chat screenshot': flat background + text-like rectangles,
    saved through JPEG once to mimic a normal single-generation compression."""
    random.seed(seed)
    img = Image.new("RGB", size, color=(245, 245, 248))
    draw = ImageDraw.Draw(img)
    # Chat bubbles
    draw.rounded_rectangle([20, 20, 400, 80], radius=12, fill=(220, 230, 255))
    draw.rounded_rectangle([200, 100, 580, 160], radius=12, fill=(200, 250, 210))
    draw.rounded_rectangle([20, 180, 420, 240], radius=12, fill=(220, 230, 255))
    for _ in range(40):
        x, y = random.randint(0, size[0] - 5), random.randint(0, size[1] - 5)
        draw.line([x, y, x + 3, y], fill=(90, 90, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _tamper(img: Image.Image) -> Image.Image:
    """Simulate a spliced/edited region: paste a re-compressed, brightened
    patch (mimics editing a number/text and re-saving just that region),
    then save the whole thing through JPEG a second time to leave a
    double-compression artifact for ELA/quantization checks to catch."""
    tampered = img.copy()
    patch = tampered.crop((220, 105, 400, 155)).convert("RGB")
    # Alter the patch content and give it its own compression history.
    patch_arr = np.array(patch).astype(np.int16)
    patch_arr[:, :, 0] = np.clip(patch_arr[:, :, 0] + 40, 0, 255)
    patch = Image.fromarray(patch_arr.astype("uint8"))
    patch_buf = io.BytesIO()
    patch.save(patch_buf, format="JPEG", quality=60)
    patch_buf.seek(0)
    patch = Image.open(patch_buf).convert("RGB")

    tampered.paste(patch, (220, 105))
    # Also duplicate a chunk elsewhere to trigger the clone detector.
    clone_src = tampered.crop((20, 20, 120, 70))
    tampered.paste(clone_src, (450, 250))

    buf = io.BytesIO()
    tampered.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


@pytest.fixture
def authentic_image_bytes() -> bytes:
    img = _make_base_screenshot(seed=1)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture
def tampered_image_bytes() -> bytes:
    base = _make_base_screenshot(seed=1)
    tampered = _tamper(base)
    buf = io.BytesIO()
    tampered.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.fixture
def authentic_image() -> Image.Image:
    return _make_base_screenshot(seed=2)
