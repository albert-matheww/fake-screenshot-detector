# Viva preparation: questions an examiner is likely to ask

Each answer points to where the evidence is. Be able to answer without the report open. File names are in `paper-draft/evidence/` unless a path is given; section numbers refer to the report. This version covers the final design (version 3: chosen type, calibration gates, assurance levels, compare and reconcile modes); the older questions about the first two versions are kept at the end.

## The problem and the contribution

1. **What does the service do, and what does it refuse to say?**
   It reports whether a calibrated check found a contradiction (the verdict), how much independent evidence supports the screenshot (an assurance level 0 to 2), and what every check did. It never says an image is authentic; the best single-screenshot outcome is "no contradiction found, still unverified" (Sections 3.6 and 3.7; tests in `backend/tests/test_v3.py` and `test_assurance.py`; the frontend wording test in `AnalysisResults.test.jsx`).
2. **What is your contribution? Is it a new algorithm?**
   No. It is a system and evaluation contribution: an audit of a photograph-forensics pipeline on screenshots, a design in which every check must be measured before it counts, reconcile and compare modes that bring in outside evidence, and measurements of what training on real tampered screenshots does and does not achieve (Section 1.5).
3. **Why did you change the design twice?**
   Version 1 flagged 20% of genuine screenshots and had AUC 0.50 on edits (Section 7.1; `fp_results.json`, `tamper_results.json`). Version 2 reached AUC 0.85 on simulated edits but flagged 2 of 9 real edits and 3 of 23 genuine screenshots (Section 7.3.3; `real_set_2026-10-16.txt`). The pixel evidence does not carry over, so version 3 treats the image alone as internal evidence only.
4. **Why can the system not simply say "genuine"?**
   A forger can make a screenshot that agrees with itself; all 32 real screenshots, genuine and edited, reached level 1 (Section 7.4; `v3_real_set.txt`). Only a genuine copy or an independent second source adds information.

## Design and method

5. **What is a calibration gate and why 20 screenshots and 15%?**
   A check counts only if it applied to at least 20 genuine real screenshots and the Wilson 95% upper bound of its false-alarm rate is at most 15% (Section 4.7). With zero false alarms 20 screenshots give 16.1%, 22 give 14.9% and 23 give 14.3%, so 22 is the real minimum; with one false alarm it is 34 (`backend/screencheck/gates.py`, `common.py`).
6. **Which checks count today?** Only file metadata and the content rules (23 genuine screenshots, 0 flagged, bound 14.3%). Everything else is advisory (Table 7.11; `gates_v3.json`).
7. **Why can the verdict never be "no inconsistency found"?** It needs a live content check and a live visual check, and no visual check is calibrated (Section 3.6). Every clean screenshot is "inconclusive".
8. **What is the difference between the verdict and the assurance level?** The verdict says whether a counted check found a contradiction; the level says how much independent evidence supports the screenshot (Section 3.7; `verdict.py`, `assurance.py`).
9. **How does reconcile mode avoid false conflicts from OCR errors?** The screenshot is read twice (as is and enlarged); a value both reads agree on is confident; a conflict needs a confident different value; a reference that differs by one digit is "review", never agreement (Section 4.8; `fields.py`, `reconcile.py`).
10. **What was the bug the mutation test found?** An altered amount passed when the reference still matched, because the amount was merely "not found". The rule now requires every hard fact the second source supplies to be matched (Sections 4.8.2 and 7.8; `reconcile_mutation_test.txt`).
11. **Why did you let the person choose the type?** The routers are not validated: the content router answered 18 of 23 correctly, the structure router was right on 4 of 23 (Section 7.6; `router_eval_v3.txt`). The chosen type is trusted and recorded (Section 4.3).
12. **How does compare mode work and when does it fail?** Blur, difference, threshold, clean, connected regions, plus OCR text changes only where pixels differ; it needs the same proportions and a genuine copy (Section 4.9). It found 9 of 9 edit pairs and wrongly flagged 3 of 27 harmless re-saves (Section 7.7; `compare_mode_eval.txt`).

## Data

