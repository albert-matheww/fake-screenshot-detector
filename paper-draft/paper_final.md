@abstract
Screenshots of chats, bank statements and payment histories are routinely accepted as informal evidence, yet any image editor can alter them. This project builds and evaluates a service that tells a person what can and cannot be established about an uploaded screenshot. Its one rule is that a check counts toward the verdict only after it has been measured on at least 20 genuine real screenshots with a 95% upper bound on its false-alarm rate of at most 15%; every other check is shown and never counted, a check may say that it could not examine the image, and any doubt gives "inconclusive". The service never calls an image authentic. It returns an assurance level instead: level 1 means the content is consistent with itself, and level 2 means a second source, which the person states did not come from the sender, agrees with the screenshot. Two earlier versions failed on this principle. A photograph-forensics version flagged 12 of 60 genuine screenshots (20%) and could not separate edits from originals (AUC 0.50). A word-level rendering model reached an AUC of 0.85 on simulated edits and 0.81 on held-out words of 3,932 real tampered screenshots (STFD), but re-compression lowered it to 0.66 and the models trained on real edits flagged 40% to 80% of genuine screens of another domain, so it is kept as an advisory hint. The evaluation uses 47 genuine real items, nine edit pairs, 13 SMS messages, 3,932 public tampered screenshots, 300 rendered receipts, 300 Rico screens and 1,080 rendered test documents. On the real items every verdict was inconclusive and none received a medium or high finding from a counted check; level 1 does not separate genuine from consistently edited screenshots. Compare mode found differences in all nine edit pairs and wrongly flagged 3 of 27 harmless re-saves. Reconcile mode never corroborated an altered second source, but on real Google Pay lists it corroborated none of 7 true pairs, mainly because OCR reads the rupee sign as a digit. Testing with ground truth or real data found and repaired six defects in the rules and in reconcile mode (a seventh, overclaiming interface wording, was caught by the wording test); afterwards the content rules fired on 25 to 30 of 30 injected contradictions of each of 16 kinds. A screenshot rendered with false content that is consistent in itself, or a second source supplied by the forger, defeats the checks.
@endabstract

@chapter 1|INTRODUCTION

@section 1.1|OVERVIEW
A screenshot is among the cheapest forms of evidence to produce. It is offered to prove that a payment was sent, that a message was received, that an account held a given balance, or that a post said what someone claims it said. It is also among the cheapest things to fake: opening the image in any editor, covering a number and typing another takes a few minutes and no special skill. Work on forged text images describes finance, certificate checking and news screenshots as typical targets [@yu2025fsts], and a 2026 benchmark paper treats fabricated screenshots, documents and news pages as a prominent vehicle for misinformation and fraud [@zhang2026textfake].

This project, a fake screenshot detector, is a working service that looks at one uploaded screenshot and answers a deliberately modest question: what can be established about this image, and how much independent evidence supports it? The answer has three parts. A verdict says whether a calibrated check found a contradiction. An assurance level (0, 1 or 2) says how much independent evidence supports the screenshot; it rises above level 1 only with outside evidence. Every check that ran is listed with what it did, including the checks that could not examine the image and the checks that are shown but not counted. The service never states that an image is authentic, and a list of what it cannot detect is returned with every answer.

The report also records how the design changed. The first version reused the toolbox of photograph forensics and failed an honest audit. The second version replaced it with a word-level model and measured well on simulated edits but poorly on real ones. The third version, described in Chapters 3 and 4, drops the idea that an image alone can be declared genuine: it checks what the screenshot says, lets the person bring a genuine copy or a second source, and says plainly when it cannot tell. Chapters 5 and 7 give the evidence for each step, including the experiments that failed.

@section 1.2|WHY SCREENSHOTS ARE DIFFERENT FROM PHOTOGRAPHS
Passive image forensics grew up around photographs [@farid2009survey]: a forger splices part of one picture into another, moves a region within one picture, or removes an object by inpainting [@verdoliva2020], and an analyst looks for traces left by the camera, the JPEG coder or the editing step [@piva2013overview]. Most of those traces are weak or absent in a screenshot.

There is no camera sensor, so methods built on sensor pattern noise [@lukas2006prnu] have nothing to measure. Large regions are flat colour, and the text is rendered by the operating system with crisp edges rather than captured through a lens. Error level analysis resaves the image at a known JPEG quality and compares the result with the original [@krawetz2007]; it is defined for images stored with lossy compression, whereas the 60 genuine device screenshots of the first audit were almost all lossless (59 were PNG files). Most of the 23 genuine screenshots of the later real set had been shared and are lossy (15 of 23). A screenshot is also frequently re-shared through messaging applications, which re-compress and sometimes down-scale it, so the file that reaches an examiner may differ from the one the device produced.

A text edit is expected to leave local traces: the inserted glyphs may have been drawn by a different program, at a slightly different size, with a different anti-aliasing recipe, on a patch of background that may not match its surroundings exactly. Work on document tampering notes that document images mostly share one background colour and that text within a cluster usually shares one font and size, which is why visual clues of tampering are scarce [@qu2023doctamper]. The inference drawn here, that a replaced word therefore tends to differ in rendering (size, anti-aliasing, local background), was the working hypothesis of the second version. Chapter 7 reports how far it held, and why it is not enough on its own.

There is a second, more basic difficulty. A careful edit in the matching font, or a screenshot rendered with false content from the start, leaves nothing in the pixels to find. For those cases the only evidence that can help lies outside the image, which is why the final version adds a way to bring that evidence in.

@section 1.3|PROBLEM STATEMENT
Given a screenshot of a kind the person can name, and optionally a genuine copy of it or a record of the same event from a source the sender did not control, report which checks found a contradiction, show every difference or disagreement with the outside evidence, and state how much independent evidence supports the screenshot. False alarms on genuine screenshots must be rare, every check must be measured before it is trusted, and the cases the method cannot handle must be stated.

Three properties of the problem shape every design decision in this report. First, a single screenshot is only internal evidence: it can contradict itself, but it cannot prove that it matches reality. Second, the edited area is tiny: a changed amount is a few words in an image of several hundred, and a detector that scores every word will meet hundreds of chances to raise a false alarm. Third, there is no freely available labelled collection of the screenshots that matter here (bank, payment and order screens as people actually share them) with their untouched originals. Among the datasets reviewed (Table {tab:related}), the screenshot data is access-controlled and contains tampered images only [@yu2023stfd; @hf_stfd], and the other public sets are from different domains, so the measurements in this report come from small private sets and from public sets that cover only part of the question.

@section 1.4|OBJECTIVES
The project set seven objectives, each tied to something that can be checked.

@numbered
1. Audit the first version on genuine screenshots and on realistic edits, and record what the audit shows (Chapter 7, Section 7.1).
2. Build a word-level, explainable rendering model and measure it on generated edits, on edits made by a person and on public real edits (Chapters 4, 5 and 7).
3. Add rule checks that read the content of a screenshot, including rules for named types, and make every check pass a calibration gate before it can influence a verdict (Chapters 3, 4 and 7).
4. Replace a yes or no answer by a verdict that never says "authentic" and an assurance level that rises above level 1 only with independent evidence (Chapter 3).
5. Provide two ways of using outside evidence, compare mode for a genuine copy and reconcile mode for a second source, and measure both (Chapters 4 and 7).
6. Evaluate with protocols that expose weaknesses: unseen edit fonts, split by source screenshot, a second editing engine, genuine screenshots held out file by file, public real edits, and genuine public screens (Chapters 5 and 7).
7. Deliver a usable service with an application programming interface, a web interface, automated tests and container files, and document its limits (Chapters 6 and 8).
@end

@section 1.5|SCOPE AND CONTRIBUTIONS
**The contribution in one sentence.** Relative to detectors that classify an image from its pixels, this work builds and evaluates a service in which every check must earn the right to count (at least 20 genuine real screenshots, a Wilson upper bound of at most 15%), the answer is an assurance level that rises only with independent evidence, and the checks are tested by injecting known contradictions and by running them on real statements, chats and bank messages, which found and repaired six defects that simpler measurements had missed, besides one overclaiming interface wording caught by the wording test (Sections 7.15 to 7.20).

The scope is screenshots of the types in Table {tab:types}, checked for contradictions inside the image, for differences from a genuine copy and for disagreement with a second source. Out of scope are verifying a screenshot against an issuer's systems (the service has no access to any), images generated by an AI model, and print-and-scan recapture. A screenshot rendered natively with false content, for example text changed in a browser's developer tools before the screenshot was taken, is in scope only to the extent that its content contradicts itself or disagrees with an outside record.

@table types|Screenshot types the service knows and the rules written for them
Type | Rules written for the type
Payment receipt or transfer | UPI reference has 12 digits; success and failure shown together
Bank statement or balance | running balance follows the amounts (debit and credit columns, either order); one broken link among otherwise consistent ones
Order, invoice or refund | subtotal, items and total agree
Chat conversation | message times do not run backwards
SMS, e-mail or notification | one-time code has a usual length
Social media post | no type-specific rule
Web page or dashboard | no type-specific rule
@endtable

The contributions, in the order in which the evidence for them appears, are:

@bullets
- a documented audit of a photograph-forensics pipeline on genuine screenshots, showing that its pixel cues carried no usable signal (Section 7.1);
- a design in which a check may abstain, must be calibrated on genuine real screenshots before it counts, and any doubt leads to "inconclusive", with a verdict policy and assurance levels that never call an image authentic (Chapters 3 and 4);
- reconcile mode and compare mode, which bring outside evidence in, with three tests of reconcile mode (a mutation test, ground-truth receipts and real bank SMS against real Google Pay lists) that show where it works, where the rupee sign defeats OCR, and that no test produced a false corroboration (Sections 7.7, 7.8, 7.17 and 7.18);
- a mutation and real-data test programme for the rules, covering 16 kinds of injected contradiction, real chats and real e-statements, that found and repaired six defects in the rules and in reconcile mode (Sections 7.15, 7.16 and 7.20);
- a measurement of what training on real tampered screenshots (STFD) does and does not achieve for a word-level model, with five grouped splits, a bootstrap, a feature-family ablation and a random baseline, including a quantitative result on the idea that comparing a word with its neighbours matters: on clean words each feature half carries about the same signal, and after re-compression only the comparisons keep it (Sections 7.9 to 7.11 and 7.19);
- ScreenForge, a leak-controlled generated corpus used for the second version, a layout rule measured on 6,656 genuine images, and a record of negative results (Chapter 5 and Sections 7.2, 7.12 and 7.13).
@end

These contributions are of the system, application and cautionary-evidence kind. The report does not claim a new learning algorithm and it does not claim performance on edits made by independent people with real tools: the project has two small hand-collected sets of edits (nine pairs edited by its owner, and an eight-image sample whose editor was not recorded) and a public set of tampered screenshots without originals.

@chapter 2|BACKGROUND AND LITERATURE SURVEY

@section 2.1|INTRODUCTION
This chapter places the project among existing work. It is organised around the question the project had to answer in turn: which established cues survive in a screenshot (Section 2.2), what learned localisers offer (2.3), what has been done for text and document tampering and what data exists (2.4), what is known about screenshots specifically (2.5), and which evaluation practices matter for a small-data project (2.6). Section 2.7 states the gap.

@section 2.2|CLASSICAL PASSIVE IMAGE FORENSICS
Surveys describe passive forensics as the search for traces that an image acquires at capture, coding and editing [@piva2013overview; @verdoliva2020]. Compression history is the best-known family: the "JPEG ghost" technique spots a region first saved at a lower JPEG quality than the rest [@farid2009ghosts], block-grained likelihood maps localise double compression [@bianchi2012block], and error level analysis resaves an image at a known quality and inspects where the difference is large [@krawetz2007]; all presuppose that the image went through JPEG coding at least once. A second family looks for resampling traces, which resizing or rotating leaves in pixel correlations [@popescu2005resampling], and for noise inconsistencies [@mahdian2009noise] or a camera's sensor pattern noise [@lukas2006prnu]; resampling matters here because shared screenshots are often down-scaled, whereas a screenshot has no sensor. A third family is copy-move detection, compared under controlled conditions by Christlein and colleagues [@christlein2012eval]; duplicating a digit or a row is a plausible screenshot edit, but screenshots also contain many legitimate repeated elements such as icons and list rows, a source of false matches.

@section 2.3|LEARNED LOCALISATION AND BENCHMARKS FOR NATURAL IMAGES
Many recent localisers are learned rather than hand-built [@verdoliva2020]: ManTra-Net treats localisation as local anomaly detection [@wu2019mantranet], CAT-Net learns compression artefacts jointly from RGB and DCT streams [@kwon2021catnet], and TruFor adds a learned noise fingerprint and a reliability map intended to reduce false alarms [@guillaro2023trufor]. A unified benchmark and code base now spans deepfake, manipulation, AI-generated and document images [@du2025forensichub]. The first version of this project was trained partly on standard natural-image data, the CASIA tampering database [@dong2013casia] (natural colour images with realistic tampering) and IMD2020 [@novozamsky2020imd] (35,000 real and 35,000 manipulated images, plus 2,000 real-life manipulations); Section 7.1 shows why that was inappropriate for screenshots.

@section 2.4|TAMPERED TEXT AND DOCUMENT FORGERY
@sub 2.4.1|DATASETS AND DETECTORS
Text in documents differs from objects in photographs: backgrounds are uniform and text within a cluster usually shares one font and size, so visual clues are scarce [@qu2023doctamper]. DocTamper contributes 170,000 document images covering splicing, copy-move and generation, together with a detector that adds frequency-domain information [@qu2023doctamper]. A receipt dataset for document forgery detection [@tornes2023receipt] was also used in the first version of this project. The Screenshot Text Forgery Dataset (STFD) is described by its authors as the first public dataset for localising text forgery in smartphone screenshots [@yu2023stfd]; a later paper reports that it contains 4,094 tampered instances [@yu2025fsts]. Its dataset card states that the archive can only be extracted with a password obtained by e-mailing the authors from an academic or institutional address, and that it is for academic research [@hf_stfd]. A request from a university address was sent for this project and the authors replied with the password (the reply is not stored in the repository). The dataset card asks users to cite the paper and not to redistribute images that may leak information [@hf_stfd]. The archive holds 3,932 tampered screenshots with pixel masks (Section 5.4). The later paper gives 4,094 both as a count of tampered instances and, in one of its tables, as an image count [@yu2025fsts]; the card says the images were manually screened to remove sensitive information [@hf_stfd], which may explain part of the difference, but the reason was not investigated.

Two recent datasets are built from human-made tampering, and one paper notes that annotated human-made data is scarce [@yu2025fsts; @xu2026reality; @dhouib2026doctamper]. FSTS collected 16,750 real tampering instances from 67 people, modelled their operations and post-processing parameters (including blur and JPEG recompression), and used them to synthesise training data [@yu2025fsts]; the corresponding release is a roughly 46 GB archive under a non-commercial licence [@hf_fsts] and was not used. RWTamper offers completely manual tampering in three subsets under different degradation conditions [@xu2026reality], an explainable detector describes tampered text in natural language [@qu2024textsleuth], and work on print-and-scan recapture studies a setting where traces are concealed by halftoning and blur [@chen2025unmask].

@sub 2.4.2|WHAT RECENT DOCUMENT-FORENSICS PAPERS WARN ABOUT
Three findings from this literature shaped the evaluation design of this project. First, an improvement measured on a synthetic benchmark that resembles the training data does not carry over reliably to forgeries made by people or to data from another domain [@dhouib2026doctamper]. This is the central caveat for any result in this report that rests on simulated edits, and Chapter 7 shows a case of it. Second, a training set restricted to a narrow range of JPEG quantisation tables does not match the varied compression of operational document pipelines, and training with realistic tables lowered false positives on authentic documents, but only for architectures that take the quantisation table as an input [@ronfleux2026docqt]; the generated corpus here therefore draws the JPEG quality at random, and it applies the same sharing step to genuine and edited images so that compression history cannot reveal the label, a choice made in this project. Third, a zero-shot benchmark of 14 methods on eight document datasets found moderate pixel-level AUC but near-zero F1 at the conventional 0.5 threshold, attributed to the tiny share (about 0.3 to 4%) of tampered pixels, and reported that adapting a threshold on ten in-domain images recovered 39 to 55% of the gap in representative cases [@zhao2026docforge]. This supports adapting alert thresholds to the target domain. The present system fixes thresholds at false-alarm rates measured on genuine in-domain images, and the final version goes further by refusing to count any check that has not been so measured.

