"""Cue scores of the first version on the browser-rendered bank page and on the same page with two amounts changed in the HTML
(prints the values quoted in Section 7.1.3). Run with the backend virtual environment."""
import sys
sys.path.insert(0, "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend")
from legacy.config import Config
from legacy.forensic import analyze_image_bytes
E = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/paper-draft/evidence"
for name in ("real", "fake"):
    r = analyze_image_bytes(open(f"{E}/v1_native_{name}.png", "rb").read(), Config)
    f = r["features"]
    print(name, "fake_score", r["fake_score"], {k: f[k] for k in ("ela_score", "noise_score", "edge_score", "ghost_score", "arithmetic_score")})
