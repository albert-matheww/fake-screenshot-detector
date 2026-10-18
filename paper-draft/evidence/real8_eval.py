"""Scores the eight hand-collected payment-list screenshots (4 edited .jpg, 4 real .webp). The images are personal and
are NOT in the repository; this script documents the exact procedure that produced real8_results.txt."""
import sys; sys.path.insert(0, "backend")
import analysis
IMG = "/private/tmp/claude-501/-Users-albertmathew-Desktop-projects-fake-screenshot-detector/dd5abb74-8524-43e1-980c-664131e23a6d/images"
for n, lab in [("3.jpg","edited"),("4.jpg","edited"),("5.jpg","edited"),("6.jpg","edited"),("7.webp","real"),("8.webp","real"),("9.webp","real"),("10.webp","real")]:
    r = analysis.analyze_image_bytes(open(f"{IMG}/{n}","rb").read())
    rule = [f["evidence"]["text"] for f in r["findings"] if f["id"].startswith("layout")]
    model = [(g["text"], g["level"]) for g in r["regions"] if g.get("source") != "rule"]
    print(f'{n:8s} {lab:7s} {r["image"]["width"]}x{r["image"]["height"]} verdict={r["verdict"]:20s} risk={r["risk_score"]:.2f} '
          f'top_word_p={r["stats"]["top_word_probability"]:.3f} model_regions={model} layout_rule={rule}')
