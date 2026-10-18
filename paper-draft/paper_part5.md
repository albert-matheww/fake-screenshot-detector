@chapter 8|DISCUSSION, LIMITATIONS AND ETHICS

@section 8.1|WHAT THE RESULTS SHOW
The central result is a contrast. A pipeline of established photograph-forensics cues flagged one genuine screenshot in five and could not distinguish an edited word from its original, while a detector that asks only whether each word matches its neighbours separated simulated edits from genuine images with an AUC of about 0.85 on unseen images and unseen fonts. The contrast is consistent with this project's working hypothesis that an inserted word differs in rendering from its neighbours; work on document tampering notes that text within a cluster usually shares one font and size [@qu2023doctamper] but does not itself show that insertions differ in rendering. It also fits the broader point that screenshots lack the camera and compression traces on which photograph forensics relies (Section 1.2). The evidence does not identify which cues carry the signal: no ablation of feature groups was run, so the contribution of anti-aliasing, stroke, seam, noise and geometry features is unmeasured.

A second result concerns the cost of the evaluation. Four design decisions each changed the apparent quality of the system by a visible margin (no systematic tuning of the classifier was run for comparison): keeping low-confidence OCR boxes (the edited word reached the classifier in 90.2% of test edits instead of 67.4%), calibrating thresholds on genuine real screenshots, adding whole full-size screenshots to training, and training on two editing engines. Most of the time spent on this project went into data, protocols and error analysis, not into the model, and that is where the largest corrections were found.

The third is a pattern in what failed. The first version's cues failed because they were built for another medium. The layout rule's first version failed because a missing OCR box looked like a displaced number. The column-comparison idea failed because it was tested on the same eight images that suggested it. The calibration script failed because a threshold was fitted on data the model had already seen. In each case a measurement on a larger or separate sample, not a sharper argument, exposed the problem.

@section 8.2|LIMITATIONS
@numbered
1. **The edits are simulated.** Every figure in Chapter 7 except Section 7.9 comes from edits produced by the simulator of Section 5.3. Work on forgeries made by people cautions that results on synthetic benchmarks may not carry over to them or to other domains [@dhouib2026doctamper]. The only human-made edits tried are the four of Section 7.9, which are development data, and two of them were missed. The project cannot say how often a real forger's edit would be caught.
2. **One person's real screenshots.** The 73 real files come from one machine and one operating system, so layouts, fonts and applications are narrower than the world's. The font bank, used for simulated edits, is the font set of that machine.
3. **No public benchmark.** The only public screenshot-forgery dataset identified, STFD, could not be obtained, so the method has not been compared with any published detector on shared data.
4. **A single split and a single fit.** No experiment was repeated with different seeds, so differences of a few percentage points between rows of the tables are not established. Intervals were computed only for false-alarm rates measured on genuine corpus images (leave-files-out and the layout-grid rule), not for the AUC values or detection rates. The test split was consulted repeatedly during development, which makes its figures somewhat optimistic; the leave-files-out and hand-collected evidence are the independent checks, and they are small.
5. **Dependence on OCR.** About 10% of edited test images do not reach the classifier with the edited word, and the rate is 18 to 19% after down-scaling. Text in other scripts is not analysed, because Tesseract is called with its default recogniser and the font bank covers Latin text only.
6. **The maximum over words.** The image score is the highest word probability, so large images invite more false alarms; the sample of genuine large images is small (Section 7.6).
7. **Weakness after down-scaling.** Edits followed by shrinking or heavy re-compression are caught far less often (AUC 0.72 to 0.73), and shrinking is something a forger can do on purpose.
8. **Partial engine transfer.** A model trained on one engine's edits lost 7 to 9 points of AUC on the other's. Results on Photoshop, Canva or phone editors are unknown.
9. **Narrow rules.** The layout rule applies to about 15% of images with a numeric column; the other rules were unit-tested but not measured on the corpus (Section 7.8).
10. **No adversarial evaluation.** A forger who knew the method could match font and size, reproduce the line's rendering, or shrink the image. The explanations the service returns name the measurements that deviate, which is also feedback for a forger.
11. **Native-rendered and generated fakes are out of reach** by construction (Section 3.5).
@end

@section 8.3|THREATS TO VALIDITY
**Construct validity.** The label "edited" in the corpus means "touched by the simulator". The simulator imitates operation types and post-processing steps described in work on human tampering [@yu2025fsts], but it is not a recording of human behaviour; a model could do well on its edits for reasons that do not carry over, such as the statistical regularities of the simulator's font choice or padding.

**Internal validity.** The leakage controls (split by base file, held-out fonts, identical degradation for both classes, thresholds on separate data) address the main routes identified in the leakage literature [@kapoor2023leakage]. They do not rule out every shortcut. For example, the Chrome and Pillow renders, being generated, may share regularities across splits that the real screenshots do not. Real, Chrome and Pillow results are therefore reported separately.

