# Handoff: using the `/paper-writer` skill

`paper-writer` is a Claude Code skill that turns a finished project (repo, report, or description) into an evidence-backed research paper in IEEE, Springer, or a university format. It reads the real code and run artifacts, builds a claim ledger, drafts from it, then runs five audits. It will not invent results or write references from memory.

## 1. Install

The skill is a folder, not a plugin. You need all of it:

```
paper-writer/
  SKILL.md                    the workflow (Stages 1-7)
  references/audits.md        audit procedures + audit_report.md template
  scripts/verify_refs.py      checks references.json against Crossref/DataCite/OpenAlex/arXiv
  scripts/overlap_check.py    flags draft text that overlaps saved source texts
```

Copy the folder to `~/.claude/skills/paper-writer/` (all projects) or `<project>/.claude/skills/paper-writer/` (one project). Restart Claude Code, then confirm `/paper-writer` appears when you type `/`.

Sender, to package it:

```bash
cd ~/.claude/skills && zip -r paper-writer.zip paper-writer
```

Receiver, to install:

```bash
mkdir -p ~/.claude/skills && unzip paper-writer.zip -d ~/.claude/skills
```

## 2. Requirements

- Claude Code with web search/fetch available. If it isn't, the skill falls back to `curl` against Crossref, OpenAlex, arXiv, and Semantic Scholar.
- Python 3. Both scripts use only the standard library.
- Internet access, because reference verification calls external APIs.
- Optional: a TeX toolchain (`latexmk`, `pdflatex`, or `tectonic`) to compile the paper. Without one you get `.tex` plus a Markdown copy, marked as not compiled.

## 3. Running it

Open Claude Code **at the root of the project to be written up**, then:

```
/paper-writer
```

The skill asks once for anything missing:

| Input | Default |
|---|---|
| Project (repo path/URL, report, or description) | required |
| Length in words | asked, never guessed |
| Format | IEEE conference |
| Citation style | the format's own |
| Level | undergraduate |
| Required sections | standard structure |

For a university format, have the guideline document or template ready. It will be followed exactly.

## 4. What happens

1. **Understand the project.** It reads source, configs, tests, result files, and `git log`. It writes an evidence inventory and a list of what does not exist, such as no baseline or a single split.
2. **Find the contribution.** It classifies the work (method, system, dataset, empirical study, case study, or negative finding) and does not dress an integration up as a new algorithm. It stops and asks only if the contribution is unclear or new experiments are needed.
3. **Research the literature.** Sources are saved to `sources/` with the depth read (full, abstract, or metadata).
4. **Claim ledger and outline.** Every claim maps to its evidence before it can enter the draft.
5. **Draft.** It writes from notes with sources closed.
6. **Five audits:** project accuracy, citations, reference verification, originality, unsupported claims.
7. **Deliver.** You get the paper, `audit_report.md`, and `viva_questions.md`.

Output goes to `paper-draft/` in the project root and is never committed or pushed unless asked. An existing `paper-draft/` is read first and never overwritten.

## 5. Behaviours to expect

- **It may say the evidence can't fill your word count.** It will offer a shorter paper or real extra experiments, which you approve and which are actually run. It won't pad.
- **Thin contributions get said out loud**, with alternative framings (application study, workshop paper, technical report).
- **Failures are reported as failures.** Non-clean reference lines, checks it couldn't run, and paywalled sources read only at abstract level all appear in the final message.
- **Numbers come only from recorded runs.** It may ask to re-run your evaluation and will check first if that is slow or needs credentials.
- **Limitations and dead ends are included on purpose**, because they are the most project-specific content.

## 6. Your responsibilities afterwards

The skill reminds you of these, but they are not optional:

- Run your institution's or venue's similarity checker. `overlap_check.py` is only a self-check.
- Follow the venue's and institution's policy on disclosing AI-assisted writing.
- Be able to explain every claim without the paper open. `viva_questions.md` is for this.
- Check the `references.json` entries flagged `VERIFIED_WITH_WARNINGS` or `NOT_FOUND` by hand.

## 7. Running the scripts directly

```bash
python3 scripts/verify_refs.py paper-draft/references.json
python3 scripts/overlap_check.py paper-draft/paper.md --sources paper-draft/sources/*.txt
```

`verify_refs.py` exits 0 only when every entry is `VERIFIED` or `VERIFIED_WITH_WARNINGS`. `overlap_check.py` exits 1 if anything is flagged.
