"""Evaluates the forensic pipeline (and whichever model is currently
bundled) against a small, hand-collected folder of REAL images — not
synthetic, not an adjacent-domain dataset. This is the validation step the
README's "Trained model" section repeatedly flags as still missing: every
number reported elsewhere in this project (calibrate.py, train_model.py)
comes from either a procedurally generated corpus or adjacent-domain
datasets (receipts/general-photos/found-forgeries), never from confirmed-
real vs. confirmed-fake *screenshots*.

This tool deliberately does NOT generate or supply that data itself. It
can't, responsibly — fabricating "real-world" fake screenshots and
presenting them as real-world validation would be exactly the kind of
misleading content this project's own README argues against throughout
(see e.g. "Known limitations": "Scores are not calibrated against real-
world ground truth"). What this tool does instead is make it cheap to get
a real number the moment you, or anyone, has even a small folder of
genuine examples — your own real screenshots for --authentic-dir, and
known-fake examples you've personally verified (e.g. from a fraud report
or fact-check writeup you trust) for --fake-dir.

Usage:
    python3 tools/evaluate_manual.py \
        --authentic-dir /path/to/confirmed_real_screenshots \
        --fake-dir /path/to/confirmed_fake_screenshots

Either flag may be omitted if you only have one side collected yet (e.g.
just checking the false-positive rate against your own real screenshots).
Neither directory needs to be large to be useful: even 10-20 of each is
more informative *per image* than another 1,000 synthetic ones, precisely
because it's the one thing every other evaluation in this project is
currently a substitute for (see README's "Trained model" honest caveats).

Reports accuracy/precision/recall/F1 in the same shape as
tools/train_model.py's report(), for direct comparison, plus every
misclassified filename with its score and detected content type, so a
wrong verdict can be inspected directly rather than only seen as a number.
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config  # noqa: E402
from forensic import analyze_image_bytes  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _images_in(dir_path):
    if not dir_path:
        return []
    return sorted(
        p for p in glob.glob(os.path.join(dir_path, "*"))
        if os.path.splitext(p)[1].lower() in IMAGE_EXTS
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--authentic-dir", help="Folder of real images you've personally confirmed are authentic")
    parser.add_argument("--fake-dir", help="Folder of real images you've personally confirmed are fake/tampered")
    args = parser.parse_args()

    if not args.authentic_dir and not args.fake_dir:
        parser.error("pass at least one of --authentic-dir / --fake-dir")

    cases = [(p, 0) for p in _images_in(args.authentic_dir)] + [(p, 1) for p in _images_in(args.fake_dir)]
    if not cases:
        parser.error("no supported images (.jpg/.jpeg/.png/.webp) found in the given directories")

    tp = fp = tn = fn = 0
    misclassified = []
    for path, label in cases:
        with open(path, "rb") as f:
            raw = f.read()
        try:
            result = analyze_image_bytes(raw, Config)
        except Exception as exc:
            print(f"  SKIPPED (analysis failed): {path} — {exc}")
            continue

        predicted = 1 if result["is_fake"] else 0
        if predicted != label:
            misclassified.append((path, label, predicted, result["fake_score"], result["meta"]["content_type"]))
        if label == 1 and predicted == 1:
            tp += 1
        elif label == 1 and predicted == 0:
            fn += 1
        elif label == 0 and predicted == 1:
            fp += 1
        else:
            tn += 1

    total = tp + fp + tn + fn
    if total == 0:
        print("No images could be analyzed.")
        return

    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    print(f"\nn={total} (authentic={tn + fp}, fake={tp + fn})")
    print(f"accuracy={accuracy:.4f} precision={precision:.4f} recall={recall:.4f} f1={f1:.4f}")
    print(f"confusion_matrix: tn={tn} fp={fp} fn={fn} tp={tp}")

    if misclassified:
        print(f"\nMisclassified ({len(misclassified)}):")
        for path, label, predicted, score, content_type in misclassified:
            true_label = "fake" if label == 1 else "authentic"
            pred_label = "fake" if predicted == 1 else "authentic"
            print(f"  {os.path.basename(path):40s} true={true_label:9s} predicted={pred_label:9s} "
                  f"fake_score={score:.3f} content_type={content_type}")
    else:
        print("\nNo misclassifications.")

    print("\nThis result is only as trustworthy as the ground truth you provided in "
          "--authentic-dir/--fake-dir — see this file's docstring before citing it as validation.")


if __name__ == "__main__":
    main()