**External validity.** The real screenshots, the OCR engine (Tesseract 5.5.3 on macOS), the fonts and the compression settings are those of one setup. The results are not evidence about other devices or applications, and dataset bias is a known obstacle to transfer [@torralba2011bias].

**Conclusion validity.** With one fit per experiment and non-independent edited copies, small differences should be ignored. The quantities that matter for the claims made are large: the first version's 20% false-alarm rate and AUC of 0.50 against 0.85, and the loss after down-scaling.

@section 8.4|ETHICS, PRIVACY AND MISUSE
**Privacy.** Screenshots can reveal other people's names, amounts and messages. The real screenshots used for training belong to the author, stay on the author's machine, are not committed to the repository, and the corpus derived from them is excluded from version control. The service keeps uploads in memory and does not log images (Section 6.5). The audit that found large uploads being spooled to a temporary file is an example of why such claims were checked against the code and not assumed.

**False accusations.** A "suspicious" or "evidence" verdict on a genuine screenshot could harm the person who sent it. At the suspicious tier about 5.5% of the genuine full-size screenshots tested were flagged, with an interval that reaches 13%. The wording of the tiers ("review recommended", "no evidence of editing found, not proof that the image is untouched") and the permanent limitations panel are meant to prevent the tool from being used as a verdict. It is a screener that points a person to a place and a reason.

**Dual use.** The same explanations that help a reviewer tell a forger which measurement to fix. This risk was weighed against the benefit of explainable output and accepted for a research prototype, with the recommendation that a deployed service should rate-limit and not expose the per-feature reasons to anonymous users.

**Claims.** The report does not claim real-world validation, deployment readiness or detection of generated or natively rendered fakes. Where numbers rest on simulated edits or on a few images, the text says so.

@section 8.5|PRACTICAL GUIDANCE
For a person using the service, the following follow from the results. A flag is a reason to look at the marked word, not a finding of forgery. A clean result is not a finding of authenticity. A screenshot that arrived after resizing or repeated sharing deserves less trust from the tool, and the original file should be requested. Where money or evidence is at stake, the claim should be verified with the issuer of the document.

@chapter 9|CONCLUSION AND FUTURE WORK

@section 9.1|WHAT WAS DONE
The project replaced a photograph-forensics pipeline that did not work on screenshots with a word-level detector that compares each word with its neighbours, supported by rule checks that read the content of the screenshot. It produced a leak-controlled generated corpus of 20,814 images and a generator for it, evaluation protocols that expose different weaknesses, a service with an interface, 35 backend and 58 frontend tests and a container image, and a documented record of what failed.

@section 9.2|AGAINST THE OBJECTIVES
@table objectives|Objectives of Section 1.4 and what the evidence supports
Objective | Outcome | Evidence
1 Audit the first version | Done: 20% of genuine screenshots flagged; AUC 0.50 on word edits | Section 7.1
2 Word-level, explainable detector | Built; AUC 0.85 on unseen images and fonts; reasons for every flag | Sections 4 and 7.3
3 Leak-controlled labelled corpus | Built (20,814 images); split by base file, held-out fonts, identical degradation | Chapter 5
4 Evaluation that exposes weakness | Done: held-out test, version comparison, cross-engine and leave-files-out protocols; they reveal the down-scaling and cross-engine limits | Sections 7.2 to 7.6
5 Validated rule checks | Partly: the layout rule was validated on 6,656 genuine images; other rules are only unit-tested | Sections 7.7 and 7.8
6 Usable, documented service | Done for interface, tests and documented limits; a container image was run only for an earlier model, not for the shipped one | Chapter 6
@endtable

@section 9.3|FUTURE WORK
@numbered
1. **Independent real edits.** Collect a validation set made by people other than the capturer, with real editing tools and sharing paths, following the protocol of Appendix E, and report the detection and false-alarm rates with intervals. This is the most valuable next step because it is the only one that replaces simulated edits with real ones.
2. **Public benchmark.** Obtain STFD or a comparable set and evaluate the detector zero-shot, then compare it with a published localiser on identical data.
3. **Learned crop-level model.** A small neural network on word crops could capture rendering differences that hand-made features miss, at the cost of a deep-learning dependency; whether it helps is untested.
4. **Resampling-aware features.** The weakest case is down-scaled sharing. Features sensitive to resampling traces [@popescu2005resampling] might recover some of the lost evidence.
5. **Ablation and repeated seeds.** Measure which feature groups carry the signal, repeat the experiments with several seeds and report intervals for every rate.
6. **Candidate generation without OCR.** About one tenth of the edited words never reach the classifier. A text detector independent of Tesseract's recognition could close part of that gap.
7. **Provenance.** For fakes that are rendered natively, the realistic remedy is verification with the issuer, for example a transaction-identifier lookup, which is outside what an image analyser can provide.
@end

