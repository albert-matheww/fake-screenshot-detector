# 02 Literature map (reading notes in my own words)

Read depth: full = full text read this session (saved as `sources/<key>_fulltext.txt`); abstract = abstract only (claims limited to it);
metadata = bibliographic record only (claims limited to the title).

## A. Classical passive image forensics
- **farid2009survey** (abstract). Review of the then-new field of digital forensics for detecting doctored photographs. Use: field background.
- **piva2013overview** (abstract). Survey organising passive tools by where in an image's history the trace arises (acquisition, coding, editing). Use: taxonomy of cues.
- **farid2009ghosts** (abstract). Detects a region that was compressed at a lower JPEG quality than the rest by looking at traces of the earlier quality. Use: JPEG-ghost cue in v1.
- **bianchi2012block** (abstract). Per-block likelihood map for double JPEG compression (aligned and non-aligned); localises tampered regions. Use: JPEG-grid cue (our grid-phase feature is a much simpler relative).
- **popescu2005resampling** (abstract). Resampling leaves correlations that can be detected in any image portion; shown on uncompressed and lightly compressed images. Use: why down-scaling matters.
- **mahdian2009noise** (metadata). Title: noise inconsistencies for blind image forensics. Use: only the existence of a noise-inconsistency cue.
- **lukas2006prnu** (abstract). Camera identification from sensor pattern noise. Use: screenshots have no sensor, so this family does not apply.
- **christlein2012eval** (full). Evaluation of copy-move detection approaches. Use: copy-move background; our clone detector was one of v1's cues.
- **krawetz2007** (full). Original ELA description: resave at a known quality and compare; modified 8x8 cells are no longer at the same error level; relies on lossy (JPEG) compression. Use: ELA definition.
- **verdoliva2020** (full). Overview of media forensics and deepfakes. Use: field context.

## B. Learned localisation and benchmarks for natural images
- **wu2019mantranet** (abstract). End-to-end network for many forgery types with local-anomaly (z-score) formulation. Use: learned baselines exist; our relative z-scores echo "local anomaly" thinking (own observation).
- **kwon2021catnet** (abstract). RGB+DCT streams learning compression artefacts for splicing localisation. Use: learned compression-aware localisation.
- **guillaro2023trufor** (abstract). Fuses RGB with a learned noise fingerprint; outputs localisation, an integrity score and a reliability map. Use: learned detector; reliability map relevance to false alarms.
- **dong2013casia** (abstract). CASIA tampering benchmark of natural colour images with realistic tampering. Use: v1 training data.
- **novozamsky2020imd** (abstract). IMD2020: large camera-based sets plus 2,000 "real-life" manipulated images downloaded from the Internet. Use: v1 training data.

## C. Document and text tampering
- **tornes2023receipt** (metadata). Receipt dataset for document forgery detection. Use: v1 training data; existence only.
- **qu2023doctamper** (full). DTD detector + DocTamper dataset (170,000 document images; splicing, copy-move, generation); notes that document tampering lacks the visual clues of natural-image tampering because backgrounds are uniform and text shares font and size. Use: motivates comparing text with its own neighbours.
- **qu2024textsleuth** (full). Explains tampered-text detection in natural language with a multimodal model; dataset ETTD. Use: explainability trend.
- **yu2023stfd** (abstract) + **hf_stfd** (full card). First public smartphone-screenshot text-forgery dataset STFD with masks; card: password by e-mail from an academic address, cc-by-4.0 licence tag. Use: the closest public data; not obtainable in time.
- **yu2025fsts** (full). 16,750 real tampering instances collected from 67 people with editing logs; models operation parameters (including post-processing such as blur and JPEG recompression) to synthesise training data; reports STFD has 4,094 tampered instances and FindIt 240. Use: validates simulating operations and post-processing; **hf_fsts** (full card): ~46 GB zip, cc-by-nc-4.0.
- **xu2026reality** (abstract). RWTamper: completely manual tampering, three degradation subsets of 9,326 images each; model uses OCR information. Use: human-crafted data is considered necessary.
- **ronfleux2026docqt** (full). Training on narrow JPEG-table distributions fails to transfer; realistic tables cut false positives on authentic documents. Use: supports degrading both classes identically.
- **dhouib2026doctamper** (full). Gains on synthetic benchmarks translate poorly to human-made forgeries and cross-domain data. Use: the caveat we apply to our own results.
- **chen2025unmask** (abstract). Tampering localisation under print-and-scan recapturing. Use: recapture is a separate hard setting (not in scope).
- **zhao2026docforge** (full). 14 methods, 8 datasets; moderate pixel-AUC but near-zero F1 attributed to threshold miscalibration (tampered area 0.3-4 %); adapting a threshold on ten domain images recovers 39-55 % of the gap in representative cases. Use: justifies calibrating on in-domain genuine data.
- **du2025forensichub** (abstract). Unified benchmark/codebase across deepfake, manipulation, AIGC and document domains. Use: evaluation landscape.

