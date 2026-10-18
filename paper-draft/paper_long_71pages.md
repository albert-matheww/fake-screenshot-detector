@abstract
Screenshots of chats, bank statements and payment histories are routinely accepted as informal evidence, yet any image editor can alter them. This project builds and evaluates a screenshot-forensics service that reports signs of editing in an uploaded image and states plainly what it cannot see. A first version, which combined photograph-forensics cues (error level analysis, JPEG ghosts, noise and clone detection) with a random forest, was audited on genuine screenshots: it flagged 12 of 60 untouched images (20%) and could not separate realistic word edits from their originals (AUC 0.50 over 42 image sets). The second version replaces those cues with a word-level detector. Every word found by optical character recognition is described by 95 rendering and layout measurements, also expressed relative to the words around it, and a boosted-tree classifier estimates the probability that the word was edited. Rule checks add document logic: weekday against date, total against subtotal, checksums, and the regularity of number columns. Because no suitable public data could be obtained in time, a labelled corpus of 20,814 images was generated from real, Chrome-rendered and Pillow-rendered screenshots, with two independent edit engines, identical re-sharing degradation for both classes, splits by base image and held-out edit fonts. On unseen images and fonts the detector reaches an AUC of 0.85 (0.84 on a 500-image subset of the test set, on which the first version scored 0.46). On 73 genuine full-size screenshots never seen by the model that scored them, it flags 5.5% at its suspicious tier and none at its evidence tier, while catching 45% and 24% of simulated edits. Performance falls after down-scaling (AUC 0.72 to 0.73) and transfers only partly across editing engines. Edits made by a person with their own tools have been tried only on an eight-image development sample, in which two of four edits were flagged and none of four genuine images. Screenshots rendered natively with false content cannot be detected by this method.
@endabstract

@chapter 1|INTRODUCTION

@section 1.1|OVERVIEW
A screenshot is the cheapest form of evidence that exists. It is offered to prove that a payment was sent, that a message was received, that an account held a given balance, or that a post said what someone claims it said. It is also among the cheapest things to fake: opening the image in any editor, covering a number and typing another takes a few minutes and no special skill. Work on forged text images describes finance, certificate checking and news screenshots as typical targets [@yu2025fsts], and a 2026 benchmark paper treats fabricated screenshots, documents and news pages as a prominent vehicle for misinformation and fraud [@zhang2026textfake].

This project, called Screenshot Forensics, is a working service that looks at one uploaded screenshot and answers a narrow question: does any word in it show signs of having been changed after the screenshot was taken? The answer is a four-tier verdict (evidence of editing, suspicious, no evidence of editing, not enough readable text), the words that triggered it marked on the image, and a plain-language reason for each. The service never states that an image is authentic. A list of what it cannot detect is returned with every answer and displayed under every result in the interface.

The report describes how the service was built, how it was measured and, because the project went through a redesign, why the first design was abandoned. The first version reused the standard toolbox of photograph forensics. It was audited honestly against genuine screenshots and failed. Chapters 4 to 7 describe the replacement and the evidence for and against it.

@section 1.2|WHY SCREENSHOTS ARE DIFFERENT FROM PHOTOGRAPHS
Passive image forensics grew up around photographs [@farid2009survey]: a forger splices part of one picture into another, moves a region within one picture, or removes an object by inpainting [@verdoliva2020], and an analyst looks for traces left by the camera, the JPEG coder or the editing step [@piva2013overview]. Most of those traces are weak or absent in a screenshot.

There is no camera sensor, so methods built on sensor pattern noise [@lukas2006prnu] have nothing to measure. Large regions are flat colour, and the text is rendered by the operating system with crisp edges rather than captured through a lens. Error level analysis, the most widely discussed screenshot-agnostic trick, resaves the image at a known JPEG quality and compares the result with the original [@krawetz2007]; it is defined for images stored with lossy compression, whereas the genuine device screenshots collected for this project were almost all lossless: 59 of the 60 used in the first audit were PNG files. A screenshot is also frequently re-shared through messaging applications, which re-compress and sometimes down-scale it, so the file that reaches an examiner may differ from the one the device produced.

What a text edit does leave behind is local: the inserted glyphs were drawn by a different program, at a slightly different size, with a different anti-aliasing recipe, on a patch of background that rarely matches its surroundings exactly. Work on document tampering notes that document images mostly share one background colour and that text within a cluster usually shares one font and size, which is why visual clues of tampering are scarce [@qu2023doctamper]. The inference drawn here, that a replaced word therefore tends to differ in rendering (size, anti-aliasing, local background), is this project's working hypothesis. It is the starting point of the method developed here.

@section 1.3|PROBLEM STATEMENT
Given a single screenshot with no reference original, decide whether text in it was edited with a raster editor, locate the edited words, and explain the decision, while keeping false alarms on genuine screenshots low and being explicit about the cases the method cannot handle.

Three properties of the problem shape every design decision in this report. First, there is no reference image, so the only available evidence is internal consistency. Second, the edited area is tiny: a changed amount is a few words in an image of several hundred, and a detector that scores every word will meet hundreds of chances to raise a false alarm. Third, there is no freely available, labelled data of real edited screenshots that could be obtained within the project's timeline, so training and evaluation data had to be produced, and the risk that a model learns the generator instead of the edit had to be controlled explicitly.

@section 1.4|OBJECTIVES
The project set six objectives, each tied to something that can be checked.

@numbered
1. Audit the first version on genuine screenshots and on realistic edits, and record what the audit shows (Chapter 7, Section 7.1).
2. Design a detector that works at the level of individual words and explains every flag (Chapters 3 and 4).
3. Build a labelled corpus with exact edit masks, controlled against leakage between training and test data (Chapter 5).
4. Evaluate with protocols that expose weaknesses, not only a single held-out split: unseen fonts, unseen base images, a second editing engine, and genuine screenshots held out file by file (Chapter 7).
5. Add rule checks that read the content of the screenshot, each covered by a unit test that requires it to stay silent on an ordinary page, and the layout-grid rule additionally validated for false alarms on the whole corpus (Chapters 4 and 7).
6. Deliver a usable service with an application programming interface, a web interface, automated tests and a container image, and document its limits (Chapters 6 and 8).
@end

