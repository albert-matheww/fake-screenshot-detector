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
