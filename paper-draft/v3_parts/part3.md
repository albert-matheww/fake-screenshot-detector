@chapter 5|DATA AND EXPERIMENTAL SETUP

@section 5.1|WHAT THE DATA IS FOR
The final design does not depend on a training set: the checks are rules, compare mode and reconcile mode need no training, and no verdict is learned. Data is used for three purposes: to train the word-rendering model of the second version (generated and public real edits), to measure how often each check raises a false alarm on genuine screenshots, and to test the new modes. Table {tab:datasets} lists every collection used, what it contains and what it was used for.

@table datasets|Data used in this report
Collection | Content | Used for
Owner's genuine screenshots (first audit) | 60 genuine screenshots (59 PNG, 1 JPEG) | audit of the first version (Section 7.1)
Owner's real screenshot files (second version) | 89 files found, 73 with readable text | training windows and leave-files-out test of the second version (Chapter 7)
Hand-collected sample | 8 payment-history screenshots, 4 edited and 4 genuine | development data (Section 7.3)
Owner's second real set | 23 genuine screenshots and 9 edited screenshots paired with their originals | the main real-screenshot measurements of the final version (Sections 7.3 to 7.8)
Further genuine items | 24 added later: 11 chats (5 WhatsApp in a desktop window, 3 WhatsApp on a phone, 3 Instagram), 4 Google Pay transaction lists, and 9 pages of 5 bank e-statement PDFs rendered at 150 dpi | the chat, payment and bank-statement rules and the gates on 47 genuine items (Section 7.16)
Bank SMS texts | 13 messages (12 bank debit alerts and one payment confirmation), transcribed by the AI assistant from screenshots shared by the owner (the screenshots were not saved) | reconcile mode against real second sources (Section 7.17)
Rendered documents | 1,080 documents for the mutation test and 300 rendered receipts with known facts | recall of the rules and reconcile mode under OCR noise (Sections 7.15 and 7.18)
ScreenForge | 20,814 generated images (Section 5.3) | training and testing the second version
STFD | 3,932 tampered screenshots with pixel masks (Section 5.4) | pipeline run and training on real edits (Sections 7.9 and 7.10)
Rico subset | 4,217 genuine app screens in the test split; 300 sampled (Section 5.5) | false alarms on genuine screens of another domain (Section 7.11)
@endtable

@section 5.2|THE OWNER'S REAL SCREENSHOTS
All real screenshots are the project owner's own, are private, are never distributed and are excluded from version control. The second real set (collected in October 2026) has 23 genuine screenshots in seven types (payment receipts 8, bank statements 3, orders or invoices 3, web pages 3, social posts 2, SMS, e-mail or notifications 3, chats 1; the types were assigned by hand and are listed in `backend/tools/real_labels.json` by file name). They are a mix of PNG, JPEG and WebP files, about half named as messaging-application images, which is to say that they had been shared before they reached the project. The nine edited screenshots (three each of bank statements, web pages and orders or invoices) were edited by the owner with tools that were not recorded; each is paired with its original, which is among the 23. This set is far too small to estimate rates. It is the only set that resembles the intended use, and it is used with intervals and without tuning.

@section 5.3|THE GENERATED CORPUS (SCREENFORGE)
The second version needed screenshots in which every edited word is labelled exactly, and no suitable public data could be obtained when it was built. The corpus built for it, called ScreenForge, combines genuine bases from three sources with a simulator that applies edit operations and records the exact edit rectangle. Its construction is summarised here because the second version's results depend on it; the details are in the repository (`backend/tools/forge/`).

@bullets
- **Bases.** The 73 real files (random windows of 700 to 1,500 by 500 to 1,100 pixels, plus whole screenshots), 1,600 application screens generated as HTML in 16 layouts and rendered with headless Google Chrome 155, and 1,000 screens drawn by Pillow in ten categories.
- **Edits.** The simulator edits one word (a second in 20% of cases) by re-typing it (62%), re-typing and blurring the patch (24%) or splicing in a crop from another image (14%). A second, independent engine rasterises the new text with Chrome instead of Pillow. Digits are preferred in 60% of draws because amounts and dates are the usual targets.
- **Sharing.** After editing, every image, genuine or edited, passes through the same random step: lossless PNG (34%), JPEG at quality 55 to 98 (34%), down-scaling by 0.5 to 0.85 followed by PNG (14%) or by JPEG (18%).
- **Splits.** By base image (a hash of the base file path): 70% train, 15% validation, 15% test; test edits use fonts never used for a training edit (283 fonts assigned to five folds by hash; fold 0 for testing).
@end

