@chapter 5|DATASET AND EXPERIMENTAL SETUP

@section 5.1|WHY THE DATA WAS GENERATED
The detector needs screenshots in which every edited word is labelled exactly. The first version of this project was trained on three existing datasets of photographs, receipts and found manipulations [@dong2013casia; @novozamsky2020imd; @tornes2023receipt]; Section 7.1 shows that this was the wrong domain. The one public dataset of edited smartphone screenshots, STFD, can only be extracted with a password that the authors send by e-mail to academic or institutional addresses [@hf_stfd]; the request was made but no reply had arrived by the end of the experiments, so no result here depends on it. Published work on text-image forgery stresses that human-made tampering data is scarce and that synthetic data should model the operations and post-processing that people actually use [@yu2025fsts]. The corpus built for this project, called ScreenForge, therefore combines genuine bases from three sources with a simulator that applies those kinds of operations and records the exact edit rectangle.

@fig fig_corpus|15.5|Construction of the ScreenForge corpus and the controls against leakage.

@section 5.2|GENUINE BASE IMAGES
@bullets
- **Real device screenshots.** Eighty-nine screenshot files were found on the author's own machine; 16 contain no readable text (at most two OCR words) and were skipped, leaving 73. Twenty-two of the 89 are full-size Retina captures of 3,024 by 1,964 pixels and the others are smaller captures and application windows. They are private and are never distributed. For training, random windows of 700 to 1,500 by 500 to 1,100 pixels are cropped from each file (several windows per file, plus a separate set of whole screenshots).
- **Chrome-rendered application screens.** 1,600 images produced by a generator (`render_chrome.py`) that writes HTML for 16 layouts and renders it with headless Google Chrome 155 at device scale 1, 2 or 3. The layouts are chat, group chat, UPI-style receipt, bank balance, bank statement, order summary, social post, e-mail inbox, e-mail view, notifications, SMS with a one-time code, crypto wallet, stock portfolio, ride receipt, web dashboard and invoice. They use 24 fonts, light and dark themes, random accent colours, five phone viewports (plus some tall ones) and three desktop viewports, with random names, amounts and dates.
- **Pillow-rendered screens.** Ten categories of application screen (chat, bank, payment, social, e-commerce, e-mail, notification, crypto, SMS, trading) drawn by Pillow in a randomly chosen system font; 1,000 bases were generated for the first corpus build.
@end

The three sources are deliberately different. Real screenshots represent the target domain but are scarce. Chrome output is rendered by a different engine than the macOS screenshots and has many layouts. Pillow output provides a third renderer. Because the classifier compares words within one image, mixing renderers across images does not by itself let it separate classes, but the cross-engine experiment in Section 7.5 tests that assumption directly.

@section 5.3|THE EDIT SIMULATOR
For each base image the simulator (`tamper.py`) edits one word, and in 20% of cases a second one elsewhere. A word is chosen among OCR words with confidence of at least 70, a height of 12 to 90 pixels and a width of at least 14 pixels, away from the image border; words containing digits are preferred in 60% of draws, because amounts, dates and identifiers are the usual targets. Four choices define an edit.

@bullets
- **Operation.** Re-type the word (62%), re-type it and blur the patch (24%), or splice in a word crop from a different image (14%, when donor words are available).
- **New text.** For words with digits, 75% of edits change one to three digits and a quarter of those also add or remove a digit; otherwise a word of similar length from a small vocabulary replaces the text, or the letters are shuffled.
- **Rendering.** The text is drawn with a font drawn uniformly from the allowed fonts, in a size chosen so that the new text matches the old word's height within a pixel or two, with grey-scale anti-aliasing (65%), no anti-aliasing (12%) or simulated LCD sub-pixel anti-aliasing (23%). Placement is bottom-aligned in 70% of cases, with a vertical jitter of up to two pixels (otherwise vertically centred), and right-aligned, with probability 0.8, when the word ends beyond 72% of the image width. The ink colour is copied from the original word and perturbed by a few levels in 30% of edits.
- **Background.** A padded rectangle of 0 to 4 pixels is filled with a flat colour (35%), flat colour plus noise matched to the surroundings (20%), a horizontal gradient (20%) or a clone-stamped block of nearby background (25%). Further post-processing includes a blur with radius 0.35 to 0.9 (also applied to 12% of other edits) and a local JPEG round trip at quality 60 to 90 (15%).
@end