@section 2.5|SCREENSHOTS AND AI-GENERATED TEXT-RICH IMAGES
The closest published work found is a pipeline designed for screenshots that combines five groups of cues (error level, noise, JPEG traces, text-edge regularity and metadata) in one gradient-boosted classifier deciding between real and fake [@venkatesh2026screenshot]. On its own set of 1,200 screenshots with four manipulation types the authors report an AUC of 0.82 against 0.47 for an ELA-threshold baseline, with weaker recall on small text edits and on copy-move. Because that dataset, its edits and its compression conditions differ from those used here, its numbers are not compared with this project's. It does show that a similar combination of compression, noise and metadata cues has been proposed for screenshots; its evaluation conditions (per its abstract, JPEG error-level analysis and heavy recompression) differ from the lossless-PNG audit of Section 7.1.

Rico is a mobile-app dataset [@deka2017rico]. A Hugging Face copy of a subset of its screens, licensed CC BY 4.0, has a test split of 4,217 screens [@hf_rico]. The project treats these screens as genuine and unedited (its own assumption: neither source says so), which makes them usable for one purpose in this report: measuring how often a detector flags genuine screens of a domain it was not trained on (Section 7.11). Only the metadata record of the Rico paper and the dataset card were read.

A separate threat is the screenshot that never existed: an image generated by an AI model. A 2026 benchmark of 20,000 text-rich images found that none of the evaluated detectors exceeded 80% accuracy and named three failure modes, one of which (the Text Density Curse) concerns dense glyphs overwhelming low-level detectors [@zhang2026textfake]. Detecting generated screenshots is outside the scope of the present work.

@section 2.6|EVALUATION PRACTICE
Dataset bias and its effect on cross-dataset generalisation is a long-standing concern: methods can learn the quirks of a collection and fail to transfer [@torralba2011bias]. A taxonomy of data leakage lists duplicated items, non-independence between training and test units (for example, several samples derived from one source) and choices made with information from the test set among its types [@kapoor2023leakage]. Each has a counterpart here: several windows and edited copies are cut from every screenshot file, so splits must be made by file; STFD contains several edits of what are apparently the same screens, so splits must be made by source screenshot; test edits must not use fonts seen in training; and thresholds must be fixed on data the model did not fit. The project met the last problem in its own code (Chapter 7).

Ranking quality is summarised here with the area under the receiver operating characteristic curve [@fawcett2006roc], alongside the detection and false-alarm rates at the thresholds actually used. Binomial proportions that decide whether a check may count are accompanied by Wilson intervals [@wilson1927]; small samples such as the eight-image sample are not.

@section 2.7|GAP AND POSITIONING
Table {tab:related} summarises the datasets and the closest systems. Within the sources reviewed, four observations define the niche of this project. Screenshot-specific public data exists but is access-controlled (STFD) and contains tampered images only, and the only other directly relevant release found is very large (FSTS, about 46 GB) and was not used [@hf_stfd; @hf_fsts]. The one screenshot-specific forensics pipeline found combines compression-related cues with noise, text-edge and metadata features and reports weaker recall on small text edits [@venkatesh2026screenshot]. Document-forensics papers report that gains on synthetic benchmarks transfer poorly to human-made forgeries [@dhouib2026doctamper] and that adapting the decision threshold to the target domain is a key missing step for deployment [@zhao2026docforge]. Finally, the sources reviewed here detect tampering from the image itself; none of the abstracts or full texts read describes comparing a screenshot with an independent record of the same event. Of the 39 references, 14 were read in full (11 papers and 3 dataset cards), 21 at abstract level and 4 by bibliographic record, so this is a statement about what was read, not about the field.

The project therefore pursues a small, explainable, CPU-only service that measures every check before trusting it, uses a genuine copy or a second source whenever the person has one, and reports its failures. It does not compete with the learned localisers on their benchmarks; no such comparison was run.

