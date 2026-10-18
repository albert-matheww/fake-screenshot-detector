# Audit report - Fake Screenshot Detection System

Date: 2026-10-15   Draft: `paper.md` (parts 1 to 5), built into three Word reports by `build_report.js`   Length: about 15,000 words of chapter text including table cells, 82 pages (template range 60 to 100); no word target was given.

The accuracy and citation audits were cold reads carried out by separate reviewing agents that had only the repository, `evidence/` and `sources/`; I applied the corrections and re-ran the originality check and the build afterwards. The corrected text was not audited a second time in full; the changed passages were written from the audit findings.

## Summary

| Audit | Items checked | Fixed | Removed | Open |
|---|---|---|---|---|
| 1 Project accuracy | about 300 claims in 106 grouped rows; 36 mismatches | 36 | 0 | 17 unverifiable (8 reworded or softened, 9 stated as unrecorded; see open items) |
| 2 Citations | 78 citation occurrences, 37 keys | 17 (16 flagged plus 1 found by audit 1) | 0 | 0 |
| 3 Reference verification | 37 references | 0 | 0 | 3 not indexed (confirmed by hand), 1 name spelling |
| 4 Originality | 18,535 words against 49 saved sources | 8 passages rewritten | 0 | residual risk (script only) |
| 5 Unsupported claims | strength and novelty words swept (7 hits) plus the unverifiable items of audit 1 | 7 | 0 | causal and universal words were not swept line by line |

## 1 Project accuracy

All Chapter 7 table cells, the Wilson intervals, the corpus counts (20,814 images, four builds, split table), the 95-feature breakdown, classifier settings, thresholds (0.847 and 0.966), leave-files-out results (5.5%, 0%, 45%, 24%), code line counts, test counts (35 backend, 58 frontend), version pins and the API response sample were re-derived from their artifacts and match. Several evaluations were re-run by the reviewing agent with identical output (pytest, vitest, `wilson.py`, `eval_layout_rule.py`, the API sample, app behaviour for large and oversized uploads).

Mismatches found and corrected (paper wording changed in each case):

| Item | What was wrong | Correction |
|---|---|---|
| Abstract AUC | 0.85 is the full test set; 0.46 is on a 500-image subset where the final model scored 0.84 | both figures now stated |
| "Limitations shown permanently" | panel appears under results only | "displayed under every result" |
| Rules "validated on thousands of images" (objective 5, contribution, principle 2, protocol 5) | only the layout rule was measured at corpus scale | reworded in four places; other rules described as unit-tested |
| "Five protocols" vs seven | internal inconsistency | refers to Section 5.7 |
| Appendix list lacked G and H | | added |
| "Every number can be regenerated" | private screenshots, discarded faulty run | reworded |
| Layout rule recall "Yes" | recall is at most 15% | "Partly", with the minimum displacement |
| Layout rule height filter and six-row minimum | code keeps 0.75 to 1.33 of median; a six-row column can never fire | corrected |
| 1,600 Chrome images vs 3,200 genuine | same bases used in two builds | explained after the corpus table |
| "Every test edit uses an unseen font" | splices use no bank font | qualified |
| Leave-files-out "six copies" | 426 edits, Pillow engine, no splices | corrected |
| Confidence-interval statements (two places) | contradicted the Wilson intervals reported | corrected both ways |
| "Transaction identifier" in limitations text | text says only "confirm with the issuer" | reworded |
| IMD2020 "70,000 manipulated" | source: 35,000 manipulated, 70,000 in all | corrected |
| "One or more reasons for each mark" | list can be empty | reworded |
| Pillow-only model "first model scored 0.75" | artifact is a retrained Pillow-only model | reworded |
| Container check (6.6, objective 6, Appendix H) | `docker_test_final.log` was empty; the logged image holds an older model | text now says an earlier image was run; rebuild of the final tree failed (registry timeout, `docker_build_final.log`); empty log deleted |
| 42 of 60 qualifying screenshots | second draw: 28 of its 42 files overlap the audited 60 | stated |
| Native-fake pages "pixel cues did not differ" | JPEG-ghost cue differed, wrong way round | corrected with values |
| Appendix D commands | wrong `--real-windows`, missing `--bank` build, `--n 500`, docker path, over-claimed title | corrected and retitled as illustrative |
| Logging, 400/500 behaviour, interval scope, FPR denominator, anti-aliasing wording, Appendix H gaps, facts.txt stale line counts, five (not six) layout tests | small factual drifts | corrected; `facts.txt` regenerated |
| nginx buffering of large uploads (found by reviewer) | in-memory claim holds for the Flask app only | caveat added to 6.5 |
| Legacy response aliases | not mentioned | added to 3.7 |

## 2 Citations

62 of 78 occurrences supported. Flagged and fixed: 9 overstated (qu2023doctamper twice, ronfleux2026docqt, zhao2026docforge twice, venkatesh2026screenshot, zhang2026textfake, hf_stfd twice), 3 not in source (FSTS size twice, ronfleux2026docqt on label shortcuts), 3 read-depth insufficient (farid2009survey twice, mahdian2009noise), 1 cite-dropping (yu2025fsts). The FSTS size was re-verified from the Hugging Face file listing (`sources/hf_FSTS_files.txt`: one 46.0 GB archive) and kept. The inference that a replaced word differs in rendering is now labelled as this project's working hypothesis, not attributed to DocTamper. Every cited key is in `references.json` and none is orphaned.

