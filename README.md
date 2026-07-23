# Screenshot Forensics — Working MVP

A runnable implementation of the fake chat / bank statement screenshot
detector described in the design doc: a Flask backend performing Error
Level Analysis (ELA) plus complementary forensic checks, and a React
frontend for upload and results. This is a **scoped-down MVP**, not the
full 6-month production system — see "What's implemented" and "What's not"
below before treating its verdicts as authoritative.

## What's implemented

- **ELA** (`backend/forensic.py::compute_ela` / `ela_feature_score`) —
  recompresses the image and diffs it against the original. Hotspot
  detection compares each block against its own *local neighborhood*
  (robust MAD-based z-score), not a whole-image threshold — this avoids
  conflating "block has real content" with "block was tampered", which a
  global threshold cannot distinguish on mostly-flat UI screenshots.
- **JPEG Ghost (multi-quality recompression scan)** (`compute_jpeg_ghost`)
  — recompresses the image across a range of candidate qualities and looks
  for blocks whose recompression-error curve dips at a different quality
  than the rest of the image (Farid's JPEG Ghost method), the classic
  signature of a region edited and re-saved at a different generation than
  its surroundings. **Computed and shown in the per-cue breakdown, but
  intentionally excluded from `fake_score`** — calibration testing (see
  below) showed it unreliable on flat/vector-UI content, sometimes scoring
  an *untouched* image higher than its tampered counterpart. Kept visible
  for transparency/debugging, not because it's trusted.
- **JPEG quantization table check** — flags images with more compression
  tables than a single JPEG encode should have (kept as a minor, low-weight
  legacy signal; rarely fires in practice since most re-encoders still only
  emit two tables).
- **EXIF/metadata check** — flags editing-tool software tags (weighted
  heavily — this is close to a smoking gun), camera EXIF on a "screenshot",
  and GPS data. One of the two most reliable cues in this pipeline.
- **Document text check (OCR)** (`check_document_text`) — extracts the
  image's actual text (via Tesseract) and flags known fake-statement/
  fake-document generator watermarks (e.g. a site brand printed on the
  document) and placeholder data (generic names like "John Doe", obviously
  sequential/repeated-digit account numbers). This is the other most
  reliable cue: pixel-level forensics (ELA, noise, clone detection) cannot
  see *what the document says*, only how its bytes were compressed — and a
  real-world test case (see "Known limitations") showed that gap matters:
  a fake bank statement carrying a generator's own watermark read as
  "Likely Authentic" on pixel evidence alone.
- **Block-wise noise consistency check** — flags local-neighborhood noise
  outliers (same rationale as ELA above) plus overall coefficient of
  variation across blocks.
- **Copy-move (clone) detector** (`detect_clone_regions`) — rewritten to use
  offset-vector voting (Fridrich/Popescu-style block matching): near-duplicate
  blocks that are spatially far apart vote for the displacement vector
  between them, and a genuine copy-paste produces one dominant, spatially
  *compact* peak (many blocks agreeing on the same offset, clustered in one
  area). This replaces the old "any two blocks share a hash" approach, which
  couldn't tell a real rigid copy-move apart from coincidentally-similar
  repeated UI elements (icons, bullet points) scattered around the frame.
- **Trained classifier** (`backend/model_loader.py`) — a RandomForest
  trained on a real, labeled forgery dataset (see "Trained model" below for
  what dataset, measured accuracy, and honest domain-gap caveats), loaded
  from `backend/model_data/rf_model.joblib` and preferred over the
  transparent weighted-average heuristic (`predict_fake_heuristic`, kept as
  a fallback for environments without a bundled model or scikit-learn). The
  heuristic's weights were themselves reweighted based on calibration
  testing against a synthetic corpus (see `backend/tools/calibrate.py`)
  rather than the original arbitrary weights — metadata and document-text
  carry the most weight since they're the two cues testing could actually
  validate as reliable.
- **High-confidence override** (`config.OVERRIDE_CUES`, applied in
  `predict_fake` on top of *either* classifier above) — even a trained
  model can fail to weight a rare-but-conclusive signal correctly (see
  "Trained model" below — the model's own probability sometimes undershoots
  on exactly the cases that matter). A cue that's genuinely conclusive on
  its own (an editing-tool EXIF tag, an OCR-caught generator watermark) can
  get diluted or under-weighted; if `metadata_score` or `text_score`
  individually clears a high bar (0.8), the verdict is forced to "fake"
  regardless of the composite score — the composite `fake_score` is still
  reported unmodified, and the API/UI both surface *why* (`override_reason`)
  so this never happens silently. This exists because of a concrete false
  negative found in
  manual testing (see "Known limitations").
- **Flask API** (`/analyze`, `/status`) — images processed in memory only,
  never written to disk; SHA-256 logged for traceability, not the image
  itself.
- **React frontend** — drag-and-drop upload, ELA heatmap + original
  side-by-side, per-cue breakdown with suspicion scores, JSON report
  download.
- **Tests** — backend pytest tests (unit tests per forensic cue + API
  integration tests + an accuracy regression test using the tamper type
  proven reliable) and frontend vitest tests, all passing.
- **Docker** — Dockerfiles for both services + `docker-compose.yml` (nginx
  reverse-proxies `/api/*` to the Flask container).

## What's NOT implemented (out of scope for this MVP)

The design doc describes a 6-month, multi-person project. These pieces are
explicitly **not** built here, and would need real work to add:

- **No CNN / deep-learning model.** A RandomForestClassifier over the seven
  cue scores is now trained and bundled (see "What's implemented" and
  "Known limitations" below) — this is real progress over the original
  MVP's pure heuristic, but it's still a shallow model over hand-crafted
  features, not the CNN-on-ELA-image "hybrid" approach the design doc's
  model-comparison table describes as the strongest option.
- **No screenshot-specific labeled dataset.** The trained model uses a real
  scanned-*receipt* forgery dataset (see below) because no public dataset of
  labeled real/fake chat or bank-statement *screenshots* was found — there
  is a genuine, documented domain gap as a result. No CASIA/Columbia/NIST
  download or preprocessing pipeline for that data either.
- **No PRNU sensor-noise analysis** (the doc itself notes this doesn't
  apply to screenshots).
- **No font/subpixel or GAN-fingerprint analysis.**
- **No cloud deployment, autoscaling, CI/CD, or Prometheus/Grafana
  monitoring** — just local Docker Compose.
- **No auth, rate limiting, or HTTPS termination** — add a reverse proxy
  (e.g. Caddy/Traefik) with TLS before exposing this beyond localhost.

## Known limitations of the heuristic

- Scores are **not calibrated against real-world ground truth** — there is
  no labeled dataset of actual forged screenshots in this repo. The weights
  in `config.py` were calibrated against a *synthetic* corpus generated by
  `backend/tools/calibrate.py` (paired authentic/tampered images across
  several tamper types), which is the best available substitute, but it is
  not a real-world validation. Treat `fake_score` as a rough, explainable
  signal, not a probability.
- **Measured, reproducible behavior against that synthetic corpus** (run
  `python3 tools/calibrate.py` inside the backend container to reproduce):
  editing-tool EXIF fingerprints are caught **reliably (100%)**, and
  authentic images are **never** false-flagged (0% false-positive rate).
  Recompressed-patch edits, copy-move duplication, and flat/low-texture
  overwrites are caught only some of the time — compression- and
  noise-artifact analysis (ELA, JPEG Ghost, block noise) turned out to be
  **much weaker signals on flat, mostly-vector UI screenshots than on
  natural photographs**, where these classical forensic techniques were
  originally developed and validated. This is a genuine, currently-unsolved
  gap, not a hidden one — see `backend/tools/calibrate.py` to reproduce or
  extend the calibration corpus.
- JPEG Ghost (multi-quality recompression scan) is implemented and
  documented above, but testing showed it unreliable on this content type
  specifically (see note above) — it's excluded from `fake_score` for that
  reason, not included and silently trusted.
- Screenshots legitimately contain repeated UI elements (icons, rounded
  corners, bullet points). The clone detector's offset-voting approach
  specifically targets this: a real copy-paste produces one dominant,
  spatially compact displacement vector, while coincidentally-similar
  repeated elements spread their matches across many different vectors and
  a larger area. Dense, regularly-spaced decorative content (e.g. a strict
  grid of identical icons) can still produce false peaks — this remains a
  real risk, just a narrower one than before.
- ELA and JPEG Ghost are weak against images that were **never
  JPEG-compressed** at all (e.g. a PNG screenshot with no compression
  artifacts to diff) or that were **uniformly** re-saved as a whole (no
  localized hotspot).
- **Real-world false negative found in manual testing, now fixed**: a fake
  bank statement (from an actual fake-statement-generator site, carrying
  that site's own watermark and placeholder customer/account data) scored
  "Likely Authentic" — its pixel-level cues weren't remarkable for a dense,
  text-heavy document, so the composite weighted score stayed low despite
  the document being trivially identifiable as fake *by reading it*. This
  is why the OCR-based document-text check and the high-confidence
  override exist (see "What's implemented" above): pixel forensics alone
  cannot see watermarks or placeholder data, and a plain weighted average
  can dilute even a conclusive single signal below threshold. This also
  means OCR quality (font size, resolution, contrast) directly affects
  reliability of this specific cue — a blurry or very low-resolution photo
  of a statement may not OCR cleanly enough to catch a watermark that a
  clean screenshot would.

## Running locally (without Docker)

Backend (requires the `tesseract-ocr` system package for the document-text
cue — `apt-get install tesseract-ocr` / `brew install tesseract`; without it,
that cue degrades gracefully to a 0 score rather than failing the request):
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py            # serves on http://localhost:5000
```

Run backend tests:
```bash
cd backend
pytest tests/ -v
```

Frontend:
```bash
cd frontend
npm install
npm run dev               # serves on http://localhost:5173, proxies /api -> :5000
```

Run frontend tests:
```bash
cd frontend
npm test
```

## Running with Docker Compose

```bash
docker compose up --build
```
- Frontend: http://localhost:8080
- Backend API directly: http://localhost:5050 (mapped from container port 5000 —
  remapped from the default 5000 because that port is taken by macOS's
  AirPlay Receiver/ControlCenter on many Macs; change it back in
  `docker-compose.yml` if that doesn't apply to you)

## API

`POST /analyze` — multipart/form-data, field `image` (png/jpg/jpeg/webp, ≤10MB).

Response:
```json
{
  "fake_score": 0.47,
  "is_fake": true,
  "verdict": "Possible Fake",
  "override_reason": "text_score",
  "ela_image": "data:image/png;base64,...",
  "features": { "ela_score": 0.87, "quant_score": 0.0, "noise_score": 1.0, "clone_score": 0.0, "metadata_score": 0.0, "text_score": 1.0 },
  "details": { "ela": {...}, "jpeg_ghost": {...}, "quantization": {...}, "metadata": {...}, "noise": {...}, "clone_detection": {...}, "document_text": {...} },
  "meta": { "original_format": "JPEG", "sha256": "...", "processing_ms": 292.2, "model": "randomforest-v1 (trained on the real, labeled 'Find it again!' receipt-forgery dataset, ICDAR 2023 — see README) + high-confidence overrides" }
}
```
Notes:
- `features`/`fake_score` intentionally omit `ghost_score` from the
  weighted combination (see "Known limitations") even though
  `details.jpeg_ghost` is always present in the response for transparency.
- `override_reason` is `null` unless a high-confidence override cue
  (`metadata_score` or `text_score`) fired on its own — see
  `config.OVERRIDE_CUES`. The example above shows exactly that case: ELA/
  noise were elevated (a dense document, not necessarily tampering) and
  clone/metadata were clean, so the composite `fake_score` (0.47) alone
  would round down to "authentic" — but the OCR cue caught a placeholder
  name and account number, which alone is conclusive enough to override.

`GET /status` — health check.

## Trained model (done) / upgrading it further

`backend/model_loader.py` loads `backend/model_data/rf_model.joblib` — a
RandomForestClassifier — at import time if present, and prefers it over the
weighted-average heuristic (`predict_fake_heuristic`, kept as the fallback
when no model is bundled or scikit-learn/joblib aren't installed). It was
trained via `backend/tools/train_model.py` on the **"Find it again!"
receipt-forgery dataset** (ICDAR 2023, L3i lab, University of La Rochelle:
https://l3i-share.univ-lr.fr/2023Finditagain/) — 988 real scanned receipts,
163 with realistic forgeries (copy-paste, text imitation, deletion, pixel
edits) and ground-truth labels, built from the public SROIE OCR dataset.

**Measured performance** (RandomForest, `n_estimators=300`,
`class_weight="balanced"`, `max_depth=6`, on the dataset's own held-out test
split of 218 images, 35 forged):

| | Old heuristic | Trained RandomForest |
|---|---|---|
| Precision | 42.3% | **100%** (0 false positives) |
| Recall | 31.4% | 28.6% |
| F1 | 0.361 | **0.444** |

An important, honest caveat: **this dataset is scanned paper receipts, not
chat/bank-statement screenshots** — no public labeled dataset of the latter
was found (see "What's NOT implemented"). Validated against this project's
own screenshot test fixtures, the trained model's own signal doesn't
reliably transfer (e.g. it scored a screenshot with a fake-generator
watermark only 0.23 on its own) — the high-confidence override
(`config.OVERRIDE_CUES`) is doing real, necessary work here, not just
redundant transparency. Recall (28.6%, missing ~71% of real forgeries in
this receipt test set) also has real room to improve; this is a first real
step, not a solved problem.

To retrain (e.g. against a better/larger/more relevant dataset later):
```bash
# data_dir must contain train.txt/val.txt/test.txt (CSV with `image` and
# `forged` columns) and matching train/ val/ test/ image folders — the
# "Find it again!" dataset's own shape.
docker compose run --rm -v /path/to/dataset:/data_in backend \
  python3 tools/train_model.py /data_in
```
This overwrites `backend/model_data/rf_model.joblib` in place; restart the
backend container to pick it up. `backend/tools/calibrate.py` (the
synthetic-corpus calibration tool from before this model existed) still
works and now reports the *trained model's* behavior on that corpus too,
useful as a quick sanity check between retrains.

## Project structure

```
fake-screenshot-detector/
  backend/
    app.py            # Flask routes
    forensic.py        # ELA, JPEG ghost, OCR/document-text, metadata, quantization, noise, clone detection, pipeline orchestration
    model_loader.py     # Loads the trained model if present; heuristic fallback + high-confidence overrides
    config.py           # Tunable thresholds/weights/overrides
    model_data/
      rf_model.joblib      # Trained RandomForest (see "Trained model" above)
      rf_model_meta.json   # Feature order the model expects
    tools/
      calibrate.py       # Synthetic corpus + calibration report (see "Known limitations")
      train_model.py     # Retrains rf_model.joblib from a labeled dataset
    requirements.txt
    Dockerfile
    tests/
  frontend/
    src/
      App.jsx
      components/ImageUpload.jsx
      components/AnalysisResults.jsx
      services/api.js
    Dockerfile
    nginx.conf
  docker-compose.yml
```
