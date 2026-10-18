"""Experiment A: false-positive rate on genuine, untouched macOS screenshots.
Only scores are recorded -- image contents are never displayed."""
import glob, io, json, os, random, sys, time
from concurrent.futures import ProcessPoolExecutor

BACKEND = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend"
sys.path.insert(0, BACKEND)
OUT = os.path.dirname(os.path.abspath(__file__))


def run(path):
    from config import Config
    from forensic import analyze_image_bytes
    raw = open(path, "rb").read()
    t = time.time()
    r = analyze_image_bytes(raw, Config)
    from PIL import Image
    im = Image.open(io.BytesIO(raw))
    return {
        "id": os.path.basename(path)[:40], "fmt": im.format, "size": im.size, "kb": len(raw) // 1024,
        "fake_score": r["fake_score"], "is_fake": r["is_fake"], "override": r["override_reason"],
        "ctype": r["meta"]["content_type"], "thr": r["meta"]["effective_threshold"],
        "features": r["features"], "ms": round((time.time() - t) * 1000),
        "text_flags": r["details"]["document_text"].get("matched_flags", []),
        "arith_flags": r["details"]["amount_consistency"].get("matched_flags", []),
    }


if __name__ == "__main__":
    home = os.path.expanduser("~")
    paths = []
    for pat in ("Desktop/Screenshot*.png", "Downloads/Screenshot*.png", "Downloads/Screenshot*.jpeg",
                "Desktop/untitled folder/Screenshot*.png", "Desktop/untitled folder/*/Screenshot*.png"):
        paths += glob.glob(os.path.join(home, pat))
    random.Random(1).shuffle(paths)
    paths = paths[:60]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(run, paths))
    json.dump(res, open(os.path.join(OUT, "fp_results.json"), "w"))
    print("done", len(res), "images in", round(time.time() - t0), "s")
