// Builds the three project reports (one per student) in the VIT BCE497J template format.
// Usage: NODE_PATH=<dir with docx> node build_report.js [tocPages.json]
const fs = require("fs");
const path = require("path");
const D = require("docx");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, ShadingType, PageBreak, Footer, PageNumber, NumberFormat, HeadingLevel, TabStopType,
  LevelFormat, SectionType, PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader,
  LineRuleType, VerticalAlign, TableLayoutType,
} = D;

const ROOT = path.resolve(__dirname, "..");
const HERE = __dirname;
const FONT = "Times New Roman";
const MONO = "Courier New";

// ---------------------------------------------------------------- configuration
const TITLE = "Fake Screenshot Detection System";
const PROGRAM = "Computer Science and Engineering";
const MONTH_YEAR = "October, 2026";
const STUDENTS = [
  { name: "Albert Mathew Sunil", reg: "23BCE1765" },
  { name: "Gowri Manoj", reg: "23BCE1042" },
  { name: "Meghna Biju", reg: "23BCE1743" },
];
// the template: cover and title page list all team members; declaration, certificate and acknowledgement carry only the submitter
const SUBMITTERS = (process.env.SUBMITTERS ? process.env.SUBMITTERS.split(",") : ["23BCE1765"]);
const PLACEHOLDER = { guide: "Dr. Pradeep K", designation: "<Designation>", area: "<area of the guide's expertise>", hod: "Dr. Prasanna J" };

const tocPages = fs.existsSync(process.argv[2] || "") ? JSON.parse(fs.readFileSync(process.argv[2], "utf8")) : {};

// ---------------------------------------------------------------- page geometry (A4; left 3.81 cm, others 2.54 cm)
const cm = (x) => Math.round((x / 2.54) * 1440);
const PAGE = { size: { width: 11906, height: 16838 }, margin: { top: cm(2.54), bottom: cm(2.54), left: cm(3.81), right: cm(2.54), footer: 700 } };
const TEXT_W = 11906 - cm(3.81) - cm(2.54);
const LINE15 = { line: 360, lineRule: LineRuleType.AUTO };
const LINE1 = { line: 240, lineRule: LineRuleType.AUTO };

// ---------------------------------------------------------------- references (APA 7)
const refsRaw = JSON.parse(fs.readFileSync(path.join(HERE, "references_enriched.json"), "utf8"));
const refByKey = {};
refsRaw.forEach((r) => (refByKey[r.key] = r));
const lastName = (a) => a.split(",")[0].trim();
function initials(a) {
  const parts = a.split(",");
  if (parts.length < 2) return a.trim();
  const given = parts.slice(1).join(" ").trim();
  return given.split(/[\s]+/).filter(Boolean).map((g) => (g.endsWith(".") ? g : g[0] + ".")).join(" ");
}
function fmtAuthor(a) {
  return `${lastName(a)}, ${initials(a)}`;
}
function authorList(auth) {
  const f = auth.map(fmtAuthor);
  if (f.length === 1) return f[0];
  if (f.length === 2) return `${f[0]}, & ${f[1]}`;
  return f.slice(0, -1).join(", ") + ", & " + f[f.length - 1];
}
// year suffixes where author set and year coincide
const suffix = {};
{
  const groups = {};
  refsRaw.forEach((r) => {
    const k = r.authors.map(lastName).join("|") + r.year;
    (groups[k] = groups[k] || []).push(r);
  });
  Object.values(groups).forEach((g) => {
    if (g.length > 1) {
      g.sort((a, b) => a.title.localeCompare(b.title));
      g.forEach((r, i) => (suffix[r.key] = "abcdefgh"[i]));
    }
  });
}
function cite(key) {
  const r = refByKey[key];
  if (!r) throw new Error("unknown citation key " + key);
  const n = r.authors.length;
  const a = n === 1 ? lastName(r.authors[0]) : n === 2 ? `${lastName(r.authors[0])} & ${lastName(r.authors[1])}` : `${lastName(r.authors[0])} et al.`;
  return `${a}, ${r.year}${suffix[key] || ""}`;
}
function refRuns(r) {
  // returns array of {t, i} segments
  const seg = [];
  const push = (t, i = false) => seg.push({ t, i });
  push(`${authorList(r.authors)} (${r.year}${suffix[r.key] || ""}). `);
  const kind = r._type;
  if (r.key.startsWith("hf_")) {
    push(`${r.title}`, true);
    push(` [Data set]. ${r.venue.replace(" Datasets", "")}. ${r.url}`);
  } else if (kind === "journal-article") {
    push(`${r.title}. `);
    let s = r.venue;
    push(s, true);
    let tail = "";
    if (r.volume) tail += `, `;
    push(tail);
    if (r.volume) push(r.volume, true);
    if (r.issue) push(`(${r.issue})`);
    if (r.pages) push(`, ${r.pages.replace("-", "–")}`);
    push(`. https://doi.org/${r.doi}`);
  } else if (kind === "proceedings-article") {
    push(`${r.title}. In `);
    push(r._containers[0], true);
    if (r.pages) push(` (pp. ${r.pages.replace("-", "–")})`);
    push(`. ${r._publisher && r._publisher.length < 60 ? r._publisher : ""}${r._publisher && r._publisher.length < 60 ? ". " : ""}https://doi.org/${r.doi}`);
  } else if (kind === "book-chapter") {
    push(`${r.title}. In `);
    push(r._containers.slice().reverse().join(": "), true);
    if (r.pages) push(` (pp. ${r.pages.replace("-", "–")})`);
    push(`. ${r._publisher}. https://doi.org/${r.doi}`);
  } else if (r.arxiv) {
    push(`${r.title}`, true);
    push(` (arXiv:${r.arxiv}). arXiv. ${r.url}`);
  } else if (r.url) {
    push(`${r.title}`, true);
    push(` [${r.venue}]. ${r.url}`);
  } else {
    push(`${r.title}. ${r.venue}.`);
  }
  return seg;
}
const citedKeys = new Set([...fs.readFileSync(path.join(HERE, "paper.md"), "utf8").matchAll(/@([a-z0-9_]+)/g)].map((m) => m[1]));
const bibKeys = Object.keys(refByKey).filter((k) => citedKeys.has(k)).sort((a, b) => {
  const ra = refByKey[a], rb = refByKey[b];
  const k = (r) => lastName(r.authors[0]).toLowerCase() + " " + r.authors.map(lastName).join(" ").toLowerCase() + r.year + (suffix[r.key] || "");
  return k(ra).localeCompare(k(rb));
});