@table related|Datasets and systems most relevant to screenshot text forensics (size figures are as stated in the cited sources unless marked as this project's own)
Name | Content | Size reported | Use in this project
DocTamper [@qu2023doctamper] | tampered document images | 170,000 images | not used
STFD [@yu2023stfd; @hf_stfd] | smartphone screenshots with text forgeries and masks | 4,094 tampered instances or images [@yu2025fsts]; 3,932 images in the archive used (this project's count) | obtained from the authors; used (Chapters 5 and 7)
FSTS [@yu2025fsts; @hf_fsts] | real tampering parameters and synthetic tampered text images | 16,750 real instances; about 46 GB archive | not used
RWTamper [@xu2026reality] | manually tampered text images, three degradation subsets | 9,326 images per subset | not used
Rico subset [@deka2017rico; @hf_rico] | mobile-app screens, treated here as genuine (CC BY 4.0 copy) | test split of 4,217 screens | 300 screens sampled for false-alarm measurement
Screenshot forensics pipeline [@venkatesh2026screenshot] | ELA, noise, JPEG and metadata fusion with gradient boosting | 1,200 screenshots | numbers not compared
@endtable
@chapter 3|REQUIREMENTS AND SYSTEM DESIGN

@section 3.1|INTRODUCTION
This chapter states what the service has to do, the principles that were adopted after the first two versions failed, the architecture, the threat model, and the rules by which evidence becomes a verdict and an assurance level. The methods behind each check are described in Chapter 4.

@section 3.2|REQUIREMENTS
@sub 3.2.1|FUNCTIONAL REQUIREMENTS
@numbered
1. Accept one image per request in PNG, JPEG or WebP format, up to 10 MB, optionally with the type of screenshot chosen by the person.
2. Read the text in the image, run the checks that apply, and return for every check whether it found something, found nothing or could not examine the image, and whether it counts toward the verdict.
3. Return a verdict in one of four tiers, a risk score, the marked regions with their coordinates in the uploaded image, and the reasons.
4. Return an assurance level (0, 1 or 2) with the reasons for it and the next step that would raise it.
5. Accept a genuine copy of the screenshot and mark every difference (compare mode).
6. Accept a second source, as pasted text or as an image, and report for each amount, date, time and reference number whether the screenshot agrees (reconcile mode).
7. Return, with every response, a fixed list of limitations, and never describe an image as authentic or genuine.
8. Provide a web interface for all three modes that reports failures (network, size, format, server) in distinct messages and supports a demonstration mode without the back end.
@end

@sub 3.2.2|NON-FUNCTIONAL REQUIREMENTS
@bullets
- Honesty about uncertainty: a check that cannot look must say so, and the answer must move towards "inconclusive", never towards "clear", when there is doubt.
- Explainability: every finding names a place or a fact, and every check says why it counts or does not.
- Privacy: screenshots may contain payment and chat details, so the image must stay in memory and must not be stored (Section 6.5).
- Few false alarms on genuine screenshots, prioritised over detection rate: a tool that cries wolf on untouched images is useless as evidence screening.
- Runs on an ordinary CPU, with no graphics processor and no network access at analysis time.
- Reproducibility: every number from the project's own experiments was produced by a script kept in the repository (Appendix 4); numbers that depend on the authors' private screenshots can be regenerated only on that machine.
@end

@section 3.3|DESIGN PRINCIPLES ADOPTED AFTER THE AUDITS
Six principles were fixed after the failures of the first two versions (Sections 7.1 and 7.3) and they explain several choices that might otherwise look arbitrary.

@numbered
1. **Absence of evidence is not evidence of absence.** No answer is ever "authentic". The best a single screenshot can reach is "no contradiction found, still unverified", because an image rendered with false content, or edited consistently, contains nothing for the checks to find (Section 3.5).
2. **A check may abstain.** Every check returns one of three states: it found something, it found nothing, or it could not examine the image (and says why). The idea that a classifier may decline to answer, trading errors against refusals, is the reject option [@chow1970]. "Could not examine" is never counted as a pass.
3. **A check counts only after it has been measured.** A check may influence the verdict only if it was applied to at least 20 genuine real screenshots and the 95% upper bound of its false-alarm rate is at most 15% (Section 4.7). Everything else is shown as advisory and never counted.
4. **Doubt moves the answer towards "inconclusive".** An unknown type, an advisory signal, or too few readable words can only make the answer more cautious (Section 3.6).
5. **Only outside evidence adds assurance.** A screenshot can be made to agree with itself, so assurance above level 1 requires a second source that the sender did not supply (Section 3.7).
6. **Record the failures.** Negative results are kept in the report because the evidence for what works is only as good as the record of what was tried.
@end

@section 3.4|ARCHITECTURE
@fig fig_v3_pipeline|15.5|Architecture of the final service. Checks that are not yet calibrated, and the hints from the earlier versions, are shown but never counted. A second source raises the assurance; compare mode, which uses a genuine copy, gives a separate result.

The browser interface posts the image, and optionally the chosen type, to a Flask application programming interface. The application reads the image, applies the orientation stored in its metadata so that coordinates match what a browser displays, profiles the file (Section 4.2) and runs OCR. If the person chose a type, the type-specific rules run on it; otherwise two routers guess the type and the guess is used only if the routers have been validated (Section 4.3). The checks run independently of one another and each is passed through its calibration gate. The verdict module combines the counted checks into a tier and the assurance module adds the level. Compare mode and reconcile mode are separate endpoints. Compare mode uses no learned model; reconcile mode runs the normal analysis and then compares facts, and the comparison itself does not use the model.

@section 3.5|WHAT THE SERVICE CAN AND CANNOT SEE
Table {tab:threat} states the threat model.

@table threat|Threat model: which kinds of fake the service can address
Kind of fake | What the service can do | Why
A number or word re-typed over a screenshot, content still consistent | The checks usually cannot; compare mode and reconcile mode can | no contradiction exists inside the image; a genuine copy or a second source differs
Content that contradicts itself (weekday wrong for the date, a running balance that breaks at one row, totals that do not add up, a failed checksum, a generator watermark) | The live content rules can flag it if the text was read correctly; the type-specific rules (running balance, UPI reference length and so on) currently only lower the assurance, because they are not yet calibrated | the contradiction is visible in the text
A number pasted off the row grid of an evenly spaced list | Partly: when the list is perfectly regular and the displacement is at least 5 pixels and 0.2 text heights (in simulation, recall reached its ceiling of about 15% from half a text height) | layout rule (Section 4.4)
Text changed in browser developer tools, then screenshotted; output of a fake-receipt website | Only if the content contradicts itself or disagrees with a second source | the screenshot is renderer output; nothing in the pixels is inconsistent
A screenshot generated by an AI image model | Same as above; the generated image is not itself detected | no editing step exists
Edit followed by heavy down-scaling or repeated re-compression | Pixel hints lose most of their evidence; reconcile mode does not depend on pixels; compare mode needs the same layout | resampling smooths the traces (Section 7.10)
A forger who also controls the second source, or supplies it | Not detected | the second source is assumed to be independent of the sender
@endtable

For the cases the checks cannot see, the remedy that does not depend on the image is to verify with the issuer, for example by asking the bank or payment application to confirm a transaction identifier. Reconcile mode is the project's way of doing the part of that which a person can do without the issuer: comparing the screenshot with another record of the same event.

@section 3.6|VERDICT POLICY
The verdict module (`backend/screencheck/verdict.py`, Listing B.1) turns the checks that count into one of four tiers. A check counts only if its gate says it is live. Let the highest severity among live findings be high, medium, low or none.

@table verdict|Conditions for each verdict tier
Tier | Condition | Risk score shown
Inconsistency found (evidence of editing) | a live finding of high severity | 0.88
Possible inconsistency, review recommended (suspicious) | a live finding of medium severity, and none of high | 0.58
No inconsistency found by the checks that could run | no live finding of medium or high severity, a live content check and a live visual check both found nothing, the type is known, no advisory check raised a signal that carries information, and at least 15 words were read | 0.15
Inconclusive, verify with the issuer | none of the above | 0.42
@endtable

Three details matter. First, advisory checks can make the answer more cautious (an advisory finding stops a screenshot from reaching the third row) but can never make it less cautious. Second, an advisory hint that flags most genuine screenshots carries no information and is excluded from that caution (Section 4.6). Third, with the gates measured so far, no visual check is live, so the third row cannot be reached: every screenshot with no contradiction receives the fourth row. This is the intended behaviour of the policy and not a defect, and Section 7.4 shows its consequence.

The risk score is a display aid in four fixed positions, not a probability. The service marks at most ten regions; a live check's regions are drawn at their own level and an advisory check's regions are drawn as weak.

@section 3.7|ASSURANCE LEVELS
The verdict answers whether a calibrated check found a contradiction. The assurance level answers a different question: how much independent evidence supports the screenshot. It is computed in `backend/screencheck/assurance.py` (see Appendix 2).

@fig fig_assurance|15.5|The four assurance levels. Levels 0 to 2 are implemented; level 3 is reserved for a signature or signed code that can be checked.

@table assurance|Rules that set the assurance level (applied in this order)
Situation | Level and status
A live finding of medium or high severity, or a verdict of evidence or suspicious | 0, contradiction
A live finding of low severity only (for example an impossible clock time, which is usually an OCR misread) | 0, possible issue
A finding by a content check that is not yet live (for example a type-specific rule) | 0, possible issue
Reconcile mode: the second source and the screenshot disagree on a reference, amount or date | 0, conflict
Reconcile mode: a reference differs by one digit, or an amount has one extra leading digit | 0, review
Reconcile mode: every hard fact of the second source matched and the reference (or both amount and date) matches | 2, corroborated
A content check examined the text and found nothing, and at least 15 words were read | 1, consistent
Anything else | 0, unverified
@endtable

Level 1 is deliberately weak. It says that what the screenshot says is consistent with itself, and the label says "still unverified". A forger who keeps the content consistent reaches level 1 as easily as a genuine screenshot does; Section 7.4 measures exactly that. Level 2 is the first level that depends on something the forger did not control, and only if the second source is independent of the sender. The wording shown to the person never uses "authentic", "genuine" or "verified" as an assertion, and a test enforces that on all the demonstration results and on the assurance text (Section 6.4).

@chapter 4|METHODS

@section 4.1|INTRODUCTION
This chapter describes each component in the order in which a screenshot meets it. Sections 4.2 to 4.7 cover the single-screenshot path (profile, type, checks, hints, calibration), Section 4.8 reconcile mode and Section 4.9 compare mode. The word-level rendering model, which was the centre of the second version, is described in Section 4.5 in the shorter form that its reduced role deserves.

@section 4.2|CAPTURE PROFILE
`backend/screencheck/capture.py` records what happened to the file after the screenshot was taken, from the file itself and not from its name: format, size, aspect ratio, whether the file is lossless (PNG, or lossless WebP), and for a JPEG an estimate of the quality from the luminance quantisation table. The estimate follows the libjpeg scaling rule: the table's mean is compared with the mean of the standard table (57.6) and converted to a quality between 1 and 100. The profile sets a pixel reliability: high for a lossless file, reduced for a JPEG of quality 85 or more or a lossy WebP, and low for a JPEG below quality 85. It also records whether the image is phone-shaped (height at least 1.6 times the width and width at most 1,500 pixels). The profile does not decide anything by itself; it explains how much pixel evidence can still exist and tells the version-1 hints whether they have anything to read (Section 4.6).

@section 4.3|CHOOSING THE TYPE AND THE TWO ROUTERS
The person is asked what kind of screenshot it is, from the types in Table {tab:types}, with "not sure" as an option. A chosen type is trusted: the route is marked as chosen by the user, the type-specific rules run, and the automatic guess is kept in the response for comparison. This is the practical solution to the type problem for a service whose users usually know what they are holding.

For "not sure", two independent routers guess the type. Router A reads the words: for each type it has a small table of patterns with weights (for example "UPI", "paid to" and "transaction id" for a payment receipt; "balance", "statement" and "IFSC" for a bank statement), sums the weights of the patterns found, and answers only if the best score is at least 2.0; its confidence is the best score divided by the sum of the best and second-best scores and 2. Router B never looks at what the words say. It uses 32 layout statistics (aspect ratio, status-bar presence, darkness, saturation, number of lines, share of numeric words, number of numeric columns, histograms of line starts and ends, and bubble-like left and right alignment) and a boosted-tree classifier trained on 640 generated Chrome-rendered screenshots (held-out accuracy on generated images 0.925). A router influences the type only if it has been validated on real screenshots: at least 60 labelled real screenshots, answers on at least half of them, accuracy of at least 0.85 and a wrong-answer rate of at most 0.05. Neither router has met that bar (Section 7.6), so today the automatic guess is shown as tentative and does not enable type-specific rules.

@section 4.4|CHECKS
Each check is a function of the screenshot that returns a state (found something, found nothing, could not examine), a severity, findings with evidence, regions and a reason. A check that raises an exception is reported as "could not examine", never as a pass.

@sub 4.4.1|FILE METADATA AND CONTENT RULES
`backend/semantic.py` holds the rules that read the file and the text, with the guiding principle that a rule must be silent on ordinary pages. The text rules run only if at least 15 words were read with an OCR confidence of at least 60, and they read the text as rows rebuilt from the word positions: every word whose vertical centre lies within half a text height of a row's centre belongs to that row. Tesseract's own line identifiers put a label on the left and its amount on the far right of the same row into different lines, which silenced the arithmetic and running-balance rules on exactly the invoices and statements they are meant for (Section 7.15). Table {tab:rules} lists the rules.

@table rules|Rules that read the file and the text
Rule | Fires when | Severity
Editing software tag | the EXIF Software field names an image editor | high
Camera tags; GPS data | EXIF make or model; location fields are present | low
Generator watermark | OCR text contains the marker of a known fake-document generator | high
Placeholder name or number | a placeholder name ("John Doe", "Jane Doe", "Test User", "Lorem ipsum" and similar), a run of eight or more identical digits, or 123456789 or 987654321 | medium
Total below subtotal | a Subtotal and a Total are both read, the total is smaller and no discount line is present | high
Items do not add up | at least three item prices, a Subtotal, and no discount or quantity wording, and the sum differs from the Subtotal by more than one cent | medium
Weekday does not match date | a weekday, a day, a month and a year are read and the weekday is wrong for that date | high
Impossible or future date | within a date written with its weekday and year: the date does not exist, or (when the weekday matches) lies more than a day ahead | high; medium
IBAN or card number invalid | the mod-97 check of an IBAN fails, or a full card number fails the Luhn check | medium
Impossible clock time | hours above 24 or minutes above 59 | low
Duplicate status-bar clock | in an image at least 1.2 times as high as wide, an hh:mm time in the top strip of the image is repeated lower down; this rule runs inside the number-column check, so it applies only to screenshots with a column of at least eight numbers | low
@endtable

The first version of the arithmetic rule flagged any image showing both a "Balance" and a "Total", which describes an ordinary bank-application screen; it was removed and replaced by the narrower rules above, and a unit test now asserts that a page with a balance, transactions and a "Total Spent" line raises no finding.

@sub 4.4.2|TYPE-SPECIFIC RULES
Each rule in Table {tab:typedrules} runs only when its type was chosen (or confidently detected by a validated router) and says "could not examine" when the screenshot does not have the structure it needs.

@table typedrules|Type-specific rules (`backend/screencheck/checks.py`)
Type | Applies when | Finding
Payment receipt | a UPI reference or a payment status was read | the reference has a number of digits other than 12 (medium); the phrase "payment successful" or "payment completed" and one of "payment failed", "transaction failed", "payment declined" or "transaction declined" both appear (medium)
Bank statement | at least five rows each with an amount (or a debit and a credit column) and a balance, enough consecutive readable rows, and at least half of the links between rows follow balance = previous balance plus or minus amount, in oldest-first or in newest-first order, whichever fits | the failing links are one or two, consecutive, and at least three other links hold (medium); one changed balance breaks two links and one changed amount breaks one. A row with an unreadable number (a lost decimal point, "05" for 0.5) counts as a gap, not a link, because OCR often drops a decimal point; dates, times and long reference numbers are removed before the numbers of a row are read
Order or invoice | a subtotal or total line was read | the arithmetic rules of Table {tab:rules} fire on it
Chat | at least five message times were read, as 24-hour times or as 12-hour times with AM or PM written with or without a space ("8:43PM", "8:43 PM"); the top 7% of the image (the status bar) and, in a landscape window, the left third (the list of chats with their last-message times) are ignored | a time is more than 10 minutes earlier than the one before it, and by less than 10 hours, so that a day break is not mistaken for an error (low)
SMS, e-mail or notification | the word OTP, code or PIN is followed within 25 characters by 4 to 8 digits | the text also contains "OTP" or "verification code" and the code has a length other than 4, 5, 6 or 8, which only a seven-digit code can do because the pattern admits four to eight digits (low)
@endtable

@sub 4.4.3|THE LAYOUT-GRID RULE
Lists in payment, banking and shopping applications place one number per row in a column whose row spacing is constant to the pixel, and a value pasted by hand rarely lands exactly on that grid. The rule works on OCR boxes alone. It keeps numeric words of a similar size, clusters them on their right edge (tolerance 0.4 times the word height), keeps one number per row and requires a column of at least six rows (eight for every interior row to be testable). It uses the bottom edge of each box as the baseline, because digits have no descenders, and computes each interior row's deviation from the midpoint of its two neighbours. The row with the largest deviation is the candidate. The rule fires only if that deviation is at least the larger of 5 pixels and 0.2 of the text height, the other rows are regular (median deviation at most the larger of 1.5 pixels and 0.05 of the height, maximum at most the larger of 3 pixels and 0.1 of the height), the candidate dominates its neighbours by a factor of 1.5 (an edited row shifts its neighbours by half as much), and both gaps next to the candidate are between 0.6 and 1.4 times the median row pitch. The last condition was added after the first version, which did not have it, produced a 2.03% false-alarm rate: an OCR box missed in one row doubles a single gap, and without the condition that looked like an off-grid number (Section 7.12). The rule is silent when the column is not regular, which is the common case and by design, and the service applies the check only if some numeric column has at least eight rows; otherwise it reports that it could not examine the image.

@section 4.5|THE WORD-RENDERING MODEL
The second version scored every word for signs that it was drawn differently from its neighbours. It remains in the final service as an advisory check. Words and boxes come from Tesseract [@smith2007tesseract], version 5.5.3; every box is kept whatever its confidence, because discarding boxes below a confidence of 40 removed the edited word from analysis in about a third of the edited test images (Section 7.2). A word is measured only if its box is between 8 and 220 pixels high and at least 6 pixels wide, and its crop has enough contrast and ink.

Each measurable word is described by 95 features (`backend/textforensics.py`): 40 raw measurements in seven groups (edge and contrast profile, colour, strokes, background, seam along the border of the box, JPEG block grid, and two histograms), six geometry values, 38 robust z-scores that compare 19 of the measurements with all other words in the image and with the other words on the same line, and 11 line and histogram-distance features. The z-score of a value is the value minus the median of the comparison set, divided by 1.4826 times the median absolute deviation, floored and clipped. Word probabilities come from gradient-boosted trees [@friedman2001] as implemented in scikit-learn [@pedregosa2011] (the histogram-based estimator). The shipped model was trained on 808,445 labelled words, of which 10,582 are edited, and stopped after 848 iterations; a word is labelled edited when at least 30% of its box overlaps an edit rectangle and genuine when it overlaps by at most 2%.

The image score is the highest word probability. The maximum has a cost: an image with several hundred words gives the model several hundred chances to be wrong, so a flag threshold chosen per word produces a much higher flag rate per image. This was observed directly: an intermediate model flagged 11.0% of genuine full-size screenshots at the suspicious tier although it flagged only 2.1% of real test images cut into windows, until whole screenshots were added to the training data (Section 7.3.1). Two thresholds convert it into the tiers "suspicious" and "evidence": the scores exceeded by 5% and by 1% of 246 genuine real validation images, which gave 0.847 and 0.966. Reasons are generated, not learned: for a marked word the code lists the relative features with an absolute z-score of at least 3, translated into plain language, together with a few geometric reasons, and shows at most three. These explanations describe which measurements deviate; they are not a causal account of the edit.

The model is trained on generated edits (Chapter 5) and, in one experiment, on real tampered screenshots (Section 7.10). In the final service it fails its calibration gate (5 of 47 genuine items flagged, upper bound 0.23), so it is advisory: it can make the answer more cautious but can never raise a flag, for the reasons Chapter 7 gives.

@section 4.6|THE VERSION-1 PIXEL CUES AS HINTS
The five cues of the first version are kept as hint checks in `backend/screencheck/legacy_cues.py`, because they are what many readers expect a fake-screenshot detector to show: error-level analysis [@krawetz2007], a JPEG-ghost scan [@farid2009ghosts], the number of JPEG quantisation tables, noise-consistency statistics [@mahdian2009noise] and copy-move detection [@christlein2012eval]. The image is first reduced to at most 1,600 pixels on the long side. A cue reports a finding when its own score is at least 0.5. Error-level analysis, JPEG ghost and quantisation tables describe the compression history of a file, so for a lossless file they say that they could not examine the image. Two rules keep the hints honest. A check whose identifier starts with `v1.` can never be live, whatever its calibration says. And a hint that flagged at least half of at least 10 genuine screenshots is marked "uninformative": it is still listed, but it is not allowed to add caution to the verdict, since a flag that appears on almost every genuine screenshot says nothing. The measured behaviour is in Section 7.5.

@section 4.7|CALIBRATION GATES
`backend/screencheck/gates.py` implements the rule that decides whether a check counts. A check is live only if it was applicable on at least 20 genuine real screenshots and the upper end of the Wilson 95% interval [@wilson1927] of its false-alarm rate is at most 15%. A finding counts toward that false-alarm rate only if its severity is medium or high. Type-specific rules are calibrated on the genuine screenshots of their own type. The tool `backend/tools/calibrate_gates.py` measures every check on a folder of genuine screenshots and writes `model_data/gates.json`; with no gate file every check is advisory.

The numbers matter. With no false alarm at all, the Wilson upper bound is 16.1% for 20 genuine screenshots, 14.9% for 22 and 14.3% for 23. A threshold of 20 screenshots with a bound of 15% therefore cannot be met by 20 screenshots, and the smallest sample that can pass is 22, provided it contains no false alarm. One false alarm needs at least 34 screenshots and two need at least 45. The project's own genuine items passed for the two checks that apply to every screenshot (file metadata and content rules: 0 of 23 flagged at first, bound 14.3%, and 0 of 47 on the larger set of Section 7.16, bound 8%); the version-1 copy-move and quantisation cues also met the numbers but are hints by rule, and nothing else did.

@section 4.8|RECONCILING A SCREENSHOT WITH A SECOND SOURCE
@sub 4.8.1|READING THE FACTS
`backend/screencheck/fields.py` extracts six kinds of fact from text (amounts, dates, times, references, UPI identifiers and bare whole numbers). Dates in the common formats (ISO, day first with a slash, hyphen or full stop, day-month-year with a month name, month name first) are read day first, as on Indian bank and payment screens, and an impossible date such as 31 February is dropped. A day and a month with no year ("16 October", as Google Pay writes it) is kept as a day and a month. Bare whole numbers of two to six digits are kept separately, because whole-rupee amounts have no decimals. Times are converted to minutes since midnight, with am and pm handled. A reference number is a run of 10 to 22 digits, or three groups of four digits separated by spaces or hyphens, joined into one string. UPI identifiers are read with a pattern for `name@handle`. An amount is a number with a currency marker (the rupee sign, Rs or INR, or the characters that OCR commonly returns for the rupee sign), or with decimals, or with thousands grouping; a bare integer is not an amount, because it is too often a count, a year or part of an identifier. Digits that belong to a date, a time or a reference are removed before amounts are searched for.

OCR is the main source of error, so a screenshot is read twice: as it is, and enlarged twofold with Lanczos resampling. A value that both reads produce is called confident, and a value that either read produces is called present. A single misread digit therefore cannot become a confident wrong value. This protects against random misreads only: the rupee sign, which Tesseract reads as a leading digit, is misread the same way by both reads (Sections 7.17 and 7.18).

@sub 4.8.2|MATCHING
The facts of the second source (typed or pasted text, which needs no OCR, or an image, which is read the same twice-over way) are looked up in the screenshot one kind at a time. For references, amounts and dates (the hard facts) the result is matched if any one value of the second source is present in the screenshot (as either read); differs if the screenshot confidently shows (both reads agree on) other values of that kind and none of the source's values; and unclear otherwise, including when a value was seen in only one read. If no reference in the screenshot equals a reference of the second source but at least one differs from it by exactly one digit (a substituted, inserted or deleted digit), the result is near: it may be a misread, or it may be an edited digit, and it is never counted as agreement. A time matches if it is within five minutes of a time in the screenshot, because clocks and applications disagree slightly; a larger difference is reported but is not a hard fact.

@fig fig_reconcile|15.5|Reconcile mode: each fact of the second source is looked up in the screenshot, which was read twice.

Four further rules were added after the real-data tests of Sections 7.17 and 7.18. An amount that appears with one extra leading digit (18,063.17 against 8,063.17) is near, and so is a whole-rupee amount for which only a bare number, equal to it or with one extra leading digit, appears: a rupee sign read as a digit and an amount edited by prepending a digit look the same, so the person must look, and a bare number can never make an amount matched. A date given as a day and a month matches the source date with that day and month. And when a screenshot shows five or more dates it is treated as a list (a payment history, a statement), in which a payment that is not on the screen is not a conflict.

The overall status follows from the rows. Any differing hard fact is a conflict. Otherwise a near reference or a near amount means review. Otherwise the second source corroborates the screenshot only if every hard fact it supplied was matched (an amount the screenshot does not show, for example, blocks corroboration) and the reference matched, or both the amount and the date matched. A source with some matches but not enough is partial, and one with none is nothing matched. A source in which no fact of any kind (including times and UPI identifiers) can be found is reported as having no facts. UPI identifiers are extracted but not compared. Facts are matched as sets and are not tied to one row of a list.

@section 4.9|COMPARE MODE
When the person holds a genuine copy of the screenshot, compare mode (`backend/screencheck/compare.py`) needs no learned model and no assumption about how the edit was made. If the height-to-width ratios of the two images differ by more than 0.03, they cannot be compared and the service says so. Otherwise the suspect is resized to the original's size if needed, both images are blurred with a Gaussian of 1.4 pixels (compression noise sits at glyph edges, whereas an edit changes whole glyphs), and the largest per-channel difference is thresholded at 30 grey levels (38 if the image had to be resized). The mask is cleaned with a 3 by 3 opening, dilated by 5 pixels and split into connected regions; regions smaller than the larger of 60 pixels and 0.005% of the image area are discarded. Both images are also read by OCR and words that were changed, added or removed are listed, but a text difference counts only where the pixels differ as well, because OCR is unstable under compression. If either file is lossy the response carries a caution that small regions can be compression noise.
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
@chapter 7|RESULTS AND ANALYSIS

@section 7.1|AUDIT OF THE FIRST VERSION
The first version (preserved in `backend/legacy/`) combined error level analysis, a multi-quality JPEG-ghost scan, quantisation-table checks, block-wise noise statistics, copy-move detection, edge, font, status-bar-clock and arithmetic cues, EXIF and OCR rules, and a random forest trained on three photograph and receipt datasets. It was never run on screenshots that were known to be untouched until the audit reported here.

@sub 7.1.1|GENUINE SCREENSHOTS
Sixty genuine screenshots from the author's machine (59 PNG, 1 JPEG; none ever edited) were analysed. The first version flagged 12 of them, 20.0%, as fake. The cue scores follow. Three cues (ELA, block noise and edge sharpness) were non-zero on 59 of the 60 images and sat near the top of their range, and a fourth, the JPEG ghost, was non-zero on 46, so they could not be distinguishing anything: the ELA and edge cues averaged 0.85. The composite score of genuine screenshots averaged 0.385 with a maximum of 0.626, close to the 0.5 decision threshold.

Table-free summary: error level analysis, edge sharpness and block noise had a mean score of 0.845, 0.845 and 0.755 and were non-zero on 59 of the 60 images; the JPEG ghost averaged 0.496 (non-zero on 46); copy-move 0.086 (52); font consistency 0.019 (2); the editor-tag and watermark cues were zero everywhere (`fp_results.json`).

The quantisation, status-bar-clock and arithmetic cues were zero on all 60 images. The lossless format of these screenshots explains part of the saturation: error level analysis and quantisation checks presuppose lossy compression [@krawetz2007], and 59 of the 60 files were PNG. That is an explanation consistent with the data, not a tested cause.

@sub 7.1.2|REALISTIC EDITS
In this experiment a second draw of sixty PNG screenshots was made, 28 of whose 42 qualifying files also belong to the sixty audited in Section 7.1.1. Forty-two of the sixty contained a word that qualified for editing (OCR confidence at least 85, at least four characters, height 12 to 60 pixels). In each, one word, preferring words with digits, was painted over with the surrounding background colour and re-typed in Helvetica with each digit shifted, a plausible careless edit. Every image set contained the untouched original, the edited image and each of the two saved as JPEG at quality 85.

For the 42 image sets the first version flagged 6 of 42 originals and 6 of 42 edits as PNG (mean scores 0.367 and 0.366) and 5 and 5 as JPEG at quality 85 (0.359 and 0.359).

The AUC for separating edited from original images was 0.496 for PNG and 0.501 for JPEG. For the PNG variants the edit changed the score by a mean of minus 0.0013, raised it in 8 of 42 sets and lowered it in 18, and in no set did an original that had not been flagged become flagged after its edit. The first version was therefore unable to tell a re-typed word from the untouched screenshot.

@sub 7.1.3|TWO FURTHER FAILURES
A bank page rendered by Chrome and the same page with two amounts changed in the HTML were both flagged "fake" because the arithmetic rule treated the page's "Balance" and "Total Spent" lines as contradictory (scores 0.495 and 0.416); three pixel cues were equal on the two pages (ELA 0.881 and 0.880, noise 0.940 and 0.937, edge sharpness 0.937 and 0.934) and the JPEG-ghost cue scored the untouched page higher than the edited one (0.717 against 0.433). An EXIF Software tag naming an image editor raised the score from 0.412 to 0.804, but the same pixels saved without the tag returned to the baseline (`v1_native_check.txt`, `v1_native_cues.txt`). These findings defined the redesign.

@section 7.2|THE SECOND VERSION ON THE GENERATED CORPUS
Five hundred test images (340 edited) were drawn at random from the test split and scored by the first version and by the second (Table {tab:v1v2}). The first version scored an AUC of 0.459, flagged 10.6% of genuine and 7.4% of edited images, and so flagged genuine images more often than edited ones. The second version reached an AUC of 0.838 and flagged none of the genuine images at its evidence tier and 0.6% at its suspicious tier, while flagging 29.4% and 43.8% of edited images.

@table v1v2|First and second versions on 500 test images
System | AUC | Genuine flagged | Edited flagged
First version | 0.459 | 10.6% | 7.4%
Second version, evidence tier | 0.838 | 0.0% | 29.4%
Second version, suspicious tier | 0.838 | 0.6% | 43.8%
@endtable

The comparison is not an indictment of the cues themselves: the test images are generated screenshots with simulated edits, and the first version was designed for different data. On the full test set of 3,237 images (2,184 edited) from base images and edit fonts unseen in training the second version reached an image-level AUC of 0.847; at the evidence tier it caught 31% of edited images and flagged 0.3% of genuine ones, and at the suspicious tier 43% and 1.0% (word-level AUC 0.983, validation AUC 0.846). For the real-screenshot part of the test set the AUC was 0.825, with 46% of simulated edits caught and 2.1% of genuine real images flagged at the suspicious tier. The gap between the word-level and image-level AUC is consistent with the maximum over many words (not tested): the model ranks individual words well, but one genuine word with a high score can outrank an image's true positive.

By sharing step, on the test edits, the second version's AUC was 0.912 for lossless PNG (725 edited images; 43% caught at the evidence tier and 56% at the suspicious tier), 0.882 for JPEG at quality 55 to 98 (771 images; 36% and 49%), 0.729 for down-scaling then PNG (290 images; 11% and 23%) and 0.718 for down-scaling then JPEG (398 images; 13% and 20%).

Lossless edits are the easiest and JPEG sharing costs a few points. Down-scaling is the weak case: the AUC falls to 0.72 to 0.73 and fewer than a quarter of edits are caught at either tier. Resampling smooths exactly the anti-aliasing and stroke measurements the method relies on, in line with the general observation that resampling alters pixel statistics [@popescu2005resampling]. Section 7.10 returns to this effect with public real edits.

A classifier that sees edits made only by one text renderer could learn the renderer's signature instead of the edit. A model trained on Pillow edits only reached an image-level AUC of 0.846 on held-out Pillow edits and 0.752 on Chrome edits; one trained on Chrome edits only reached 0.783 and 0.855; the shipped model, trained on both, reached 0.849 and 0.844 (`cross_engine.txt`).

Transfer across engines is real but incomplete: a model trained on one engine scores 0.75 to 0.78 on the other, against 0.85 to 0.86 on its own. With only two engines it cannot show that a third (Photoshop, Canva, a phone editor) would be handled as well, and the true figure on such edits is unknown.

The second version is the result of several corrections, each prompted by a measurement (the steps overlap and show direction and rough size, not isolated causes). Keeping every OCR box whatever its confidence raised the share of test edits in which the edited word was measurable from 67.4% to 90.2% (`ocr_recall_check.txt`); skipping single-glyph boxes, adding real windows and weighting real samples threefold lowered the share of real test images flagged at the pooled 5% threshold from 24.5% to 7.8%, and calibrating on real validation images, a larger model and the Chrome-patch edits to 2.1% (`train_final_v6.log`); adding whole real screenshots lowered the full-size genuine screenshots flagged at the suspicious tier from 11.0% (8 of 73) to 5.5% (4 of 73); training on both edit engines raised the AUC on Chrome edits from 0.752 to 0.844; and a second-stage model over the word probabilities lowered the maximum-word AUC from 0.824 to 0.809 and was not adopted.

The first correction deserves a comment. A word set in an unfamiliar font is the kind of word on which Tesseract tends to be least confident, so a confidence filter silently removed a third of the edits from consideration before the classifier saw them. The same pipeline run after the change keeps the edited word in analysis for 90.2% of test edits (94% for PNG and JPEG, 81 to 82% after down-scaling). The remaining misses include words that OCR does not return at all.

@section 7.3|THE SECOND VERSION ON REAL SCREENSHOTS
@sub 7.3.1|GENUINE SCREENSHOTS THE MODEL NEVER SAW
The leave-files-out protocol (Section 5.6) is the closest test to real use for the second version. The result for the 73 real files, each scored whole by a model trained without any window of it, together with 426 edited copies, is as follows.

On the 73 real files the second version flagged 4 of 73 genuine screenshots at the suspicious tier (5.5%; Wilson 95% interval 2.2% to 13.3%) and 0 of 73 at the evidence tier (0.0% to 5.0%), and caught 191 of 426 edited copies (44.8%) at the suspicious tier and 103 (24.2%) at the evidence tier; after PNG sharing and JPEG sharing it caught 53% and 55% (28% and 36% at the evidence tier), after down-scaling 32% and 24% (12% and 8%); the image-level AUC was 0.805.

The sample is small and comes from one person's machine, so the intervals are wide: a false-alarm rate between about 2% and 13% is consistent with 4 of 73. The edited copies are up to six per file and therefore not independent, so no interval is given for the detection rates. An intermediate model, trained before whole real screenshots were added, flagged 8 of 73 (11.0%, interval 5.7% to 20.2%) with an AUC of 0.771. An earlier version of the script that computed this experiment trained on the validation images it then used to set thresholds, which makes thresholds too low; the fault was noticed and the script corrected, and the numbers above come from the corrected script (no output of the faulty run was kept).

@sub 7.3.2|A SAMPLE OF REAL EDITS
Eight screenshots from a payment-application history were collected: four edited by a person with their own tools, and four genuine. Each edit was identified by comparing the edited screenshot with its genuine counterpart. The images are personal and are not reproduced here. For the second version: in image 3 an amount was changed (75 to 79) and placed about 14 pixels above its row, and the verdict was suspicious through the layout rule (the classifier alone scored 0.11); in image 4 an amount was set in a thinner, italic font, and the verdict was evidence of editing (top word probability 0.979); in image 5 an amount was replaced by a shorter plain one (the plus sign and thousands separator dropped), and in image 6 a short amount was set in a different serif font and OCR read it as "ad", and both were called no evidence (top word probabilities 0.27 and 0.34); the four genuine images 7 to 10 were all no evidence, with highest word probabilities 0.31, 0.24, 0.12 and 0.06.

Two of the four edits were flagged and none of the four genuine images. The sample is far too small to estimate rates and it is development data: the eight images were used to find the blind spot that led to the layout rule and to test the column idea of Section 7.13. The edited and genuine images also differ in resolution and file type, so the edited files appear to have been exported at a different scale than the originals; this confounds the comparison and is itself a realistic property of forged files.

@sub 7.3.3|THE SECOND REAL SET, SCORED ONCE
After the second version was final, the second real set of Section 5.2 was scored once with the shipped model, and nothing was changed in response (the result follows).

On the second real set the second version flagged 3 of the 23 genuine screenshots at the suspicious tier (13.0%; Wilson 95% interval 4.5% to 32.1%) and 2 of the 9 edited screenshots (22.2%; 6.3% to 54.7%), and none at the evidence tier.

Two of the nine edits were flagged and none reached the evidence tier. For one flagged edit the marked word lies in the area that differs from the original; for the other the marked word is not in the changed area. All three bank-statement edits were missed. Three of the 23 genuine screenshots were flagged (one bank screenshot, one incoming-payment image and one in the social media, e-mail and notification category); the flagged bank screenshot is the original of one of the missed edits, and its edited copy scored lower than it did. The overlap test used here is lenient, because re-compression broadens the changed area. The point estimates are lower than the simulated-edit detection rates, but the interval for 2 of 9 includes them, so this set does not settle how well real edits are caught; it gives no reason to expect the detection rates of simulated edits on real ones. This result, together with the failure of the first version, is what led to the design of Chapter 3.

@section 7.4|THE FINAL PIPELINE ON THE SECOND REAL SET
The same 32 screenshots were run through the final service (Table {tab:v3real}); no type was chosen, so the automatic guess was used, which is only tentative.

@table v3real|Final pipeline on the second real set (23 genuine, 9 edited)
Measure | Genuine (23) | Edited (9)
Verdict | inconclusive: 23 | inconclusive: 9
Assurance level | level 1: 23 | level 1: 9
Live findings | 0 | 0
Advisory word-rendering finding | 3 | 2
Automatic type answered (tentative) | 18 of 23 | 7 of 9
Seconds per image, median (maximum) | 1.09 (2.08) | 1.12 (2.06)
@endtable

Every one of the 32 screenshots was inconclusive and reached assurance level 1, genuine or edited. This is the intended behaviour of the policy and also its plainest limit: no live check found a contradiction in any of them, so there was nothing to flag, and level 1 ("no contradiction found, still unverified") is reached by every screenshot whose text could be read and checked. No live check found a contradiction in the edited screenshots. The type-specific rules, which need the person to choose the type, were not run here, so whether the edited content is self-consistent was not established by this run; the only signal that leaned the right way, the advisory word-rendering finding, fired on 3 of 23 genuine and 2 of 9 edited screenshots, the same numbers as in Section 7.3.3. The level therefore tells the reader how much was examined, not whether the screenshot is genuine, and the interface says so.

@section 7.5|CALIBRATION GATES AND THE VERSION-1 HINTS
Table {tab:gates} gives the calibration of every check on the 23 genuine screenshots (type-specific rules on the screenshots of their own type), with the decision that follows.

@table gates|Calibration of the checks on the genuine real screenshots (n: screenshots on which the check applied; flagged: findings of medium or high severity)
Check | n | Flagged | Upper bound (95%) | Decision
File metadata | 23 | 0 | 0.143 | live
Content rules | 23 | 0 | 0.143 | live
Number-column layout rule | 2 | 0 | 0.658 | advisory (too few)
Word-rendering model | 23 | 3 | 0.321 | advisory (bound above 0.15)
Version-1 error-level analysis | 15 | 15 | 1.000 | hint, not informative
Version-1 JPEG ghost | 15 | 10 | 0.848 | hint, not informative
Version-1 quantisation tables | 15 | 0 | 0.204 | hint
Version-1 noise consistency | 23 | 23 | 1.000 | hint, not informative
Version-1 copy-move | 23 | 0 | 0.143 | hint by rule (would otherwise pass)
Payment-receipt rules | 8 | 0 | 0.324 | advisory (too few)
Order or invoice rules | 2 | 0 | 0.658 | advisory (too few)
Bank-statement, chat and one-time-code rules | 0 | 0 | 1.000 | advisory (never applied)
@endtable

Only two checks count, and both are of the kind that apply to every screenshot. No visual check is live, so the verdict can never reach "no inconsistency found" (Section 3.6). Four findings stand out. The word-rendering model fails the gate (3 of 23 flagged, upper bound 0.32). Error-level analysis flagged all 15 genuine screenshots it applied to (the lossy ones), noise consistency all 23 and the JPEG ghost 10 of 15, so they carry no information and are marked as such; this is the same saturation that the first audit found on a different set (Section 7.1.1). Copy-move detection flagged none of the 23 and would have passed the gate, but it is a hint by rule, not a verified detector: nothing in this report measures its recall on the edits of interest. And the type-specific rules were applied on too few genuine screenshots of their types to be measured, which is the reason for the shortened list of screenshots in `docs/SCREENSHOTS_NEEDED.md`: 22 genuine screenshots with no false alarm would be enough to switch a rule on, and 34 if one false alarm occurs. Section 7.16 repeats the calibration on 47 genuine items.

@section 7.6|THE TYPE ROUTERS
The two routers were scored on the 23 genuine screenshots with hand-assigned types (Table {tab:routers}).

@table routers|Type routers on 23 genuine real screenshots
Router | Answered | Correct of those answered | Accuracy (Wilson 95% interval) | Validated
Content (reads the words) | 18 of 23 | 18 of 18 | 1.00 (0.82 to 1.00) | no, needs 60 labelled screenshots
Structure (layout only, trained on 640 generated screenshots) | 23 of 23 | 4 of 23 | 0.17 (0.07 to 0.37) | no
@endtable

The router that reads the words was right every time it answered, which is encouraging but rests on 18 screenshots. The router that looks only at layout, trained on generated Chrome screenshots (held-out accuracy 0.925 on generated images), was right on 4 of 23 real screenshots: the same failure of generated data to carry over that appears in the other experiments. It is not used. Neither router meets the validation bar of Section 4.3, so the automatic guess stays tentative, and the person's own choice of type is what enables the type-specific rules.

@section 7.7|COMPARE MODE
Compare mode was run on the nine edit pairs and on 27 harmless re-saves (Table {tab:compare}). The file names are those of the edited screenshots: E for bank statements, I for web pages and O for orders or invoices; the originals of the web pages are named L_01 to L_03.

@table compare|Compare mode on the nine edit pairs (original against edited)
Pair | Regions marked | Text changes listed
E_01 (bank statement, JPEG) | 1 | 0
E_02 (bank statement, PNG) | 2 | 1
E_03 (bank statement, WebP) | 2 | 1
I_01 (web page) | 6 | 0
I_02 (web page) | 5 | 10
I_03 (web page) | 2 | 0
O_01 (order or invoice) | 2 | 3
O_02 (order or invoice) | 4 | 3
O_03 (order or invoice) | 4 | 3
@endtable

Differences were found in all nine pairs (9 of 9; Wilson 95% interval 70% to 100%), including the three bank-statement edits that the word-rendering model missed. For the controls, each of the nine originals was re-saved as JPEG at quality 80, at quality 60 and down-scaled to 0.75 with JPEG at quality 85, and none of those copies should show a difference. Three of the 27 were wrongly flagged (11.1%; interval 3.9% to 28.1%): two of the web-page originals (L_01 and L_02), at JPEG quality 60 in two cases and at the down-scaled setting in one, each marking a very small area (0.007% to 0.059% of the image). The mode is therefore sensitive and not free of false alarms on heavily compressed copies, which is why the response carries a caution when either file is lossy. Its limit is the need for a genuine copy with the same proportions, and an edit made before that copy was saved is invisible to it.

@section 7.8|RECONCILE MODE: A MUTATION TEST ON THE REAL SCREENSHOTS
Reconcile mode needs a second source that is independent of the sender. This first test uses the real screenshots but builds the second source from the screenshot's own facts, so it checks the logic and not the independence, and it cannot expose a misread that both OCR reads share; Sections 7.17 and 7.18 test against real and against ground-truth sources. Of the 32 real screenshots of the second real set, 17 contained enough facts (a reference number, or an amount and a date) to build a source from; the other 15 did not. For each of the 17, a faithful second source was built from the screenshot's facts and then one fact was changed (Table {tab:mutation}).

@table mutation|Reconcile mode on 17 real screenshots (faithful and altered second sources)
Second source | Result | Screenshots
Faithful | corroborated | 17 of 17
One digit of the reference changed | review (a reference differs by one digit) | 4
Amount changed | conflict | 3
Amount changed | review (one extra leading digit) or partial | 1 and 1
Date changed | conflict | 7
Date changed | partial (the screen lists many dates, so a missing date is not a conflict) | 1
@endtable

All 17 faithful sources were corroborated (interval 82% to 100%) and none of the 17 altered sources was corroborated: 10 were conflicts, 5 were sent for review and 2 stayed partial. The numbers differ from the first run of this test, which gave 12 conflicts, 4 reviews and 1 partial; the changes come from four repairs made after the real-data tests of Sections 7.17 and 7.18 (a date given as a day and a month matches the source date, an amount with one extra leading digit is a review, a screen with many dates is treated as a list, and whole-rupee numbers are matched only as "near"). An earlier version of the rule also corroborated an altered amount when the reference still matched, because the amount was merely "not found"; it now requires every hard fact the second source supplies to be matched (no output of that earlier rule was kept).

@section 7.9|THE FINAL PIPELINE ON STFD
All 3,932 STFD screenshots were run through the service (Table {tab:stfdrun}); every image is a lossless PNG, so pixel reliability was high for all.

@table stfdrun|Final pipeline on 3,932 public tampered screenshots (the type was not chosen)
Edit type | Images | Verdict suspicious | Live finding | Advisory rendering flag | Flag meets the edit mask
Copy-move | 758 | 2 | 9 | 178 (23.5%) | 50 (28.1% of flags)
Splicing | 830 | 1 | 28 | 216 (26.0%) | 74 (34.3%)
Removal | 1,016 | 0 | 20 | 234 (23.0%) | 4 (1.7%)
Insertion | 701 | 0 | 26 | 246 (35.1%) | 117 (47.6%)
Replacement | 627 | 1 | 15 | 182 (29.0%) | 35 (19.2%)
All | 3,932 | 4 (0.1%) | 98 (2.5%) | 1,056 (26.9%) | 280 (26.5%)
@endtable

The service called 3,928 of the 3,932 images inconclusive and 4 suspicious. The 98 images with a live finding all came from the content rules; Section 7.19 inspects them by rule. The word-rendering model flagged 27% of the images, and in 26.5% of those flags a marked region met the mask of the real edit. Of the version-1 hints, noise consistency raised a finding on 3,908 of the 3,932 images (99.4%) and copy-move on 61 (1.6%); error-level analysis, JPEG ghost and quantisation tables could not examine these lossless files. It does best on insertions (47.6%) and worst on removals (1.7%); a plausible reason, not tested, is that after a removal there is no inserted word to measure. This is not a detection rate against a baseline: the chance that a marked region meets a mask of median size 0.41% of the image was measured only roughly (a random-word baseline is in Section 7.19), and STFD has no genuine images from which to measure false alarms. The automatic type was "unknown" for 3,649 images (92.8%), and the answered types were social post (268), payment receipt (9), web page (2), bank statement (2) and message (2), so STFD cannot be used to validate the routers.

@section 7.10|TRAINING THE WORD MODEL ON REAL EDITS
@sub 7.10.1|LABELS, SPLIT AND RESULT ON CLEAN IMAGES
From the 3,932 images, 196,422 words were measured: 12,085 edited, 173,598 unedited and 10,739 ambiguous (dropped). The 3,932 images fall into 2,516 groups of near-identical source screenshots (the largest has 36 images), and the groups were split 70/15/15: 129,912 training words (8,554 edited), 27,555 validation words (1,782 edited) and 28,216 test words (1,749 edited). A boosted-tree model with the 95 features was trained on the training words (300 iterations, learning rate 0.06, 15 leaves, balanced class weights). On the held-out test words the word-level AUC was 0.806 (validation 0.795), against 0.562 for the shipped model trained on generated edits scored on the same words. By edit type the AUC was 0.711 for copy-move, 0.745 for splicing, 0.965 for insertion and 0.934 for replacement; removal is not reported (fewer than five edited or unedited words in the test split). With thresholds set at 5%, 1% and 0.1% of the unedited validation words, the model caught 43.5%, 22.6% and 9.4% of edited test words, with 6.2%, 1.3% and 0.18% of unedited test words flagged.

So a model trained on real edits is a large improvement over one trained on generated edits, when both are tested on the real edits. That is the answer to the question this experiment was designed to ask. The model ranks the words of the two edit types that put new text into the image best (0.965 and 0.934); the per-type AUC of the shipped model was not recorded, so the size of the gain by type is not known.

@sub 7.10.2|WHAT RE-COMPRESSION DOES
The real set that the service will meet has been shared through messaging applications, whereas the STFD files, as obtained, are lossless PNG with no recorded sharing history. The experiment was repeated on a degraded copy of STFD (long side at most 1,600 pixels, JPEG quality 60 to 90), with 179,451 words (11,140 edited, 156,684 unedited). Table {tab:stfdmodels} compares three models, with thresholds set at 5% and 1% of unedited degraded validation words.

@table stfdmodels|Word-level AUC of models trained on clean, degraded and both kinds of STFD images, and results on the second real set
Model trained on | AUC, clean test | AUC, degraded test | Edited words caught, degraded test, at 5% | Real set: image AUC | Real set: genuine flagged at 5% (of 23) | Real set: edits caught at 5% (of 9)
Clean images | 0.806 | 0.665 | 16.7% | 0.623 | 13 | 6
Degraded images | 0.694 | 0.733 | 22.4% | 0.452 | 15 | 5
Both | 0.793 | 0.732 | 23.5% | 0.495 | 15 | 4
@endtable

@fig fig_stfd_auc|14|Word-level AUC of the three models on the clean and on the degraded STFD test words.

Re-compression costs the clean-trained model 0.14 of AUC (0.806 to 0.665). Training on degraded images recovers only part of it (0.733), and on degraded words the false-alarm rate at the chosen point is about 5% to 6% for all three models, with 17% to 24% of edited words caught. On the project's own 32 real screenshots no model separates the classes: the image-level AUC is 0.62, 0.45 and 0.50, and at the 5% word-level point the models flag 13 to 15 of the 23 genuine screenshots (57% to 65%), probably because an image is flagged if any one of its many words is flagged (not tested separately). At the 1% word-level point they flag 3, 2 and 2 of the 23 genuine screenshots and catch 4, 0 and 3 of the 9 edits. With 32 images these numbers show no more than that the gain on STFD does not carry over to the owner's screenshots; an AUC of 0.45 is not distinguishable from chance on 9 edits. Section 7.19 repeats the clean-image result over five grouped splits.

@section 7.11|FALSE ALARMS ON GENUINE SCREENS OF ANOTHER DOMAIN
Because STFD has no genuine images, the genuine Rico screens (Section 5.5) were used to see how often each word model flags a genuine screen (Table {tab:rico}).

@table rico|Genuine Rico screens flagged by the word models (276 screens with at least six measurable words)
Model | Threshold | Flagged
Trained on clean STFD | 0.569 (5% of unedited degraded validation words) | 215 (77.9%)
Trained on clean STFD | 0.669 (1%) | 139 (50.4%)
Trained on clean and degraded STFD | 0.673 (5%) | 221 (80.1%)
Trained on clean and degraded STFD | 0.762 (1%) | 111 (40.2%)
Second version, trained on generated edits | 0.847 (5% of real genuine images) | 74 (26.8%)
Second version, trained on generated edits | 0.966 (1%) | 40 (14.5%)
@endtable

@fig fig_rico_fa|14|Share of the 276 genuine Rico screens flagged by each word model at its two thresholds.

The models trained on real edits flagged 40% to 80% of genuine screens of a domain they had not seen, far above the 5% and 1% they were set for at the word level; the second-version model, whose thresholds were set on whole genuine real images, flagged 14.5% to 26.8%. The explanation that fits is the one given in Section 4.5: an image has many words, so a flag threshold chosen per word produces a much higher flag rate per image, and the threshold of a model trained on one population does not transfer to another. That explanation was not tested separately. For the live checks, 300 Rico screens were run through the service: all 300 were inconclusive, the content rules raised a live finding on 2 (0.7%; Wilson interval 0.2% to 2.4%), and the number-column layout rule applied to only 2 of the 300 and raised a finding on 1 of those 2. The Rico screens are not the intended population, so these numbers are a stress test and not a calibration.

Taken together, Sections 7.9 to 7.11 are the reason the word-rendering model is advisory in the final service. With real edits it learns something real, but its false-alarm rate on whole genuine screenshots of two different kinds is far above the bound of 15%, and re-compression removes much of what it learned.

@section 7.12|THE LAYOUT-GRID RULE
The rule of Section 4.4.3 was written after the second version missed an edited amount on a real payment-history screenshot (Section 7.3.2) and was therefore tuned while looking at that example. Its false-alarm rate was measured on the whole generated corpus, using word boxes only (the counts follow).

Over 6,656 genuine corpus images the first version of the rule raised 135 false alarms (2.03%; interval 1.7% to 2.4%): 112 of 3,200 Chrome-rendered images, 1 of 1,657 Pillow-rendered and 22 of 1,799 real; the final version raised 6 (0.09%; 0.0% to 0.2%), all among the Chrome-rendered images, and none among the Pillow-rendered and real ones.

Inspection of some of the first version's false alarms (the list of all cases was not kept) showed lists where one row had been skipped by OCR, so a single gap was twice the row pitch. Requiring both gaps next to the candidate to be near the normal pitch removed these. Recall was measured by shifting one row of a genuine list vertically by a fraction of the text height: 0.1% at a shift of 0.1 text heights, 1.3% at 0.2, 7.7% at 0.3, and 15.5% and 15.2% at 0.5 and 0.8, with 1,236 images at each shift. Recall stops rising at about 15%, which suggests that the rule applies to roughly that share of images with a numeric column (applicability was not counted separately), and it named the displaced number in 191 of 191 cases at a shift of 0.5. The rule is therefore precise where it applies, and narrow. On the project's own real screenshots it applied to only 2 of the 23 genuine ones, and on the Rico screens it applied to 2 of 300 and raised a finding on 1 of those 2 (Section 7.11), so it remains advisory.

@section 7.13|A NEGATIVE RESULT: COMPARING NUMBERS WITH THEIR COLUMN
In the eight real images of Section 7.3.2 each edited amount stood out from the other amounts in its column on stroke thickness and edge sharpness (robust z-scores of 3.6 to 9.0 and 7.1 to 29.8), while no genuine amount in the four real screenshots exceeded 2.6. It was tested two ways and rejected. As 22 extra features the held-out AUC was 0.848 against 0.847 and the three missed edits still scored 0.14, 0.19 and 0.20. As a rule it fired on 10.2% of 49 genuine real images, 19.7% of 493 genuine Chrome images and 2.4% of 42 Pillow images, and on a similar share of edited ones; raising the thresholds lowered but did not remove the false alarms (8.2% of genuine real images at a sharpness z of 12). Across the corpus the z-scores were saturated even on genuine images (`negative_results.txt`). The idea was not shipped. It is kept as a warning about conclusions drawn from eight images that were also used to design the test; Section 7.10 is another case of a model that worked on one population and did not carry over to the next.

@section 7.14|SPEED
The final service analysed the 32 real screenshots in a median of 1.09 seconds (maximum 2.08 seconds) for the genuine ones and 1.12 seconds (maximum 2.06 seconds) for the edited ones, with the version-1 hints included, on a machine that was running other jobs; an earlier run on a quieter machine gave medians of 0.62 and 0.66 seconds. Reconcile mode reads the screenshot a second time, enlarged twofold, so it takes longer; that time was not measured separately. The word-level model was measured earlier on larger images and was slower for 5.9-megapixel desktop captures, which took 1.7 to 6.8 seconds in the second version (`latency_large.txt`).

@section 7.15|MUTATION TEST OF THE CONTENT RULES
The real screenshots contain no contradictions for the content rules to find, so they cannot measure the rules' recall. The mutation test of Section 5.6 (protocol 16) does: 16 kinds of mutation with 30 documents each, and 100 clean documents of each of six types, which is 1,080 rendered documents; each was run through the real pipeline with OCR as a lossless PNG and as a shared copy, 2,160 runs in all (Table {tab:mutrecall}). The statement documents come in two layouts: oldest first with an amount and a balance, and newest first with debit, credit and balance columns, as in a real e-statement.

@table mutrecall|Documents in which the rule's contradiction was injected and the rule fired (30 per mutation; shared = down-scaled 0.75, JPEG quality 75)
Mutation (rule that should fire) | PNG | Shared | Verdict moves, PNG
Weekday wrong for the date | 30 of 30 | 30 of 30 | 30
Date in the future | 30 of 30 | 30 of 30 | 30
Total below subtotal | 30 of 30 | 29 of 30 | 30
Item prices do not add up | 27 of 30 | 25 of 30 | 27
IBAN digit changed | 27 of 30 | 28 of 30 | 27
Card number digit changed | 30 of 30 | 30 of 30 | 30
Placeholder name | 30 of 30 | 30 of 30 | 30
Generator watermark | 30 of 30 | 30 of 30 | 30
Impossible clock time | 30 of 30 | 30 of 30 | 2
Running balance, a balance changed | 28 of 30 | 27 of 30 | 0
Running balance, an amount changed | 29 of 30 | 28 of 30 | 0
UPI reference of 11 or 13 digits | 30 of 30 | 30 of 30 | 0
Success and failure both shown | 30 of 30 | 29 of 30 | 0
Chat time out of order | 27 of 30 | 27 of 30 | 0
One-time code of seven digits | 30 of 30 | 30 of 30 | 0
Number off the grid of a list | 29 of 30 | 29 of 30 | 0
@endtable

Each mutation kind was caught in 25 to 30 of the 30 documents, as PNG and after down-scaling and JPEG compression (Wilson 95% intervals from 66% to 93% for 25 of 30 up to 89% to 100% for 30 of 30). The least robust are the item-sum rule (OCR sometimes loses the decimal point of a price, so a row drops out of the sum), the IBAN checksum (in two of the three misses as PNG the check digits after the country code were misread, for example "GBO3" for "GB03", so the number was not recognised as an IBAN; the cause of the third was not found) and the chat-time rule (small time stamps are the text OCR drops or garbles first; in the three PNG misses that were re-rendered and examined, OCR returned the times without their colons, split from AM or PM, or not at all). The last column shows what the calibration gates do: only the rules behind the live content check move the verdict, and the type-specific rules and the layout rule never do, because they are advisory (Section 7.5). The impossible-time rule has low severity and cannot move the verdict by itself; the two moves in its row come from a false item-sum finding that OCR produced on the same invoices.

On the 600 clean documents a medium or high finding was raised on 10 as PNG (1.7%; interval 0.9% to 3.0%) and on 14 as shared copies (2.3%; interval 1.4% to 3.9%): the item-sum rule on 2 and 9 of the 100 clean invoices, the running-balance rule on 3 and 5 of 100 clean statements, and the number-grid rule on 3 of 100 lists and 2 of 100 statements as PNG and on none as shared copies; payment, chat and one-time-code documents raised none. A false item-sum finding is a live finding and so can move the verdict; this rate (up to 9 of 100 shared invoices) is the largest false-alarm figure of any live rule in this report, and the gates cannot show it because the real invoices are few. Of the 1,200 clean runs, 22 ended at assurance level 0 and 1,178 at level 1; of the 960 runs with an injected contradiction, 874 ended at level 0.

The test also found two defects that no earlier measurement had revealed, each repaired at once (Table {tab:defects} lists every defect found by testing). First, the arithmetic and running-balance rules were silent on documents whose label and amount lie far apart: with Tesseract's own line grouping the recall of the four mutation kinds concerned was 0, 0, 0 and 1 of 30 on the earlier document set (0 and 2 of 30 for the two balance kinds when the old row grouping is run on the current generator), although the unit tests passed because they used words with the same line identifier. The rules now read rows rebuilt from the word positions (Section 4.4.1). Second, once the rows were rebuilt, a row whose amount OCR had misread (a lost decimal point, "05" for "0.5") broke the running balance falsely in an intermediate run (its output was not kept); such rows are now gaps. The item-sum rule needed the same treatment, which was applied after an independent check of the results found it (it is counted with the second defect in Table {tab:defects}). The repairs changed nothing in the measurements on real screenshots: the live checks still flagged 0 of 23 genuine screenshots and 2 of 300 Rico screens, and the 32 screenshots of the second real set gave the same verdicts and levels (Table {tab:v3real}).

Three limits must be read with these numbers. The documents are rendered by the project in six fonts from consistent facts under clean OCR conditions; the mutations are exactly the contradictions the rules look for, so the recall is an upper bound and says nothing about how often a real forger leaves such a contradiction (the nine real edits of Section 7.4 left none that a live rule found). The clean documents are easy in their layout, and their false-alarm figures are not a substitute for the measurement on genuine real screenshots that the gates require. And seven of the 16 mutation kinds test rules that are advisory in the service (six distinct rules), so their recall does not change any verdict. What the test does establish is that each rule can fire on the contradiction it was written for, through OCR and compression, which the real sets could not show.

@section 7.16|FURTHER GENUINE SCREENSHOTS: CHATS, PAYMENT LISTS AND BANK STATEMENTS
Twenty-four more genuine items were added after the main measurements: 11 chats (5 WhatsApp in a desktop window, 3 WhatsApp on a phone, 3 Instagram conversations), 4 Google Pay transaction lists, and 9 pages of five bank e-statement PDFs (an account in another currency than the rupee, rendered at 150 dpi; they are documents opened on screen, not phone screenshots). All are private and are kept out of the repository. Each was run through the service with the type chosen (Table {tab:new24}).

@table new24|Final pipeline on 24 further genuine items (type chosen by the person)
Measure | Chats (11) | Payment lists (4) | Statement pages (9)
Verdict | inconclusive: 11 | inconclusive: 4 | inconclusive: 9
Assurance level | level 1: 11 | level 1: 4 | level 1: 7; level 0 (possible issue): 2
Live finding | none | none | impossible clock time, low severity: 2
Word-rendering model | flagged: 2 | flagged: 0 | flagged: 0
Type-specific rule | applied, found nothing: 5; could not examine: 6 | applied, found nothing: 1; could not examine: 3 | applied, found nothing: 7; could not examine: 2
@endtable

No counted check flagged any of the 24. The two statement pages at level 0 each carry a low-severity "impossible clock time" finding from the content rules; in both pages it was a transaction time in the first column of the statement that OCR misread (an hour of 28 or 42, where the neighbouring rows read 23 and 12), so it is an OCR artefact and the service labels it a possible issue and not a contradiction (Section 3.7). The more important results are about the type-specific rules, which real data changed twice. When the chat rule was first run on the 11 chats it applied to none of them: real timestamps are written "8:43PM", glued to AM or PM, and the rule accepted only a bare "8:43"; it would also have read the status-bar clock and, in a desktop window, the list of chats on the left (newest first) as a conversation running backwards. It now reads 12-hour times with and without a space, ignores the top 7% of the image and the left third of a landscape window, and applies to 5 of the 11 chats, finding nothing. Second, the running-balance rule applied to none of the nine statement pages: they have separate debit and credit columns, whole-number amounts and the newest transaction first. The rule now reads a debit and a credit column (or one amount column), tries both row orders and treats a misread row as a gap; it applies to 7 of the 9 pages and finds nothing, and one false alarm that remained on a page (OCR had read 0.5 as 05) disappeared once such numbers became gaps (the earlier output was not kept). The synthetic documents of Section 7.15 were changed to use these real formats, which lowered the chat rule's recall from 29 of 30 to 27 of 30 as PNG.

With the 23 earlier screenshots there are now 47 genuine items, and the gates were recalculated (Table {tab:gates47}).

@table gates47|Calibration of the checks on 47 genuine real items (n: items on which the check applied; flagged: findings of medium or high severity)
Check | n | Flagged | Upper bound (95%) | Decision
File metadata | 47 | 0 | 0.08 | live
Content rules | 47 | 0 | 0.08 | live
Number-column layout rule | 14 | 0 | 0.22 | advisory (too few)
Word-rendering model | 47 | 5 | 0.23 | advisory (bound above 0.15)
Version-1 error-level analysis | 30 | 30 | 1.00 | hint, not informative
Version-1 JPEG ghost | 30 | 15 | 0.67 | hint, not informative
Version-1 quantisation tables | 30 | 0 | 0.11 | hint by rule (would otherwise pass)
Version-1 noise consistency | 47 | 46 | 1.00 | hint, not informative
Version-1 copy-move | 47 | 0 | 0.08 | hint by rule (would otherwise pass)
Payment-receipt rules | 9 | 0 | 0.30 | advisory (too few)
Bank-statement rules | 7 | 0 | 0.35 | advisory (too few)
Chat rules | 5 | 0 | 0.43 | advisory (too few)
Order or invoice rules | 2 | 0 | 0.66 | advisory (too few)
One-time-code rules | 0 | 0 | 1.00 | advisory (never applied)
@endtable

The two live checks now have a bound of 8%. No check changed between live and advisory. Among the hints, the quantisation cue now meets the numbers (and is a hint by rule), and error-level analysis and the JPEG ghost fail them. The type-specific rules are closer (bank statements 7, payment rules 9, chats 5 applicable items, against 22 needed) but not there. The service ships the gate file calculated on these 47 items.

@section 7.17|REAL SECOND SOURCES: BANK SMS AGAINST GOOGLE PAY LISTS
Reconcile mode was tested on real data for the first time with 13 bank SMS messages (12 debit alerts of one bank and one Swiggy payment confirmation) and the four Google Pay transaction lists of Section 7.16. The SMS texts were transcribed by hand (by the AI assistant, from screenshots the owner shared in the chat; the SMS screenshots themselves were not available as files), and which list shows each payment was judged by eye: seven of the 13 payments appear in one of the four lists, the others in none. Every SMS was reconciled with every list, 52 pairs: 7 true pairs and 45 pairs in which the payment is not in that list (Table {tab:realpairs}).

@table realpairs|Reconcile mode on 52 real pairs of an SMS text and a Google Pay list screenshot
Result | As first built | After repairs
True pairs (7): corroborated | 0 | 0
True pairs: review | 0 | 5
True pairs: partial | 1 | 2
True pairs: conflict | 6 | 0
Other pairs (45): conflict | 45 | 0
Other pairs: nothing matched, partial or review | 0 | 36, 7 and 2
False corroborations (of 45) | 0 | 0
@endtable

As first built, reconcile mode corroborated none of the 7 true pairs and called 51 of the 52 pairs a conflict. The OCR text shows why: Tesseract reads the rupee sign as a leading digit ("105" is printed as "2105"), whole-rupee amounts have no decimals and so were not read as amounts at all, and the lists write dates without a year ("16 October"). The service also took a missing payment on a long list for a conflict. Four repairs followed: a date without a year is read as a day and a month; a bare whole number can make an amount "near" (a review), never "matched"; an amount shown with one extra leading digit is a review, because a rupee sign read as a digit and an amount edited by prepending a digit look the same; and a screen with five or more dates is treated as a list, in which a payment that is not on the screen is not a conflict. After the repairs there are no false conflicts and no false corroborations, 5 of the 7 true pairs are sent for review, and still none is corroborated. That is the honest state on this application: the currency sign makes the amount unreadable to the service, so a person must still compare the amount by eye. The test also shows two limits of the design. Facts are matched as sets, not tied to one row, so on a list a date from one row and an amount from another could in principle corroborate a payment that is not there (none did in these 45 pairs). And the pairs are few and come from one phone and one bank.

@section 7.18|RECONCILE MODE UNDER OCR NOISE WITH GROUND TRUTH
The mutation test of Section 7.8 builds its second source from the OCR output, which is circular. A second test removes the circularity: payment receipts were rendered from known facts (payee, amount with or without the rupee sign, date, time, a 12-digit reference) in six fonts, light and dark themes, with the amount printed with the rupee sign or as "Rs", and saved as PNG, as a shared copy (0.75, JPEG 75) and as a heavily shared copy (0.5, JPEG 60), 100 receipts each. The second source is the SMS text written from the same known facts, so a faithful source is faithful by construction (Table {tab:groundtruth}).

@table groundtruth|Reconcile mode on 300 rendered receipts against a faithful second source (statuses; single read against the two-read consensus)
Condition | Method | Corroborated | Review | Partial | Conflict
PNG | one read | 82 | 17 | 0 | 1
PNG | two-read consensus | 84 | 16 | 0 | 0
Shared copy | one read | 84 | 13 | 1 | 2
Shared copy | two-read consensus | 86 | 14 | 0 | 0
Heavily shared copy | one read | 91 | 1 | 5 | 3
Heavily shared copy | two-read consensus | 100 | 0 | 0 | 0
@endtable

With the consensus a faithful source was never called a conflict (0 of 300); a single read called 6 of 300 a conflict. The corroboration rate was 84% to 100%, and the remaining faithful sources were reviews, almost all caused by the rupee sign: in the receipts printed with the sign, OCR read "₹8,063.17" as "18,063.17" and the amount was not matched. The true reference was present among the values read in 100 of 100 receipts as PNG and 99 to 100 in the others, the date in 94 to 100, and the amount in only 82 to 97 for a single read (84 to 100 for either read). For altered second sources (one or two digits of the reference, the amount, or the date), none of the 300 receipts was corroborated by either method, so the safety property held; with the consensus 70% to 86% of the altered amounts were called a conflict or review and the rest stayed partial. These receipts are rendered, not captured, and the OCR conditions are friendlier than a phone screenshot of a list, which is what Section 7.17 found.

@section 7.19|HOW STABLE IS THE STFD RESULT? SEEDS, INTERVALS, ABLATION AND A RANDOM BASELINE
Four checks address the single-split, single-seed weakness of Section 7.10 (all on the cached word features, with splits by source-screenshot group). Over five different grouped splits the clean-trained model's word-level AUC on its test groups was 0.789 on average (standard deviation 0.014; range 0.771 to 0.806) and 0.668 on the degraded copy (standard deviation 0.012), and a bootstrap over source groups gave a 95% interval of 0.776 to 0.831 for the first split. A random baseline for localisation: choosing one measurable word at random in an STFD image gives an edited word with probability 6.5% (12,085 of 185,683 labelled words; 7.4% averaged over images), against the 26.5% of the word model's flags that met the mask in Section 7.9 (the definitions differ slightly, so this is a rough comparison, not a test).

The ablation removes one family of features at a time (each with its neighbour z-scores) and retrains (Table {tab:ablation}).

@table ablation|Word-level AUC of the clean-trained model on held-out STFD words with one feature family removed (seed 0)
Features | Clean test | Change | Degraded test
All 95 features | 0.806 | | 0.665
Without edge and contrast | 0.789 | -0.017 | 0.659
Without colour | 0.799 | -0.007 | 0.652
Without strokes | 0.801 | -0.006 | 0.648
Without background | 0.802 | -0.004 | 0.666
Without seam | 0.807 | +0.001 | 0.656
Without JPEG grid | 0.805 | -0.001 | 0.657
Without histograms | 0.785 | -0.022 | 0.652
Without geometry | 0.803 | -0.004 | 0.661
Without line context | 0.779 | -0.028 | 0.599
Raw measurements and geometry only (no comparison with neighbours) | 0.754 | -0.052 | 0.560
Comparison with neighbours only | 0.758 | -0.049 | 0.675
@endtable

No single family carries the result; the largest drops come from removing the line-context features (0.028) and the histograms (0.022). Removing all comparison with neighbours costs the most (0.052 on clean words, and the degraded-test AUC falls from 0.665 to 0.560, close to chance), and a model that uses only the comparisons still reaches 0.758. A model trained on degraded images lost its neighbour comparison in the same way (0.733 to 0.662 on degraded words). This gives partial quantitative support for the working hypothesis of Section 1.2, and only for re-compressed images: on clean words the raw and geometry features alone (0.754) and the comparisons alone (0.758) carry about the same signal, and after re-compression only the comparisons keep it (0.675 against 0.560).

The 98 images with a live finding in Section 7.9 were also inspected by rule. Ninety-four of them carry only the low-severity impossible-clock-time rule, with values such as 42:57, which cannot move the verdict; in the one image examined the value came from the status area (the text "AM 8:11" read as "48:11"), so they are OCR artefacts and not detections. The other four images carry 7 card-number checksum findings (in 3 images), one IBAN checksum failure and one placeholder number, and they are the four images with a "suspicious" verdict. Whether they relate to the edit was not examined, and STFD has no unedited originals against which to count them as false alarms.

@section 7.20|DEFECTS FOUND BY TESTING
Table {tab:defects} lists the six defects that testing against ground truth or real data found in the rules and in reconcile mode, with their effect before and after the repair, and, in its last row, a seventh defect (interface wording that overclaimed) that the wording test found. None had been visible in the measurements that came before.

@table defects|Defects found by testing and repaired
Defect | Found by | Before | After
Arithmetic and running-balance rules silent when a label and its amount are far apart | mutation test (Section 7.15) | recall 0 to 2 of 30 | 25 to 30 of 30
Misread rows (lost decimal point, "05") broke the running balance or the item sum | mutation test | false findings on clean statements and invoices in intermediate runs (output not kept) | misread rows are gaps; 5 of 100 clean statements still flagged, and the item-sum rule still flagged 2 of 100 clean invoices as PNG and 9 of 100 as shared copies
Chat-time rule found no message time in any real chat | 11 real chats (Section 7.16) | applied to 0 of 11 | applied to 5 of 11, no finding
Running-balance rule could not read real e-statements (debit and credit columns, whole numbers, newest first) | 9 real statement pages | applied to 0 of 9 | applied to 7 of 9, no finding
Reconcile mode called faithful receipts conflicts when OCR read the rupee sign as a digit | rendered receipts with ground truth (Section 7.18) | conflict in 1 to 3 of 100 (one read); amount unmatched in 18 of 100 | 0 of 300 conflicts; the case is a review
Reconcile mode on real Google Pay lists: whole-rupee amounts, dates without a year, a missing payment taken for a conflict | 52 real pairs (Section 7.17) | 51 of 52 conflicts; 0 of 7 corroborated | 0 conflicts; 5 of 7 reviews; 0 corroborated
Wording of the assurance ladder claimed "verified" and "real" | the front-end wording test (Section 6.4) | one test failed, on all four demonstration fixtures (the failing log was not kept) | wording changed
@endtable
@chapter 8|DISCUSSION, LIMITATIONS AND ETHICS

@section 8.1|WHAT THE RESULTS SHOW
The first result is about what a screenshot can prove by itself. A pipeline of established photograph-forensics cues flagged one genuine screenshot in five and could not distinguish an edited word from its original (Section 7.1). A word-level model that asks whether each word matches its neighbours separated simulated edits from genuine images (AUC 0.85), and a version fitted on real edits separated edited from unedited words of held-out STFD screenshots (AUC 0.81 on the main split and a mean of 0.79 over five grouped splits, standard deviation 0.014; 0.93 to 0.97 for the two edit types that insert text, Section 7.10). The ablation of Section 7.19 partly supports the working hypothesis of Section 1.2: removing every comparison with neighbouring words costs 0.052 of AUC and, after re-compression, leaves the model close to chance (0.560), but on clean words the comparisons alone (0.758) and the raw and geometry features alone (0.754) carry about the same signal, so the advantage of the comparisons appears only after re-compression (0.675 against 0.560). But on the project's own 56 real items (32 screenshots and 24 further chats, payment lists and statement pages) the final pipeline gave the same verdict for every one: inconclusive, with no counted check raising a flag, and all but two statement pages at level 1 of the assurance scale. The advisory word-rendering finding fired on 3 of 23 genuine and 2 of 9 edited screenshots, so it did not separate them either. No live check found a contradiction in the edited screenshots, and the type-specific rules were not run on them, so whether the edited content is self-consistent was not established. Why the signal fails to carry over from STFD to the owner's screenshots, and from clean to re-compressed images, was not isolated.

The second result is that the checks that use evidence from outside the image did what they were designed to do where they were tried, and fail in one specific place. Compare mode found differences in nine of nine edit pairs, including the three bank-statement edits that the word model missed (Section 7.7). Reconcile mode never corroborated an altered or mismatched second source in any of its tests (17 altered sources made from real screenshots, 300 rendered receipts, 52 real pairs, of which 45 are sources for other payments), although 2 of the 17 altered sources stayed "partial" and, with the two-read consensus, 14% to 30% of altered amounts did too, and with the two-read consensus it called none of the 300 faithful receipts a conflict; against a faithful source it corroborated 84% to 100% of the rendered receipts. On the real Google Pay lists it corroborated none of 7 true pairs: mainly because Tesseract reads the rupee sign as a digit (whole-rupee amounts and dates without a year also contribute, and the cause of the 2 pairs that stayed partial was not examined), the amounts cannot be confirmed, and the best the service can do is send 5 of 7 for review (Sections 7.17 and 7.18). A person comparing the amounts by eye is therefore still the last step for that application.

The third result concerns testing, and it is the most reusable. Six defects in the rules and in reconcile mode were found by tests that used ground truth or real data, and a seventh, interface wording that overclaimed, by the wording test (Table {tab:defects}); none had been visible earlier. The unit tests passed while the arithmetic and running-balance rules never fired on layouts where a label and its amount are far apart, because the tests used words that shared a line identifier; the chat-time rule applied to none of 11 real chats and the running-balance rule to none of 9 real statement pages, because the formats of real timestamps and real statements were not what the rules had been written for; and reconcile mode called 51 of 52 real pairs a conflict. The earlier failures follow the same pattern: the first version's cues were built for another medium, the layout rule's first version produced false alarms where OCR had skipped a row, the column-comparison idea looked convincing on the eight images that suggested it and failed on the corpus, and the model trained on real edits flagged 40% to 80% of genuine screens of another domain at its word-level thresholds (50% and 40% at the 1% threshold, 78% and 80% at the 5% threshold; a threshold per word probably becomes a much looser threshold per image, which was not tested separately). In each case a measurement on a larger or separate sample, or a test that injected known facts, exposed the problem, and the principle of Section 3.3 (a check counts only after it has been measured on genuine real screenshots) is the lesson, written into the code.

A last observation is an interpretation, not a measured result. For this problem a detector learned from edited examples is the wrong first tool, because the question that matters (is this screenshot true?) cannot be answered from pixels once a forger is careful. The design that the evidence supports is to check what can be checked, to measure each check on real data before trusting it, to abstain loudly, and to give the person a way to bring in a genuine copy or a second source.

@section 8.2|LIMITATIONS
@numbered
1. **Almost no check counts.** Only the file-metadata and content rules are live. The type-specific rules are advisory because they were measured on too few genuine items (applicable items: bank statements 7, payment rules 9, chats 5, orders 2, one-time codes 0, against 22 needed), the layout rule on 14, and the word-rendering model was measured on 47 but fails the bound (5 of 47 flagged, upper bound 0.23) (Section 7.16). No visual check is live, so the verdict can never be "no inconsistency found".
2. **Level 1 does not separate genuine from consistently edited screenshots.** All 23 genuine and all nine edited screenshots reached level 1 (Section 7.4). Only a genuine copy or a second source adds information.
3. **Reconcile mode is not yet useful on real Google Pay lists.** It corroborated none of 7 true pairs (Section 7.17). The rupee sign is read as a digit, which is the main cause of the 5 reviews; the cause of the 2 partial pairs was not examined; whole-rupee amounts, dates without a year and facts that are matched as sets and not tied to a row are further limits. Independence of the second source from the sender is assumed. The 13 SMS texts (12 debit alerts of one bank and one payment confirmation) come from one phone and were transcribed by the AI assistant from screenshots (the files were not saved), so a transcription error is possible.
4. **Small, private, single-person real data.** The 47 genuine items, the nine edit pairs (edited by the owner with unrecorded tools) and the 13 SMS texts come from one person's devices and accounts. Intervals are wide and no rate should be quoted from them.
5. **STFD has no genuine images and was not examined for language.** It shows how the pipeline responds to known edits, not how often it raises a false alarm. The cause of the 93% of "unknown" types was not established, and the 98 live findings were inspected only by rule (Section 7.19).
6. **The pixel model is weak outside its training conditions.** Simulated chat-style re-compression lowered the clean-trained model's AUC from 0.81 to 0.66 (models trained on re-compressed images reached 0.73), and the models flagged 14% to 80% of genuine Rico screens depending on the model and threshold (14% to 27% for the model trained on simulated edits, 40% to 80% for the models trained on real edits; Sections 7.10 and 7.11).
7. **Dependence on OCR.** The recogniser is Tesseract with its default English model. The two-read consensus removes random misreads but not a systematic one such as the rupee sign, and amounts without a currency marker, decimals or grouping are extracted only as bare numbers.
8. **Narrow type rules.** Each type has one to two rules and two types have none (Table {tab:types}); rules assume formats that other applications may not follow, and the service then says it could not examine the screenshot. Real formats forced two rules to be rewritten (Section 7.16), which suggests other applications will force more.
9. **Simulated edits in the second version.** Every figure of Section 7.2 comes from edits produced by a simulator; work on forgeries made by people cautions that results on synthetic benchmarks may not carry over [@dhouib2026doctamper], and Sections 7.3 and 7.10 are examples.
10. **Compare mode needs a genuine copy of the same proportions**, cannot see an edit made before that copy was saved, and wrongly flagged 3 of 27 harmless re-saves.
11. **Mutation test limits.** The documents of Section 7.15 are rendered by the project and the mutations are the contradictions the rules look for, so the recall is an upper bound. Its live item-sum rule raised a false finding on up to 9 of 100 clean shared invoices.
12. **No adversarial evaluation.** A forger who knew the method could keep the content consistent, match font and size, shrink the image, or supply the second source.
13. **Native-rendered and generated fakes** are out of reach of the pixel analysis by construction (Section 3.5); only a contradiction or a disagreement with a second source can expose them.
14. **Single split for the main experiments, no container run.** The robustness study repeats only the STFD word-model result over five grouped splits; the test split of the second version was consulted repeatedly during development; and the final container image was never run (Section 6.6).
@end

@section 8.3|THREATS TO VALIDITY
**Construct validity.** The label "edited" in the generated corpus means "touched by the simulator", and in STFD "inside a mask drawn by its authors". Neither is a recording of what a forger of bank or payment screenshots does. The mutation tests change one fact at a time, which is a simple forger and not the careful one the limitations describe.

**Internal validity.** The leakage controls (split by base file or by source group, held-out fonts, identical degradation for both classes, thresholds on separate data) address several of the leakage types listed in the leakage literature [@kapoor2023leakage] (duplicates, non-independence, use of test information). They do not rule out every shortcut: the STFD split depends on a perceptual hash. The gates were measured on the same genuine items that were used while the system was being repaired, and several repairs (the chat rule, the bank rule, the reconcile rules) were designed after looking at those very items, so the real-data figures after the repairs are not an independent test of the repaired rules.

**External validity.** The real items, the OCR engine (Tesseract 5.5.3 on macOS), the fonts and the compression settings are those of one setup. STFD and Rico are different populations from each other and from the intended one. Dataset bias is a known obstacle to transfer [@torralba2011bias], and several experiments here (Sections 7.6, 7.11 and 7.17) are demonstrations of it.

**Conclusion validity.** Intervals are wide and most experiments have one fit, so small differences should be ignored. The quantities that matter for the claims made are large: the first version's 20% false-alarm rate and AUC of 0.50, the all-inconclusive result of Sections 7.4 and 7.16, the 40% to 80% false-alarm rate on Rico, the 0 of 7 real corroborations, and the 9 of 9 compare result, with the limits stated.

@section 8.4|ETHICS, PRIVACY AND MISUSE
**Privacy.** Screenshots, bank messages and statements reveal other people's names, amounts and messages. The real items belong to the project owner and the owner's family, stay on the owner's machine, and are not committed to the repository; the generated corpus and the transcribed SMS texts are excluded from version control too. The report quotes no account number, name or message text from them. The service keeps uploads, pasted second sources and second images in memory and does not log them (Section 6.5).

**Public data.** STFD was obtained from its authors for academic research on request from a university address; the dataset card asks users to cite the paper and not to redistribute images that may leak information. The images are kept in an ignored folder and the repository holds only per-image results and scripts. The Rico subset is licensed CC BY 4.0.

**False accusations.** A "suspicious" or "evidence" verdict on a genuine screenshot could harm the person who sent it. The only live checks are rules that look for contradictions, with an upper false-alarm bound of 8% on 47 genuine real items (but the item-sum rule alone flagged 9 of 100 clean rendered invoices as shared copies, Wilson upper bound 16%, which the few real invoices cannot show); the word model that flagged 5 of 47 is not counted. A level of 1 or 2 must not be read as proof of authenticity either: that is why the label says "still unverified", why level 3 is shown as not available and why a test forbids the words authentic, genuine and verified as assertions. The service is a screener that points a person to a place and a reason, or to the next step to take.

**Dual use.** The same explanations that help a reviewer tell a forger which measurement to fix, and reconcile mode tells a forger exactly which facts a second source would have to match. This risk was accepted for a research prototype; a deployed service should rate-limit and not show the per-feature reasons to anonymous users.

**Claims.** The report does not claim real-world validation, deployment readiness or detection of generated or natively rendered fakes.

@section 8.5|PRACTICAL GUIDANCE
For a person using the service: choose the type of screenshot, so that the rules written for it can run. A flag is a reason to look at the marked place or fact, not a finding of forgery. A clean result is not a finding of authenticity: level 1 only says that the screenshot agrees with itself. To get more than that, bring a second source that the sender did not supply (the receiver's bank SMS, a statement line, the issuer's e-mail) and use reconcile mode; where the screenshot is a list of payments, expect a review and compare the amount by eye. If a genuine copy exists, compare mode adds information, though not an assurance level. Where money or evidence is at stake, verify the claim with the issuer of the document, and ask for the original file if the screenshot was resized or shared repeatedly.

@chapter 9|CONCLUSION AND FUTURE WORK

@section 9.1|WHAT WAS DONE
The project replaced a photograph-forensics pipeline that did not work on screenshots with a service built on a different principle. A check may abstain, must be measured on genuine real screenshots before it counts, and any doubt makes the answer "inconclusive". The service never calls an image authentic; it returns a verdict and an assurance level (0 to 2) that rises above level 1 only with independent evidence. It lets the person name the type of screenshot, so that rules written for the type can run, compare a suspect with a genuine copy, and reconcile a screenshot with a second source. The word-level rendering model of the second version, and in one experiment a version fitted on 70% of 3,932 real tampered screenshots, were built, measured and demoted to an advisory hint. Tests that injected known contradictions and ran the rules on real chats, real e-statements and real bank messages found six defects in the rules and in reconcile mode, which were repaired, and showed where the service still fails (reconcile mode on Google Pay lists). The work produced a generated corpus and its generator, evaluation protocols that expose different weaknesses, a service with an interface, 101 backend and 72 frontend tests and container build files (an image from an earlier tree was run), and a documented record of what failed.

@section 9.2|AGAINST THE OBJECTIVES
@table objectives|Objectives of Section 1.4 and what the evidence supports
Objective | Outcome | Evidence
1 Audit the first version | Done: 20% of genuine screenshots flagged; AUC 0.50 on word edits | Section 7.1
2 Word-level, explainable rendering model measured on generated, own and public real edits | Built and measured: AUC 0.85 on simulated edits; 0.79 (five splits) to 0.81 on held-out STFD words; fails the false-alarm gate; advisory only | Sections 7.2, 7.3, 7.9 to 7.11, 7.19
3 Rule checks behind calibration gates | Built; two checks live; type-specific rules written, tested (25 to 30 of 30 injected contradictions caught per kind) and repaired on real chats and statements, but not calibrated for lack of enough genuine items of their types | Sections 4.4, 4.7, 7.5, 7.15, 7.16
4 A verdict that never says authentic and an assurance level that rises above level 1 only with independent evidence | Done and tested; level 3 not built | Sections 3.6, 3.7 and 6.4
5 Compare mode and reconcile mode, measured | Compare: 9 of 9 edit pairs found (3 of 27 harmless re-saves wrongly flagged). Reconcile: no altered source corroborated in any test; 84% to 100% of faithful rendered receipts corroborated; 0 of 7 real Google Pay pairs corroborated (5 reviews) | Sections 7.7, 7.8, 7.17, 7.18
6 Evaluation that exposes weakness | Done: held-out, version comparison, cross-engine, leave-files-out, public real edits with source-grouped splits and five seeds, ablation, re-compression, genuine public screens, mutation tests and real-data tests; they exposed the sharing, domain, threshold and format limits and six defects in the rules and in reconcile mode | Sections 7.2, 7.3, 7.10, 7.11, 7.15 to 7.20
7 Usable, documented service | Done for interface, tests and documented limits; the final container image was not run | Chapter 6
@endtable

@section 9.3|WHAT THE PROJECT LEARNED
Four findings were not obvious at the outset. First, a rule can be silently dead, and only a test with ground truth or real data shows it: two arithmetic rules and the running-balance rule never fired on common layouts, the chat rule read no message time in real chats and the bank rule could not read real statements, while every unit test passed. Second, a model that works on a population does not carry its thresholds to another: the model fitted on real edits was far better than the one trained on generated edits on STFD words, yet at the 5% word-level thresholds taken from degraded validation words it flagged 78% to 80% of the Rico screens and 13 to 15 of the owner's 23 genuine screenshots, and a threshold per word probably turns into a much looser threshold per image. Third, the honest answer for most real screenshots is "inconclusive": every one of the 56 real items received it, and level 1 was reached by genuine and edited alike. Fourth, evidence from outside the image is the only thing that adds assurance, and its simplest forms, a genuine copy and a second source, needed no learned model; compare mode found all 9 edit pairs and reconcile mode never corroborated an altered or mismatched source (though some altered sources stayed "partial"), at the cost of 3 false alarms on 27 re-saves and, for reconcile mode, a dependence on OCR that failed on the rupee sign.

@section 9.4|PLANNED OUTPUTS, BENEFITS AND WHAT WAS NEW
No accuracy target was fixed before the work started, so the measurements are reported as results and not as targets met. The numeric targets that existed were the operating points of about 5% and 1% false alarms for the second version's two thresholds, the gate criteria of the final version (at least 20 genuine real screenshots and an upper bound of 15%), and, for the real-edit set, at least 20 genuine and 20 edited screenshots made by a person other than the capturer. The planned outputs were a replacement detector, a labelled corpus, a service and a validation set of real edits. The first three were produced; the validation set exists only as 47 genuine items and nine edited screenshots (edited by the project's owner) plus the eight-image sample (editor not recorded), so that output was only partly achieved. The gate criteria were met numerically by file metadata and the content rules (bound 8%, which is a live result), by the version-1 copy-move and quantisation cues (held back as hints by rule), and by no other check with the items available.

The benefits are a screener that runs on an ordinary CPU, explains every check and says when it could not look, never calls an image authentic, and gives the person two ways of using outside evidence; a reusable generator of labelled screenshots with leakage controls; a mutation test and a real-data test programme for its rules; and an honest record of what failed. A claim of usefulness on real forgeries is not made.

What is new, as distinct from what already existed: OCR, the boosting library, the Chrome renderer and the two public datasets are existing tools and data; the feature set, the corpus generator, the evaluation protocols, the rule checks, the gates, the verdict and assurance logic, reconcile mode and the service were built here. The project did not train or evaluate any published learned localiser. How much remains to be done is large: the most important gap is more real data, genuine items of the types the rules serve, real second sources from more banks and applications, and real edits made by other people.

@section 9.5|FUTURE WORK
@numbered
1. **A readable rupee sign.** Reconcile mode needs the currency sign handled before the amount is read, for example by cropping the amount and reading it with a model that knows the glyph, or by detecting the glyph in the image; this decides whether Google Pay and similar lists can ever be corroborated automatically.
2. **Genuine items per type.** Collect at least 22 genuine items for each type-specific rule (bank statements 22, payment receipts 22, chats 22, orders 22, one-time-code messages 22) and run the gate calibration; this switches the rules on (the list is in `docs/SCREENSHOTS_NEEDED.md`).
3. **Real second sources and independent edits.** Collect pairs of a payment screenshot and the matching bank record from several banks, and edits made by people other than the capturer with real tools and sharing paths, following Appendix E, and report rates with intervals.
4. **Row-aware matching.** Tie a payment's amount, date and name to one row of a list, so that facts are no longer matched as sets.
5. **Confirm the extracted facts.** Show the facts read from the screenshot in a table that the person can correct before they are compared.
6. **Level 3.** Check a digital signature or a signed code where a document carries one; this needs the formats of such documents to be studied first.
7. **Challenge-response.** Before a payment, the checker chooses a one-time code that must appear in the payment remark, which defeats screenshots prepared in advance. It is a usage protocol, not code, and was not built or tested.
8. **Other languages and a better reader.** An OCR model for other scripts and for small dark text on phone screens.
9. **Run the container** once the registry is reachable, and repeat the checks of Chapter 6 against it.
@end

@appendix A|APPLICATION PROGRAMMING INTERFACE
@appendixtext
The service exposes four endpoints. `POST /analyze` takes a multipart form with one field named `image` (png, jpg, jpeg or webp, at most 10 MB) and an optional field `type` (payment_receipt, bank_statement, order_invoice, chat, message_alert, social_post or web_page). `POST /reconcile` takes `image`, an optional `type`, and a second source as `source_text` or `source_image`. `POST /compare` takes `original` and `suspect`. `GET /status` returns the health of the service, the model's metadata, the validation state of the routers and the state of every gate. Status codes: 200 for a completed request, 400 for a missing, wrongly named, empty or unreadable file, an unknown type or a missing second source, 413 for an oversized upload and 500 for an unexpected error. Table {tab:apifields} describes the response of `POST /analyze`; an actual response (shortened, stored in the evidence folder) was produced by the final service for `docs/samples/statement_edited_detected.png` (a bank statement rendered by the project with one amount edited; the final service does not flag it, and returns "inconclusive" with level 1), with the free-text lists shortened. `POST /reconcile` returns the same fields plus an object `reconcile` and an assurance level that includes the second source. The object has `status` (corroborated, conflict, review, partial, nothing_matched or no_facts), `rows` (one per kind of fact: kind, status, the values of the second source, the values of the screenshot, an optional note), `matched`, `differs`, `needs`, `source_fields` and `screenshot_fields`.
@endappendixtext

@table apifields|Fields of the analysis response
Field | Meaning
verdict, verdict_label | one of evidence_of_editing, suspicious, no_evidence, inconclusive, and its display text
risk_score | one of four fixed positions on a scale from 0 to 1
reasons | up to eight plain-language sentences (the reasons for the verdict, then the cautions)
regions | marked regions: x, y, w, h in pixels of the (EXIF-oriented) image, text, score, level (evidence, suspicious or weak), reasons, the check that produced them
findings | findings of all checks: id, severity, message, evidence, the check, and whether it is counted
assurance | level (0 to 2), label, status, reasons, next step, the four-step ladder with which steps were reached
fields | amounts, dates, times, reference numbers and UPI identifiers read from the screenshot
routing | the type (chosen by the person or guessed), its status, the two routers' output and their validation state
capture | format, size, whether lossless, estimated JPEG quality, pixel reliability
checks | every check: id, name, category, status (finding, clear or not_applicable), severity, findings, why, regions, and its gate (live or advisory, with the reason)
coverage | how many live checks found nothing, found something, how many advisory signals, how many could not examine
verify_steps, limitations | what to ask the issuer; the fixed list of what the service cannot detect
image, stats, meta | size and format; word counts and thresholds; SHA-256 of the file, processing time and model description
@endtable

The shortened response itself is stored in `paper-draft/evidence/api_response_sample.json`.

@appendix B|SOURCE CODE LISTINGS
@appendixtext
The listings below are excerpts of the code as it stood when the report was built; they are read from the repository when the report is generated, so they cannot differ from the code described in the text. Line numbers are those of the source file.
@endappendixtext
@listing backend/screencheck/verdict.py|verdict_start|verdict_end|Listing B.1 The verdict policy (backend/screencheck/verdict.py)
@listing backend/app.py|inmemory|route_end|Listing B.2 Keeping uploads in memory (backend/app.py)

@appendix C|AUTOMATED TESTS
@appendixtext
The backend tests (101) and the frontend tests (72) are run with `pytest tests` in `backend/` and `npm test` in `frontend/`. Table {tab:tests} lists the backend tests by file. The 72 frontend tests are in 11 files (`vitest.txt`).
@endappendixtext
@testtable

@appendix D|HOW TO REPRODUCE THE RESULTS
@appendixtext
The commands below are an illustration of the steps, not a single script; they assume macOS with Tesseract installed and, for the second version's corpus, Google Chrome. The private screenshots and the generated corpus are not part of the repository, and STFD must be obtained from its authors. Listing D.1 runs the evaluations of the final version; the corpus and model of the second version are rebuilt with the scripts in `backend/tools/forge/` (`render_chrome.py`, `patchbank.py`, `build_dataset.py`, `merge_corpora.py` and `train_text_model.py`). The evidence folder `paper-draft/evidence/` holds the log of nearly every run reported here; not kept are the output of the faulty script of Section 7.3.1, the list of the first version's layout false alarms, the outputs of the intermediate runs and earlier rule versions mentioned in Sections 7.8 and 7.15, and the browser sessions.
@endappendixtext
@code Commands|Listing D.1 Commands for the evaluations of the final version
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt
pytest tests -q
(cd ../frontend && npm install && npm test)
python tools/train_router.py --per-family 40
python tools/eval_router.py --real-dir <genuine real screenshots> --real-labels tools/real_labels.json   # add --write-gate to write the gate file
python tools/calibrate_gates.py --real-dir <genuine real screenshots> --real-labels tools/real_labels.json --write
python tools/eval_compare.py --pairs pairs.json
python tools/eval_reconcile.py <folder of real screenshots>
python tools/mutation_content.py --per-mutation 30 --clean 100 --out mutation_content_results.json
python tools/eval_reconcile_synthetic.py --n 100 --out reconcile_synthetic_results.json
python tools/eval_reconcile_real_pairs.py --pairs <sms_pairs.json> --lists <Google Pay list screenshots>
python tools/stfd_robustness.py --feats feats.npz --feats-shared feats_shared.npz --out stfd_robustness.json
python tools/eval_stfd.py --root <STFD folder> --per-type 100000 --out stfd_pipeline_full.json
python tools/train_stfd.py featurize --root <STFD folder> --out feats.npz
python tools/train_stfd.py featurize --degrade --root <STFD folder> --out feats_shared.npz
python tools/train_stfd.py train --feats feats.npz --out-dir model_data_stfd --real <real set folder>
python tools/train_stfd.py compare --feats feats.npz --feats-shared feats_shared.npz --real <real set folder>
python tools/eval_rico.py --parquet <Rico test parquet> --n 300 --out rico_genuine_eval.json
python ../paper-draft/evidence/v3_real_set.py <real set folder>
@endcode

@appendix E|PROTOCOL FOR A REAL VALIDATION SET
@appendixtext
The most important missing evidence is detection on edits made by people with real tools, and reconciliation against real second sources. The protocol keeps the people who capture and edit separate, and fixes the rules before any output is seen. Person 1 takes at least 40 screenshots of real applications and changes nothing: half go into a folder of genuine images and half are passed to Person 2. Person 2 makes exactly one edit in each, using at least five different tools, a mix of lazy, careful and expert edits, a mix of lossless and compressed exports (single digits, whole amounts, names, dates or times, statuses, added or removed text, and a few edits made with the browser's Inspect Element tool), and keeps the untouched originals. For payment screenshots Person 1 also saves, before any edit, the record that the receiving side shows (the bank SMS or the statement line), which is the second source for reconcile mode. Nobody runs the service until every file exists, and no edit is revised after seeing a result. The folders are scored with `backend/tools/evaluate_manual.py` (single screenshots), `backend/tools/eval_compare.py` (pairs) and the reconcile endpoint (second sources), and the report gives the verdict and assurance breakdown with intervals. The second real set of Section 5.2 does not satisfy this protocol (nine edits made by the project owner with unrecorded tools, no second sources), so the protocol's own result is still outstanding.
@endappendixtext

@appendix F|TOOLS AND ASSISTANCE
@appendixtext
The implementation, the experiments and the first drafts of this report were produced with the help of an AI coding assistant (Claude Code, Anthropic). The assistant wrote and ran code, ran the evaluations and drafted text; the project team directed the work, supplied the real screenshots, requested the STFD data from its authors, and is responsible for the claims made. Nearly all numbers in this report are taken from logs and scripts stored in the evidence folder and were re-derived from them during an audit (the exceptions are marked in the text and listed in the audit report); the text was checked against the code. Third-party tools used: Tesseract OCR 5.5.3, scikit-learn 1.9.0, Pillow 12.3.0, NumPy 2.5.1, SciPy 1.18.0, Flask 3.0.3, React 18 with Vite, and Google Chrome 155 for rendering the generated screens and for capturing the demonstration page. Papers cited were retrieved and checked against Crossref, OpenAlex, arXiv or the publisher, and the read depth of each (full text, abstract or bibliographic record only) was recorded; claims about papers read at abstract level are limited to what the abstract states. Four works were read at the level of their bibliographic record only (the Rico paper, Mahdian and Saic on noise inconsistencies, Tornes and colleagues on receipt forgery, and Fawcett on ROC analysis), and the Wilson reference is cited as a pointer.
@endappendixtext

@appendix G|EVIDENCE FILES
@appendixtext
Table {tab:evidence} maps each result in the report to the file that holds it. All files are in `paper-draft/evidence/` of the repository. Private screenshots are not in the repository; files that describe them hold verdicts and counts only.
@endappendixtext
@table evidence|Evidence files and the results they support
File | Supports
fp_results.json, tamper_results.json, v1_native_check.txt (scripts exp_fp.py, exp_tamper.py) | first-version audit (Section 7.1)
compare_legacy.txt, train_final_v6.log, ocr_recall_check.txt, train_v2_corpus_features.log, train_v4_corpus_features.log, second_stage_check.txt, cross_engine.txt | second version on the generated corpus and its development steps (Section 7.2)
leave_files_out_v5_intermediate.log, leave_files_out_v6.log, cv_summary_v6.json, wilson.txt, real8_results.txt, real_set_2026-10-16.txt, real_set_per_image.txt | second version on real screenshots (Section 7.3)
v3_real_set.py, v3_real_set.txt | final pipeline on the second real set (Sections 7.4 and 7.14)
gates_v3.json | calibration of every check on 23 genuine screenshots (Section 7.5)
router_eval_v3.txt, router_gate_v3.json, router_structure_meta.json | type routers; training size and held-out accuracy of the structure router (Section 7.6)
compare_mode_eval.txt | compare mode and its controls (Section 7.7)
reconcile_mutation_test.txt | reconcile mutation test (Section 7.8)
stfd_pipeline_full.json, stfd_pipeline_summary.txt, summarise_stfd.py | final pipeline on STFD (Section 7.9)
stfd_train_run.txt, stfd_compare_run.txt, stfd_feature_counts.txt | training on real edits, re-compression and the three-model comparison (Section 7.10)
rico_genuine_eval.json, rico_genuine_run.txt | false alarms on genuine Rico screens (Section 7.11)
layout_rule_eval.txt, layout_rule_eval_first_version.txt, negative_results.txt, column_z_8images.txt, train_v7_column_peers.log | layout-grid rule and the rejected column idea (Sections 7.12 and 7.13)
latency_large.txt | second-version latency on large captures (Section 7.14)
facts.txt, facts_v3.txt (regenerated by facts_v3.sh) | corpus, code and environment facts (Chapters 5 and 6)
pytest.txt, vitest.txt (earlier runs: pytest_v2.txt, vitest_v2.txt) | automated tests (Chapter 6)
mutation_content_run.txt, mutation_content_results.json, mutation_content_run_old_rows.txt, mutation_content_results_old_rows.json | mutation test of the content rules, with the repaired and the earlier row grouping (Section 7.15)
v3_new15.py, v3_new15.txt, v3_statements.py, v3_statements.txt, gates_v3_47.json, gates_calibration_47.txt | further genuine chats, payment lists and statement pages, and the gates on 47 genuine items (Section 7.16); gates_v3_38.json is the intermediate calibration on 38
reconcile_real_pairs_before.txt, reconcile_real_pairs_after.txt | reconcile mode on real SMS and Google Pay lists, before and after the repairs (Section 7.17)
reconcile_synthetic_run.txt, reconcile_synthetic_results.json | reconcile mode with ground truth under OCR noise (Section 7.18)
stfd_robustness_run.txt, stfd_robustness.json, stfd_live_findings.txt | seeds, bootstrap, ablation, random baseline and the 98 live findings (Section 7.19)
wilson_v3.txt | Wilson intervals of the proportions in Chapter 7 that the older files do not hold (Chapter 7)
v1_native_cues.py, v1_native_cues.txt | cue values quoted in Section 7.1.3
docker_test.log, docker_build_final.log | container check of an earlier image, and the failed rebuild of the final one (Section 6.6)
api_response_sample.json | response listing of Appendix 1
corpus_build_v1.log | corpus build statistics (Section 5.3)
run_evidence.sh, cross.py, real8_eval.py, latency.py | scripts that regenerate the second version's evaluations (Chapter 7)
@endtable