A second, independent engine, `patchbank.py`, rasterises the new text with Chrome instead of Pillow. It pre-renders 11,000 text patches on a transparent background in the 24 Chrome fonts, matches a patch to the word being replaced by character pattern (digits as a class), polarity and height, recolours it and composites it with the same background fills. This was added because a model trained on Pillow edits only scores an AUC of 0.75 on Chrome-rendered edits (Section 7.5). {fig:fig_sample_pair} shows an untouched generated screenshot and an edited copy.

@fig fig_sample_pair|9.5|A generated Chrome-rendered bank statement (a) untouched and (b) with one amount edited by the simulator. Both images are generated content, not private data.

The fonts used for Pillow edits come from 283 Latin-capable fonts found on the machine, each assigned by a hash of its name to one of five folds. Folds 1 to 4 supply edits in the training and validation splits and fold 0 supplies edits in the test split only, so every test edit that renders new text uses a font the model never saw (spliced crops carry whatever font their donor image used). For Chrome patches four families (Futura, Optima, Palatino, Charter) play the same role. A unit test checks that an edit changes pixels only inside the recorded rectangle, and another that the edited word is on average a stronger outlier than untouched words.

@section 5.4|SHARING DEGRADATION
After editing, every image, genuine or edited, passes through the same random sharing step: lossless PNG (34%), JPEG at quality 55 to 98 with 4:4:4 or 4:2:0 subsampling (34%), down-scaling by 0.5, 0.66, 0.75 or 0.85 followed by PNG (14%), or down-scaling followed by JPEG (18%). The resampling filter is chosen among bilinear, bicubic and Lanczos. Genuine and edited images are treated identically so that compression history cannot serve as a shortcut for the label. Related work shows that localisation models depend on the compression settings seen in training [@ronfleux2026docqt]. Edit rectangles are scaled with the image so that word labels remain exact.

@section 5.5|SPLITS AND LEAKAGE CONTROLS
Splits are made by base image, using a hash of the base file path (real screenshots), of the Chrome image identifier, or of the Pillow base index: 70% of hash values go to training, 15% to validation and 15% to test. All windows, whole-image copies and edited versions derived from one screenshot file therefore fall in the same split. This addresses the non-independence between training and test units that a taxonomy of leakage singles out [@kapoor2023leakage]. Test edits use held-out fonts, as described in Section 5.3. Decision thresholds are fixed on the validation split. In the leave-files-out protocol (Section 5.7) the model is trained on the training split only, so the validation images used for calibration are never trained on; an earlier version of that script violated this and its output was discarded (Section 7.6).

@section 5.6|CORPUS STATISTICS
The final corpus holds 20,814 images, assembled from four builds (Table {tab:builds}) and described by split, source and class in Table {tab:corpus}.

@table builds|The four builds that make up the final corpus
Build | Contents | Images
Base corpus | five windows per real file, 1,600 Chrome images, 1,000 Pillow bases; Pillow edits | 8,888
Extra real windows | up to 14 windows per real file; Pillow edits | 3,472
Chrome-patch edits | Chrome, Pillow and real bases; edits rasterised by Chrome | 7,599
Whole real screenshots | full-size real screenshots, genuine and edited | 855
Total | | 20,814
@endtable

@table corpus|Final corpus by split, base source and class (number of images)
Split | Source | Genuine | Edited
Train | Real screenshots | 1,226 | 3,506
Train | Chrome-rendered | 2,248 | 4,345
Train | Pillow-rendered | 1,148 | 2,021
Validation | Real screenshots | 246 | 717
Validation | Chrome-rendered | 484 | 923
Validation | Pillow-rendered | 251 | 462
Test | Real screenshots | 327 | 891
Test | Chrome-rendered | 468 | 870
Test | Pillow-rendered | 258 | 423
Total | | 6,656 | 14,158
@endtable

