# Outline, word budget and data sources

Format: VIT BCE497J project report (A4, Times New Roman 12 pt, 1.5 spacing, left margin 3.81 cm, other margins 2.54 cm, APA references, 60 to 100 pages). The user gave no word target; the length follows the template's page range. Delivered: about 14,500 words of chapter text (with table cells), 80 pages including front matter, references and appendices.

The default conference budget was rebalanced toward Method, Results and Limitations, because the report is a project report with a long results section and because the project's failures are its most specific content.

| Chapter | Words (approx., incl. table cells) | Ledger rows (claim_ledger.md) | Figures and tables (data source) |
|---|---|---|---|
| Abstract | 310 | A | none |
| 1 Introduction | 1,180 | I | none |
| 2 Background and survey | 1,670 | B | Table 2.1 (facts as stated in cited papers and dataset cards; `sources/`) |
| 3 Requirements and design | 1,150 | D | Fig 3.1 (architecture; `make_figures.py`), Tables 3.1 (threat model) and 3.2 (verdict tiers; `backend/analysis.py`) |
| 4 Method | 2,000 | M | Fig 4.1; Table 4.1 (rules; `backend/semantic.py`) |
| 5 Dataset and setup | 1,900 | S | Figs 5.1, 5.2; Tables 5.1, 5.2 (build logs, `final_log_parsed.json`) |
| 6 Implementation | 1,000 | P | Fig 6.1 (`docs/demo_v2_result.jpg`); Table 6.1 (line counts, `wc -l`) |
| 7 Results | 3,740 | R | Figs 7.1 to 7.8 and Tables 7.1 to 7.14 (each cites its log in Appendix 8) |
| 8 Discussion, limits, ethics | 1,300 | L | none |
| 9 Conclusion | 600 | C | Table 9.1 (objectives against evidence) |
| Appendices 1 to 8 | 1,120 | X | API response (`api_response_sample.json`, produced by the final model), code listings (read from the repository when the report is built), test table, commands, protocol, tools statement, evaluation log, evidence index |

Every Chapter 7 table has its source script or log named in Appendix 8 (Table 8.1).
