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