## 3 Reference verification

`verify_refs.py`: 34 of 37 verified (one with a venue-string warning: the FSTS preprint is also listed as a NeurIPS 2025 Datasets and Benchmarks Track paper in its own record; cited as the arXiv version read). Three not indexed in Crossref, OpenAlex or arXiv: `krawetz2007` (white paper; PDF read in full, URL recorded), `hf_stfd` and `hf_fsts` (dataset cards; pages read, URLs recorded, accessed 2026-10-15). Several sources were read at abstract level only; claims about them are limited to the abstract.

## 4 Originality

Before: 5 verbatim runs of 8 or more words (45 words, 0.3%) and 3 structure-preserving hits. After rewriting from notes: 0 and 0. The script sees only the 49 saved sources. Related Work paragraphs were organised around what this project needs, not around any one source's order. Quotations: none beyond short quoted terms.

## 5 Unsupported claims

Swept: novel, first, state-of-the-art, outperform, best, superior, robust, comprehensive, significant, generalise, scalable, real-time, accurate, reliable and similar words. Seven hits; "best-known" (error level analysis) softened; "robust z-score" is a statistical term. No "significant" without a test, no "outperforms", no deployment-readiness wording. Claims the audit could not tie to an artifact were softened (sharpness features "heavily" used, time "dominated by OCR", design changes mattering "more than any tuning", the guard "exercised in practice", the browser check, the cause of z-score saturation). Not done: a line-by-line sweep for causal and universal words.

## Open items (need a decision or evidence)

- Guide name, designation, area of expertise, HoD name: highlighted placeholders in the reports. The month and year on the cover (October, 2026) is the current month; change if needed.
- Final container image was never run (base-image pull timed out). Re-run `paper-draft/evidence/docker_check.sh` with network access and add the result if wanted.
- The STFD password request has no correspondence on record in the repository; the report states it as made and unanswered on the authors' word.
- Who made the four edited screenshots and with which tools is unrecorded; the report says "a person with their own tools" and does not call them independent in the abstract.
- The Chrome version at corpus render time (155) is the installed version, not a logged one; 89 real files are counted from the build log, a fresh search finds 88.
- Author name in `lukas2006prnu`: Crossref gives "Luka"; the printed surname probably has diacritics. Check against the paper itself before submission.
- The first-model out-of-distribution evaluation and the faulty cross-validation run have no saved output; both are described as such.

## Not checked / limits of these audits

- Similarity software (the institution's checker) was not run; the overlap script is a self-check only.
- No second full audit after the corrections.
- Read at abstract level only (claims limited to what the abstract states): 21 sources, namely Farid 2009 (both), Popescu and Farid 2005, Lukáš et al. 2006, Bianchi and Piva 2012, Piva 2013, ManTra-Net, CAT-Net, TruFor, CASIA, IMD2020, STFD paper, RWTamper, ForensicHub, Unmask Tampering, Venkatesh 2026, Tesseract, Friedman 2001, scikit-learn, Torralba and Efros, Wilson 1927. Bibliographic record only (the report asserts only that the work exists or what its title says): Mahdian and Saic 2009, Tornés et al. 2023, Fawcett 2006. Read in full: 13 sources.
- The 8 private screenshots and the author's real screenshots were scored but not shown; the per-image descriptions in Table 7.13 cannot be re-checked by anyone without them.

## Revision 2026-10-16 (shortened, single student)

Shortened from 82 to 71 pages by removing sections 1.6, 3.7, 6.7, 7.12 and 9.3, six figures that duplicated tables, two small tables (replaced by text), Appendix G (the verbatim training log, still in `evidence/`), and two of the four code listings; Chapter 2 was condensed; figures were scaled down. No new claims were added, so the audits above were not repeated; the reference list now holds only works that are cited. The report is built for Albert Mathew Sunil (23BCE1765) only; the guide (Dr. Pradeep K) and HoD (Dr. Prasanna J) are filled in. A copy of the previous 82-page, three-student version is in `paper-draft-backup-82pages/`.

## Revision 2026-10-16 (second shortening, 40 pages)

The report was rewritten in condensed form (`paper_short.md`, built as `paper.md`): about 6,500 words instead of 15,000, line spacing 1.25, six chapters shortened and the appendices reduced to five. All sentences were condensed from the audited long text (`paper_long_71pages.md`), and an automated check confirmed that every number in the short text also occurs in the long text. The condensed wording itself was not audited a second time by a separate reader. Dropped: the development-changes table, the cue tables, the dataset table of related work, most figures, the API JSON listing, three of the four code listings, the real-edit protocol appendix (its content is now future-work item 1), and references no longer cited.

## Revision 2026-10-16 (template-conformant 76-page version)

After the shortened versions, the report was rebuilt to follow the template (1.5 spacing, 60 to 100 pages, all team members on the cover and title page, chapter headings as in the template). It uses the 71-page text plus: a restored "what the project learned" section, a new section on planned outputs, benefits and what was new (the template asks for these), and Section 7.9.1 for the second hand-collected set. Two further cold-read re-audits (20 and 16 mismatches) were corrected. See `template_compliance.md`.