## D. Screenshots and AI-generated text-rich images
- **venkatesh2026screenshot** (abstract). Screenshot-tailored pipeline fusing ELA, noise residual, JPEG double-compression/blockiness, text-edge regularity and metadata in a gradient-boosting model; 1,200 screenshots; reports AUC 0.82 versus 0.47 for an ELA-only baseline, weakest on small text edits. Use: closest prior work; no cross-dataset numeric comparison.
- **zhang2026textfake** (full). 20,000-image benchmark for AI-generated text-rich images; no evaluated method above 80 % accuracy; failure modes named. Use: AI-generated screenshots are out of scope and hard.

## E. Methods and evaluation practice
- **smith2007tesseract** (abstract). Overview of the Tesseract engine. Use: OCR component.
- **friedman2001** (abstract). Gradient boosting of regression trees. Use: classifier family.
- **pedregosa2011** (abstract; arXiv preprint). scikit-learn. Use: library actually used (v1.9.0 pinned).
- **torralba2011bias** (abstract). Dataset bias and cross-dataset generalisation in recognition datasets. Use: reason to test across sources and engines.
- **kapoor2023leakage** (full). Taxonomy of leakage (e.g. duplicates, non-independent train/test units, sampling bias, pre-processing before split). Use: split design; our own cross-validation calibration bug fits the "same data for fitting and selection" class.
- **fawcett2006roc** (metadata). ROC analysis introduction. Use: only to point to ROC/AUC analysis.
- **wilson1927** (abstract). Binomial confidence interval. Use: the interval reported for 4/73.

## Positioning
1. **What exists.** Pixel-level passive forensics (ELA, JPEG, noise, resampling, copy-move) built for photographs; learned localisers (ManTra-Net, CAT-Net, TruFor); text-specific tampering data and detectors (DocTamper, STFD, RWTamper, FSTS-trained models); a 2026 screenshot-tailored multi-feature pipeline.
2. **Limitations (attributed carefully).** Document-forgery work reports that synthetic-benchmark gains transfer poorly to human-made forgeries (dhouib2026doctamper), that thresholds fixed at 0.5 are miscalibrated for tiny tampered regions (zhao2026docforge), and that compression assumptions matter (ronfleux2026docqt). Whether classical cues transfer to *lossless* screenshots is, in the sources read, not tested; this is our own observation from the v1 audit.
3. **Where this project fits.** A small, explainable, CPU-only word-level detector for screenshots plus rule checks, with an unusually explicit negative-result record.
4. **Contribution (type: system/application + cautionary empirical finding).** (a) a measured audit showing that a v1 photo-forensics pipeline carried no signal on genuine screenshots; (b) a rendering-consistency word-level detector evaluated with unseen-font, unseen-base and leave-files-out protocols; (c) a leak-controlled generated corpus (ScreenForge) and its generator; (d) validated layout/semantic rules; (e) documented negative results.
5. **Evidence.** `evidence/` files listed in 01.