The final corpus holds 20,814 images, assembled from four builds: 6,656 genuine and 14,158 edited. Training uses 14,494 images, validation 3,083 and test 3,237 (2,184 of them edited). Table {tab:corpus} gives the split by source and class.

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

Genuine images are fewer than edited ones because each base yields one genuine and two or three edited samples. The 1,600 Chrome bases are used in two builds, each time with an independently drawn sharing step, so the 3,200 genuine Chrome images derive from 1,600 bases; all derivatives of one base fall in the same split. The edits are simulated, which is the central limitation of every number that comes from this corpus (Section 8.2).

@section 5.4|STFD: PUBLIC TAMPERED SCREENSHOTS
STFD [@yu2023stfd] was obtained as described in Section 2.4.1. The archive (2.9 GB, AES-encrypted) contains five folders of tampered screenshots, each with a mask of the tampered pixels: copy-move (758 images), splicing (830), removal (1,016), insertion (701) and replacement (627), 3,932 in all. The card lists the format as PNG or JPEG, but every image in the archive as obtained is a PNG (this project's observation). In a sample of 60 images from each folder the most common size was 1,080 by 2,340 pixels, with others such as 1,080 by 1,920, 1,080 by 2,400, 828 by 1,792 and 750 by 1,334. The edited area is small: it covers a median of 0.41% of the image (10th to 90th percentile 0.13% to 2.5%). According to the dataset card the screens come mostly from smartphones, with some tablets, laptops and Windows PCs, in scenes such as chat, payment, banking, maps, browsing, social media and e-commerce [@hf_stfd]. The content-based type router, whose patterns are English, labels 93% of the images "unknown" (Section 7.9). The language of the screens was not examined, so the cause (other languages, other layouts, or both) is not established. STFD contains tampered images only: it has no untouched originals, which means it can show how the pipeline responds to known edits but not how often it raises a false alarm. The data stays in an ignored folder of the repository and is not redistributed.

@section 5.5|RICO: GENUINE SCREENS OF ANOTHER DOMAIN
The Hugging Face copy of a Rico subset [@deka2017rico; @hf_rico] has a test split of 4,217 genuine Android app screens (JPEG), licensed CC BY 4.0. Three hundred screens were drawn at random with a fixed seed (0); 276 of them have at least six measurable words and can be scored by the word models. The screens are app screens from a dataset published in 2017 and were not shared through a messaging application, so they test false alarms on a different genuine population, not on the intended one. Only the dataset card and the metadata of the Rico paper were read.

@section 5.6|EVALUATION PROTOCOLS
Twenty protocols are used, each answering a different question. The first six belong to the second version and the rest to the final version, the public data, the mutation test and the real-data tests.

@numbered
1. **Held-out test (second version).** Unseen base images and edit fonts; AUC, detection and false-alarm rates at the two thresholds, by sharing step.
2. **Version comparison.** The first-version pipeline and the second-version model on the same 500 test images.
3. **Cross-engine.** Models trained on Pillow edits, Chrome edits and both, tested on each engine's edits.
4. **Leave-files-out.** Five folds over the 73 real files; each held-out file scored whole by a model that never saw it, with 426 edited copies.
5. **Rule validation.** False alarms of the layout rule on every genuine corpus image, and its recall under simulated misplacement.
6. **Hand-collected samples.** The eight-image sample (development data) and the second real set, scored once.
7. **Final pipeline on the second real set.** All 32 screenshots: verdicts, assurance levels, advisory signals, time per image.
8. **Compare mode.** The nine edit pairs, plus 27 controls (each original re-saved as JPEG at quality 80 and 60, and down-scaled to 0.75 with JPEG at quality 85).
9. **Type routers.** The 23 genuine screenshots with hand-assigned types, scored by both routers against the validation criteria of Section 4.3.
10. **Gate calibration.** Every check applied to the genuine items (type-specific rules to the items of their own type), with Wilson intervals.
11. **Reconcile mutation test.** For each real screenshot with enough facts, a faithful second source (must be corroborated) and a source with one fact changed (must not be).
12. **STFD pipeline run.** The final pipeline on all 3,932 STFD images, with a check of whether marked regions meet the edit mask; made first on 2026-10-18 and repeated on the final code, with the same verdicts and counts of live findings.
13. **Training on real edits.** Words of the STFD images are labelled from the masks (edited if at least 25% of the box lies inside the mask; unedited if the box and an 8-pixel margin touch no mask pixel); near-identical source screenshots are grouped by a 16 by 16 difference hash (Hamming distance at most 20 of 256 bits) and the groups are split 70/15/15. The experiment is repeated on a copy degraded like sharing through a chat application (long side at most 1,600 pixels, JPEG quality 60 to 90) with three models: trained on clean images, on degraded images and on both.
14. **False alarms on Rico.** 300 genuine Rico screens scored by the STFD-trained models, the shipped second-version model and the live checks.
15. **Latency.** Wall-clock time of the analysis of the 32 real screenshots.
16. **Mutation test of the content rules.** Documents (invoices, statements in two layouts, receipts, chats, one-time-code messages, number lists) are rendered from a consistent set of facts in six fonts; in each of 16 kinds of mutation (for example a weekday, a total, an item price, a balance, a checksum digit, a reference length, a message time or a displaced number) exactly one fact is changed so that one rule's invariant is broken. Thirty documents per mutation and 100 clean documents per type are run through the real pipeline with OCR, as PNG and as a shared copy (down-scaled 0.75, JPEG quality 75), with the type chosen. This measures whether each rule fires on the contradiction it was written for and stays silent on clean documents, not how often a real forger leaves a contradiction.
17. **Further genuine items.** Twenty-four genuine items (11 chats, 4 payment lists, 9 statement pages) are run through the service with the type chosen, and the gates are recalculated on all 47.
18. **Real second sources.** Each of 13 bank SMS texts is reconciled with each of four Google Pay list screenshots (52 pairs); which list shows the payment was judged by eye.
19. **Reconcile mode with ground truth.** 300 payment receipts rendered from known facts are reconciled with a faithful and four altered second sources, with one OCR read and with the two-read consensus.
20. **Stability of the STFD result.** Five grouped splits, a bootstrap over source groups, a feature-family ablation and a random-word baseline on the cached word features.
@end

Rates are reported as proportions. The AUC (area under the receiver operating characteristic curve; see [@fawcett2006roc]) summarises ranking independently of thresholds. Wilson intervals [@wilson1927] are given for the proportions that decide whether a check may count, for the small hand-collected sets, the layout rule, the Rico screens, the mutation tests and leave-files-out; the STFD word model also has five grouped splits and a bootstrap over source groups (Section 7.19). No other confidence intervals were computed, and the other experiments use a single split and a single seed, so differences of a few percentage points between rows should not be read as established.

@section 5.7|ENVIRONMENT
All experiments ran on one Apple M5 machine with 16 GB of memory, using Python 3.14.3 with the versions pinned in `requirements.txt` (Appendix 6 lists the main ones), Tesseract 5.5.3 and Google Chrome 155.0.8059.40 for rendering; the frontend is a React 18 application built with Vite.

@chapter 6|IMPLEMENTATION

@section 6.1|BACKEND
The backend is a Flask application (178 lines in `app.py`) with four endpoints. `POST /analyze` accepts a multipart field `image` and an optional field `type`; a missing, wrongly named, empty or undecodable file, or an unknown type, returns 400, an oversized upload 413 and any unexpected error a generic 500. `POST /reconcile` accepts `image`, an optional `type`, and a second source as `source_text` (the first 20,000 characters are used) or `source_image`; it returns the full analysis plus the comparison of facts and an assurance level that includes the second source. `POST /compare` accepts `original` and `suspect`. `GET /status` returns the health of the service, the model's metadata, the validation state of the routers and the state of every gate.

The analysis lives in the package `backend/screencheck/` (1,420 lines in 14 files): the capture profile, the routers, the checks and the legacy cues, the gates, the verdict policy, the assurance module, field extraction, reconcile mode and compare mode, and the pipeline that connects them. The word-rendering model's code is in `textforensics.py` (393 lines) and the content rules in `semantic.py` (342 lines). At start-up the model loader compares the feature names stored with the model against those the current code produces and refuses to load the model if they differ; the check then says it could not examine the image. A check that raises an exception is converted to "could not examine" by the pipeline and is never reported as a pass.

@section 6.2|FRONTEND
The interface is a React 18 application with 17 components. It has three modes, selected by tabs: check one screenshot, compare with a genuine copy, and check against a second source. In the first and third modes a drop-down asks what kind of screenshot it is. After analysis it shows the verdict banner with the risk gauge, the assurance panel with its four-step ladder, the image with numbered boxes over the marked regions, the reasons, the checks panel (each check with what it did and whether it counts, and for an advisory check why not), the findings, a limitations panel that cannot be dismissed, and a download of the JSON report. In reconcile mode a table shows, for each fact, the value in the second source, the value in the screenshot and the result. An error panel gives distinct messages for network failure, timeout, oversized file, invalid image, rate limiting and server errors. A demonstration mode opened with a query parameter renders fixture results without the back end. {fig:fig_ui_v3} shows the result of the demonstration for a "no inconsistency" case; it is a fixture, because the shipped service cannot yet produce that verdict (Section 3.6).

@fig fig_ui_v3|13.5|The result screen in demonstration mode: the verdict banner, the assurance ladder at level 1, and the first reasons. The page is a fixture with placeholder content, not a real analysis.

The frontend was written with an AI coding assistant (Appendix F), checked by 72 automated tests and built for production. It was also tried by hand in a browser against the running back end (a generated receipt image and a matching bank SMS, entered in reconcile mode, gave level 2 with all four facts matching and no console errors); that manual check was not logged.

@section 6.3|TOOLING FOR DATA, TRAINING AND EVALUATION
The corpus, training and evaluation tools live in `backend/tools/forge/` (the second version's generator and training code) and `backend/tools/`. The tools added for the final version are `mutation_content.py` (the mutation test of the content rules), `eval_reconcile_synthetic.py` (reconcile mode with ground truth), `eval_reconcile_real_pairs.py` (reconcile mode on real SMS and lists), `stfd_robustness.py` (seeds, bootstrap, ablation, baseline), `train_router.py` and `eval_router.py` (the structure router and the validation of both routers), `calibrate_gates.py` (the gates), `eval_compare.py` (compare mode and its controls), `eval_reconcile.py` (the mutation test), `eval_stfd.py` and `train_stfd.py` (the STFD pipeline run and the training on real edits, including the degraded copy and the comparison of three models) and `eval_rico.py` (false alarms on genuine Rico screens). The first version's code is kept in `backend/legacy/` and the previous single-model analyser in `backend/analysis_v2.py`, only so that the earlier numbers can be reproduced.

@section 6.4|TESTING
The backend has 101 automated tests (Table {tab:tests}) and the frontend has 72 in 11 files, all passing at the time of writing. The backend tests cover the interface (status, rejection of bad files and unknown types, the response contract, a blank image being inconclusive, a guard against uploads being spooled to disk), the content rules (including tests that ordinary pages raise no finding), the feature extractor and edit simulator, and the design of the final version: routing, the gate rule, the verdict policy (a clean result is never "authentic", and an advisory signal can only make the answer more cautious), the type-specific rules, compare mode, fact extraction, reconciliation, the assurance levels, and the rule that the version-1 cues can never be live. The frontend tests cover overlay geometry, error mapping, each verdict state, the demonstration mode, the checks panel (a check that could not examine the image is never shown as a pass), the assurance panel (level 3 is never shown as reached) and the reconcile panel.

One of the frontend tests failed on the project's own new text and is worth recording. An existing test requires that no result page contains the words authentic, genuine, verified, real or "is safe". The new assurance panel contained "Verified against signed data" for the unavailable level 3 and a note that began "No level proves a screenshot is real". The test caught both; the level was renamed "Confirmed by signed data" and the note reworded. The test also matched "Unverified" and "unverified" because they contain "verified", so its pattern was changed to match the whole word. The test is doing its job when it fails on an overclaim, and the edit to its pattern removes a false match without letting any of the banned assertions through.

@section 6.5|PRIVACY AND SECURITY PROPERTIES
Screenshots can contain payment and chat details, so privacy was designed in and then audited against the code. The application reads each upload into memory and never writes the image to a path it chose. An audit of the code path found that the web framework's default upload parser spools any file part above 512,000 bytes to a temporary file on disk; a 2 MB upload triggered this. The application now installs a request class that keeps every upload part in memory, bounded by the 10 MB size limit, and a regression test fails if a large upload rolls over to disk (Listing B.2). The second source of reconcile mode is handled the same way: pasted text and the second image are kept in memory and the log records only the sizes. The application logs the number of bytes received, the verdict, the risk score and the number of marked regions, and a traceback if an analysis fails, but not the image or its text, although the response includes a SHA-256 digest of the file. Under the compose file the nginx front proxy may buffer large request bodies to disk, so the in-memory property holds for the Flask application only. Cross-origin access is open by default and configurable through an environment variable; there is no authentication, rate limiting or transport security in the prototype, and the README says that a reverse proxy should provide them before exposure.

@section 6.6|DEPLOYMENT
The backend image is built from a Python 3.12 slim base with the Tesseract package, the pinned requirements and gunicorn with two workers and a 180-second timeout; a `.dockerignore` keeps the virtual environment, tests and tooling out of the image. A second image serves the built frontend through nginx, which proxies `/api/` to the backend with a 180-second read timeout. A compose file starts both, and a Render blueprint describes a two-service deployment. An image built earlier in the project, with an intermediate model, was started and queried through its published port; it was 788 MB and returned the expected verdict for the generated sample (`docker_test.log`). A rebuild from the final tree could not complete because the base image could not be pulled (registry timeout, `docker_build_final.log`), so the final image has not been run, and the final version has been run only from source.
