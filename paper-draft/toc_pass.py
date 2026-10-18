"""Reads a rendered PDF of the report and writes the page numbers used in the contents and the lists."""
import json, re, subprocess, sys
pdf, outline_json, out = sys.argv[1:4]
meta = json.load(open(outline_json))
n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
pages = []
for p in range(1, n + 1):
    t = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", pdf, "-"], capture_output=True, text=True).stdout
    pages.append([re.sub(r"\s+", " ", l).strip() for l in t.split("\n") if l.strip()])
def find(pred, start=0):
    for i in range(start, n):
        if any(pred(l) for l in pages[i]):
            return i
    return None
abstract = find(lambda l: l == "ABSTRACT")
body = find(lambda l: l == "CHAPTER 1" )
# skip contents page hits: TOC lines carry dots and numbers, so exact match is body only
def arabic(i): return i - body + 1
def roman(i):
    k = i - abstract + 1
    vals = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    s = ""
    for v, r in vals:
        while k >= v: s += r; k -= v
    return s
res = {}
for o in meta["outline"]:
    key = o["key"]
    if o["level"] == 1:
        pat = o["num"]
        i = find(lambda l: l == pat, body)
    else:
        head = re.sub(r"\s+", " ", f'{o["num"]} {o["title"].upper()}')
        i = find(lambda l: head.startswith(l) and len(l) > len(o["num"]) + 8 or l.startswith(head[:40]) and l.startswith(o["num"] + " "), body)
    res[key] = arabic(i) if i is not None else None
refs = find(lambda l: l == "REFERENCES", body)
res["refs"] = arabic(refs) if refs is not None else None
for lst, pre in ((meta["tableList"], "t_"), (meta["figList"], "f_")):
    for num, cap, key in lst:
        c = re.sub(r"\s+", " ", cap)[:22]
        i = find(lambda l: l.startswith(num + " " + c) or l.startswith(num + " " + c[:12]), body)
        res[key] = arabic(i) if i is not None else None
# front pages
for key, title in (("lot", "LIST OF TABLES"), ("lof", "LIST OF FIGURES"), ("loa", "LIST OF SYMBOLS, ABBREVIATIONS AND NOMENCLATURE")):
    i = find(lambda l: l == title, abstract)
    res[key] = roman(i) if i is not None else None
missing = [k for k, v in res.items() if v is None]
json.dump(res, open(out, "w"), indent=1)
print("pages", n, "abstract pdf page", abstract + 1, "body starts pdf page", body + 1, "missing", missing)
