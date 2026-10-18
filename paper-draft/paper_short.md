@abstract
Screenshots of chats, bank statements and payment histories are routinely accepted as informal evidence, yet any image editor can alter them. This project builds and evaluates a screenshot-forensics service that reports signs of editing in an uploaded image and states plainly what it cannot see. A first version, which combined photograph-forensics cues with a random forest, was audited on genuine screenshots: it flagged 12 of 60 untouched images (20%) and could not separate realistic word edits from their originals (AUC 0.50 over 42 image sets). The second version replaces those cues with a word-level detector. Every word found by optical character recognition is described by 95 rendering and layout measurements, also expressed relative to the words around it, and a boosted-tree classifier estimates the probability that the word was edited. Rule checks add document logic such as weekday against date, totals and the regularity of number columns. Because no suitable public data could be obtained in time, a labelled corpus of 20,814 images was generated from real, Chrome-rendered and Pillow-rendered screenshots, with two edit engines, identical re-sharing degradation for both classes, splits by base image and held-out edit fonts. On unseen images and fonts the detector reaches an AUC of 0.85 (0.84 on a 500-image subset on which the first version scored 0.46). On 73 genuine full-size screenshots never seen by the model that scored them, it flags 5.5% at its suspicious tier and none at its evidence tier, while catching 45% and 24% of simulated edits. Performance falls after down-scaling and transfers only partly across editing engines. Edits made by a person have been tried only on an eight-image development sample (two of four flagged, none of four genuine). Screenshots rendered natively with false content cannot be detected by this method.
@endabstract

@chapter 1|INTRODUCTION

@section 1.1|OVERVIEW
A screenshot is offered to prove that a payment was sent, that a message was received or that an account held a given balance. It is also among the cheapest things to fake: opening the image in an editor, covering a number and typing another takes minutes. Work on forged text images names finance, certificate checking and news screenshots as typical targets [@yu2025fsts], and a 2026 benchmark treats fabricated screenshots and documents as a prominent vehicle for misinformation and fraud [@zhang2026textfake].

This project, Screenshot Forensics, is a working service that examines one uploaded screenshot and asks a narrow question: does any word in it show signs of having been changed after the screenshot was taken? The answer is a four-tier verdict (evidence of editing, suspicious, no evidence of editing, not enough readable text), the words that triggered it marked on the image, and a plain-language reason for each. The service never states that an image is authentic, and a list of what it cannot detect is returned with every answer. The project also went through a redesign: the first version reused the standard toolbox of photograph forensics, was audited on genuine screenshots and failed, so this report records both versions.

@section 1.2|WHY SCREENSHOTS ARE DIFFERENT FROM PHOTOGRAPHS
Passive image forensics grew up around photographs [@farid2009survey]: a forger splices part of one picture into another, moves a region, or removes an object by inpainting [@verdoliva2020], and an analyst looks for traces left by the camera, the JPEG coder or the editing step [@piva2013overview]. Most of those traces are weak or absent in a screenshot. There is no camera sensor, so sensor-noise methods [@lukas2006prnu] have nothing to measure. Error level analysis, the most widely discussed trick, resaves the image at a known JPEG quality and compares it with the original [@krawetz2007]; it presupposes lossy compression, whereas 59 of the 60 genuine screenshots used in the first audit were lossless PNG files. A screenshot is also often re-shared through messaging applications that re-compress or down-scale it.

What a text edit does leave behind is local: the inserted glyphs were drawn by a different program, at a slightly different size, with a different anti-aliasing recipe, on a patch of background that rarely matches its surroundings exactly. Work on document tampering notes that text within a cluster usually shares one font and size, which is why visual clues of tampering are scarce [@qu2023doctamper]. The inference drawn here, that a replaced word therefore tends to differ in rendering, is this project's working hypothesis and the starting point of the method.

@section 1.3|PROBLEM STATEMENT AND OBJECTIVES
Given a single screenshot with no reference original, decide whether text in it was edited with a raster editor, locate the edited words and explain the decision, keeping false alarms low and being explicit about the cases the method cannot handle. There is no reference image, so the only evidence is internal consistency; the edited area is tiny, so a detector that scores every word has hundreds of chances to raise a false alarm; and no labelled data of real edited screenshots could be obtained in time, so training and evaluation data had to be produced and the risk that a model learns the generator instead of the edit had to be controlled.

The project set six objectives: (1) audit the first version on genuine screenshots and realistic edits; (2) design a word-level detector that explains every flag; (3) build a labelled corpus with exact edit masks, controlled against leakage; (4) evaluate with protocols that expose weaknesses, not only one held-out split; (5) add rule checks that read the content of the screenshot; and (6) deliver a usable service with an interface, tests and a container image, and document its limits.

