# 01 Project understanding

## What the project does
Screenshot Forensics takes an uploaded screenshot (chat, payment, bank, order, social, e-mail, SMS, dashboard) and returns
a four-tier verdict (evidence of editing / suspicious / no evidence / not enough text), the words most likely to have been
edited (with plain-language reasons), rule-based findings, and a fixed list of limitations. It is a research prototype, run
locally (Flask backend, React frontend, Docker image). Images are processed in memory only (`backend/app.py`, `analysis.py`).

History: v1 (git `9980514`..`4a89a2d`, now `backend/legacy/`) was an ELA / JPEG-ghost / noise / clone / EXIF / OCR-rule pipeline
with a RandomForest trained on photo and receipt datasets. v2 (this report; **uncommitted working tree** at time of writing)
replaces the detection core.

## Components -> files
| Component | Files |
|---|---|
| OCR + per-word features (95) + explanations | `backend/textforensics.py` |
| Rule checks (metadata, watermarks, arithmetic, dates, IBAN/Luhn, clock, layout grid) | `backend/semantic.py` |
| Verdict logic, regions, limitations | `backend/analysis.py` |
| API | `backend/app.py` (`/analyze`, `/status`) |
| Classifier artefacts | `backend/model_data/word_gbm.joblib`, `word_gbm_meta.json` |
| Corpus tooling (ScreenForge) | `backend/tools/forge/` (`render_chrome.py`, `patchbank.py`, `tamper.py`, `build_dataset.py`, `refeaturize.py`, `merge_corpora.py`) |
| Training / evaluation | `train_text_model.py`, `eval_real_cv.py`, `eval_ood.py`, `compare_legacy.py`, `eval_layout_rule.py`, `backend/tools/evaluate_manual.py` |
| Frontend | `frontend/src/**` (React 18, Vite, vitest; demo mode) |
| Deployment | `backend/Dockerfile`, `docker-compose.yml`, `render.yaml`, `frontend/nginx.conf` |
| Legacy v1 (benchmark only) | `backend/legacy/` |

## Methodology as implemented
1. OCR with Tesseract (default page mode; boxes with confidence >= 0 kept; words of one character skipped).
2. 95 per-word features: 40 raw rendering measurements, 6 geometry, 19 + 19 robust z-scores (vs. the rest of the image / vs.
   the other words on the same line), 11 line/image-relative extras. Boosted decision trees (scikit-learn
   `HistGradientBoostingClassifier`) give P(word edited); image score = max word probability.
3. Two thresholds calibrated on validation genuine real screenshots (target 5 % -> "suspicious", 1 % -> "evidence").
4. Rule checks produce findings (high/medium/low). High-severity findings force the evidence tier, medium the suspicious tier.
5. Training data: ScreenForge, generated (see 05 in the report). Edits simulated by two engines (Pillow/FreeType, Chrome).

## Data
20,814 generated images (14,494 train / 3,083 val / 3,237 test) from three authentic sources: real device screenshots
(one author's machine, never distributed), 1,600 Chrome-rendered app UIs (16 layouts, 24 fonts), Pillow-rendered UIs.
Splits by base image (hash); test edits use held-out fonts. Licences: Chrome/Pillow renders are generated; real screenshots
are private; no third-party dataset is used by the final model (STFD requires an e-mailed password: requested, not received).

## Evidence inventory (what exists)
| Evidence | Artefact (paper-draft/evidence/) |
|---|---|
| v1 audit on 60 genuine screenshots | `fp_results.json`, `exp_fp.py`; summary in `facts.txt` |
| v1 edit experiment (42 image sets x 4 variants) | `tamper_results.json`, `exp_tamper.py` |
| Final model training + held-out test breakdown | `train_final_v6.log` |
| Leave-files-out on 73 full-size genuine screenshots | `leave_files_out_v6.log`, `cv_summary_v6.json` |
| v1 vs v2 on 500 identical test images | `compare_legacy.txt` |
| Cross-engine experiment | `cross_engine.txt` (re-run, see script) |
| Layout-grid rule validation | `layout_rule_eval.txt` |
| Eight hand-collected screenshots | `real8_results.txt` (images private) |
| Column-peer experiment (rejected) | `train_v7_column_peers.log` + session record |
| Corpus build log | `corpus_build_v1.log` |
| Tests | `pytest.txt`, `vitest.txt` |
| Docker image build + live request | `docker_test.log` |
| Derived corpus / code / environment facts | `facts.txt`, `derive_facts.py` |

## What does NOT exist
- No evaluation on edits made by independent people with real tools beyond a **8-image development sample** (4 edited, 4 real;
  these images were used to diagnose and improve the system, so they are development data, not a test).
- No evaluation on STFD, DocTamper or any public text-forgery benchmark (no access).
- No comparison with a published learned localiser (TruFor, DTD...) on the same data.
- No ablation of the 95 features or of the two rule families.
- No confidence intervals except an interval computed by hand for one proportion (Wilson).
- No multiple random seeds (single split, single model fit per experiment).
- No evidence on AI-generated screenshots (the tool does not target them).
- No latency/throughput benchmark beyond logged per-image milliseconds.

## Limitations and failures found (from code, tests, commits and runs)
- v1: 20 % of genuine screenshots flagged; cues saturated; AUC 0.50 on word edits; arithmetic rule false alarms.
- OCR dropped one third of edited words at confidence threshold 40 (fixed: keep all boxes).
- Seam feature fires on UI borders; single-glyph boxes -> false alarms (fixed: skip them, more real windows, weighting).
- Evaluation bugs found and fixed: group breakdown compared edits with wrong genuine images; cross-validation calibrated
  thresholds on data the model had trained on.
- Pillow-only training learned an engine signature (cross-engine AUC 0.75).
- Layout rule first version 2.0 % false alarms (skipped OCR rows) -> tightened to 0.09 %.
- Column-peer features / rule: no gain / 8-20 % false alarms -> not shipped.
- Eight-image sample: two of four real edits missed.
