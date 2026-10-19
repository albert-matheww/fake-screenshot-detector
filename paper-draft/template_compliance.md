# What the BCE497J template asks for, and where the report stands

Template: `BCE497J PROJECT REPORT TEMPLATE_V1.docx`. Report built: `reports/Albert_Mathew_Sunil_23BCE1765_Project_Report.docx`, 96 pages (chapters start at page 1 after 12 front-matter pages; references p. 71; appendices p. 75 to 83).

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
| 14 | References, APA format | Done: 40 references, all cited |
| 15 | Appendices | Done: 7 appendices |

## 3. Format rules

| Rule | Template value | Report | Verdict |
|---|---|---|---|
| Paper size | A4 | A4 | met |
| Margins | left 3.81 cm; right, top, bottom 2.54 cm | same (checked in the file) | met |
| Total pages | 60 to 100 | 96 | met (rendered with LibreOffice; Word may differ by a page or two, so check before printing) |
| Binding and paper | flexible cover, white art paper, cover printed in black letters, same text as title page | not a file matter; the logo is coloured as in the template | yours to do at printing |
| Page numbers | Arabic numerals, bottom centre, on all text pages | Arabic from Chapter 1, bottom centre. The front matter uses lower-case roman numerals, as the template's own sample pages do | met, with that note |
| Font | Times New Roman 12 pt throughout the text | TNR 12 for text | met |
| Captions of tables and figures | smaller allowed, not below 10 pt | 11 pt; table text 10 pt | met |
| Program listings | not below 10 pt only stated for captions | Courier New 10 pt (listings), 11 pt inline code | met (raised from 9 pt so the strict reading is also satisfied) |
| Paragraphs | no opening line alone at a page bottom; clear, modest gap between paragraphs | widow and orphan control on; 6 pt gap | met |
| Chapter heading | 16 pt, bold, TNR | "CHAPTER n" 12 pt bold above a 16 pt bold title, as in the template's own sample page | met |
| Section heading | 14 pt, TNR, capitals | 14 pt bold capitals | met |
| Subsection heading | 12 pt, TNR, capitals | 12 pt bold capitals | met |
| Line spacing | one consistent value; captions, contents and lists may be single | 1.5 for text; single in captions, tables, contents, lists and listings | met |
| Cover and title page layout | sizes given for each line (italic 12, bold 20 capitals, italic 14, bold 22, italic 14, bold 16 capitals, school, date) | followed line by line | met |

## 4. Content the template asks for

**Declaration and certificate**: template sentences kept word for word, with name, reg. no., title, guide and HoD filled in. The declaration still says "thesis", as the template does.

**Acknowledgement**: template text kept. Dr. Pradeep K is named as Associate Professor, with cloud computing as the area of expertise (the two former blanks). I changed "his/her", "he/she", "him/her" to "their", "they", "them" because I do not know the guide's pronouns.

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

The report was rewritten around the final version (type chosen by the person, calibration gates, assurance levels, compare and reconcile modes) and re-checked after each round of changes.

- Four audit rounds by separate reviewing agents against the code and the evidence files (accuracy of Chapters 1 to 6; accuracy of Chapters 7 to 9; citations; a consistency sweep; a re-audit of the new sections; a final audit of the rewritten parts). Each round's corrections were applied; the first two rounds alone produced about 50 corrections.
- Every cross-reference resolves, all 40 references are cited, and no verbatim run of eight words or more matches a saved source (the overlap check was run on an earlier draft and not repeated; re-run it before submitting, and run your institution's similarity checker).
- Not verifiable from the repository and stated as such in the text: the reply from the STFD authors, the transcription of the SMS texts (done by the AI assistant from screenshots), the private-image descriptions, the outputs of earlier rule versions and intermediate runs, and the browser session.
- The report states its limits plainly: almost no check counts, level 1 does not separate genuine from consistently edited screenshots, and reconcile mode corroborated none of 7 real Google Pay pairs.