@section 1.4|SCOPE AND CONTRIBUTIONS
The scope is raster edits of text in screenshots: re-typed words and numbers, spliced word crops and background patches painted under them. Out of scope are screenshots rendered natively with false content (text changed in a browser's developer tools, output of a fake-receipt website), images generated by an AI model, and print-and-scan recapture; the first two leave no editing inconsistency for any pixel-level method to find. The contributions are of the system, application and cautionary-evidence kind: an audit of a photograph-forensics pipeline on genuine screenshots (Section 7.1); a word-level, explainable detector with its behaviour under several evaluation protocols (Chapters 4 and 7); ScreenForge, a leak-controlled generated corpus with two edit engines (Chapter 5); a layout-grid rule measured on 6,656 genuine images, with the record of a first version that failed that measurement (Section 7.5); and a record of negative results (Section 7.6). The report does not claim a new learning algorithm or performance on edits made by independent people with real tools.

@chapter 2|BACKGROUND AND LITERATURE SURVEY

@section 2.1|CLASSICAL AND LEARNED FORENSICS
Surveys describe passive forensics as the search for traces an image acquires at capture, coding and editing [@piva2013overview; @verdoliva2020]. Compression history is the best-known family. The "JPEG ghost" technique of Farid is aimed at spotting a region first saved at a lower JPEG quality than the rest of the image [@farid2009ghosts]; Bianchi and Piva map the likelihood that each 8 by 8 block was compressed twice [@bianchi2012block]; and error level analysis inspects where a resave at a known quality differs most from the original [@krawetz2007]. All presuppose that the image went through JPEG coding. Other families look for resampling [@popescu2005resampling], noise inconsistencies [@mahdian2009noise] or copy-move duplication [@christlein2012eval]. Resampling matters here because shared screenshots are often down-scaled; noise and sensor cues matter little because a screenshot has no sensor; and copy-move is plausible but screenshots contain many legitimate repeated icons and list rows.

Learned localisers replaced hand-built cues in much of the recent literature. ManTra-Net treats localisation as local anomaly detection with a convolutional network [@wu2019mantranet], CAT-Net learns compression artefacts from RGB and DCT streams [@kwon2021catnet], and TruFor learns a noise-sensitive fingerprint from real data only and outputs a reliability map to reduce false alarms [@guillaro2023trufor]. The first version of this project was trained partly on standard natural-image data, the CASIA database [@dong2013casia] and IMD2020 [@novozamsky2020imd]; Section 7.1 shows why that was inappropriate for screenshots.

@section 2.2|TAMPERED TEXT, DOCUMENTS AND SCREENSHOTS
Text in documents differs from objects in photographs: backgrounds are uniform and text usually shares one font and size, so visual clues are scarce [@qu2023doctamper]. The Screenshot Text Forgery Dataset (STFD) is described by its authors as the first public dataset for localising text forgery in smartphone screenshots [@yu2023stfd]; its dataset card says the archive can only be extracted with a password obtained by e-mailing the authors from an academic or institutional address [@hf_stfd]. That request was made for this project but no password had arrived when the experiments were completed, so no result here uses STFD. FSTS collected 16,750 real tampering instances from 67 people and used their operations and post-processing parameters to synthesise training data [@yu2025fsts]; its release is a roughly 46 GB archive [@hf_fsts] and was not used. The closest published work found is a pipeline designed for screenshots that combines error-level, noise, JPEG, text-edge and metadata cues in a gradient-boosted classifier and reports an AUC of 0.82 on its own 1,200 screenshots, with weaker recall on small text edits [@venkatesh2026screenshot]; its numbers are not compared with this project's because data and conditions differ. Detection of AI-generated screenshots is a separate problem, outside the scope of this work [@zhang2026textfake].

Three findings from the document-forensics literature shaped the evaluation. An improvement on a synthetic benchmark that resembles the training data does not carry over reliably to forgeries made by people or to other domains [@dhouib2026doctamper]. Training with a narrow range of JPEG quantisation tables does not match varied operational compression [@ronfleux2026docqt]; the corpus here therefore passes genuine and edited images through the same random sharing step. And adapting the decision threshold to the target domain is described as a key missing step for deployment [@zhao2026docforge]; this system fixes its two thresholds at false-alarm rates of 5% and 1% on genuine, in-domain validation images. Dataset bias [@torralba2011bias] and data leakage [@kapoor2023leakage] are known threats to generalisation, so splits are made by base file, test edits use fonts unseen in training, and thresholds are fixed on data the model did not fit.

@section 2.3|GAP AND POSITIONING
Public screenshot data is access-controlled or very large, published screenshot work relies mainly on compression-related cues, and document-forensics papers warn that synthetic gains transfer poorly to human forgeries. The project therefore pursues a small, explainable, CPU-only detector built on rendering consistency within a single image, evaluated with leak-controlled protocols and reported with its failures. It does not compete with learned localisers on their benchmarks; no such comparison was run.

@chapter 3|REQUIREMENTS AND SYSTEM DESIGN

@section 3.1|REQUIREMENTS
The service must accept one PNG, JPEG or WebP image of up to 10 MB; read the text and judge each word; return a verdict in one of four tiers, a risk score, the marked words with coordinates and reasons; run rule checks on the content and the file metadata; return a fixed list of limitations with every response without ever calling an image authentic; and provide a web interface that shows the marked words and reports failures distinctly. Non-functional requirements are explainability (every flag points to a place and a reason a person can check), privacy (the image stays in memory), few false alarms on genuine screenshots, prioritised over detection rate, and operation on an ordinary CPU without network access.

@section 3.2|DESIGN PRINCIPLES
Four principles were fixed after the audit of the first version. (1) Absence of evidence is not evidence of absence: the lowest tier is "no evidence of editing found", never "authentic", because a natively rendered fake contains nothing for the method to find. (2) A rule ships only if it stays silent on ordinary pages: every rule has a unit test showing this, the layout rule was also measured on 6,656 genuine images, and one rule that fired on an ordinary bank screen was removed (Section 7.5). (3) Thresholds belong to the domain: they are set on genuine, real validation screenshots, where false alarms hurt (Section 4.3). (4) Failures are recorded, because evidence for what works is only as good as the record of what was tried.

@section 3.3|ARCHITECTURE
@fig fig_architecture|15.5|Architecture of the Screenshot Forensics service. Rule checks and the classifier both feed the verdict independently.

The browser interface posts the image to a Flask application programming interface. The application reads the image, applies the orientation stored in its metadata so that coordinates match what a browser shows, runs OCR, and hands the word boxes to two independent components: a word-level component, in which each word is measured and scored by the classifier, and a rule component that reads the text, the metadata and the layout. A verdict module combines both into a tier, a risk score, marked regions and reasons, and attaches the limitations. Because the two components do not depend on each other, a rule can escalate a screenshot even when the classifier sees nothing (Section 7.6).

@section 3.4|WHAT THE METHOD CAN AND CANNOT SEE
@table threat|Threat model: which kinds of fake the method can address
Kind of fake | Detectable? | Why
A word or number re-typed over a screenshot in a raster editor | Partly (Chapter 7) | the inserted glyphs differ from their neighbours in rendering, size, colour or placement
A word crop spliced in from another image | Partly | the crop carries its own rendering and background
A number pasted off the row grid of an evenly spaced list | Partly, when the list is regular | rule on column spacing (Section 4.4)
Text changed in browser developer tools, or output of a fake-receipt website | No | the screenshot is genuine renderer output; nothing is inconsistent
A screenshot generated by an AI image model | No (out of scope) | no editing step exists
Edit followed by heavy down-scaling or re-compression | Weakly | resampling smooths the anti-aliasing evidence (Section 7.2)
@endtable

For cases the method cannot see, the only dependable remedy is to verify with the issuer. The limitations text returned by the service gives this general advice.

@section 3.5|VERDICT POLICY
Let p be the highest word probability in the image, T_s the suspicious threshold and T_e the evidence threshold (Section 4.3). Table {tab:verdict} gives the four tiers.

@table verdict|Conditions for each verdict tier
Tier | Condition | Risk score
Evidence of editing found | p >= T_e, or a high-severity rule finding | at least 0.70
Suspicious - review recommended | p >= T_s, or a medium-severity finding | 0.40 to 0.70
No evidence of editing found | neither, and at least six words measured | below 0.40
Not enough readable text | neither, and fewer than six words measured, or no model loaded | not shown
@endtable

The risk score is a monotone rescaling of p so that the two thresholds always fall at 0.40 and 0.70 on the gauge in the interface; it is a display aid, not a calibrated probability. The service marks at most ten words, those with p of at least 0.75 T_s.

@chapter 4|DETECTION METHOD

@section 4.1|IDEA AND OPTICAL CHARACTER RECOGNITION
The method rests on one idea: a word inserted after the screenshot was taken is an outlier among its neighbours. Because the appearance of text varies enormously between applications, fonts and devices, the detector never asks whether a word looks "normal"; it asks whether this word was rendered like the others in the same image ({fig:fig_word_idea}).

@fig fig_word_idea|15.5|The word-level analysis: OCR boxes, per-word measurements, comparison with neighbours, probability of editing.

Words and boxes come from Tesseract [@smith2007tesseract], version 5.5.3. Every box is kept whatever its confidence: discarding boxes below a confidence of 40 removed the edited word from analysis in about a third of the edited test images, because a word set in an unusual font is exactly the one Tesseract reads with low confidence. A word is measured only if its box is 8 to 220 pixels high and at least 6 pixels wide and its crop has enough contrast and ink; an image with fewer than three measurable words yields no features.

@section 4.2|PER-WORD MEASUREMENTS AND COMPARISON WITH NEIGHBOURS
For each measurable word the code (`backend/textforensics.py`) crops the box with a margin, takes the median of the margin ring as the local background, and defines ink and anti-aliased pixels relative to the word's contrast. Forty raw measurements are derived in seven groups: edge and contrast profile (9), colour including sub-pixel fringing (3), stroke width (3), background texture (4), seam (3), JPEG grid (2) and histograms of ink level and gradient orientation (16). The seam measurements look for the step in colour that a background patch painted under an edit leaves along its border. Six geometry values complete the absolute description.

Nineteen measurements are re-expressed as robust z-scores (value minus the median of a comparison set, divided by 1.4826 times the median absolute deviation, clipped to the range minus 12 to 12), computed twice: against all other words in the image and against the other words on the same line, which gives 38 relative features. Because Tesseract's line identifiers proved unreliable on interface layouts, the code groups words into lines itself, which adds line-relative height, offset and colour features and chi-square distances between a word's histograms and the median histograms of the image and the line. The 40 raw measurements, 6 geometry values, 38 z-scores and 11 line and histogram features make up the 95 features of the classifier.

@section 4.3|CLASSIFIER AND THRESHOLDS
Word probabilities come from scikit-learn's histogram-based gradient-boosted trees [@friedman2001; @pedregosa2011]: up to 1,500 iterations, learning rate 0.05, at most 63 leaves, at least 40 samples per leaf, L2 regularisation 2.0 and early stopping on a 10% internal split. Training used 808,445 labelled words, of which 10,582 are edited, and stopped after 848 iterations. A word is labelled edited when at least 30% of its box overlaps an edit rectangle and genuine when it overlaps by at most 2%; words in between are excluded. Words from real screenshots have a sample weight of 3, because the real domain is the target and the scarcest.

The image score is the highest word probability. The suspicious threshold is the score exceeded by 5% of validation images that are genuine and real, and the evidence threshold the score exceeded by 1%; with 246 such images the values were 0.847 and 0.966. Calibrating on real genuine images, not on pooled data, answered the observation that real screenshots produced more false alarms than generated ones. The maximum over words has a cost: an image with several hundred words gives several hundred opportunities to be wrong. An intermediate model flagged 11.0% of genuine full-size screenshots although it flagged only 2.1% of real test windows, until full-size genuine screenshots were added to training (Section 7.4). A second-stage model over the word probabilities did not improve the ranking, so the simple maximum was kept.

@section 4.4|RULE CHECKS AND EXPLANATIONS
The rule module (`backend/semantic.py`) reads the file and the text. Its rules cover editing-software tags in the metadata, watermarks of known fake-document generators, placeholder names and numbers, a total smaller than its subtotal, items that do not add up, a weekday that does not match its date, impossible or future dates, invalid IBAN or card numbers, impossible clock times, a duplicated status-bar clock, and a number off its column grid. Each carries a severity (high, medium or low) that feeds the verdict. The first version of the arithmetic rule flagged any image showing both a "Balance" and a "Total", which describes an ordinary bank screen; it was removed and replaced by narrower rules, and a unit test now asserts that such a page raises no finding.

The layout-grid rule uses the fact that lists in payment and shopping applications place one number per row at constant pixel spacing, which a pasted value rarely matches. Using OCR boxes only, it clusters numeric words on their right edge, requires at least six rows (and in practice eight for every row to be testable), measures each interior row's baseline deviation from the midpoint of its neighbours, and flags the row with the largest deviation when it is at least the larger of 5 pixels and 0.2 of the text height while the other rows are regular. A fourth condition, that both gaps beside the candidate lie between 0.6 and 1.4 times the median row pitch, was added after the first version, which lacked it, had a 2.03% false-alarm rate because an OCR box missed in one row doubles a gap (Section 7.5). The rule is silent when the column is not regular, which is the common case and by design.

Reasons are generated, not learned: for a marked word the code lists the relative features with an absolute z-score of at least 3 in plain language, together with four geometric reasons (a patch outline, a height differing from the line, a baseline offset and a colour distance to the line), and shows at most three. They describe which measurements deviate; they are not a causal account of the edit.

@chapter 5|DATASET AND EXPERIMENTAL SETUP

@section 5.1|WHY THE DATA WAS GENERATED AND ITS SOURCES
The detector needs screenshots in which every edited word is labelled exactly. The first version was trained on photographs, receipts and found manipulations, the wrong domain (Section 7.1), and STFD could not be obtained (Section 2.2). Published work stresses that human-made tampering data is scarce and that synthetic data should model the operations and post-processing people actually use [@yu2025fsts]. The corpus, ScreenForge, therefore combines three sources of genuine bases with a simulator that applies such operations and records the exact edit rectangle.

The sources are deliberately different. Real device screenshots, from the author's own machine, represent the target domain but are scarce: 89 files were found, 16 contain no readable text, leaving 73 (22 of the 89 are full-size 3,024 by 1,964 pixel captures); they are private and never distributed. Chrome-rendered application screens (1,600 images from 16 layouts such as chats, bank statements, receipts and e-mail, in 24 fonts, light and dark themes and several viewports) come from a different rendering engine than the macOS screenshots. Pillow-rendered screens (ten categories, one randomly chosen system font) provide a third renderer.

@section 5.2|THE EDIT SIMULATOR
For each base image the simulator edits one word (a second in 20% of cases), preferring words with digits in 60% of draws because amounts, dates and identifiers are the usual targets. An edit re-types the word (62%), re-types it and blurs the patch (24%), or splices in a word crop from another image (14%). For words with digits, 75% of edits change one to three digits. The new text is drawn in a randomly chosen font at the old word's height with grey-scale (65%), no (12%) or simulated LCD sub-pixel (23%) anti-aliasing, in the original ink colour, over a padded background patch filled with a flat colour, noise-matched colour, gradient or clone-stamped block, with optional blur and a local JPEG round trip.

A second, independent engine, `patchbank.py`, rasterises the new text with Chrome instead of Pillow, using 11,000 pre-rendered patches in 24 Chrome fonts. It was added because a model trained on Pillow edits only scores an AUC of 0.75 on Chrome-rendered edits (Section 7.3). Pillow edits use 283 Latin-capable fonts, each assigned by hash to one of five folds: folds 1 to 4 supply training and validation edits and fold 0 supplies test edits only, so every test edit that renders new text uses a font the model never saw. Four Chrome families play the same role. A unit test checks that an edit changes pixels only inside the recorded rectangle.

@section 5.3|SHARING DEGRADATION AND SPLITS
After editing, every image, genuine or edited, passes through the same random sharing step: lossless PNG (34%), JPEG at quality 55 to 98 (34%), down-scaling by 0.5 to 0.85 followed by PNG (14%) or by JPEG (18%). Genuine and edited images are treated identically so that compression history cannot serve as a shortcut for the label, since localisation models depend on the compression seen in training [@ronfleux2026docqt].

Splits are made by base image, using a hash of the base file path or identifier: 70% of hash values go to training, 15% to validation and 15% to test, so all windows, copies and edits derived from one screenshot file fall in the same split [@kapoor2023leakage]. Thresholds are fixed on the validation split. In the leave-files-out protocol (Section 5.5) the model is trained on the training split only; an earlier version of that script violated this and its output was discarded.

@section 5.4|CORPUS STATISTICS
The final corpus holds 20,814 images assembled from four builds (a base corpus of 8,888, extra real windows 3,472, Chrome-patch edits 7,599 and whole real screenshots 855). Training uses 14,494 images, validation 3,083 and test 3,237 (2,184 edited). The 1,600 Chrome bases are used in two builds, each with an independently drawn sharing step, so the 3,200 genuine Chrome images derive from 1,600 bases; all derivatives of one base fall in the same split.

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

@section 5.5|EVALUATION PROTOCOLS AND ENVIRONMENT
Seven protocols answer different questions: (1) a held-out test with unseen base images and edit fonts, with image-level AUC and detection and false-alarm rates at the two thresholds; (2) a comparison of the first and final versions on 500 random test images; (3) a cross-engine test of models trained on Pillow edits only, Chrome edits only and both; (4) leave-files-out, five folds over the 73 real files, each file scored whole as a genuine image together with up to six edited copies (426 in all, Pillow engine, held-out fonts, no splices) by a model trained without any window of it; (5) rule validation on every genuine corpus image; (6) an eight-image hand-collected sample, used for development and therefore not a test; and (7) latency. Rates are proportions of images, AUC is the area under the receiver operating characteristic curve [@fawcett2006roc], and Wilson intervals [@wilson1927] are given for selected false-alarm rates; every experiment uses one split and one fit, so differences of a few percentage points should not be read as established.

All experiments ran on one Apple M5 machine with 16 GB of memory, with Python 3.14.3, scikit-learn 1.9.0, Pillow 12.3.0, NumPy 2.5.1, Tesseract 5.5.3 and Google Chrome 155 for rendering; the container image uses Python 3.12.

@chapter 6|IMPLEMENTATION

@section 6.1|BACKEND AND FRONTEND
The backend is a small Flask application (94 lines in `app.py`) with `POST /analyze`, which accepts one multipart image and returns the analysis as JSON (400 for a missing, wrongly named, empty or undecodable file, 413 for an oversized upload, 500 for any unexpected error), and `GET /status`, which returns the loaded model's metadata. The analysis is split into `textforensics.py` (about 390 lines: OCR, per-word measurements, explanations), `semantic.py` (about 320 lines: rules) and `analysis.py` (about 170 lines: model loading and verdict policy). At start-up `analysis.py` refuses to load a model whose stored feature names differ from those the code produces.

The interface is a React 18 application built with Vite. After analysis it shows a verdict banner, a gauge of the risk score with both thresholds marked, the uploaded image with numbered boxes over the marked words, the reasons, expandable rule findings, a limitations panel and a JSON download; separate error panels distinguish network failure, oversized file, invalid image and server errors, and a demonstration mode renders fixture results without the back end ({fig:fig_ui}). The frontend was written with an AI coding assistant (Appendix D) and tried by hand in a browser against the running back end; that manual check was not recorded in a log.

@fig fig_ui|13.5|The result screen for an edited amount in a generated bank statement: the verdict banner, the risk gauge with the two tier boundaries, the marked word on the image and the reasons.

@section 6.2|TESTING, PRIVACY AND DEPLOYMENT
The backend has 35 automated tests (11 for the interface, 18 for the rules and 6 for the feature extractor and edit simulator) and the frontend 58, all passing at the time of writing (Appendix C).

Screenshots can contain payment and chat details, so privacy was audited against the code. The application never writes the image to a path it chose. The audit found that the web framework's default upload parser spools any file part above 512,000 bytes to a temporary file; a 2 MB upload triggered this. The application now installs a request class that keeps every upload part in memory, bounded by the 10 MB limit (Listing B.1), and a regression test fails if a large upload rolls over to disk. The application logs the number of bytes received, the verdict, the risk score and the number of regions, but not the image or its hash. Under the compose file the nginx front proxy may buffer large request bodies to disk, so the in-memory property holds for the Flask application only. Cross-origin access is open by default, and the prototype has no authentication or rate limiting.

The backend image is built from a Python 3.12 slim base with Tesseract and gunicorn, a second image serves the frontend through nginx, a compose file starts both, and a Render blueprint describes a two-service deployment. An image built earlier with an intermediate model was started and queried through its published port (788 MB, expected verdict on the generated sample; `docker_test.log`). A rebuild from the final tree could not complete because the base image could not be pulled (registry timeout), so the final image has not been run.

@chapter 7|RESULTS AND ANALYSIS

@section 7.1|AUDIT OF THE FIRST VERSION
The first version (kept in `backend/legacy/`) combined error level analysis, a JPEG-ghost scan, quantisation checks, noise statistics, copy-move detection, edge, font, clock and arithmetic cues, metadata rules and a random forest trained on three photograph and receipt datasets. It had never been run on screenshots known to be untouched. On 60 genuine screenshots from the author's machine (59 PNG, 1 JPEG) it flagged 12, 20.0%, as fake. Three cues (ELA, block noise, edge sharpness) were non-zero on 59 of the 60 images and near the top of their range, so they could not be distinguishing anything; the composite score averaged 0.385 with a maximum of 0.626, close to the 0.5 decision threshold. The lossless format explains part of the saturation, because error level analysis presupposes lossy compression [@krawetz2007], but that is an explanation consistent with the data, not a tested cause.

In a second experiment, a draw of sixty PNG screenshots gave 42 image sets in which one word, preferring digits, was painted over and re-typed in Helvetica. The first version scored an AUC of 0.496 for separating edited from original images (0.501 after JPEG at quality 85); the edit changed the score by a mean of minus 0.0013. It could not tell a re-typed word from the untouched screenshot. It also flagged both a Chrome-rendered bank page and a copy with two amounts changed in the HTML (scores 0.495 and 0.416), because its arithmetic rule read the page's "Balance" and "Total Spent" lines as contradictory. These findings define the redesign: drop the photograph cues, compare words with their neighbours, calibrate on genuine real screenshots, and make every rule demonstrate silence on ordinary pages.

On 500 test images drawn at random (340 edited) the first version scored an AUC of 0.459 and flagged 10.6% of genuine and 7.4% of edited images, so it flagged genuine images more often than edited ones; the final model scored 0.838 and flagged none of the genuine images at its evidence tier and 0.6% at its suspicious tier, while flagging 29.4% and 43.8% of edited images (Table {tab:v1v2}). The comparison is not an indictment of the cues themselves, since the first version was designed for different data; it shows that on these images rendering-consistency features separate the classes and the first version's cues do not.

@table v1v2|First and final versions on 500 test images
System | AUC | Genuine flagged | Edited flagged
First version | 0.459 | 10.6% | 7.4%
Final, evidence tier | 0.838 | 0.0% | 29.4%
Final, suspicious tier | 0.838 | 0.6% | 43.8%
@endtable

@section 7.2|PERFORMANCE ON THE HELD-OUT TEST SET
The test set contains 3,237 images (2,184 edited) from base images and edit fonts unseen in training. The image-level AUC is 0.847 (validation 0.846). At the evidence tier 31% of edited images are caught with 0.3% of genuine images flagged; at the suspicious tier 43% are caught with 1.0% flagged. The word-level AUC is 0.983, much higher than the image-level figure, because the image score is the maximum over many words and one genuine word with a high score can outrank an image's true positive. Table {tab:groups} breaks the result down.

@table groups|Held-out test results by group
Group | Edited images | AUC | Caught, evidence | Caught, suspicious
Chrome-rendered bases | 870 | 0.875 | 31% | 42%
Pillow-rendered bases | 423 | 0.824 | 26% | 39%
Real screenshots | 891 | 0.825 | 33% | 46%
Re-typed (Pillow) | 941 | 0.831 | 28% | 40%
Re-typed and blurred | 360 | 0.895 | 53% | 63%
Spliced word crop | 204 | 0.846 | 31% | 45%
Chrome-rendered patch | 679 | 0.844 | 23% | 35%
Shared as lossless PNG | 725 | 0.912 | 43% | 56%
Shared as JPEG, quality 55-98 | 771 | 0.882 | 36% | 49%
Down-scaled, then PNG | 290 | 0.729 | 11% | 23%
Down-scaled, then JPEG | 398 | 0.718 | 13% | 20%
@endtable

On real screenshots, the target domain, 46% of simulated edits are caught at the suspicious tier and 2.1% of genuine real images are flagged. Edits that were blurred to hide inconsistencies were caught more often, not less; a plausible reading, which these data do not test, is that blur changes the sharpness profile of the patch, and no feature-importance analysis was run. Down-scaling is the weak case: the AUC falls to 0.72 to 0.73 and fewer than a quarter of edits are caught, consistent with the general observation that resampling alters pixel statistics [@popescu2005resampling]. The service cannot recover that evidence; its limitations text warns about it.

@section 7.3|DOES THE MODEL LEARN THE EDITING ENGINE?
A classifier that sees edits from one renderer could learn the renderer's signature instead of the edit. Table {tab:cross} shows models trained on Pillow edits only, Chrome edits only and both, each tested on held-out edits from each engine. Transfer across engines is real but incomplete: a model trained on one engine scores 0.75 to 0.78 on the other, against 0.85 to 0.86 on its own, and training on both restores 0.84 to 0.85 on each. With two engines the result cannot show that a third (Photoshop, Canva, a phone editor) would be handled as well.

@table cross|Cross-engine generalisation (image-level AUC on the test split)
Trained on | Tested on Pillow edits | Tested on Chrome edits
Pillow edits only | 0.846 | 0.752
Chrome edits only | 0.783 | 0.855
Both engines (shipped) | 0.849 | 0.844
@endtable

@section 7.4|GENUINE SCREENSHOTS THE MODEL NEVER SAW
The leave-files-out protocol is the closest test to real use. Table {tab:cv} gives the result for the 73 real files, each scored whole by a model trained without any window of it, together with 426 edited copies.

@table cv|Leave-files-out results (5 folds, 73 genuine full-size screenshots, 426 edited copies)
Measure | Suspicious tier | Evidence tier
Genuine screenshots flagged | 4 of 73 (5.5%; Wilson 95% interval 2.2% to 13.3%) | 0 of 73 (0.0%; interval 0.0% to 5.0%)
Edited copies caught | 191 of 426 (44.8%) | 103 of 426 (24.2%)
Caught after PNG sharing / JPEG | 53% / 55% | 28% / 36%
Caught after down-scaling (PNG / JPEG) | 32% / 24% | 12% / 8%
@endtable

The sample is small and comes from one person's machine, so the intervals are wide: a false-alarm rate between about 2% and 13% is consistent with 4 of 73. The edited copies are six per file and not independent, so no interval is given for detection rates. An intermediate model trained before whole real screenshots were added flagged 8 of 73 (11.0%, interval 5.7% to 20.2%), against 4 of 73 for the final model. An earlier version of the script had a calibration fault (its output was not kept): it trained on the validation images it then used to set thresholds, so the thresholds came out too low; the numbers above come from the corrected script.

@section 7.5|THE LAYOUT-GRID RULE
The layout rule was written after the classifier missed an edited amount on a real payment-history screenshot and was tuned while looking at that example, so its false-alarm rate was measured separately on the whole corpus, using word boxes only (Table {tab:layout}). Inspection of some of the first version's false alarms (the list of all cases was not kept) showed lists where OCR had skipped a row, so a single gap was twice the row pitch; requiring both gaps beside the candidate to be near the normal pitch removed these.

@table layout|False alarms of the layout-grid rule on genuine corpus images, first and final version
Source | First version | Final version
Chrome-rendered | 112 of 3,200 (3.50%) | 6 of 3,200 (0.19%)
Pillow-rendered | 1 of 1,657 (0.06%) | 0 of 1,657 (0.00%)
Real screenshots | 22 of 1,799 (1.22%) | 0 of 1,799 (0.00%)
All genuine images | 135 of 6,656 (2.03%; interval 1.7% to 2.4%) | 6 of 6,656 (0.09%; interval 0.0% to 0.2%)
@endtable

Recall was measured by shifting one row of a genuine list vertically: it was 0.1% at a shift of 0.1 text heights, 1.3% at 0.2, 7.7% at 0.3, and 15.5% and 15.2% at 0.5 and 0.8. Only about 15% of genuine images with a numeric column are evenly spaced enough for the rule to apply, and on those it finds essentially every shift of half a text height or more; the rule is precise and narrow. The remaining rules are validated by unit tests (a contradiction that must fire and an ordinary page that must stay silent) but their false-alarm rates were not measured on the corpus, because the generated screenshots rarely contain the contradictions they test.

@section 7.6|A SAMPLE OF REAL EDITS AND A NEGATIVE RESULT
Eight screenshots from a payment-application history were collected: four edited by a person with their own tools and four genuine. The final system flagged two of the four edits and none of the four genuine images. One flag came from the classifier alone (top word probability 0.979 for an amount set in a thinner italic font). The other came from the layout rule, on an amount placed about 14 pixels above its row, which the classifier had scored 0.11. The other two edits (a shorter plain amount and a short amount in a different serif font that OCR read as "ad") scored 0.27 and 0.34. The sample is development data, not a test: it was used to find the blind spot that led to the layout rule, and the edited files also differ from the originals in resolution and file type. The images are personal and are not reproduced.

In these images each edited amount stood out from the other amounts in its column on stroke thickness and edge sharpness, while no genuine amount exceeded a z-score of 2.6. That looked like a strong, simple signal and was tested two ways. Twenty-two column-relative features added to the model gave a held-out AUC of 0.848 against 0.847, and the three missed edits still scored 0.14, 0.19 and 0.20. As a rule, a stroke z-score of at least 3 and a sharpness z-score of at least 6 fired on 10.2% of 49 genuine real images and 19.7% of 493 genuine Chrome images, and on a similar share of edited images. The idea was not shipped. It is kept as a warning about conclusions drawn from eight images that also designed the test.

@section 7.7|SPEED
Over 80 test images of up to 3 megapixels, analysis took a median of 581 ms, a 90th percentile of 1,030 ms and a maximum of 1,637 ms. Eight whole 5.9-megapixel desktop captures took 1.7 to 6.8 seconds (median 3.6 seconds) while other jobs were running, so these are upper estimates. Time grows with the number of words; the run was not profiled.

@chapter 8|DISCUSSION, LIMITATIONS AND ETHICS

@section 8.1|WHAT THE RESULTS SHOW
The central result is a contrast. A pipeline of established photograph-forensics cues flagged one genuine screenshot in five and could not distinguish an edited word from its original, while a detector that asks only whether each word matches its neighbours separated simulated edits from genuine images with an AUC of about 0.85. The contrast is consistent with the working hypothesis that an inserted word differs in rendering from its neighbours, which work on document tampering does not itself show [@qu2023doctamper]; no ablation of feature groups was run, so which cues carry the signal is unmeasured. A second lesson concerns evaluation. Keeping low-confidence OCR boxes (the edited word reached the classifier in 90.2% of test edits instead of 67.4%), calibrating thresholds on real genuine screenshots, adding whole full-size screenshots to training and training on two editing engines each changed the apparent quality of the system by a visible margin, and most of the project's time went into data, protocols and error analysis. A third lesson is the pattern in what failed: the first version's cues were built for another medium, the layout rule's first version mistook a missing OCR box for a displaced number, the column idea was tested on the images that suggested it, and the calibration script fitted a threshold on data the model had seen. In each case a measurement on a larger or separate sample, not a sharper argument, exposed the problem.

@section 8.2|LIMITATIONS AND THREATS TO VALIDITY
@numbered
1. **The edits are simulated.** Every figure in Chapter 7 except Section 7.6 comes from the simulator, and results on synthetic data may not carry over to forgeries made by people [@dhouib2026doctamper]. The only human-made edits tried are four development images, two of which were missed, so the project cannot say how often a real forger's edit would be caught.
2. **One person's screenshots, one setup.** The 73 real files, the OCR engine, the fonts and the compression settings are those of one machine, and dataset bias is a known obstacle to transfer [@torralba2011bias]. No public benchmark could be used, so the method has not been compared with a published detector.
3. **A single split and a single fit.** No experiment was repeated with different seeds, intervals exist only for some false-alarm rates, and the test split was consulted repeatedly during development, which makes its figures somewhat optimistic.
4. **Dependence on OCR.** About 10% of edited test images do not reach the classifier with the edited word (18 to 19% after down-scaling), and text in other scripts is not analysed.
5. **Large images and down-scaling.** The image score is the highest word probability, so large images invite more false alarms, and edits followed by shrinking or heavy re-compression are caught far less often, which a forger can do on purpose.
6. **Partial engine transfer and narrow rules.** A model trained on one engine lost 7 to 9 points of AUC on the other, and the layout rule applies to about 15% of images with a numeric column.
7. **No adversarial evaluation, and some fakes are out of reach.** A forger who knew the method could match font and size or shrink the image, and the returned explanations are also feedback for a forger; natively rendered and generated fakes are undetectable by construction (Section 3.4).
@end

@section 8.3|ETHICS, PRIVACY AND PRACTICAL GUIDANCE
Screenshots can reveal other people's names, amounts and messages. The real screenshots used for training stay on the author's machine and are not committed, and the service keeps uploads in memory (Section 6.2). A "suspicious" or "evidence" verdict on a genuine screenshot could harm its sender: at the suspicious tier about 5.5% of the genuine full-size screenshots tested were flagged, with an interval that reaches 13%. The wording of the tiers and the permanently shown limitations panel are meant to keep the tool from being used as a verdict; it is a screener that points a person to a place and a reason. The same explanations could tell a forger which measurement to fix, a risk accepted for a research prototype, with the recommendation that a deployed service rate-limit and withhold per-feature reasons from anonymous users. For a user, a flag is a reason to look at the marked word, not a finding of forgery; a clean result is not a finding of authenticity; a screenshot that arrived after resizing or repeated sharing deserves less trust from the tool; and where money or evidence is at stake the claim should be verified with the issuer. The report does not claim real-world validation or deployment readiness.

@chapter 9|CONCLUSION AND FUTURE WORK

@section 9.1|CONCLUSION
The project replaced a photograph-forensics pipeline that did not work on screenshots with a word-level detector that compares each word with its neighbours, supported by rule checks that read the content of the screenshot. It produced a leak-controlled generated corpus of 20,814 images, evaluation protocols that expose different weaknesses, a service with an interface, 35 backend and 58 frontend tests, and a documented record of what failed. Against the six objectives: the audit was done (20% of genuine screenshots flagged, AUC 0.50 on word edits); the detector reaches an AUC of 0.85 on unseen images and fonts; the corpus and the protocols were built and exposed the down-scaling and cross-engine limits; the layout rule was validated on 6,656 genuine images but the other rules only by unit tests; and the service was delivered, with a container image run only for an earlier model.

@section 9.2|FUTURE WORK
@numbered
1. **Independent real edits.** Collect a validation set in which the person who captures and the person who edits are different, with real editing tools and sharing paths, fixing the rules before any detector output is seen, and report detection and false-alarm rates with intervals. This is the most valuable next step, because it is the only one that replaces simulated edits with real ones.
2. **Public benchmark.** Obtain STFD or a comparable set and compare the detector with a published localiser on identical data.
3. **Resampling-aware and learned features.** The weakest case is down-scaled sharing, where resampling-sensitive features [@popescu2005resampling] or a small learned crop model might recover some of the lost evidence; neither has been tried.
4. **Ablation, repeated seeds and OCR-free candidates.** Measure which feature groups carry the signal, repeat the experiments with several seeds, and add a text detector independent of Tesseract's recognition to reach the words OCR misses.
@end

@appendix A|APPLICATION PROGRAMMING INTERFACE
@appendixtext
`POST /analyze` takes a multipart form with one field named `image` (png, jpg, jpeg or webp, at most 10 MB); `GET /status` returns the service state and the model's metadata. Table {tab:apifields} describes the response of `POST /analyze`.
@endappendixtext

@table apifields|Fields of the analysis response
Field | Meaning
verdict, verdict_label | one of evidence_of_editing, suspicious, no_evidence, inconclusive, and its display text
risk_score | monotone score from 0 to 1 with the two thresholds at 0.40 and 0.70
reasons | up to eight plain-language sentences
regions | marked words: x, y, w, h in pixels, text, score, level (evidence, suspicious or weak), reasons, and source = "rule" for rule-based marks
findings | rule findings: id, severity (high, medium, low), message, evidence
limitations | the fixed list of what the method cannot detect
image, stats, meta | image size and format; OCR and measured word counts, highest word probability and thresholds; SHA-256 of the file, processing time and model description
fake_score, is_fake, verdict_text | aliases kept for older clients
@endtable

@appendix B|SOURCE CODE LISTING
@appendixtext
The listing is read from the repository when the report is built, so it cannot differ from the code described in the text. Line numbers are those of the source file.
@endappendixtext
@listing backend/app.py|inmemory|route_end|Listing B.1 Keeping uploads in memory, and the analysis endpoint (backend/app.py)

@appendix C|AUTOMATED TESTS AND REPRODUCTION
@appendixtext
The backend tests (35) and the frontend tests (58) are run with `pytest tests` in `backend/` and `npm test` in `frontend/`. Table {tab:tests} lists the backend tests by file. The evidence folder `paper-draft/evidence/` holds the log of each run reported here, and `run_evidence.sh` re-runs the evaluations. The commands below illustrate the steps; the reported corpus merged four builds, and the Chrome-patch edits need an extra `--bank` build. The generated corpus and the real screenshots are not in the repository, the first because it is large and derived from private images and the second because they are private.
@endappendixtext
@testtable
@code Commands|Listing C.1 Illustrative commands for building a corpus, training the model and running the evaluations
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt
python tools/forge/render_chrome.py --out ../data/chrome --count 1600 --seed 21 --workers 8
python tools/forge/patchbank.py build --out ../data/patchbank --pages 100 --workers 4
OMP_THREAD_LIMIT=1 python tools/forge/build_dataset.py --out ../data/forge_v1 --chrome-dir ../data/chrome --pillow 1000 --real-windows 5 --real-glob "<your screenshots>"
OMP_THREAD_LIMIT=1 python tools/forge/build_dataset.py --out ../data/forge_bank --chrome-dir ../data/chrome --pillow 1000 --real-windows 5 --bank ../data/patchbank --real-glob "<your screenshots>"
OMP_THREAD_LIMIT=1 python tools/forge/build_dataset.py --out ../data/forge_full --real-full --real-windows 3 --seed 21 --real-glob "<your screenshots>"
python tools/forge/merge_corpora.py --dst ../data/forge_all ../data/forge_v1 ../data/forge_bank ../data/forge_full
python tools/forge/train_text_model.py --data ../data/forge_all
python tools/forge/eval_real_cv.py --data ../data/forge_all --real-glob "<your screenshots>"
python tools/forge/compare_legacy.py --data ../data/forge_all --n 500
python tools/forge/eval_layout_rule.py --data ../data/forge_all
@endcode

@appendix D|TOOLS AND ASSISTANCE
@appendixtext
The implementation, the experiments and the first drafts of this report were produced with the help of an AI coding assistant (Claude Code, Anthropic). The assistant wrote and ran code, ran the evaluations and drafted text; the project team directed the work, supplied the real screenshots and the eight-image sample, and is responsible for the claims made. All numbers in this report are taken from logs and scripts stored in the evidence folder and were re-derived from them during an audit of the longer version of this report. Third-party tools used: Tesseract OCR 5.5.3, scikit-learn 1.9.0, Pillow 12.3.0, NumPy 2.5.1, SciPy 1.18.0, Flask 3.0.3, React 18 with Vite, and Google Chrome 155 for rendering the generated screens. Papers cited were retrieved and checked against Crossref, OpenAlex, arXiv or the publisher, and the read depth of each (full text, abstract or bibliographic record only) was recorded; claims about papers read at abstract level are limited to what the abstract states.
@endappendixtext

@appendix E|EVIDENCE FILES
@table evidence|Evidence files (in paper-draft/evidence/) and the results they support
File | Supports
fp_results.json, exp_fp.py, tamper_results.json, exp_tamper.py, v1_native_check.txt | first-version audit (Section 7.1)
compare_legacy.txt | first and final versions on 500 test images (Section 7.1)
train_final_v6.log | held-out test results of the shipped model (Section 7.2)
cross_engine.txt | cross-engine experiment (Section 7.3)
leave_files_out_v6.log, cv_summary_v6.json, wilson.txt, leave_files_out_v5_intermediate.log | leave-files-out results and intervals (Section 7.4)
layout_rule_eval.txt, layout_rule_eval_first_version.txt | layout-grid rule (Section 7.5)
real8_results.txt, column_z_8images.txt, negative_results.txt, train_v7_column_peers.log | eight-image sample and rejected column idea (Section 7.6)
latency.txt, latency_large.txt | speed (Section 7.7)
ocr_recall_check.txt, second_stage_check.txt, corpus_build_v1.log, facts.txt | development steps, corpus build and code facts (Chapters 4 to 6)
pytest.txt, vitest.txt, docker_test.log, docker_build_final.log | automated tests and container checks (Chapter 6)
@endtable
