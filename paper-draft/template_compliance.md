# What the BCE497J template asks for, and where the report stands

Template: `BCE497J PROJECT REPORT TEMPLATE_V1.docx`. Report built: `reports/Albert_Mathew_Sunil_23BCE1765_Project_Report.docx`, 76 pages (chapters start at page 1 after 12 front-matter pages; references p. 50; appendices p. 54 to 64).

## 1. Who submits what

| Template says | Status |
|---|---|
| Group project of at most three members | Three members: Albert Mathew Sunil (23BCE1765), Gowri Manoj (23BCE1042), Meghna Biju (23BCE1743) |
| 1st and 2nd page (cover and title page) list all team members | Done: all three listed on both |
| Declaration, certificate and acknowledgement carry only your own name | Done for Albert. The same build with `SUBMITTERS=23BCE1042` or `23BCE1743` produces the other two copies (not built yet, as you asked) |
| Every individual submits a report; no group submissions | The reports are identical apart from those three pages, as you said |

## 2. Order of the report (template items 1 to 15)

| # | Template item | Status |
|---|---|---|
| 1 | Cover page | Done |
| 2 | Title page (identical text to the cover) | Done |
| 3 | Declaration by the candidate | Done; template wording kept, guide named |
| 4 | Certificate | Done; guide and HoD named; signature, examiner and seal lines left blank for signing |
| 5 | Certificate by external guide (only for PAT-discontinued students) | Not applicable, omitted |
| 6 | Abstract | Done (one page) |
| 7 | Acknowledgement | Done; two highlighted blanks (below) |
| 8 | Table of contents | Done, with page numbers |
| 9 to 10 | List of tables, list of figures | Done, with page numbers |
| 11 | List of symbols, abbreviations and nomenclature | Done (4 symbols, 11 abbreviations) |
| 12 | Chapters of the report | Done: 9 chapters |
| 13 | Conclusion and future work | Chapter 9 |
| 14 | References, APA format | Done: 37 references, all cited |
| 15 | Appendices | Done: 7 appendices |

## 3. Format rules

| Rule | Template value | Report | Verdict |
|---|---|---|---|
| Paper size | A4 | A4 | met |
| Margins | left 3.81 cm; right, top, bottom 2.54 cm | same (checked in the file) | met |
| Total pages | 60 to 100 | 76 | met |
| Binding and paper | flexible cover, white art paper, cover printed in black letters, same text as title page | not a file matter; the logo is coloured as in the template | yours to do at printing |
| Page numbers | Arabic numerals, bottom centre, on all text pages | Arabic from Chapter 1, bottom centre. The front matter uses lower-case roman numerals, as the template's own sample pages do | met, with that note |
| Font | Times New Roman 12 pt throughout the text | TNR 12 for text | met |
| Captions of tables and figures | smaller allowed, not below 10 pt | 11 pt; table text 10 pt | met |
| Program listings | not below 10 pt only stated for captions | Courier New 9 pt (listings), 11 pt inline code | grey area: raise to 10 pt if your guide reads the rule strictly |
| Paragraphs | no opening line alone at a page bottom; clear, modest gap between paragraphs | widow and orphan control on; 6 pt gap | met |
| Chapter heading | 16 pt, bold, TNR | "CHAPTER n" 12 pt bold above a 16 pt bold title, as in the template's own sample page | met |
| Section heading | 14 pt, TNR, capitals | 14 pt bold capitals | met |
| Subsection heading | 12 pt, TNR, capitals | 12 pt bold capitals | met |
| Line spacing | one consistent value; captions, contents and lists may be single | 1.5 for text; single in captions, tables, contents, lists and listings | met |
| Cover and title page layout | sizes given for each line (italic 12, bold 20 capitals, italic 14, bold 22, italic 14, bold 16 capitals, school, date) | followed line by line | met |

## 4. Content the template asks for

**Declaration and certificate**: template sentences kept word for word, with name, reg. no., title, guide and HoD filled in. The declaration still says "thesis", as the template does.

**Acknowledgement**: template text kept. Open: **Dr. Pradeep K's designation** and **area of expertise** (yellow). I changed "his/her", "he/she", "him/her" to "their", "they", "them" because I do not know the guide's pronouns.

**Chapter 1 (the template's sample lists introduction, overview, challenges, statement, objectives, scope)**: covered by 1.1 Overview, 1.2 Why screenshots are different (the challenges), 1.3 Problem statement, 1.4 Objectives, 1.5 Scope and contributions. **Chapter 2 (introduction, survey)**: covered.

**Conclusion and Future Work chapter**, item by item:

| Template asks | Where in Chapter 9 |
|---|---|
| Summarise key aspects, failures as well as successes | 9.1 What was done; 9.3 what failed and what was learned |
| State conclusions | 9.1, 9.2 |
| Outline what you would do with more time; be realistic | 9.5 Future work |
| Insights not obvious at the outset | 9.3 What the project learned |
| Discuss the success of the approach and the academic objectives achieved | 9.2 table, objective by objective, including the parts not achieved |
| Avoid meaningless conclusions and "complete success" claims | The text states the partial results (rules unit-tested only, final container not run, real-edit set only partly collected) |
| How the project performed against planned outputs and targets | 9.4: there was no accuracy target; the numeric targets that existed (about 5% and 1% false alarms; at least 20 genuine and 20 edited real screenshots) and what was reached |
| Benefits of the project | 9.4 |
| Distinguish what you did from what already existed | 9.4 (Tesseract, scikit-learn and Chrome existed; the feature set, corpus generator, protocols, rules and service are new) |
| How much more remains to be done | 9.4 and 9.5 |

**Appendices**: numbered with Arabic numerals (Appendix 1 to 7), each with its title also in the contents page; tables inside them numbered A1.1 and so on. **References**: APA 7 entries, alphabetical, numbered "[n]." in the style of the template's sample, with APA author-year citations in the text.

## 5. Recheck of the content

The text was re-read cold against the code and the run records by two separate reviewing agents, after a first audit had already produced 36 accuracy and 17 citation corrections.

- Re-audit of the abstract and Chapters 1 to 5: 20 mismatches, all corrected (examples: "held-out fonts" now says held-out edit fonts; claims that every rule had been measured or unit-tested were reduced to what exists; statements about confidence intervals and about native fakes were qualified).
- Re-audit of Chapters 6 to 9 and the appendices: 16 mismatches, all corrected (examples: logging, container wording, the claim that nothing numeric had been targeted, one causal claim attributed to a table row that the logs do not support).
- Every cross-reference resolves; all numbers in tables, abstract and prose match their logs; every Wilson interval was recomputed.
- Still not verifiable and stated as such in the text: the STFD password request and its silence; the discarded faulty script; the Chrome version at render time; the private-image descriptions; who edited the first eight-image sample.
- New in this version: Section 7.9.1 reports the second hand-collected set (2 of 9 edits flagged, 3 of 23 genuine screenshots flagged); the abstract, limitations and conclusion say so.
- Originality check against the 49 saved sources: no verbatim run of eight words or more and no structure-preserving rewording. This does not replace your institution's similarity checker.
