"""Column-relative z-scores of every amount-like word in the eight hand-collected screenshots (stroke thickness and edge
sharpness vs the other numbers of the same right-aligned column). Reproduces the observation that motivated, and then
failed, the column-comparison idea. Images are private and not in the repository."""
import sys, numpy as np
sys.path.insert(0, "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend")
from PIL import Image
import textforensics as tf
IMG = "/private/tmp/claude-501/-Users-albertmathew-Desktop-projects-fake-screenshot-detector/dd5abb74-8524-43e1-980c-664131e23a6d/images"
def rz(vals, own):
    med = np.median(vals); mad = np.median(np.abs(vals - med)) * 1.4826; sc = max(mad, 0.05 * abs(med), 1e-3); return abs((own - med) / sc)
col = {n: i for i, n in enumerate(tf.FEATURE_NAMES)}
for name, lab in (("3.jpg","edited"),("4.jpg","edited"),("5.jpg","edited"),("6.jpg","edited"),("7.webp","real"),("8.webp","real"),("9.webp","real"),("10.webp","real")):
    im = Image.open(f"{IMG}/{name}").convert("RGB"); X, kept, _ = tf.image_word_features(im)
    right = np.array([w["left"] + w["width"] for w in kept]); h = np.array([w["height"] for w in kept]); cy = np.array([w["top"] + w["height"] / 2 for w in kept])
    res = []
    for i, w in enumerate(kept):
        if w["left"] < im.width * 0.6: continue
        peers = [j for j in range(len(kept)) if j != i and abs(right[j] - right[i]) <= 0.4 * h[i] + 8 and 0.7 <= h[j] / h[i] <= 1.4 and abs(cy[j] - cy[i]) > 0.8 * h[i]]
        if len(peers) < 4: continue
        res.append((rz(X[peers, col["stroke_w2"]], X[i, col["stroke_w2"]]), rz(X[peers, col["sharp_hi"]], X[i, col["sharp_hi"]])))
    print(f"{name:8s} {lab:6s} words in the amount column: {len(res):2d} | max |z| stroke thickness {max(r[0] for r in res):5.1f} | max |z| edge sharpness {max(r[1] for r in res):5.1f}")