// ---------------------------------------------------------------- source markup
const SRC = fs.readFileSync(path.join(HERE, "paper.md"), "utf8").split("\n");

// First pass: numbering of tables and figures, collection of headings.
const labels = { tab: {}, fig: {} };
{
  let ch = null, tc = 0, fc = 0, app = null;
  for (const line of SRC) {
    let m;
    if ((m = line.match(/^@chapter (\d+)\|/))) { ch = m[1]; tc = 0; fc = 0; app = null; }
    else if ((m = line.match(/^@appendix ([A-H])\|/))) { app = "A" + (m[1].charCodeAt(0) - 64); ch = app; tc = 0; fc = 0; }
    else if ((m = line.match(/^@table (\w+)\|/))) { tc++; labels.tab[m[1]] = `${ch}.${tc}`; }
    else if ((m = line.match(/^@fig (\w+)\|/))) { fc++; labels.fig[m[1]] = `${ch}.${fc}`; }
    else if (/^@testtable/.test(line)) { tc++; labels.tab["tests"] = `${ch}.${tc}`; }
  }
}

// ---------------------------------------------------------------- text helpers
function appendixDigits(s) {
  s = s.replace(/\bAppendix ([A-H])\b/g, (_, l) => `Appendix ${l.charCodeAt(0) - 64}`);
  s = s.replace(/\bListing ([A-H])\.(\d)/g, (_, l, n) => `Listing ${l.charCodeAt(0) - 64}.${n}`);
  return s;
}
function resolveRefs(s) {
  s = s.replace(/\{tab:(\w+)\}/g, (_, k) => { if (!labels.tab[k]) throw new Error("no table " + k); return labels.tab[k]; });
  s = s.replace(/\{fig:(\w+)\}/g, (_, k) => { if (!labels.fig[k]) throw new Error("no figure " + k); return "Figure " + labels.fig[k]; });
  s = s.replace(/\[((?:@[\w]+;?\s*)+)\]/g, (_, g) => "(" + g.split(";").map((x) => x.trim().replace(/^@/, "")).filter(Boolean).map(cite).join("; ") + ")");
  return appendixDigits(s);
}
// inline: **bold**, `code`
function runs(text, base = {}) {
  text = resolveRefs(text);
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\bT_[se]\b)/g;
  let last = 0, m;
  const mk = (t, extra = {}) => new TextRun({ text: t, font: FONT, size: 24, ...base, ...extra });
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(mk(text.slice(last, m.index)));
    const tok = m[0];
    if (tok.startsWith("T_")) { out.push(mk("T")); out.push(mk(tok[2], { subScript: true })); }
    else if (tok.startsWith("**")) out.push(mk(tok.slice(2, -2), { bold: true }));
    else out.push(new TextRun({ text: tok.slice(1, -1), font: MONO, size: Math.max(20, (base.size || 24) - 2) }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(mk(text.slice(last)));
  return out;
}
const plain = (t) => resolveRefs(t).replace(/\*\*/g, "").replace(/`/g, "");

function para(text, opt = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { ...LINE15, after: 120 },
    keepLines: false,
    widowControl: true,
    children: runs(text, opt.run || {}),
    ...opt.p,
  });
}
const blank = (n = 1, size = 24) => Array.from({ length: n }, () => new Paragraph({ children: [new TextRun({ text: "", font: FONT, size })] }));
const centered = (t, size, o = {}) =>
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 120, before: o.before ?? 0, ...LINE1 }, children: [new TextRun({ text: t, font: FONT, size, bold: o.bold, italics: o.italics, underline: o.underline, allCaps: o.caps, highlight: o.hl })] });

// ---------------------------------------------------------------- images
function imgInfo(file) {
  const b = fs.readFileSync(file);
  if (b.slice(0, 8).toString("hex") === "89504e470d0a1a0a") return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), type: "png", data: b };
  let i = 2;
  while (i < b.length) {
    if (b[i] !== 0xff) { i++; continue; }
    const mk = b[i + 1];
    const len = b.readUInt16BE(i + 2);
    if (mk >= 0xc0 && mk <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(mk)) return { h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7), type: "jpg", data: b };
    i += 2 + len;
  }
  throw new Error("bad image " + file);
}
function figureBlock(key, widthCm, caption) {
  const file = key === "fig_ui" ? path.join(ROOT, "docs", "demo_v2_result.jpg") : path.join(HERE, "figures", key + ".png");
  const im = imgInfo(file);
  const maxW = (TEXT_W / 1440) * 2.54;
  const wc = Math.min(widthCm * 0.9, maxW);
  const wpx = Math.round((wc / 2.54) * 96), hpx = Math.round((wpx * im.h) / im.w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60, ...LINE1 }, children: [new ImageRun({ type: im.type, data: im.data, transformation: { width: wpx, height: hpx }, altText: { title: key, description: caption, name: key } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200, ...LINE1 }, children: runs(`Figure ${labels.fig[key]} ${caption}`, { size: 22 }).map((r) => r) }),
  ];
}

// ---------------------------------------------------------------- tables
const thin = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const BORDERS = { top: thin, bottom: thin, left: thin, right: thin };
function tableBlock(key, caption, rows) {
  const ncol = rows[0].length;
  const wts = Array.from({ length: ncol }, (_, c) => {
    const lens = rows.map((r) => plain(r[c] || "").length);
    const mean = lens.reduce((a, b) => a + b, 0) / lens.length;
    return Math.min(Math.max(Math.sqrt(Math.max(mean, 6)), 3), 9) * (c === 0 ? 1.0 : 1.0);
  });
  const sum = wts.reduce((a, b) => a + b, 0);
  let widths = wts.map((w) => Math.floor((w / sum) * TEXT_W));
  widths[ncol - 1] += TEXT_W - widths.reduce((a, b) => a + b, 0);
  const fs_ = 20; // template: nothing below 10 pt
  const trs = rows.map((r, ri) =>
    new TableRow({
      tableHeader: ri === 0,
      cantSplit: true,
      children: r.map((cell, ci) =>
        new TableCell({
          width: { size: widths[ci], type: WidthType.DXA },
          borders: BORDERS,
          margins: { top: 40, bottom: 40, left: 80, right: 80 },
          verticalAlign: VerticalAlign.CENTER,
          shading: ri === 0 ? { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } : undefined,
          children: [new Paragraph({ keepNext: rows.length <= 12 && ri < rows.length - 1, alignment: ci > 0 && /^[\d.,%\-–+ ]+$/.test(plain(cell).trim()) && plain(cell).trim() ? AlignmentType.RIGHT : AlignmentType.LEFT, spacing: { ...LINE1 }, children: runs(cell, { size: fs_, bold: ri === 0 }) })],
        })
      ),
    })
  );
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 200, after: 80, ...LINE1 }, children: runs(`Table ${labels.tab[key]} ${caption}`, { size: 22, bold: false }) }),
    new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED, rows: trs }),
    new Paragraph({ spacing: { after: 160, ...LINE1 }, children: [] }),
  ];
}

// ---------------------------------------------------------------- listings
function codeLines(lines, caption, startNo) {
  const out = [new Paragraph({ keepNext: true, spacing: { before: 200, after: 80, ...LINE1 }, alignment: AlignmentType.LEFT, children: runs(caption, { size: 22 }) })];
  lines.forEach((l, i) => {
    const no = startNo != null ? String(startNo + i).padStart(4, " ") + "  " : "";
    out.push(new Paragraph({ spacing: { ...LINE1 }, indent: { left: 0 }, children: [new TextRun({ text: no + l.replace(/\t/g, "    "), font: MONO, size: 18 })] }));
  });
  out.push(new Paragraph({ spacing: { after: 160, ...LINE1 }, children: [] }));
  return out;
}
const LISTING = {
  "backend/analysis.py": { start: /^def _risk\(/, end: null },
  "backend/semantic.py": { start: /^def _is_numeric\(/, end: /^def check_status_bar_duplicate\(/ },
  "backend/textforensics.py": { start: /^def word_measurements\(/, end: /^def _robust_z\(/ },
  "backend/app.py": { start: /^class InMemoryUploadRequest/, end: /^@app.errorhandler\(413\)/ },
  "backend/tools/forge/train_text_model.py": { start: /^def word_table_w\(/, end: /^def tpr_at_fpr\(/ },
};
function listingBlock(file, caption) {
  const spec = LISTING[file];
  const lines = fs.readFileSync(path.join(ROOT, file), "utf8").split("\n");
  let s = lines.findIndex((l) => spec.start.test(l));
  if (s < 0) throw new Error("listing start not found " + file);
  let e = spec.end ? lines.findIndex((l, i) => i > s && spec.end.test(l)) : lines.length;
  if (e < 0) throw new Error("listing end not found " + file);
  let seg = lines.slice(s, e);
  while (seg.length && !seg[seg.length - 1].trim()) seg.pop();
  return codeLines(seg, caption, s + 1);
}
function apiJsonBlock(caption) {
  const j = JSON.parse(fs.readFileSync(path.join(HERE, "evidence", "api_response_sample.json"), "utf8"));
  const shorten = (v) => {
    if (typeof v === "string") return v.length > 90 ? v.slice(0, 87) + "..." : v;
    if (Array.isArray(v)) { const k = v.slice(0, 2).map(shorten); if (v.length > 2) k.push(`... (${v.length - 2} more)`); return k; }
    if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([a, b]) => [a, shorten(b)]));
    return v;
  };
  const lines = JSON.stringify(shorten(j), null, 2).split("\n");
  return codeLines(lines, caption, null);
}

// ---------------------------------------------------------------- headings
const outline = []; // for TOC: {level, num, title, key}
function titleCase(t) {
  const small = new Set(["and", "of", "the", "in", "for", "to", "a", "on", "or", "with"]);
  return t.toLowerCase().split(" ").map((w, i) => (i > 0 && small.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1))).join(" ");
}
function chapterHeading(num, title) {
  outline.push({ level: 1, num: `CHAPTER ${num}`, title, key: `c${num}` });
  return [
    new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER, spacing: { before: 0, after: 60, ...LINE1 }, outlineLevel: 0, children: [new TextRun({ text: `CHAPTER ${num}`, font: FONT, size: 24, bold: true })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 360, ...LINE1 }, children: [new TextRun({ text: titleCase(title), font: FONT, size: 32, bold: true })] }),
  ];
}
function sectionHeading(num, title) {
  outline.push({ level: 2, num, title, key: `s${num}` });
  return new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, spacing: { before: 280, after: 120, ...LINE1 }, outlineLevel: 1, children: [new TextRun({ text: `${num} ${title.toUpperCase()}`, font: FONT, size: 28, bold: true })] });
}
function subHeading(num, title) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true, spacing: { before: 200, after: 100, ...LINE1 }, outlineLevel: 2, children: [new TextRun({ text: `${num} ${title.toUpperCase()}`, font: FONT, size: 24, bold: true })] });
}

// ---------------------------------------------------------------- body from markup
const bodyChildren = [];
const appendixChildren = [];
let abstractText = "";
let target = bodyChildren;
let inApp = false;
{
  let i = 0;
  const L = SRC;
  while (i < L.length) {
    const line = L[i];
    let m;
    if (!line.trim()) { i++; continue; }
    if (line === "@abstract") {
      const buf = [];
      i++;
      while (L[i] !== "@endabstract") buf.push(L[i++]);
      abstractText = buf.join(" ").trim();
      i++;
      continue;
    }
    if ((m = line.match(/^@chapter (\d+)\|(.*)$/))) { target.push(...chapterHeading(m[1], m[2])); i++; continue; }
    if ((m = line.match(/^@section ([\d.]+)\|(.*)$/))) { target.push(sectionHeading(m[1], m[2])); i++; continue; }
    if ((m = line.match(/^@sub ([\d.]+)\|(.*)$/))) { target.push(subHeading(m[1], m[2])); i++; continue; }
    if ((m = line.match(/^@appendix ([A-H])\|(.*)$/))) {
      target = appendixChildren;
      const n = m[1].charCodeAt(0) - 64;
      outline.push({ level: 1, num: `APPENDIX ${n}`, title: m[2], key: `a${n}` });
      target.push(
        new Paragraph({ pageBreakBefore: true, keepNext: true, heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER, spacing: { after: 60, ...LINE1 }, outlineLevel: 0, children: [new TextRun({ text: `APPENDIX ${n}`, font: FONT, size: 24, bold: true })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { after: 240, ...LINE1 }, children: [new TextRun({ text: titleCase(m[2]), font: FONT, size: 32, bold: true })] })
      );
      i++; continue;
    }
    if (line === "@appendixtext") {
      i++;
      while (L[i] !== "@endappendixtext") { if (L[i].trim()) target.push(para(L[i])); i++; }
      i++; continue;
    }
    if (line === "@bullets" || line === "@numbered") {
      const numbered = line === "@numbered";
      i++;
      const inst = i;
      while (L[i] !== "@end") {
        const t = L[i].replace(/^(- |\d+\. )/, "");
        target.push(new Paragraph({ numbering: { reference: numbered ? "numbers" : "bullets", level: 0, instance: inst }, alignment: AlignmentType.JUSTIFIED, spacing: { ...LINE15, after: 80 }, children: runs(t) }));
        i++;
      }
      i++; continue;
    }
    if ((m = line.match(/^@fig (\w+)\|([\d.]+)\|(.*)$/))) { target.push(...figureBlock(m[1], parseFloat(m[2]), m[3])); i++; continue; }
    if ((m = line.match(/^@table (\w+)\|(.*)$/))) {
      const rows = [];
      i++;
      while (L[i] !== "@endtable") { rows.push(L[i].split("|").map((c) => c.trim())); i++; }
      const n = rows[0].length;
      rows.forEach((r) => { while (r.length < n) r.push(""); });
      target.push(...tableBlock(m[1], m[2], rows));
      i++; continue;
    }
    if (line === "@testtable") {
      const rows = [
        ["Test file", "Tests", "What the tests check"],
        ["tests/test_api.py", "11", "status and analysis endpoints, rejection of missing, wrongly named and unreadable files, response contract, inconclusive result on a blank image, the rule that the lowest tier is never called authentic, escalation by a contradiction and by an editing-software tag, agreement between the model's feature list and the code, and that large uploads are never spooled to disk"],
        ["tests/test_semantic.py", "18", "rule checks: silence on an ordinary bank page, total below subtotal, item sums, weekday against date, date formats and future dates, IBAN and Luhn checksums, generator watermarks, duplicated status-bar clock, metadata editing tag, and five cases of the layout-grid rule"],
        ["tests/test_textforensics.py", "6", "OCR and feature shape, a blank image has no measurable words, the edit simulator changes pixels only inside the target box, an edited word is a stronger outlier than untouched words, the font bank holds an unseen test fold, and degradation rescales boxes"],
        ["Total", "35", ""],
      ];
      target.push(...tableBlock("tests", "Backend automated tests by file (35 tests, all passing in the recorded run)", rows));
      i++; continue;
    }
    if ((m = line.match(/^@apijson (\S+)\|(.*)$/))) { target.push(...apiJsonBlock(appendixDigits(m[2]))); i++; continue; }
    if ((m = line.match(/^@listing (\S+)\|(\w+)\|(\w+)\|(.*)$/))) { target.push(...listingBlock(m[1], appendixDigits(m[4]))); i++; continue; }
    if ((m = line.match(/^@code (.*?)\|(.*)$/))) {
      const buf = [];
      i++;
      while (L[i] !== "@endcode") buf.push(L[i++]);
      i++;
      target.push(...codeLines(buf, appendixDigits(m[2]), null));
      continue;
    }
    if ((m = line.match(/^@verbatim (\S+)\|(.*)$/))) {
      const f = path.join(ROOT, m[1]);
      const lines = fs.readFileSync(f, "utf8").split("\n").map((l) => l.replace(/\s+$/, ""));
      while (lines.length && !lines[lines.length - 1]) lines.pop();
      // wrap long lines to fit the page width at 7.5pt Courier
      const wrapped = [];
      lines.forEach((l) => { for (let k = 0; k < Math.max(1, Math.ceil(l.length / 88)); k++) wrapped.push((k ? "    " : "") + l.slice(k * 88, (k + 1) * 88)); });
      target.push(...codeLines(wrapped, appendixDigits(m[2]), null));
      i++; continue;
    }
    if (line.startsWith("@")) throw new Error("unhandled directive: " + line);
    target.push(para(line));
    i++;
  }
}

// ---------------------------------------------------------------- acronyms
const SYMBOLS = [["p", "Highest word probability of being edited in an image (output of the classifier)"], ["T_s", "Suspicious-tier threshold on p (about 5% false alarms on validation images)"], ["T_e", "Evidence-tier threshold on p (about 1% false alarms on validation images)"], ["z", "Robust z-score of a measurement against the comparison set (median and scaled median absolute deviation)"]];
const ACRONYMS = [
  ["AA", "Anti-aliasing"], ["API", "Application programming interface"], ["AUC", "Area under the ROC curve"],
  ["CPU", "Central processing unit"], ["EXIF", "Exchangeable image file format (image metadata)"],
  ["ELA", "Error level analysis"], ["FPR", "False-positive rate (share of genuine images flagged)"],
  ["GBM", "Gradient-boosted trees"], ["IBAN", "International bank account number"],
  ["JPEG", "Joint Photographic Experts Group image format"], ["LCD", "Liquid-crystal display"],
  ["OCR", "Optical character recognition"], ["PNG", "Portable Network Graphics image format"],
  ["ROC", "Receiver operating characteristic"], ["SHA-256", "Secure hash algorithm, 256-bit"],
  ["TPR", "True-positive rate (share of edited images flagged)"], ["UI", "User interface"],
];
const acronymsUsed = ACRONYMS.filter(([a]) => new RegExp("\\b" + a.replace("-", "\\-") + "\\b").test(SRC.join("\n")));

// ---------------------------------------------------------------- front matter
const logoData = fs.readFileSync(path.join(HERE, "assets", "vit_logo.jpg"));
const logoPara = () => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120, ...LINE1 }, children: [new ImageRun({ type: "jpg", data: logoData, transformation: { width: Math.round((8.78 / 2.54) * 96), height: Math.round((2.93 / 2.54) * 96) }, altText: { title: "VIT logo", description: "Vellore Institute of Technology, Chennai", name: "logo" } })] });

function titlePage(final) {
  const kids = [
    blank(1)[0],
    centered("A project report on", 24, { italics: true, after: 200 }),
    centered(TITLE.toUpperCase(), 40, { bold: true, after: 240, before: 120 }),
    centered("Submitted in partial fulfillment for the award of the degree of", 28, { italics: true, after: 240 }),
    centered(`Bachelor of Technology in ${PROGRAM}`, 44, { bold: true, after: 360 }),
    centered("by", 28, { italics: true, after: 200 }),
    ...STUDENTS.map((s) => centered(`${s.name.toUpperCase()} (${s.reg})`, 32, { bold: true, after: 100 })),
    ...blank(3),
    logoPara(),
    centered("SCHOOL OF COMPUTER SCIENCE AND ENGINEERING", 32, { bold: true, after: 200, before: 120 }),
    centered(MONTH_YEAR.toUpperCase(), 32, { bold: true }),
  ];
  return kids;
}
function hl(text, size = 24, extra = {}) {
  return new TextRun({ text, font: FONT, size, ...(text.startsWith("<") ? { highlight: "yellow" } : {}), ...extra });
}
function declaration(s) {
  return [
    logoPara(),
    ...blank(1),
    centered("DECLARATION", 28, { bold: true, underline: {}, after: 360 }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { ...LINE15, after: 200 }, indent: { firstLine: 720 }, children: [
      new TextRun({ text: `I hereby declare that the thesis entitled \u201C${TITLE.toUpperCase()}\u201D submitted by ${s.name.toUpperCase()} (${s.reg}), for the award of the degree of Bachelor of Technology in ${PROGRAM}, Vellore Institute of Technology, Chennai is a record of bonafide work carried out by me under the supervision of `, font: FONT, size: 24 }),
      hl(PLACEHOLDER.guide), new TextRun({ text: ".", font: FONT, size: 24 }) ] }),
    para("I further declare that the work reported in this thesis has not been submitted and will not be submitted, either in part or in full, for the award of any other degree or diploma in this institute or any other institute or university.", { p: { indent: { firstLine: 720 } } }),
    ...blank(4),
    new Paragraph({ spacing: { ...LINE1 }, children: [new TextRun({ text: "Place: Chennai", font: FONT, size: 24 })] }),
    new Paragraph({ spacing: { before: 120, ...LINE1 }, tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }], children: [new TextRun({ text: "Date:", font: FONT, size: 24 }), new TextRun({ text: "\tSignature of the Candidate", font: FONT, size: 24, bold: true })] }),
    new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 120, ...LINE1 }, children: [new TextRun({ text: `${s.name} (${s.reg})`, font: FONT, size: 24 })] }),
  ];
}
function certificate(s) {
  const t = (x, o = {}) => new TextRun({ text: x, font: FONT, size: 24, ...o });
  const L1 = (children, o = {}) => new Paragraph({ spacing: { before: 120, ...LINE1 }, children, ...o });
  return [
    logoPara(),
    centered("School of Computer Science and Engineering", 24, { bold: true, after: 240 }),
    centered("CERTIFICATE", 28, { after: 240 }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { ...LINE15, after: 240 }, children: [
      t(`This is to certify that the report entitled \u201C${TITLE}\u201D is prepared and submitted by ${s.name} (${s.reg}) to Vellore Institute of Technology, Chennai, in partial fulfillment of the requirement for the award of the degree of Bachelor of Technology in ${PROGRAM} is a bonafide record carried out under my guidance. The project fulfills the requirements as per the regulations of this University and in my opinion meets the necessary standards for submission. The contents of this report have not been submitted and will not be submitted either in part or in full, for the award of any other degree or diploma and the same is certified.`) ] }),
    L1([t("Signature of the Guide:")]),
    L1([t("Name: "), hl(PLACEHOLDER.guide)]),
    L1([t("Date:")]),
    ...blank(1),
    new Paragraph({ spacing: { before: 200, ...LINE1 }, tabStops: [{ type: TabStopType.LEFT, position: cm(8.2) }], children: [t("Signature of the Examiner\tSignature of the Examiner")] }),
    new Paragraph({ spacing: { before: 120, ...LINE1 }, tabStops: [{ type: TabStopType.LEFT, position: cm(8.2) }], children: [t("Name:\tName:")] }),
    new Paragraph({ spacing: { before: 120, ...LINE1 }, tabStops: [{ type: TabStopType.LEFT, position: cm(8.2) }], children: [t("Date:\tDate:")] }),
    ...blank(1),
    centered("Approved by the Head of Department,", 24, { before: 200, after: 40 }),
    centered(`B.Tech. ${PROGRAM}`, 24, { bold: true, after: 120 }),
    new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { ...LINE1 }, children: [t("Name: "), hl(PLACEHOLDER.hod)] }),
    new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 120, ...LINE1 }, children: [t("Date:")] }),
    ...blank(1),
    new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { ...LINE1 }, children: [t("(Seal of the School of Computer Science and Engineering)", { bold: true, size: 20 })] }),
  ];
}
function abstractPage() {
  return [
    centered("ABSTRACT", 28, { bold: true, underline: {}, after: 360 }),
    para(abstractText, { p: { spacing: { ...LINE15, after: 200 } } }),
    new Paragraph({ spacing: { ...LINE15, before: 120 }, children: [new TextRun({ text: "Keywords: ", font: FONT, size: 24, bold: true }), new TextRun({ text: "screenshot forensics; text tampering; optical character recognition; gradient-boosted trees; synthetic dataset; explainable detection", font: FONT, size: 24 })] }),
  ];
}
function acknowledgement(s) {
  const t = (x, o = {}) => new TextRun({ text: x, font: FONT, size: 24, ...o });
  const P = (children) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { ...LINE15, after: 160 }, children });
  return [
    centered("ACKNOWLEDGEMENT", 28, { bold: true, after: 300 }),
    P([t("It is my pleasure to express with deep sense of gratitude to "), hl(PLACEHOLDER.guide), t(", "), hl(PLACEHOLDER.designation), t(", School of Computer Science and Engineering, Vellore Institute of Technology, Chennai, for their constant guidance, continual encouragement, understanding; more than all, they taught me patience in my endeavor. My association with them is not confined to academics only, but it is a great opportunity on my part of work with an intellectual and expert in the field of "), hl(PLACEHOLDER.area), t(".")]),
    P([t("It is with gratitude that I would like to extend my thanks to the visionary leader Dr. G. Viswanathan our Honorable Chancellor, Mr. Sankar Viswanathan, Dr. Sekar Viswanathan, Dr. G V Selvam Vice Presidents, Dr. Sandhya Pentareddy, Executive Director, Ms. Kadhambari S. Viswanathan, Assistant Vice-President, Dr. V. S. Kanchana Bhaaskaran Vice-Chancellor, Dr. T. Thyagarajan Pro-Vice Chancellor, VIT Chennai and Dr. P. K. Manoharan, Additional Registrar for providing an exceptional working environment and inspiring all of us during the tenure of the course.")]),
    P([t("Special mention to Dr. Viswanathan V, Dean, Dr. Nithyanandam P, Associate Dean, Dr. Suganya G, Associate Dean, Dr. Sweetlin Hemalatha C, Associate Dean, School of Computer Science and Engineering, Vellore Institute of Technology, Chennai for spending their valuable time and efforts in sharing their knowledge and for helping us in every aspect.")]),
    P([t("In jubilant state, I express ingeniously my whole-hearted thanks to "), hl(PLACEHOLDER.hod), t(`, Head of the Department, B.Tech. ${PROGRAM} and the Project Coordinators for their valuable support and encouragement to take up and complete the thesis.`)]),
    P([t("My sincere thanks to all the faculties and staffs at Vellore Institute of Technology, Chennai who helped me acquire the requisite knowledge. I would like to thank my parents for their support. It is indeed a pleasure to thank my friends who encouraged me to take up and complete this task.")]),
    new Paragraph({ spacing: { before: 200, ...LINE1 }, children: [t("Place: Chennai")] }),
    new Paragraph({ spacing: { before: 120, ...LINE1 }, tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W }], children: [t("Date:"), t(`\t${s.name}`, { bold: true })] }),
  ];
}

// ---------------------------------------------------------------- TOC and lists
function tocEntry(label, pageKey, o = {}) {
  const pg = tocPages[pageKey] !== undefined ? String(tocPages[pageKey]) : "00";
  return new Paragraph({
    spacing: { before: o.before ?? 40, after: 20, ...LINE1 },
    indent: { left: o.indent || 0, hanging: o.hanging || 0 },
    tabStops: [{ type: TabStopType.RIGHT, position: TEXT_W, leader: "dot" }],
    children: [new TextRun({ text: label, font: FONT, size: 24, bold: o.bold }), new TextRun({ text: `\t${pg}`, font: FONT, size: 24, bold: o.bold })],
  });
}
function tocPageChildren() {
  const kids = [centered("CONTENTS", 28, { bold: true, after: 240 })];
  kids.push(tocEntry("LIST OF TABLES", "lot", { bold: true }), tocEntry("LIST OF FIGURES", "lof", { bold: true }), tocEntry("LIST OF SYMBOLS, ABBREVIATIONS AND NOMENCLATURE", "loa", { bold: true }));
  const add = (o) => {
    if (o.level === 1) kids.push(tocEntry(`${o.num}  ${o.title.toUpperCase()}`, o.key, { bold: true, before: 160 }));
    else kids.push(tocEntry(`${o.num}  ${o.title.toUpperCase()}`, o.key, { indent: 1000, hanging: 700 }));
  };
  outline.filter((o) => !o.key.startsWith("a")).forEach(add);
  kids.push(tocEntry("REFERENCES", "refs", { bold: true, before: 160 }));
  outline.filter((o) => o.key.startsWith("a")).forEach(add);
  return kids;
}
const tableList = [];
const figList = [];
{
  let ch = null;
  for (const line of SRC) {
    let m;
    if ((m = line.match(/^@table (\w+)\|(.*)$/))) tableList.push([`Table ${labels.tab[m[1]]}`, plain(m[2]), "t_" + m[1]]);
    else if (line === "@testtable") tableList.push([`Table ${labels.tab["tests"]}`, "Backend automated tests by file (35 tests, all passing in the recorded run)", "t_tests"]);
    else if ((m = line.match(/^@fig (\w+)\|[\d.]+\|(.*)$/))) figList.push([`Figure ${labels.fig[m[1]]}`, plain(m[2]), "f_" + m[1]]);
  }
}
function shortCap(c) { c = c.replace(/\s*\(evidence:[^)]*\)/g, ""); const m = c.match(/^(.*?[a-z0-9)])\.(\s|$)/); return (m ? m[1] : c.replace(/\.$/, "")); }
function listPage(title, items, keyPrefix) {
  const kids = [centered(title, 28, { bold: true, after: 240 })];
  for (const [num, cap, key] of items) {
    const pg = tocPages[key] !== undefined ? String(tocPages[key]) : "00";
    kids.push(new Paragraph({ spacing: { before: 60, after: 40, ...LINE1 }, indent: { left: 1500, hanging: 1500 }, tabStops: [{ type: TabStopType.LEFT, position: 1500 }, { type: TabStopType.RIGHT, position: TEXT_W, leader: "dot" }], children: [new TextRun({ text: `${num}\t${shortCap(cap)}\t${pg}`, font: FONT, size: 22 })] }));
  }
  return kids;
}
function acronymPage() {
  const kids = [centered("LIST OF SYMBOLS, ABBREVIATIONS AND NOMENCLATURE", 28, { bold: true, after: 240 })];
  const w1 = cm(3.2);
  const thinN = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const nb = { top: thinN, bottom: thinN, left: thinN, right: thinN };
  kids.push(new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: [w1, TEXT_W - w1], layout: TableLayoutType.FIXED,
    rows: [...SYMBOLS, ...acronymsUsed].map(([a, d]) => new TableRow({ children: [
      new TableCell({ width: { size: w1, type: WidthType.DXA }, borders: nb, children: [new Paragraph({ spacing: { before: 40, after: 40, ...LINE1 }, children: runs(a, { bold: true }) })] }),
      new TableCell({ width: { size: TEXT_W - w1, type: WidthType.DXA }, borders: nb, children: [new Paragraph({ spacing: { before: 40, after: 40, ...LINE1 }, children: [new TextRun({ text: d, font: FONT, size: 24 })] })] }),
    ] })) }));
  return kids;
}

// ---------------------------------------------------------------- references section
function referencesSection() {
  const kids = [
    new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER, spacing: { after: 360, ...LINE1 }, outlineLevel: 0, children: [new TextRun({ text: "REFERENCES", font: FONT, size: 32, bold: true })] }),
  ];
  bibKeys.forEach((k, n) => {
    const segs = refRuns(refByKey[k]);
    kids.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { ...LINE1, after: 120 }, indent: { left: 567, hanging: 567 }, children: [new TextRun({ text: `[${n + 1}]. `, font: FONT, size: 24 }), ...segs.map((s) => new TextRun({ text: s.t, font: FONT, size: 24, italics: s.i }))] }));
  });
  return kids;
}

// ---------------------------------------------------------------- document assembly
const footerNum = () => new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 24 })] })] });
const noFooter = () => new Footer({ children: [new Paragraph({ children: [] })] });

const defaultStyles = {
  default: { document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { ...LINE15 } } } },
  paragraphStyles: [
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 32, bold: true, color: "000000" }, paragraph: { spacing: { before: 0, after: 120 }, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 28, bold: true, color: "000000" }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 24, bold: true, color: "000000" }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
  ],
};
const numberingCfg = {
  config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  ],
};

function buildDoc(s) {
  const secProps = (extra = {}) => ({ page: { ...PAGE, ...extra }, type: SectionType.NEXT_PAGE });
  const roman = () => secProps({ pageNumbers: { formatType: NumberFormat.LOWER_ROMAN } });
  return new Document({
    creator: s.name,
    title: `${TITLE} - project report`,
    description: "BCE497J project report",
    styles: defaultStyles,
    numbering: numberingCfg,
    sections: [
      { properties: secProps(), footers: { default: noFooter() }, children: titlePage() },
      { properties: secProps(), footers: { default: noFooter() }, children: titlePage() },
      { properties: secProps(), footers: { default: noFooter() }, children: declaration(s) },
      { properties: secProps(), footers: { default: noFooter() }, children: certificate(s) },
      { properties: secProps({ pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } }), footers: { default: footerNum() }, children: abstractPage() },
      { properties: roman(), footers: { default: footerNum() }, children: acknowledgement(s) },
      { properties: roman(), footers: { default: footerNum() }, children: tocPageChildren() },
      { properties: roman(), footers: { default: footerNum() }, children: listPage("LIST OF TABLES", tableList) },
      { properties: roman(), footers: { default: footerNum() }, children: listPage("LIST OF FIGURES", figList) },
      { properties: roman(), footers: { default: footerNum() }, children: acronymPage() },
      { properties: secProps({ pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } }), footers: { default: footerNum() }, children: bodyChildren },
      { properties: secProps(), footers: { default: footerNum() }, children: referencesSection() },
      { properties: secProps(), footers: { default: footerNum() }, children: appendixChildren },
    ],
  });
}

(async () => {
  const outDir = path.join(HERE, "reports");
  fs.mkdirSync(outDir, { recursive: true });
  for (const s of STUDENTS.filter((x) => SUBMITTERS.includes(x.reg))) {
    const buf = await Packer.toBuffer(buildDoc(s));
    const f = path.join(outDir, `${s.name.replace(/ /g, "_")}_${s.reg}_Project_Report.docx`);
    fs.writeFileSync(f, buf);
    console.log("wrote", f, buf.length);
  }
  fs.writeFileSync(path.join(HERE, "reports", "_outline.json"), JSON.stringify({ outline, tableList, figList, refs: bibKeys.length }, null, 1));
})();
