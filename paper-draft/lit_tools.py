"""Literature retrieval helpers (Crossref / OpenAlex / arXiv). Queries come from me; the records come from the services."""
import json, re, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET

UA = {"User-Agent": "paper-writer-student-project/1.0 (mailto:albertmathewsunil@gmail.com)"}


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def crossref(query, rows=4):
    u = "https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query.bibliographic": query, "rows": rows,
         "select": "title,DOI,author,issued,container-title,type,abstract,volume,issue,page,publisher"})
    out = []
    for it in json.loads(get(u))["message"]["items"]:
        out.append({"src": "crossref", "title": (it.get("title") or [""])[0], "doi": it.get("DOI"),
                    "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
                    "venue": (it.get("container-title") or [""])[0], "type": it.get("type"),
                    "authors": [f'{a.get("family","")}, {a.get("given","")}' for a in it.get("author", [])][:8],
                    "volume": it.get("volume"), "issue": it.get("issue"), "pages": it.get("page"),
                    "abstract": re.sub(r"<[^>]+>", "", it.get("abstract", "") or "")})
    return out


def arxiv(query, rows=3):
    u = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": "all:" + query, "max_results": rows})
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(get(u))
    out = []
    for e in root.findall("a:entry", ns):
        out.append({"src": "arxiv", "title": " ".join(e.find("a:title", ns).text.split()),
                    "id": e.find("a:id", ns).text.split("/abs/")[-1],
                    "year": int(e.find("a:published", ns).text[:4]),
                    "authors": [a.find("a:name", ns).text for a in e.findall("a:author", ns)][:8],
                    "abstract": " ".join(e.find("a:summary", ns).text.split())})
    return out


def show(rs, n=4):
    for r in rs[:n]:
        ident = r.get("doi") or r.get("id")
        print(f'  [{r["src"]}] {r["title"][:110]} | {r.get("year")} | {r.get("venue","")[:40]} | {ident} | {", ".join(r["authors"][:3])}')


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print("Q:", q)
        try:
            show(crossref(q, 3))
        except Exception as ex:
            print("  crossref error", ex)
        try:
            show(arxiv(q, 2))
        except Exception as ex:
            print("  arxiv error", ex)