@appendix A|APPLICATION PROGRAMMING INTERFACE
@appendixtext
The service exposes two endpoints. `POST /analyze` takes a multipart form with one field named `image` (png, jpg, jpeg or webp, at most 10 MB). `GET /status` returns `{"status": "ok", "service": "screenshot-forensics", "model": {...}}` with the model's number of features, number of training images and word-level count, thresholds and held-out AUC. Status codes: 200 for a completed analysis, 400 for a missing, wrongly named, empty or unreadable file, 413 for an oversized upload and 500 for an unexpected error. Table {tab:apifields} describes the response of `POST /analyze`; the listing below it is the actual response, produced by the final model for the generated sample `docs/samples/statement_edited_detected.png`, with the free-text lists shortened.
@endappendixtext

@table apifields|Fields of the analysis response
Field | Meaning
verdict, verdict_label | one of evidence_of_editing, suspicious, no_evidence, inconclusive, and its display text
risk_score | monotone score from 0 to 1 with the two thresholds at 0.40 and 0.70
reasons | up to eight plain-language sentences
regions | marked words: x, y, w, h in pixels of the (EXIF-oriented) image, text, score, level (evidence, suspicious or weak), reasons, and source = "rule" for rule-based marks
findings | rule findings: id, severity (high, medium, low), message, evidence
limitations | the fixed list of what the method cannot detect
image | width, height, format
stats | OCR word count, measured word count, highest word probability, the two thresholds
meta | SHA-256 of the file, processing time in milliseconds, model description
fake_score, is_fake, verdict_text | aliases kept for older clients
@endtable

@apijson docs/samples/statement_edited_detected.png|Response of POST /analyze for the generated sample (shortened)

@appendix B|SOURCE CODE LISTINGS
@appendixtext
The listings below are excerpts of the code as it stood when the report was built; they are read from the repository when the report is generated, so they cannot differ from the code described in the text. Line numbers are those of the source file.
@endappendixtext
@listing backend/analysis.py|verdict_start|verdict_end|Listing B.1 The verdict logic (backend/analysis.py)
@listing backend/app.py|inmemory|route_end|Listing B.2 Keeping uploads in memory, and the analysis endpoint (backend/app.py)

@appendix C|AUTOMATED TESTS
@appendixtext
The backend tests (35) and the frontend tests (58) are run with `pytest tests` in `backend/` and `npm test` in `frontend/`. Table {tab:tests} lists the backend tests by file; the frontend test files are `overlay.test.js`, `demo.test.js`, `api.test.js`, `ImageUpload.test.jsx`, `Panels.test.jsx`, `App.test.jsx` and `AnalysisResults.test.jsx`.
@endappendixtext
@testtable

@appendix D|HOW TO REPRODUCE THE RESULTS
@appendixtext
The commands below are an illustration of the steps, not a script that reproduces the exact corpus: the reported corpus merged four builds (Section 5.6), and the Chrome-patch edits used in Sections 7.3.2, 7.3.4 and 7.5 need the extra `--bank` build shown at the end of the build lines. The cross-engine, latency and hand-sample scripts are in `paper-draft/evidence/` (see `run_evidence.sh`). Run from the repository root on macOS with Tesseract installed (`brew install tesseract`) and Google Chrome for rendering. The generated corpus and the real screenshots are not part of the repository; the first because it is large and derived from private images, the second because they are private. The evidence folder `paper-draft/evidence/` holds the log of each run reported here.
@endappendixtext
@code Commands|Listing D.1 Illustrative commands for building a corpus, training the model and running the evaluations
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt
python tools/forge/render_chrome.py --out ../data/chrome --count 1600 --seed 21 --workers 8
python tools/forge/patchbank.py build --out ../data/patchbank --pages 100 --workers 4
OMP_THREAD_LIMIT=1 python tools/forge/build_dataset.py --out ../data/forge_v1 --chrome-dir ../data/chrome --pillow 1000 --real-windows 5 --real-glob "<your screenshots>"
OMP_THREAD_LIMIT=1 python tools/forge/build_dataset.py --out ../data/forge_bank --chrome-dir ../data/chrome --pillow 1000 --real-windows 5 --bank ../data/patchbank --real-glob "<your screenshots>"   # Chrome-patch edits
OMP_THREAD_LIMIT=1 python tools/forge/build_dataset.py --out ../data/forge_full --real-full --real-windows 3 --seed 21 --real-glob "<your screenshots>"
python tools/forge/merge_corpora.py --dst ../data/forge_all ../data/forge_v1 ../data/forge_bank ../data/forge_full
python tools/forge/train_text_model.py --data ../data/forge_all            # trains, evaluates, writes model_data/
python tools/forge/eval_real_cv.py --data ../data/forge_all --real-glob "<your screenshots>"
python tools/forge/compare_legacy.py --data ../data/forge_all --n 500
python tools/forge/eval_layout_rule.py --data ../data/forge_all
pytest tests -q                                                           # 35 backend tests
cd ../frontend && npm install && npm test                                 # 58 frontend tests
cd .. && docker build -t fsd-backend ./backend                              # container image
@endcode

