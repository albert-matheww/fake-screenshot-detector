"""First-version pipeline on (a) a browser-rendered bank page and the same page with two amounts changed in the HTML,
(b) the same pixels saved as JPEG with and without an editing-software EXIF tag. Run from the repository root."""
import io, sys
sys.path.insert(0, "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend")
from legacy.config import Config
from legacy.forensic import analyze_image_bytes
from PIL import Image
E = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/paper-draft/evidence"
for name in ("real", "fake"):
    r = analyze_image_bytes(open(f"{E}/v1_native_{name}.png", "rb").read(), Config)
    print(f"native render '{name}': fake_score={r['fake_score']} is_fake={r['is_fake']} override={r['override_reason']} content_type={r['meta']['content_type']}")
    print("   arithmetic findings:", r["details"]["amount_consistency"].get("matched_flags"))
im = Image.open(f"{E}/v1_native_real.png").convert("RGB")
ex = Image.Exif(); ex[0x0131] = "Adobe Photoshop 25.0"
b1, b2 = io.BytesIO(), io.BytesIO()
im.save(b1, "JPEG", quality=92, exif=ex); im.save(b2, "JPEG", quality=92)
r1 = analyze_image_bytes(b1.getvalue(), Config); r2 = analyze_image_bytes(b2.getvalue(), Config)
print(f"JPEG with Software tag 'Adobe Photoshop 25.0': fake_score={r1['fake_score']} override={r1['override_reason']}")
print(f"same pixels, tag absent: fake_score={r2['fake_score']} is_fake={r2['is_fake']} override={r2['override_reason']}")
