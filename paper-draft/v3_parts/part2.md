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