@appendix E|PROTOCOL FOR A REAL-EDIT VALIDATION SET
@appendixtext
The most important missing evidence is detection on edits made by people with real tools. The protocol prepared for that experiment keeps the people who capture and edit separate so that neither can bias the other, and fixes the rules before any detector output is seen. Person 1 (the capturer) takes 40 screenshots of real applications and changes nothing: 20 go into a folder of genuine images and 20 are passed to Person 2. Person 2 (the editor) makes exactly one edit in each of the 20 using at least five different tools, a mix of lazy, careful and expert edits, a mix of lossless and compressed exports, and keeps the untouched originals. The mix of edits is five single-digit changes, four whole-amount changes, two names, two dates or times, two statuses, two added or removed pieces of text and three edits made with the browser's Inspect Element tool, which the method is expected to miss. Nobody runs the detector until every file exists, and no edit is revised after seeing a result. The folders are then scored with `backend/tools/evaluate_manual.py`, and the report gives the verdict breakdown for genuine and edited images, the false alarms and the misses, with intervals. At the time of writing this protocol had been prepared but the set had not been collected, so no result from it appears in this report.
@endappendixtext

@appendix F|TOOLS AND ASSISTANCE
@appendixtext
The implementation, the experiments and the first drafts of this report were produced with the help of an AI coding assistant (Claude Code, Anthropic). The assistant wrote and ran code, ran the evaluations and drafted text; the project team directed the work, supplied the real screenshots and the eight-image sample, and is responsible for the claims made. All numbers in this report are taken from logs and scripts stored in the evidence folder and were re-derived from them during an audit; the text was checked against the code. Third-party tools used: Tesseract OCR 5.5.3, scikit-learn 1.9.0, Pillow 12.3.0, NumPy 2.5.1, SciPy 1.18.0, Flask 3.0.3, React 18 with Vite, and Google Chrome 155 for rendering the generated screens. Papers cited were retrieved and checked against Crossref, OpenAlex, arXiv or the publisher, and the read depth of each (full text, abstract or bibliographic record only) was recorded; claims about papers read at abstract level are limited to what the abstract states.
@endappendixtext

@appendix G|EVIDENCE FILES
@appendixtext
Table {tab:evidence} maps each result in the report to the file that holds it. All files are in `paper-draft/evidence/` of the repository.
@endappendixtext
@table evidence|Evidence files and the results they support
File | Supports
fp_results.json, exp_fp.py | first-version audit on 60 genuine screenshots (Section 7.1.1)
tamper_results.json, exp_tamper.py | first-version edit experiment (Section 7.1.2)
v1_native_check.txt | first version on a natively rendered fake and on the editor tag (Section 7.1.3)
compare_legacy.txt | first and final versions on 500 test images (Section 7.2)
train_final_v6.log | held-out test results of the shipped model (Section 7.3)
ocr_recall_check.txt, train_v2_corpus_features.log, train_v4_corpus_features.log, leave_files_out_v5_intermediate.log, second_stage_check.txt | development steps (Section 7.4)
cross_engine.txt | cross-engine experiment (Section 7.5)
leave_files_out_v6.log, cv_summary_v6.json, wilson.txt | leave-files-out results and intervals (Sections 7.6 and 7.7)
layout_rule_eval.txt, layout_rule_eval_first_version.txt | layout-grid rule (Section 7.7)
real8_results.txt, column_z_8images.txt | eight-image sample (Sections 7.9 and 7.10)
negative_results.txt, train_v7_column_peers.log | rejected column idea (Section 7.10)
latency.txt, latency_large.txt | speed (Section 7.11)
facts.txt (regenerated by derive_facts.py) | corpus, code and environment facts (Chapters 5 and 6)
pytest.txt, vitest.txt | automated tests (Chapter 6)
docker_test.log, docker_build_final.log | container check of an earlier image, and the failed rebuild of the final one (Section 6.6)
api_response_sample.json | response listing of Appendix 1
corpus_build_v1.log | corpus build statistics (Section 5.6)
run_evidence.sh, cross.py, real8_eval.py, latency.py | scripts that regenerate the evaluations (Chapter 7)
@endtable