Training uses 14,494 images, validation 3,083 and test 3,237 (2,184 of them edited). The corpus labels about 0.81 million words in training, of which 10,582 words in edited images are labelled edited after ambiguous overlaps are excluded. Genuine images are fewer than edited ones because each base yields one genuine and two or three edited samples. The 1,600 Chrome bases are used in two builds (the base corpus and the Chrome-patch build), each time with an independently drawn sharing step, so the 3,200 genuine Chrome images in Table {tab:corpus} derive from 1,600 bases; the Pillow bases were likewise rendered again for the second build. All derivatives of one base fall in the same split. The corpus build, logged for the first build, processed 3,045 bases (8,888 samples) in 1,019 seconds with nine worker processes and the OCR thread limit set to one per worker.

@section 5.7|EVALUATION PROTOCOLS
Seven protocols are used, each answering a different question.

@numbered
1. **Held-out test.** Unseen base images and unseen edit fonts; image-level AUC, detection rates and false-alarm rates at the two thresholds, broken down by base source, edit operation, sharing step, anti-aliasing mode and fill. Breakdowns that depend on how a file was shared compare edited images with genuine images that went through the same sharing, because comparing against all genuine images would mix conditions.
2. **Version comparison.** The first-version pipeline and the final model score the same 500 randomly drawn test images.
3. **Cross-engine.** Models trained only on Pillow edits, only on Chrome edits and on both are tested on each engine's test edits.
4. **Leave-files-out.** Five folds over the 73 real files. For each fold a model is trained on the training split without any window of the held-out files, thresholds are set on validation real images from the other files, and each held-out file is scored whole (genuine) together with up to six edited copies (426 in all) made with the Pillow-engine re-type and blur operations, held-out fonts and random sharing, without splices. This is the nearest approximation to real use: full-size genuine screenshots that the scoring model never saw.
5. **Rule validation.** Word boxes of every genuine corpus image test the false-alarm rate of the layout rule, which is additionally tested with simulated misplacement; the other rules are validated by unit tests only.
6. **Hand-collected sample.** Eight screenshots from a payment application, four edited by a person with their own tools and four genuine. They were used to diagnose and improve the system, so they count as development data and not as a test.
7. **Latency.** Wall-clock time of the complete analysis on 80 test images and on the largest full-size captures.
@end

Rates are reported as proportions of images. The area under the receiver operating characteristic curve [@fawcett2006roc] summarises ranking independently of thresholds. For the one proportion that decides whether the system is usable on real screenshots, the false-alarm rate in protocol 4, a Wilson interval is given [@wilson1927]. Wilson intervals are also given for the false-alarm rates of the intermediate model and of the layout rule; no other confidence intervals were computed and every experiment uses one split and one fit of the model (no repeated seeds), so differences of a few percentage points between rows should not be read as established.

@section 5.8|ENVIRONMENT
All experiments ran on one Apple M5 machine with 16 GB of memory. The backend uses Python 3.14.3 in a virtual environment, with the pins in `requirements.txt` (Flask 3.0.3, Pillow 12.3.0, NumPy 2.5.1, scikit-learn 1.9.0, SciPy 1.18.0, pytesseract 0.3.13, gunicorn 26.0.0, joblib 1.5.3 and flask-cors 4.0.1), Tesseract 5.5.3 and Google Chrome 155.0.8059.40 for rendering. The container image is based on Python 3.12.

@chapter 6|IMPLEMENTATION

@section 6.1|BACKEND
The backend is a small Flask application (94 lines in `app.py`) with two endpoints. `POST /analyze` accepts a multipart field named `image`, checks that a file was supplied, that its extension is png, jpg, jpeg or webp, that it is non-empty and that Pillow can decode it, and returns the analysis as JSON; a missing, wrongly named, empty or undecodable file returns 400, an oversized upload 413 and any unexpected error a generic 500 (a truncated PNG was observed to take this last path). `GET /status` returns the health of the service and the loaded model's metadata, including its number of features, number of training images, thresholds and held-out AUC.

The analysis itself is split across three modules. `textforensics.py` (about 390 lines) holds the OCR wrapper, the per-word measurements and the explanations. `semantic.py` (about 320 lines) holds the rule checks. `analysis.py` (about 170 lines) loads the model, calls the other two and applies the verdict policy of Section 3.6. At start-up, `analysis.py` compares the feature names stored with the model against those the current code produces and refuses to load the model if they differ; the service then reports that no model is loaded and answers "not enough readable text" instead of using a mismatched model. This guard is checked by a test that compares the stored feature list with the code.