13. **Where does the data come from?** The owner's private screenshots (23 genuine, 9 edit pairs in the final set), the generated ScreenForge corpus (20,814 images), STFD (3,932 tampered screenshots obtained from the authors on request) and a 300-screen sample of a Rico subset (CC BY 4.0) (Chapter 5).
14. **Could you redistribute STFD?** No. The authors asked that it not be redistributed and that their paper be cited. The images are in an ignored folder; the repository holds scripts and per-image results only (Sections 5.4 and 8.4).
15. **Why can STFD not measure false alarms?** It contains tampered images only (Section 5.4). Rico supplies genuine screens of another domain (Section 5.5).
16. **Is the STFD run up to date with the final code?** It used the service as of 2026-10-18, before the version-1 hints and assurance levels; those cannot change a verdict (Section 5.6, protocol 12).

## Results

17. **What happened when you trained on real edits?** Word-level AUC on held-out STFD words rose from 0.56 (model trained on generated edits) to 0.81, but after chat-style re-compression it fell to 0.66 to 0.73, and on 276 genuine Rico screens the models trained on real edits flagged 40% to 80% (14% to 27% for the model trained on generated edits) (Sections 7.10 and 7.11; `stfd_train_run.txt`, `stfd_compare_run.txt`, `rico_genuine_run.txt`).
18. **Why is the pixel model still in the product?** As a hint only: it fails the gate (3 of 23 genuine flagged, bound 0.32) and cannot change a verdict (Table 7.11).
19. **Why did the word-level false-alarm rate not carry over to images?** An image is flagged if any one of its many words is flagged, so a per-word threshold becomes a looser per-image threshold (Sections 4.5 and 7.11). That explanation was not tested separately.
20. **How did you split STFD to avoid leakage?** Near-identical source screenshots were grouped by a 16 by 16 difference hash (Hamming distance at most 20 of 256 bits), 2,516 groups, split 70/15/15 by group (Sections 5.6 and 7.10.1).
21. **What are the version-1 hints worth?** Error-level analysis flagged all 15 genuine screenshots it applied to and noise consistency all 23, so they are labelled "not informative"; copy-move flagged none of 23 but is a hint by rule (Section 7.5).
22. **Does any number establish how well real edits are caught?** No. The real sets are small and the edits are the owner's. State the intervals (Sections 7.3 and 7.7) and say "larger", never "significant". No significance tests were run.
23. **Is the second source test realistic?** No: it uses perfect text built from the same screenshots, so it tests the logic and OCR robustness, not real SMS matches. Real pairs are the next step (Sections 7.8, 8.2 and 9.5).

## The mutation test

- **What did the mutation test show?** 16 kinds of injected contradiction, 30 documents each, run through OCR as PNG and as shared copies: each rule fired on 27 to 30 of 30; 5 of 240 clean documents raised a medium or high finding as PNG, 1 of 240 as shared copies (Section 7.15; `mutation_content_run.txt`).
- **What defect did it find?** The arithmetic and running-balance rules never fired when a label and its amount were far apart, because Tesseract put them in different lines; recall was 0 of 30 before the repair and 29 to 30 of 30 after (`mutation_content_run_old_rows.txt`). Real screenshots could not have shown this, as they contain no contradictions.
- **What did real chats add?** The chat-time rule found no message time in any of 11 real chats (times are written "8:43PM"), and would have read the status-bar clock and a desktop chat list as messages; after the repair it applied to 5 of the 11 and flagged none (Section 7.16; `v3_new15.txt`).
- **Does that prove the rules catch real forgeries?** No. It is an upper bound: the contradictions are the ones the rules look for, the documents are rendered by the project, and the nine real edits left no contradiction that a live rule found.

## The real-data tests

