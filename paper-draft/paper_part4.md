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

