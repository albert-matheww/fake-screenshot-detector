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
