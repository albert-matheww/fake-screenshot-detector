# Viva preparation: questions an examiner is likely to ask

Each answer points to where the evidence is. Be able to answer without the report open. File names are in `paper-draft/evidence/` unless a path is given; section numbers refer to the report.

## The problem and the contribution

1. **What exactly does the system do, and what does it refuse to say?**
   It reports whether any word in one screenshot shows signs of editing, marks the words and explains them. The lowest tier is "no evidence of editing found", never "authentic" (Section 3.3, `backend/analysis.py`, test `test_no_evidence_is_never_called_authentic`).
2. **What is your contribution? Is it a new algorithm?**
   No. It is a system and evaluation contribution: an audit of a photograph-forensics pipeline on screenshots, a word-level detector with explanations, a leak-controlled generated corpus, rule checks measured for false alarms, and recorded negative results (Section 1.5).
3. **Why did you abandon the first version?**
   Measured: 12 of 60 genuine screenshots flagged (20%), AUC 0.50 on 42 realistic edit sets, a natively rendered fake not flagged by the pixel cues (Section 7.1; `fp_results.json`, `tamper_results.json`, `v1_native_check.txt`).
4. **Why not just use ELA / a pretrained deep localiser (ManTra-Net, TruFor)?**
   ELA is defined for lossy-compressed images and 59 of 60 genuine screenshots were PNG (Section 1.2, 7.1). No deep localiser was run; the report says no comparison with them was made (Section 2.7). Do not claim you beat them.
5. **Closest published work?** Venkatesh et al. (2026), a gradient-boosted fusion of compression, noise and metadata cues, AUC 0.82 on their own 1,200 screenshots. Not compared numerically because data differ (Section 2.5).

## Data

6. **Where does the data come from, and why generated?** STFD needs a password by e-mail, not received; FSTS is a ~46 GB archive, not used (Section 2.7, 5.1). Real, Chrome-rendered and Pillow-rendered screenshots plus two edit engines.
7. **Could the model have learned the generator instead of the edit?** Controls: identical sharing degradation for both classes, splits by base-file hash, held-out edit fonts, a second engine, and a leave-files-out test on real full-size screenshots (Section 5.4–5.5, 7.5, 7.6). Residual risk is stated (Section 8.3).
8. **How many real screenshots, whose are they?** 89 files found, 73 used; the authors' own device screenshots, private, not in the repository (Section 5.2, `unused_real_files.txt`).
9. **Why is the first version's "native fake" result important?** It shows pixel cues cannot see content rendered natively with false text; this is also out of scope for the new method (Section 3.5, 7.1.3).

## Method

10. **Walk through the pipeline.** OCR boxes (Tesseract) → 95 measurements per word → robust z-scores vs. line/image → boosted trees → image score = maximum word probability → thresholds from validation genuine images → verdict (Chapter 4, Figure 3.1).
11. **Why the maximum over words, and what does it cost?** One edited word is enough to matter; the cost is that false alarms grow with the number of words (Section 4.5.3, 7.3.5).
12. **How were thresholds chosen?** 5% and 1% false-alarm points on 246 validation genuine real images: 0.847 and 0.966 (`train_final_v6.log`).
13. **Is the risk score a probability?** No, a display rescaling with the thresholds at 0.40 and 0.70 (Section 3.6).
14. **What does the layout-grid rule do and why was it added?** It flags a number off the row grid of an evenly spaced column; added after a hand-collected edit was missed; its first version had false alarms (Section 4.6.1, 7.7; `layout_rule_eval*.txt`).
15. **What failed?** Column-peer features looked good on 8 images and failed on the corpus; a second-stage aggregator gave no gain (Section 7.10; `negative_results.txt`, `second_stage_check.txt`).

## Results

16. **Headline numbers.** Test AUC 0.847 on unseen images and fonts, TPR 31% at 1% and 43% at 5% false alarms (Table 7.5; `train_final_v6.log`). First version on the same 500 images: AUC 0.46 (Table 7.4; `compare_legacy.txt`).
17. **How does it do on genuine screenshots it never saw?** Leave-files-out: 4 of 73 (5.5%) flagged at the suspicious tier, 0 at the evidence tier, with Wilson intervals; 45% / 24% of simulated edits caught (Table 7.12; `leave_files_out_v6.log`, `wilson.txt`).
18. **What happens after down-scaling or re-compression?** AUC falls to 0.72–0.73 (Table 7.8). State this as a weakness.
19. **Does it work on real human edits?** The eight-image development sample (2 of 4 edits flagged, 0 of 4 genuine; `real8_results.txt`) and a later set scored once (2 of 9 edits flagged, 3 of 23 genuine flagged; Section 7.9.1, `real_set_2026-10-16.txt`). Both are far too small for rates. The proper validation protocol is in Appendix 5 and has not been run.
20. **Is any difference statistically significant?** No tests were run; one seed per experiment; only Wilson intervals for proportions (Section 8.3). Say "larger", not "significant".
21. **Is it real-time? How slow?** Median 581 ms, 90th percentile 1,030 ms on 80 test images on a laptop CPU (Section 7.11; `latency.txt`).

## Engineering, privacy, ethics

22. **Is the uploaded image stored?** No. Kept in memory; Werkzeug normally spools uploads above 512 KB to disk, which was found and fixed with an in-memory request class and a regression test (Section 6.5, Listing 2.2, `test_large_uploads_are_never_spooled_to_disk`).
23. **What could a forger do with this tool?** Use the explanations to tune an edit; the report names this and says the tool is no proof of authenticity (Section 8.4).
24. **Tests?** 35 backend (`pytest.txt`), 58 frontend (`vitest.txt`).
25. **Deployment?** Python 3.12 slim image with Tesseract, gunicorn; nginx frontend; Render blueprint. An image from an earlier tree was run (`docker_test.log`); the rebuild for the final tree failed on a registry timeout (`docker_build_final.log`), so the final image has not been run.
26. **Use of AI assistance?** Disclosed in Appendix 6: code, runs and first drafts were produced with an AI coding assistant; the team is responsible for the claims. Follow your institution's disclosure policy.

## Questions you cannot answer from the report (be honest)

- Accuracy on real forgers' edits made with Photoshop, Canva or phone editors: not measured.
- Behaviour on screenshots from other operating systems or languages than those in the corpus: not measured.
- Comparison with deep localisers or with STFD-trained models: not done.