@section 1.5|SCOPE AND CONTRIBUTIONS
The scope is raster edits of text in screenshots: re-typed words and numbers, spliced word crops, and background patches painted under them. Out of scope are screenshots rendered natively with false content (for example, text changed in a browser's developer tools before the screenshot was taken, or output of a fake-receipt website), images generated by an AI model, and print-and-scan recapture. The first two leave no editing inconsistency for any pixel-level method to find; Chapter 8 says what to do about them instead.

The contributions, in the order in which the evidence for them appears, are:

@bullets
- a documented audit of a photograph-forensics pipeline on genuine screenshots, showing that its cues carried no usable signal (Section 7.1);
- a word-level, rendering-consistency detector with explainable output, and its measured behaviour under the evaluation protocols of Section 5.7 (Chapters 4 and 7);
- ScreenForge, a leak-controlled generated corpus and generator that uses two independent text-rendering engines for edits (Chapter 5);
- a layout-grid rule whose false-alarm rate was measured on 6,656 genuine images, including the record of a first version that failed that measurement, and a set of content rules validated by unit tests only (Sections 4.6, 7.7 and 7.8);
- a record of negative results: a column-comparison idea that looked convincing on eight images and was rejected on the corpus (Section 7.10).
@end

These contributions are of the system, application and cautionary-evidence kind. The report does not claim a new learning algorithm, and it does not claim performance on edits made by independent people with real tools: the project has only a small, development-stage sample of those.

@chapter 2|BACKGROUND AND LITERATURE SURVEY

@section 2.1|INTRODUCTION
This chapter places the project among existing work. It is organised around the question the project had to answer in turn: which established cues survive in a screenshot (Section 2.2), what learned localisers offer (2.3), what has been done for text and document tampering and what data exists (2.4), what is known about screenshots specifically (2.5), and which evaluation practices matter for a small-data project (2.6). Section 2.7 states the gap.

@section 2.2|CLASSICAL PASSIVE IMAGE FORENSICS
Surveys describe passive forensics as the search for traces that an image acquires at three stages of its life: capture, coding and editing [@piva2013overview; @verdoliva2020]. Three families of cue are relevant here.

Compression history is the best-known family. The "JPEG ghost" technique of Farid is aimed at spotting a region that was first saved at a lower JPEG quality than the remainder of the image [@farid2009ghosts]; Bianchi and Piva map the likelihood that each 8 by 8 block was compressed twice, aligned or not, to localise forged regions [@bianchi2012block]; and error level analysis, popularised in a conference white paper, resaves an image at a known quality and inspects where the difference is large, a method its author ties to the behaviour of lossy compression [@krawetz2007]. All of these presuppose that the image went through JPEG coding at least once. A second family looks for resampling (Popescu and Farid describe how resizing or rotating leaves specific correlations among pixels that can be detected in any part of an image [@popescu2005resampling]) and for noise inconsistencies [@mahdian2009noise] or a camera's sensor pattern noise [@lukas2006prnu]. Resampling matters here because shared screenshots are often down-scaled; noise and sensor cues matter much less because a screenshot has no sensor. A third family is copy-move detection, compared under controlled conditions by Christlein and colleagues [@christlein2012eval]; duplicating a digit or a row is a plausible screenshot edit, but screenshots also contain many legitimate repeated elements such as icons and list rows, a source of false matches.

@section 2.3|LEARNED LOCALISATION AND BENCHMARKS FOR NATURAL IMAGES
Learned localisers replaced hand-built cues in much of the recent literature. ManTra-Net trains a fully convolutional network on a large set of manipulation types and treats localisation as local anomaly detection with a z-score feature [@wu2019mantranet]. CAT-Net feeds RGB and DCT streams to learn compression artefacts jointly, with the DCT stream pretrained on double-JPEG detection [@kwon2021catnet]. TruFor combines the image with a learned noise-sensitive fingerprint trained on real data only, flags deviations from the expected pattern, and additionally outputs a reliability map intended to reduce false alarms [@guillaro2023trufor]. A unified benchmark and code base now spans deepfake, manipulation, AI-generated and document images, which exposes how fragmented evaluation had been [@du2025forensichub].

The first version of this project was trained partly on standard natural-image data, the CASIA tampering database [@dong2013casia] and IMD2020 [@novozamsky2020imd]; Section 7.1 shows why that was inappropriate for screenshots.

@section 2.4|TAMPERED TEXT AND DOCUMENT FORGERY
@sub 2.4.1|DATASETS AND DETECTORS
Text in documents differs from objects in photographs: backgrounds are uniform and text within a cluster usually shares one font and size, so visual clues are scarce [@qu2023doctamper]. DocTamper contributes 170,000 document images covering splicing, copy-move and generation, together with a detector that adds frequency-domain information [@qu2023doctamper]. A receipt dataset for document forgery detection [@tornes2023receipt] was used in the first version of this project. The Screenshot Text Forgery Dataset (STFD) is described by its authors as the first public dataset for localising text forgery in smartphone screenshots [@yu2023stfd]; a later paper reports that it contains 4,094 tampered instances [@yu2025fsts]. Its dataset card states that the archive can only be extracted with a password obtained by e-mailing the authors from an academic or institutional address [@hf_stfd]. That request was made for this project but no password had been received when the experiments were completed, so no result in this report uses STFD.

Human-made tampering is increasingly seen as necessary. FSTS collected 16,750 real tampering instances from 67 people, modelled their operations and post-processing parameters (including blur and JPEG recompression), and used them to synthesise training data [@yu2025fsts]; the corresponding release is a roughly 46 GB archive under a non-commercial licence [@hf_fsts]. RWTamper offers completely manual tampering at three degradation levels [@xu2026reality], an explainable detector describes tampered text in natural language [@qu2024textsleuth], and work on print-and-scan recapture studies a setting where traces are concealed by halftoning and blur [@chen2025unmask].

@sub 2.4.2|WHAT RECENT DOCUMENT-FORENSICS PAPERS WARN ABOUT
Three findings from this literature shaped the evaluation design of this project. First, an improvement measured on a synthetic benchmark that resembles the training data does not carry over reliably to forgeries made by people or to data from another domain [@dhouib2026doctamper]. This is the central caveat for any result in this report that rests on simulated edits. Second, a training set restricted to a narrow range of JPEG quantisation tables does not match the varied compression of operational document pipelines, and training with realistic tables lowered false positives on authentic documents, but only for architectures that take the quantisation table as an input [@ronfleux2026docqt]; the corpus here therefore passes genuine and edited images through the same random sharing step. Third, a zero-shot benchmark of 14 methods on eight document datasets found moderate pixel-level AUC but near-zero F1 at the conventional 0.5 threshold, attributed to the tiny share (about 0.3 to 4%) of tampered pixels, and reported that adapting a threshold on ten in-domain images recovered 39 to 55% of the gap in representative cases [@zhao2026docforge]. This supports adapting alert thresholds to the target domain. The present system does so with a different criterion from that benchmark: it fixes its two thresholds at false-alarm rates of 5% and 1% on genuine in-domain validation images.

@section 2.5|SCREENSHOTS AND AI-GENERATED TEXT-RICH IMAGES
The closest published work found is a pipeline designed for screenshots that combines five groups of cues (error level, noise, JPEG traces, text-edge regularity and metadata) in one gradient-boosted classifier deciding between real and fake [@venkatesh2026screenshot]. On its own set of 1,200 screenshots with four manipulation types the authors report an AUC of 0.82 against 0.47 for an ELA-threshold baseline, with weaker recall on small text edits and on copy-move. Because that dataset, its edits and its compression conditions differ from those used here, its numbers are not compared with this project's. It does show that the combination of cues that this project's first version used has been proposed for screenshots; the difference is that the first version was audited on untouched PNG screenshots, as Section 7.1 reports.

A separate threat is the screenshot that never existed: an image generated by an AI model. A 2026 benchmark of 20,000 text-rich images found that none of the evaluated detectors exceeded 80% accuracy and named three failure modes, one of which (the Text Density Curse) concerns dense glyphs overwhelming low-level detectors [@zhang2026textfake]. Detecting generated screenshots is outside the scope of the present work.

@section 2.6|EVALUATION PRACTICE
Dataset bias is a known obstacle to generalisation: methods can learn the quirks of a collection and fail to transfer [@torralba2011bias]. A taxonomy of data leakage lists duplicated items, non-independence between training and test units (for example, several samples derived from one source) and choices made with information from the test set among its types [@kapoor2023leakage]. Each has a counterpart here: several windows and edited copies are cut from every screenshot file, so splits must be made by file; test edits must not use fonts seen in training; and thresholds must be fixed on data the model did not fit. The project met the last problem in its own code (Chapter 7).

Ranking quality is summarised here with the area under the receiver operating characteristic curve [@fawcett2006roc], alongside the detection and false-alarm rates at the two operating thresholds actually used by the service. Selected binomial proportions are accompanied by Wilson intervals [@wilson1927]; small samples such as the eight-image sample are not.

@section 2.7|GAP AND POSITIONING
Table {tab:related} summarises the datasets and the closest systems. Within the sources reviewed, three observations define the niche of this project. Screenshot-specific public data exists but is access-controlled (STFD), and the only other directly relevant release found is very large (FSTS, about 46 GB) and was not used. The one screenshot-specific forensics pipeline found combines compression-related cues (error level, JPEG traces) with noise, text-edge and metadata features and reports weaker recall on small text edits [@venkatesh2026screenshot]. Document-forensics papers report that gains on synthetic benchmarks transfer poorly to human-made forgeries [@dhouib2026doctamper] and that adapting the decision threshold to the target domain is a key missing step for deployment [@zhao2026docforge]. The project therefore pursues a small, explainable, CPU-only detector built on rendering consistency within a single image, evaluated with leak-controlled protocols and reported with its failures. It does not compete with the learned localisers on their benchmarks; no such comparison was run.

@table related|Datasets and systems most relevant to screenshot text forensics (facts as stated in the cited papers or dataset cards)
Name | Content | Size reported | Access in this project
CASIA tampering database [@dong2013casia] | natural colour images with realistic tampering | not retrieved | used by the first version only
IMD2020 [@novozamsky2020imd] | camera-diverse real and manipulated images, plus uncontrolled real-life manipulations | 35,000 real and 35,000 manipulated (70,000 in all), plus 2,000 real-life | used by the first version only
Receipt forgery dataset [@tornes2023receipt] | receipts for document forgery detection | not retrieved | used by the first version only
DocTamper [@qu2023doctamper] | tampered document images | 170,000 images | not used
STFD [@yu2023stfd; @hf_stfd] | smartphone screenshots with text forgeries and masks | 4,094 tampered instances [@yu2025fsts] | password by e-mail; not received
FSTS [@yu2025fsts; @hf_fsts] | real tampering parameters and synthetic tampered text images | 16,750 real instances; about 46 GB archive | not used
RWTamper [@xu2026reality] | manually tampered text images, three degradation subsets | 9,326 images per subset | not used
Screenshot forensics pipeline [@venkatesh2026screenshot] | ELA, noise, JPEG and metadata fusion with gradient boosting | 1,200 screenshots | numbers not compared
@endtable
@chapter 3|REQUIREMENTS AND SYSTEM DESIGN

@section 3.1|INTRODUCTION
This chapter states what the service has to do, the principles that were adopted after the first version failed, the architecture and the rule by which evidence becomes a verdict. The detection method itself is described in Chapter 4.

@section 3.2|REQUIREMENTS
@sub 3.2.1|FUNCTIONAL REQUIREMENTS
@numbered
1. Accept one image per request in PNG, JPEG or WebP format, up to 10 MB.
2. Read the text in the image and judge each word for signs of editing.
3. Return a verdict in one of four tiers, a risk score, the marked words with their coordinates in the uploaded image, and reasons for the marks (when no single measurement stands out, the response says so in general terms).
4. Run rule checks on the content and on the file metadata, and return each finding with a severity.
5. Return, with every response, a fixed list of limitations, and never describe an image as authentic.
6. Provide a web interface that shows the image with the marked words, supports a demonstration mode without the back end, and reports failures (network, size, format, server) in distinct messages.
@end

@sub 3.2.2|NON-FUNCTIONAL REQUIREMENTS
@bullets
- Explainability: every flag points to a place in the image and a reason a person can check.
- Privacy: screenshots may contain payment and chat details, so the image must stay in memory and must not be stored (Section 6.5).
- Few false alarms on genuine screenshots, prioritised over detection rate: a tool that cries wolf on untouched images is useless as evidence screening.
- Runs on an ordinary CPU, with no graphics processor and no network access at analysis time.
- Reproducibility: every number in this report was produced by a script kept in the repository (Appendix 4); the numbers that depend on the authors' private screenshots can be regenerated only on that machine.
@end

@section 3.3|DESIGN PRINCIPLES ADOPTED AFTER THE AUDIT
Four principles were fixed after the audit of the first version (Section 7.1) and they explain several choices that might otherwise look arbitrary.

@numbered
1. **Absence of evidence is not evidence of absence.** The lowest tier is called "no evidence of editing found", never "authentic", because an image rendered natively with false content contains nothing for the method to find (Section 3.5).
2. **A cue ships only if it is silent on ordinary images.** Every rule has a unit test showing that it stays silent on an ordinary page, and the layout rule was also measured on 6,656 genuine images; one rule that fired on an ordinary bank screen was removed and another was tightened after a corpus measurement (Section 7.7).
3. **Thresholds belong to the domain.** Alert thresholds are set on validation screenshots that are genuine and real, the domain where false alarms hurt, not on pooled or synthetic data (Section 4.5).
4. **Record the failures.** Negative results are kept in the report because the evidence for what works is only as good as the record of what was tried.
@end

@section 3.4|ARCHITECTURE
@fig fig_architecture|15.5|Architecture of the Screenshot Forensics service. Rule checks and the classifier both feed the verdict independently.

The browser interface posts the image to a Flask application programming interface. The application reads the image, applies the orientation stored in its metadata so that coordinates match what a browser displays, runs OCR, and hands the word boxes to two independent components. The word-level component measures each word and the classifier scores it. The rule component reads the text, the file metadata and the layout. A verdict module combines the classifier output and the rule findings into a tier, a risk score, marked regions and reasons, and attaches the limitations. The classifier and the rules do not depend on one another, which is why a screenshot can be escalated by a rule even when the classifier sees nothing (Section 7.9 gives an example).

@section 3.5|WHAT THE METHOD CAN AND CANNOT SEE
Table {tab:threat} states the threat model. The method looks for an inconsistency between an inserted word and its surroundings, so it applies only where an edit was made on top of a rendered screenshot.

@table threat|Threat model: which kinds of fake the method can address
Kind of fake | Detectable by this method? | Why
A word or number re-typed over a screenshot in a raster editor | Partly (measured in Chapter 7) | the inserted glyphs differ from their neighbours in rendering, size, colour or placement
A word crop spliced in from another image | Partly | the crop carries its own rendering and background
A number pasted off the row grid of an evenly spaced list | Partly: when the list is regular and the displacement is at least about half a text height (and at least 5 pixels) | rule on column spacing (Section 4.6)
Text changed in browser developer tools, then screenshotted | No | the screenshot is genuine renderer output; nothing is inconsistent
Output of a fake-receipt website that renders natively | No | same reason
A screenshot generated by an AI image model | No (out of scope) | no editing step exists
Edit followed by heavy down-scaling or repeated re-compression | Weakly | resampling smooths the anti-aliasing evidence (Section 7.3)
@endtable

For the cases the method cannot see, the only dependable remedy is to verify with the issuer, for example by asking the bank or payment application to confirm a transaction identifier. The limitations text returned by the service gives the general version of this advice, to confirm important claims with the issuer; naming a transaction identifier is an example added in this report.

@section 3.6|VERDICT POLICY
The verdict module (`backend/analysis.py`) turns the classifier's word probabilities and the rule findings into one of four tiers. Let p be the highest word probability in the image, T_s the suspicious threshold and T_e the evidence threshold (Section 4.5), and let the highest rule severity be high, medium, low or none.

@table verdict|Conditions for each verdict tier
Tier | Condition | Risk score
Evidence of editing found | p >= T_e, or a high-severity finding | at least 0.70; at least 0.85 if a high-severity finding fired
Suspicious - review recommended | p >= T_s, or a medium-severity finding (and not the evidence condition) | 0.40 to 0.70; at least 0.55 if a medium finding fired
No evidence of editing found | neither condition, and at least six words were measured | below 0.40
Not enough readable text to analyse | neither condition, and fewer than six measured words, or no model loaded | not shown
@endtable

The risk score is a monotone rescaling of p so that the two thresholds always fall at 0.40 and 0.70 on the gauge in the interface: below T_s the score rises linearly from 0 to 0.40, between T_s and T_e from 0.40 to 0.70, and above T_e from 0.70 to 1. It is a display aid, not a calibrated probability. The service marks at most ten words, those with p of at least 0.75 T_s; a rule finding that points to one number is also marked, labelled as a rule result with no probability attached.

@chapter 4|DETECTION METHOD

@section 4.1|INTRODUCTION
The method rests on one idea: a word that was inserted after the screenshot was taken is an outlier among its own neighbours. The absolute appearance of text varies enormously between applications, fonts and devices, so the detector never asks whether a word looks "normal". It asks whether this word was rendered like the others in the same image. {fig:fig_word_idea} shows the stages.

@fig fig_word_idea|15.5|The word-level analysis: OCR boxes, per-word measurements, comparison with neighbours, probability of editing.

@section 4.2|OPTICAL CHARACTER RECOGNITION
Words and their boxes come from Tesseract [@smith2007tesseract], version 5.5.3, called through pytesseract with its default page-segmentation mode. Every box with a confidence of at least zero is kept: during development, discarding boxes below a confidence of 40 removed the edited word from analysis in about a third of the edited test images (Section 7.4), because a word set in an unusual font is exactly the word that Tesseract reads with low confidence. The confidence is therefore a feature, not a filter. Words of a single character are skipped, since icons, bullets and OCR noise dominate that class and the measurements are unreliable at that size.

A word is measured only if its box is between 8 and 220 pixels high and at least 6 pixels wide, its crop has a contrast of at least 10 grey levels and it contains at least six "ink" pixels. An image with fewer than three measurable words yields no features at all.

@section 4.3|PER-WORD MEASUREMENTS
For each measurable word the code (`backend/textforensics.py`) takes a crop with a margin of 0.35 of the word height around the OCR box. The median grey level of the margin ring is the local background. The contrast c is the 98th percentile of the absolute difference between the word's pixels and that background. Pixels with a difference above 0.5 c are called ink and pixels between 0.12 c and 0.88 c are called anti-aliased. Forty raw measurements are then derived, in seven groups.

@bullets
- **Edge and contrast profile (9).** The contrast c itself; the ratio of anti-aliased to ink pixels; the 95th percentile of gradient magnitude relative to c; the fraction of pixels with a gradient above 0.6 c; the ratio of horizontal to vertical gradient energy; the three quartiles of the ink-level distribution; the standard deviation of ink levels.
- **Colour (3).** Saturation of ink pixels and of edge pixels relative to the background, and the mean red-blue difference at anti-aliased pixels relative to c, which is high for sub-pixel (LCD) rendering.
- **Strokes (3).** Stroke width estimated as twice the area over the perimeter of the ink mask, and twice the median ridge of its distance transform, each divided by the word height; the ink fraction.
- **Background (4).** Standard deviation of the Laplacian of the background inside the box and in the margin, their ratio, and the shift of the mean background level inside the box.
- **Seam (3).** A background patch painted under an edit leaves a step in colour along its border. For each of the four sides of the box the code compares consecutive one-pixel strips moving outward up to nine pixels and takes the median colour step along the side. It records the largest step, its distance from the box and the number of sides with a step above 2.5.
- **JPEG grid (2).** The strength of an 8 by 8 block-boundary pattern in absolute image coordinates, and whether its phase differs from the phase of the whole image.
- **Histograms (16).** An eight-bin histogram of ink levels and an eight-bin gradient-orientation histogram weighted by gradient magnitude, each normalised to sum to one.
@end

Six geometry values complete the absolute description: height, width, width per character relative to height, OCR confidence, number of characters and the share of digits.

@section 4.4|COMPARISON WITH NEIGHBOURS
@sub 4.4.1|ROBUST Z-SCORES
Nineteen of the measurements (those listed as relative in the code) are re-expressed as robust z-scores: the value minus the median of the comparison set, divided by 1.4826 times the median absolute deviation, with the scale floored at 5% of the median's magnitude, at 0.001 and clipped to the range from minus 12 to 12. Each is computed twice, against all other words in the image (the word itself excluded) and against the other words on the same line when there are at least two. That gives 38 relative features.

@sub 4.4.2|LINES
Tesseract's line identifiers proved unreliable on user-interface layouts, so the code groups words into lines itself. A word joins one of the five most recently opened lines when its vertical centre lies within 0.45 of the smaller of the line's median height and its own height, and the height ratio is between 0.6 and 1.7. Lines give seven further features: the word height relative to the line, the offsets of its bottom and top edges from the line's median, the distance between its ink colour and the line's, the distance between its background colour and the line's, the number of line mates, and the number of measured words in the image. Chi-square distances between the word's two histograms and the median histograms of the image and of its line add four more. The 40 raw measurements, 6 geometry values, 38 z-scores and these 11 line and histogram features make up the 95 features used by the classifier.

@section 4.5|CLASSIFIER AND THRESHOLDS
@sub 4.5.1|MODEL
Word probabilities come from scikit-learn's histogram-based gradient-boosted trees [@friedman2001; @pedregosa2011] with these settings: up to 1,500 iterations, learning rate 0.05, at most 63 leaves per tree, at least 40 samples per leaf, L2 regularisation 2.0, and early stopping on a 10% internal validation split with a patience of 25 iterations. Training used 808,445 labelled words, of which 10,582 are edited, and stopped after 848 iterations. A word is labelled edited when at least 30% of its box overlaps an edit rectangle, genuine when it overlaps by at most 2%, and words in between are excluded as ambiguous. Words from real screenshots receive a sample weight of 3, because the real domain is the target and the scarcest.

@sub 4.5.2|IMAGE SCORE AND THRESHOLDS
The image score is the highest word probability. Two thresholds convert it into tiers. They are chosen on the validation split, using only images that are genuine and real: the suspicious threshold is the score exceeded by 5% of those images and the evidence threshold the score exceeded by 1%. With 246 such validation images the values were 0.847 and 0.966. Calibrating on real genuine images, not on the pooled validation data, was a deliberate response to the observation that real screenshots produced more false alarms than the generated ones (Section 7.4). It follows the principle, reported for document forgery, that a threshold fixed in advance is a poor fit for a domain where the tampered area is tiny [@zhao2026docforge].

@sub 4.5.3|WHY THE MAXIMUM, AND WHAT IT COSTS
An image with several hundred words gives a detector several hundred opportunities to be wrong, so the maximum over words inflates false alarms in large images. This was observed directly: an intermediate model flagged 11.0% of the genuine full-size screenshots at the suspicious tier although it flagged only 2.1% of real test images cut into windows, until full-size genuine images were added to the training data (Section 7.6). A second-stage model on top of the word probabilities was tried on the development corpus and did not improve the ranking, so the simple maximum was kept.

@section 4.6|RULE CHECKS
The rule module (`backend/semantic.py`) reads the file and the text. Its guiding principle is that a rule must be silent on ordinary pages. Table {tab:rules} lists the rules.

@table rules|Rule checks implemented
Rule | Fires when | Severity
Editing software tag | the EXIF Software field names an image editor | high
Camera tags; GPS data | EXIF make or model; location fields are present | low
Generator watermark | OCR text contains the marker of a known fake-document generator | high
Placeholder name or number | "John Doe", or a long run of one digit, or 123456789 | medium
Total below subtotal | a Subtotal and a Total are both read, the total is smaller and no discount line is present | high
Items do not add up | at least three item prices, a Subtotal, and no discount or quantity wording, and the sum differs from the Subtotal by more than one cent | medium
Weekday does not match date | a weekday, a day, a month and a year are read and the weekday is wrong for that date | high
Impossible or future date | the date does not exist, or lies more than a day ahead | high; medium
IBAN or card number invalid | the mod-97 check of an IBAN fails, or a full card number fails the Luhn check | medium
Impossible clock time | hours above 24 or minutes above 59 | low
Duplicate status-bar clock | in a phone-shaped image, the status-bar time is repeated in the body | low
Number column off its grid | one number in an evenly spaced column sits off the grid (Section 4.6.1) | medium
@endtable

The first version of the arithmetic rule flagged any image showing both a "Balance" and a "Total", which describes an ordinary bank-application screen; it was removed and replaced by the narrower rules above, and a unit test now asserts that a page with a balance, transactions and a "Total Spent" line raises no finding.

@sub 4.6.1|THE LAYOUT-GRID RULE
Lists in payment, banking and shopping applications place one number per row in a column whose row spacing is constant to the pixel. A value pasted by hand rarely lands exactly on that grid. The rule works on OCR boxes alone and proceeds in four steps.

@numbered
1. Keep numeric words (at least half of their characters are digits, two or more characters, height between 10 and 120 pixels). Cluster them on their right edge, using a tolerance of 0.4 times the word height, then drop words more than a quarter shorter or a third taller than the cluster median (this removes month totals and headers). Keep at most one number per row and require at least six rows to form a column; because the final test needs three further rows beyond the candidate and its neighbours, a column of eight rows is needed for every row to be testable.
2. Use the bottom edge of each box as the baseline; digits have no descenders, so it is the most stable edge. For each interior row compute its deviation from the midpoint of its two neighbours.
3. Take the row with the largest deviation as the candidate. Require that deviation to be at least the larger of 5 pixels and 0.2 of the text height; the median deviation of the other rows (excluding the candidate and its two neighbours) to be at most the larger of 1.5 pixels and 0.05 of the height, and their maximum at most the larger of 3 pixels and 0.1 of the height; and the candidate to dominate its neighbours by a factor of at least 1.5, because an edited row shifts its two neighbours by half as much.
4. Require both gaps next to the candidate to lie between 0.6 and 1.4 times the median row pitch. This fourth condition was added after the first version, which did not have it, produced a 2.03% false-alarm rate: an OCR box missed in one row doubles a single gap, and without the condition that looked like an off-grid number (Section 7.7).
@end

The finding names the number, its offset and the grid pitch, for example: the numbers in this column are evenly spaced (about 199 pixels apart), but "79" sits 14 pixels off that grid. The rule is silent when the column is not regular, which is the common case and by design.

@section 4.7|EXPLANATIONS
Reasons are generated, not learned. For a marked word, the code lists the relative features with an absolute z-score of at least 3, translated into plain language ("stroke thickness differs from neighbouring words on the same line"), together with four geometric reasons: a rectangular patch outline on at least three sides, a height that differs from the line by more than 18%, a baseline offset above 9% of the height and a colour distance to the line above 0.12. At most three reasons are shown, with duplicates by topic removed. These explanations describe which measurements deviate; they are not a causal account of the edit.
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

@chapter 7|RESULTS AND ANALYSIS

@section 7.1|AUDIT OF THE FIRST VERSION
The first version (preserved in `backend/legacy/`) combined error level analysis, a multi-quality JPEG-ghost scan, quantisation-table checks, block-wise noise statistics, copy-move detection, edge, font, status-bar-clock and arithmetic cues, EXIF and OCR rules, and a random forest trained on three photograph and receipt datasets. It was never run on screenshots that were known to be untouched until the audit reported here.

@sub 7.1.1|GENUINE SCREENSHOTS
Sixty genuine screenshots from the author's machine (59 PNG, 1 JPEG; none ever edited) were analysed. The first version flagged 12 of them, 20.0%, as fake. {tab:v1cues} lists the cue scores. Three cues (ELA, block noise and edge sharpness) were non-zero on 59 of the 60 images and sat near the top of their range, and a fourth, the JPEG ghost, was non-zero on 46, so they could not be distinguishing anything: the ELA and edge cues averaged 0.85. The composite score of genuine screenshots averaged 0.385 with a maximum of 0.626, close to the 0.5 decision threshold.

@table v1cues|First-version cue scores on 60 genuine screenshots
Cue | Mean score | Maximum | Images with a non-zero score
Error level analysis | 0.845 | 0.939 | 59
Edge sharpness | 0.845 | 0.950 | 59
Block noise | 0.755 | 1.000 | 59
JPEG ghost | 0.496 | 1.000 | 46
Copy-move | 0.086 | 1.000 | 52
Font consistency | 0.019 | 1.000 | 2
EXIF editing-software tag | 0.000 | 0.000 | 0
OCR watermark / placeholder text | 0.000 | 0.000 | 0
@endtable

The quantisation, status-bar-clock and arithmetic cues were zero on all 60 images. The lossless format of these screenshots explains part of the saturation: error level analysis and quantisation checks presuppose lossy compression [@krawetz2007], and 59 of the 60 files were PNG. That is an explanation consistent with the data, not a tested cause.

@sub 7.1.2|REALISTIC EDITS
In this experiment a second draw of sixty PNG screenshots was made, 28 of whose 42 qualifying files also belong to the sixty audited in Section 7.1.1. Forty-two of the sixty contained a word that qualified for editing (OCR confidence at least 85, at least four characters, height 12 to 60 pixels). In each, one word, preferring words with digits, was painted over with the surrounding background colour and re-typed in Helvetica with each digit shifted, a plausible careless edit. Every image set contained the untouched original, the edited image and each of the two saved as JPEG at quality 85.

@table v1edit|First-version scores on genuine and edited screenshots (42 image sets)
Variant | Images flagged | Mean score
Original, PNG | 6 of 42 | 0.367
Edited, PNG | 6 of 42 | 0.366
Original, JPEG q85 | 5 of 42 | 0.359
Edited, JPEG q85 | 5 of 42 | 0.359
@endtable

The AUC for separating edited from original images was 0.496 for PNG and 0.501 for JPEG. The edit changed the score by a mean of minus 0.0013, raised it in 8 of 42 sets and lowered it in 18, and in no set did an original that had not been flagged become flagged after its edit. The first version was therefore unable to tell a re-typed word from the untouched screenshot.

@sub 7.1.3|TWO FURTHER FAILURES
A bank page rendered by Chrome and the same page with two amounts changed in the HTML were both flagged "fake" by the first version, because its arithmetic rule treated the page's "Balance" and "Total Spent" lines as contradictory (scores 0.495 and 0.416); three of the four pixel cues were equal on the two pages (ELA 0.881 and 0.880, noise 0.940 and 0.937, edge sharpness 0.937 and 0.934), and the fourth, the JPEG-ghost cue, scored the untouched page higher than the edited one (0.717 against 0.433), the wrong way round. The one cue that did separate edited from untouched files, an EXIF Software tag naming an image editor, raised the score from 0.412 to 0.804 when present, but the same pixels saved without the tag returned to the baseline. A tag is trivial to remove.

These findings define the redesign: drop the photograph cues, compare words with their neighbours, calibrate on genuine real screenshots, and make every rule demonstrate silence on ordinary pages.

@section 7.2|THE TWO VERSIONS ON THE SAME IMAGES
Five hundred test images (340 edited) were drawn at random from the test split and scored by both versions (Table {tab:v1v2}). The first version scored an AUC of 0.459, flagged 10.6% of genuine and 7.4% of edited images, and so flagged genuine images more often than edited ones. The final model reached an AUC of 0.838 and flagged none of the genuine images at its evidence tier and 0.6% at its suspicious tier, while flagging 29.4% and 43.8% of edited images.

@table v1v2|First and final versions on 500 test images
System | AUC | Genuine flagged | Edited flagged
First version | 0.459 | 10.6% | 7.4%
Final, evidence tier | 0.838 | 0.0% | 29.4%
Final, suspicious tier | 0.838 | 0.6% | 43.8%
@endtable

The comparison is not an indictment of the cues themselves: the final test images are generated screenshots with simulated edits, and the first version was designed for different data. The result shows that, on these images, rendering-consistency features separate the classes and the first version's cues do not.

@section 7.3|PERFORMANCE ON THE HELD-OUT TEST SET
The test set contains 3,237 images (2,184 edited) from base images and edit fonts unseen in training. Table {tab:overall} gives the overall result.

@table overall|Held-out test set: overall results
Measure | Value
Image-level AUC | 0.847
Evidence tier: edited images caught / genuine images flagged | 31% / 0.3%
Suspicious tier: edited images caught / genuine images flagged | 43% / 1.0%
Word-level AUC (all test words) / average precision | 0.983 / 0.782
Validation AUC (images, seen fonts) | 0.846
@endtable

The gap between the word-level AUC of 0.983 and the image-level AUC of 0.847 reflects the maximum over many words: the detector ranks individual words very well but one genuine word with a high score can outrank an image's true positive. Taking the highest probability among the images' words remains a conservative summary.

@sub 7.3.1|BY BASE SOURCE
@table bysource|Test results by source of the base image (same-source genuine images as the baseline)
Source | Images | Edited | AUC | Caught / flagged, evidence | Caught / flagged, suspicious
Chrome-rendered | 1,338 | 870 | 0.875 | 31% / 0.0% | 42% / 0.9%
Pillow-rendered | 681 | 423 | 0.824 | 26% / 0.0% | 39% / 0.0%
Real screenshots | 1,218 | 891 | 0.825 | 33% / 0.9% | 46% / 2.1%
@endtable

Real screenshots, the target domain, give an AUC of 0.825 with 46% of simulated edits caught and 2.1% of genuine real images flagged at the suspicious tier.

@sub 7.3.2|BY EDIT OPERATION
@table byop|Test results by kind of edit
Edit | Edited images | AUC | Caught, evidence | Caught, suspicious
Re-typed (Pillow) | 941 | 0.831 | 28% | 40%
Re-typed and blurred | 360 | 0.895 | 53% | 63%
Spliced word crop | 204 | 0.846 | 31% | 45%
Chrome-rendered patch | 679 | 0.844 | 23% | 35%
@endtable

Edits that were blurred to hide inconsistencies were caught more often, not less. A plausible reading, which these data do not test, is that the blur itself changes the sharpness profile of the patch relative to its neighbours, and the classifier may rely on sharpness features; no feature-importance analysis was run.

@sub 7.3.3|BY HOW THE EDIT WAS SHARED
@table bydegrade|Test results by sharing step
Sharing step | Edited images | AUC | Caught, evidence | Caught, suspicious
Lossless (PNG) | 725 | 0.912 | 43% | 56%
JPEG, quality 55-98 | 771 | 0.882 | 36% | 49%
Down-scaled, then PNG | 290 | 0.729 | 11% | 23%
Down-scaled, then JPEG | 398 | 0.718 | 13% | 20%
@endtable

Lossless edits are the easiest and JPEG sharing costs a few points. Down-scaling is the weak case: the AUC falls to 0.72 to 0.73 and fewer than a quarter of edits are caught at either tier. Resampling smooths exactly the anti-aliasing and stroke measurements the method relies on, in line with the general observation that resampling alters pixel statistics [@popescu2005resampling]. The service cannot recover that evidence; its limitations text warns about it.

@sub 7.3.4|BY ANTI-ALIASING AND BACKGROUND FILL
Image-level AUC was 0.833 for edits with grey-scale anti-aliasing (845 edited images), 0.873 for simulated LCD sub-pixel text, 0.888 for text with no anti-aliasing and 0.844 for Chrome-rendered patches, and between 0.837 and 0.871 across the four background fills (flat, clone-stamped, gradient and noise-matched; evidence: `train_final_v6.log`). Grey-scale anti-aliasing, the closest imitation of ordinary operating-system text, has the lowest AUC of the Pillow rendering modes, while the Chrome-rendered patches are caught least often at the suspicious tier (35%, against 42% for grey-scale). The four background fills differ by less than four points of AUC, so the choice of fill is not the main determinant of detectability.

@sub 7.3.5|FALSE ALARMS AND THE NUMBER OF WORDS
Because the image score is the maximum over words, larger images offer more chances for false alarms. On genuine test images, the share flagged at the suspicious tier was 1.8% for images with up to 30 measured words (395 images), 0.8% for 30 to 80 words (398), 0.4% for 80 to 200 (248) and 0 of 12 above 200. The service does not show a rising trend with word count on the test set, but few genuine test images are large, and the leave-files-out experiment (Section 7.6) is the better evidence for full-size screenshots.

@section 7.4|WHAT DEVELOPMENT CHANGED
The final model is the result of several corrections, each prompted by a measurement. Table {tab:dev} lists them with the evidence for each. The steps overlap and the test sets changed size between them, so the rows show the direction and rough size of each effect, not isolated causal contributions.

@table dev|Corrections made during development and the measurements that prompted them
Change | Measurement before | Measurement after | Evidence
Keep every OCR box, whatever its confidence | edited word measurable in 67.4% of test edited images (531) | 90.2% (2,184 images) | `ocr_recall_check.txt`
Skip single-glyph boxes; add more real windows; weight real samples 3 times | real test images flagged at the pooled 5% threshold: 24.5% (212 images) | 7.8% (848 images) | `train_v2...log`, `train_v4...log`
Calibrate thresholds on real validation images; larger boosted model; add Chrome-patch edits and whole real screenshots | 7.8% | 2.1% (1,218 images, final) | `train_final_v6.log`
Add whole real screenshots to training | full-size genuine screenshots flagged, suspicious tier: 11.0% (8 of 73) | 5.5% (4 of 73) | `leave_files_out_v5_intermediate.log`, `leave_files_out_v6.log`
Train on edits from both engines | AUC on Chrome edits 0.752 (Pillow-only model) | 0.844 | `cross_engine.txt`
A second-stage model over word probabilities | max-word AUC 0.824 | stage-2 AUC 0.809 (not adopted) | `second_stage_check.txt`
@endtable

The first row deserves a comment. A word set in an unfamiliar font is precisely the word on which Tesseract is least confident, so a confidence filter silently removed a third of the edits from consideration before the classifier saw them. The same pipeline run after the change keeps the edited word in analysis for 90.2% of test edits (94% for PNG and JPEG, 81 to 82% after down-scaling). The remaining misses are words that OCR does not return at all, and they bound the recall of any method built on OCR boxes.

@section 7.5|DOES THE MODEL LEARN THE EDITING ENGINE?
A classifier that sees edits made only by one text renderer could learn the renderer's signature instead of the edit. Table {tab:cross} shows a model trained on Pillow edits only, on Chrome edits only and on both, each tested on held-out edits from each engine.

@table cross|Cross-engine generalisation (image-level AUC on the test split)
Trained on | Tested on Pillow edits | Tested on Chrome edits
Pillow edits only | 0.846 | 0.752
Chrome edits only | 0.783 | 0.855
Both engines (shipped) | 0.849 | 0.844
@endtable

Transfer across engines is real but incomplete: a model trained on one engine scores 0.75 to 0.78 on the other, against 0.85 to 0.86 on its own. Training on both restores 0.84 to 0.85 on each. This is consistent with the signal being partly engine-specific. With only two engines it cannot show that a third engine (Photoshop, Canva, a phone editor) would be handled as well as either of these, and the true figure on such edits is unknown.

@section 7.6|GENUINE SCREENSHOTS THE MODEL NEVER SAW
The leave-files-out protocol (Section 5.7) is the closest test to real use. Table {tab:cv} gives the result for the 73 real files, each scored whole by a model trained without any window of it, together with 426 edited copies.

@table cv|Leave-files-out results (5 folds, 73 genuine full-size screenshots, 426 edited copies)
Measure | Suspicious tier | Evidence tier
Genuine screenshots flagged | 4 of 73 (5.5%; Wilson 95% interval 2.2% to 13.3%) | 0 of 73 (0.0%; interval 0.0% to 5.0%)
Edited copies caught | 191 of 426 (44.8%) | 103 of 426 (24.2%)
Caught after PNG sharing / JPEG | 53% / 55% | 28% / 36%
Caught after down-scaling (PNG / JPEG) | 32% / 24% | 12% / 8%
Image-level AUC, edited versus genuine | 0.805 | 
@endtable

The thresholds differ by fold because each fold's validation set differs: suspicious thresholds ranged from 0.62 to 0.95 and evidence thresholds from 0.94 to 0.999. The sample is small and comes from one person's machine, so the intervals are wide: a false-alarm rate between about 2% and 13% is consistent with 4 of 73. The edited copies are six per file and therefore not independent, so no interval is given for the detection rates.

An intermediate model, trained before whole real screenshots were added, flagged 8 of 73 (11.0%, interval 5.7% to 20.2%) with an AUC of 0.771, compared with 4 of 73 and 0.805 for the final model. An earlier version of the script that computed this experiment had a calibration fault (its output was not kept), noticed because its thresholds came out far lower than those of the shipped model: it trained on the validation images that it then used to set thresholds, so their scores were optimistic and the thresholds too low. The script was corrected so that the model sees the training split only, and the numbers above come from the corrected script.

@section 7.7|THE LAYOUT-GRID RULE
The rule of Section 4.6.1 was written after the classifier missed an edited amount on a real payment-history screenshot (Section 7.9) and was therefore tuned while looking at that example. Its false-alarm rate and its recall were measured separately on the whole corpus, using word boxes only (Table {tab:layout}).

@table layout|False alarms of the layout-grid rule on genuine corpus images, first and final version
Source | First version | Final version
Chrome-rendered | 112 of 3,200 (3.50%) | 6 of 3,200 (0.19%)
Pillow-rendered | 1 of 1,657 (0.06%) | 0 of 1,657 (0.00%)
Real screenshots | 22 of 1,799 (1.22%) | 0 of 1,799 (0.00%)
All genuine images | 135 of 6,656 (2.03%; interval 1.7% to 2.4%) | 6 of 6,656 (0.09%; interval 0.0% to 0.2%)
@endtable

Inspection of some of the first version's false alarms (the list of all cases was not kept) showed lists where one row had been skipped by OCR, so a single gap was twice the row pitch. Requiring both gaps next to the candidate to be near the normal pitch removed these. On edited corpus images, where placement error is at most two pixels by construction, the final rule fired on 12 of 6,138 Chrome-rendered, 0 of 2,906 Pillow-rendered and 0 of 5,114 real-screenshot images.

Recall was measured by shifting one row of a genuine list vertically by a fraction of the text height and asking whether the rule found it. Recall rises to about 15% and then stops rising: 0.1% at a shift of 0.1 text heights, 1.3% at 0.2, 7.7% at 0.3, and 15.5% and 15.2% at 0.5 and 0.8. Of 1,242 genuine images that have a numeric column (1,236 on which the rule had not already fired), only about 15% are evenly spaced enough for the rule to apply, and on those it finds essentially every shift of half a text height or more; when it fired at a shift of 0.5, it named the displaced number in 191 of 191 cases. The rule is therefore precise and narrow.

@section 7.8|OTHER RULE CHECKS
The remaining rules (metadata, watermarks, arithmetic, dates, checksums, clock) are validated by unit tests that include both a contradiction that must fire and an ordinary page that must stay silent, but their false-alarm rates were not measured on the corpus, because the generated screenshots rarely contain the specific contradictions or the specific identifiers they test. They are reported as implemented, not as measured.

@section 7.9|A SAMPLE OF REAL EDITS
Eight screenshots from a payment-application history were collected: four edited by a person with their own tools, and four genuine. Each edit was identified by comparing the edited screenshot with its genuine counterpart. The images are personal and are not reproduced here. Table {tab:real8} gives the result.

@table real8|Final system on eight hand-collected payment-history screenshots (development data)
Image | Truth | What differs from the original | Verdict | What fired
3 | edited | an amount changed (75 to 79) and placed about 14 pixels above its row | suspicious | layout rule; classifier alone scored 0.11
4 | edited | an amount set in a thinner, italic font | evidence of editing | classifier, top word probability 0.979
5 | edited | an amount replaced by a shorter plain one (the plus sign and thousands separator dropped) | no evidence | top word probability 0.27
6 | edited | a short amount in a different serif font; OCR read it as "ad" | no evidence | top word probability 0.34
7-10 | genuine | none | no evidence (all four) | highest word probabilities 0.31, 0.24, 0.12, 0.06
@endtable

Two of the four edits were flagged and none of the four genuine images. The sample is far too small to estimate rates and it is development data, not a test: the eight images were used to find the blind spot that led to the layout rule and to test the column idea described next. The edited and genuine images also differ in resolution and file type (1,125 by 2,000 pixel JPEG against 923 by 2,000 pixel WebP), so the edited files were exported at a different scale than the originals; this confounds the comparison and is itself a realistic property of forged files. A protocol for collecting a proper validation set, with a capturer and an editor who are different people, is given in Appendix E.

@section 7.10|A NEGATIVE RESULT: COMPARING NUMBERS WITH THEIR COLUMN
In the eight real images each edited amount stood out from the other amounts in its column on stroke thickness and edge sharpness (robust z-scores of 3.6 to 9.0 for stroke thickness and 7.1 to 29.8 for edge sharpness; `column_z_8images.txt`), while no genuine amount in the four real screenshots exceeded 2.6 on either measure. That looked like a strong, simple signal. It was tested two ways and rejected.

@bullets
- **As features.** Twenty-two column-relative features were added and the model retrained on the full corpus. The held-out AUC was 0.848 against 0.847 for the shipped model, and the three missed edits still scored 0.14, 0.19 and 0.20, below the 0.765 suspicious threshold of that model (`negative_results.txt`).
- **As a rule.** Restricted to numeric columns, a rule requiring a stroke z-score of at least 3 and an edge-sharpness z-score of at least 6 fired on 10.2% of 49 genuine real images, 19.7% of 493 genuine Chrome images and 2.4% of 42 Pillow images, and on a similar share of edited images (13.7%, 19.4% and 3.3%). Raising the thresholds lowered but did not remove the false alarms (8.2% of genuine real images at a sharpness z of 12).
@end

Across the corpus, the column z-scores were saturated even on genuine images (the median image had a word with a z-score of 7.5 to 8, with scores clipped at 12), which is consistent with genuine numeric columns in the corpus being far less uniform than the four in the hand-collected screenshots; this explanation was not tested. The idea was not shipped. The episode is kept in this report as a warning about conclusions drawn from eight images that were also used to design the test.

@section 7.11|SPEED
Over 80 test images of up to 3 megapixels, analysis took a median of 581 ms, a 90th percentile of 1,030 ms and a maximum of 1,637 ms, from 194 ms for the smallest third of images to 749 ms for the largest third. Eight whole 5.9-megapixel desktop captures took between 1.7 and 6.8 seconds (median 3.6 seconds), measured while other jobs were running on the machine, so these are upper estimates. Time grows with the number of words; OCR is probably the largest part, but the run was not profiled.

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
