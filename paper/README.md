# Paper: Detecting Fabricated Chat and Bank-Statement Screenshots

`main.tex` + `references.bib` — an IEEEtran conference-format paper covering
architecture, forensic-cue design, implementation, usage flow, datasets,
and evaluation results for this project, with a 23-paper literature review.

## Compiling

Requires a standard TeX distribution with `IEEEtran.cls` (bundled with the
"full" scheme of TeX Live / MiKTeX, and always available on Overleaf —
create a new Overleaf project, upload both files, and it will compile with
no further setup).

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

(Two `pdflatex` passes after `bibtex` are needed to resolve citation numbers
and cross-references.)

## Verification note

This machine has no local LaTeX installation (`pdflatex`/`bibtex` not
found), so the document could not be compiled and rendered here. Instead,
the source was checked programmatically for: brace balance, `\begin`/`\end`
environment matching, `\label`/`\ref` consistency (no dangling references),
`\cite` keys matching `references.bib` (all 23 entries cited, none orphaned),
consistent column counts across all three tables, and correct escaping of
`_`, `%`, and `&` throughout. These checks catch the failure modes most
likely in hand-written LaTeX, but they are not a substitute for an actual
compile — please compile once (e.g. via Overleaf) before relying on this
as final.