@section 6.2|FRONTEND
The interface is a React 18 application built with Vite. After analysis it shows a verdict banner for each tier, a gauge for the risk score with the two thresholds marked, the uploaded image with numbered boxes over the marked words, a list of reasons, the rule findings with expandable evidence, per-word cards, a panel with the limitations that cannot be dismissed, a statistics row and a download of the JSON report. Hovering or selecting a box highlights the matching card and the reverse. Separate error panels distinguish network failure, timeout, oversized file, invalid image, rate limiting and server errors, and never show raw server output. A demonstration mode, opened with a query parameter, renders fixture results over a placeholder image without calling the back end, which allows the interface to be shown without the model. {fig:fig_ui} shows the result screen for an edited bank statement.

@fig fig_ui|13.5|The result screen for an edited amount in a generated bank statement: the verdict banner, the risk gauge with the two tier boundaries, the marked word on the image and the reasons.

The frontend was written with an AI coding assistant (Appendix F), checked by 58 automated tests, built for production, and tried by hand in a browser against the running back end during development; that manual check was not recorded in a log.

@section 6.3|TOOLING FOR DATA, TRAINING AND EVALUATION
The corpus, training and evaluation tools live in `backend/tools/forge/`. `render_chrome.py` (about 1,700 lines) renders the Chrome screens; `patchbank.py` builds and uses the Chrome text patches; `tamper.py` implements the edit simulator and the sharing degradation; `build_dataset.py` assembles samples in parallel, runs OCR and feature extraction and writes checkpointed feature files; `refeaturize.py` recomputes features from saved OCR boxes without repeating OCR, which made feature experiments several times faster; `merge_corpora.py` combines builds; `train_text_model.py` trains the classifier and reports every breakdown; `eval_real_cv.py`, `eval_ood.py`, `compare_legacy.py` and `eval_layout_rule.py` implement the other protocols; and `backend/tools/evaluate_manual.py` scores folders of hand-collected screenshots. The first version's code is kept in `backend/legacy/` only so that the comparison of protocol 2 can be reproduced.

@section 6.4|TESTING
The backend has 35 automated tests: 11 for the interface (status, rejection of missing, wrongly named and unreadable files, the response contract, a blank image being "not enough text", the rule that the lowest tier never uses the words "authentic" or "genuine", forced escalation by a rule finding or an editing-software tag, a guard that the model's feature list matches the code, and a guard against uploads being spooled to disk), 18 for the rules (including tests that ordinary pages raise no finding) and 6 for the feature extractor and edit simulator. The frontend has 58 tests in seven files that cover overlay geometry, error mapping, each verdict state, the demonstration mode and the absence of any wording that implies authenticity. All pass at the time of writing.

@section 6.5|PRIVACY AND SECURITY PROPERTIES
Screenshots can contain payment and chat details, so privacy was designed in and then audited against the code. The application reads the upload into memory and never writes the image to a path it chose. An audit of the code path found that the web framework's default upload parser spools any file part above 512,000 bytes to a temporary file on disk; a 2 MB upload triggered this. The application now installs a request class that keeps every upload part in memory, bounded by the 10 MB size limit, and a regression test fails if a large upload rolls over to disk. The application logs the number of bytes received, the verdict, the risk score and the number of marked regions, and a traceback if an analysis fails, but not the image or its hash, although the response includes a SHA-256 digest of the file. Under the compose file the nginx front proxy may buffer large request bodies to disk, so the in-memory property holds for the Flask application only. Cross-origin access is open by default and configurable through an environment variable; there is no authentication, rate limiting or transport security in the prototype, and the README says that a reverse proxy should provide them before exposure.

@section 6.6|DEPLOYMENT
The backend image is built from a Python 3.12 slim base with the Tesseract package, the pinned requirements and gunicorn with two workers and a 180-second timeout; a `.dockerignore` keeps the virtual environment, tests and tooling out of the image. A second image serves the built frontend through nginx, which proxies `/api/` to the backend with a 180-second read timeout. A compose file starts both, and a Render blueprint describes a two-service deployment. An image built earlier in the project, with an intermediate model, was started and queried through its published port; it was 788 MB and returned the expected verdict for the generated sample (`docker_test.log`). A rebuild from the final tree could not complete because the base image could not be pulled (registry timeout, `docker_build_final.log`), so the final image has not been run and the container check is not repeated for the shipped model.