- **What did the real statements, chats and bank messages show?** Six defects in the rules and in reconcile mode were found and repaired by tests with ground truth or real data, and a seventh (interface wording that overclaimed) by the wording test (Table 7.16 in Section 7.20): the bank rule applied to none of 9 real statement pages and the chat rule to none of 11 real chats until they were rewritten; reconcile mode called 51 of 52 real SMS-against-Google-Pay pairs a conflict (`reconcile_real_pairs_before.txt`).
- **Does reconcile mode work on real data?** Not on Google Pay lists: 0 of 7 true pairs corroborated, 5 sent for review, no false conflict and no false corroboration after the repairs (`reconcile_real_pairs_after.txt`). The main cause is that Tesseract reads the rupee sign as a leading digit (the cause of the 2 pairs that stayed partial was not examined). On rendered receipts with known facts it corroborated 84% to 100% of faithful sources and none of the altered ones (`reconcile_synthetic_run.txt`).
- **Who transcribed the SMS texts?** The AI assistant, from screenshots the owner shared in the chat; the files were not saved, so a transcription error is possible (Section 7.17).
- **How stable is the STFD result?** Five grouped splits: word AUC 0.789, standard deviation 0.014; bootstrap interval 0.776 to 0.831; removing every comparison with neighbours costs 0.052 and leaves the model near chance after re-compression (Section 7.19; `stfd_robustness_run.txt`).
- **Is the repaired rule an independent test?** No. The repairs were designed after looking at those very items (Section 8.3); the figures after repair are not an independent test.

## Engineering, privacy, ethics

24. **Is the uploaded image stored?** No. Uploads, pasted second sources and second images stay in memory; the web framework's default spooling to disk was found and fixed with an in-memory request class and a regression test (Section 6.5, Listing 2.4, `test_large_uploads_are_never_spooled_to_disk`).
25. **What could a forger do with this tool?** Use the explanations, or learn which facts a second source would have to match; the report names this (Section 8.4).
26. **Tests?** 101 backend (`pytest.txt`), 72 frontend (`vitest.txt`). One existing frontend test failed on the new text for using "verified" and "real" wording; the wording was changed and the test's pattern now matches whole words (Section 6.4).
27. **Deployment?** Python 3.12 slim image with Tesseract, gunicorn; nginx frontend; Render blueprint. An image from an earlier tree was run (`docker_test.log`); the rebuild for the final tree failed on a registry timeout (`docker_build_final.log`), so the final image has not been run.
28. **Use of AI assistance?** Disclosed in Appendix 6: code, runs and first drafts were produced with an AI coding assistant; the team directed the work and is responsible for the claims. Follow your institution's disclosure policy.

## Questions you cannot answer from the report (be honest)

- Accuracy on real forgers' edits made with Photoshop, Canva or phone editors: not measured.
- Reconcile mode on real pairs of a screenshot and an independent record: not measured.
- Behaviour on screenshots from other applications or languages than those tested: not measured.
- Type-specific rules (UPI reference, running balance, order arithmetic, chat times, one-time code): written and unit-tested, not calibrated.
- Comparison with deep localisers or with detectors trained on STFD by other authors: not done.

## Older questions (first two versions)

- **How was the version-2 threshold chosen?** 5% and 1% false-alarm points on 246 validation genuine real images: 0.847 and 0.966 (`train_final_v6.log`).
- **How does version 2 do on genuine screenshots it never saw?** Leave-files-out: 4 of 73 (5.5%) flagged at the suspicious tier, 0 at the evidence tier, with Wilson intervals; 45% and 24% of simulated edits caught (Table 7.7; `leave_files_out_v6.log`, `wilson.txt`).
- **What happens after down-scaling?** The version-2 AUC falls to 0.72 to 0.73 (Table 7.4), and the STFD experiment shows the same effect on real edits (Section 7.10.2).
- **Why the maximum over words?** One edited word is enough to matter; the cost is that false alarms grow with the number of words (Sections 4.5 and 7.3.1).
- **What did the layout rule fix and how often does it apply?** An edited number off the row grid; false alarms 0.09% on 6,656 genuine corpus images, applicable to about 15% of images with a numeric column and to 2 of 23 real genuine screenshots (Section 7.12; `layout_rule_eval.txt`).
- **What failed in version 2?** The column-peer idea looked good on 8 images and failed on the corpus (Section 7.13; `negative_results.txt`).
