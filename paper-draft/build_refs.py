"""Builds references.json and sources/<key>.txt from authoritative records (Crossref by DOI, arXiv by id).
The identifiers below were chosen from search results retrieved in this session (see lit_tools.py output)."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lit_tools import get, arxiv
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
M = [  # key, doi | arxiv, used_for
    ("farid2009ghosts", "doi:10.1109/tifs.2008.2012215", "JPEG ghost method (double-compression traces)"),
    ("farid2009survey", "doi:10.1109/msp.2008.931079", "overview of passive forgery detection"),
    ("popescu2005resampling", "doi:10.1109/tsp.2004.839932", "resampling traces as a forensic cue"),
    ("mahdian2009noise", "doi:10.1016/j.imavis.2009.02.001", "noise inconsistency as a forensic cue"),
    ("lukas2006prnu", "doi:10.1109/tifs.2006.873602", "sensor pattern noise (needs a camera)"),
    ("bianchi2012block", "doi:10.1109/tifs.2012.2187516", "block-grained JPEG artifact localisation"),
    ("christlein2012eval", "doi:10.1109/tifs.2012.2218597", "copy-move detection evaluation"),
    ("piva2013overview", "doi:10.1155/2013/496701", "image forensics overview"),
    ("verdoliva2020", "doi:10.1109/jstsp.2020.3002101", "media forensics overview"),
    ("wu2019mantranet", "doi:10.1109/cvpr.2019.00977", "learned manipulation tracing"),
    ("kwon2021catnet", "doi:10.1109/wacv48630.2021.00042", "compression-artifact tracing network"),
    ("guillaro2023trufor", "doi:10.1109/cvpr52729.2023.01974", "learned forgery detection and localisation"),
    ("dong2013casia", "doi:10.1109/chinasip.2013.6625374", "CASIA tampering benchmark"),
    ("novozamsky2020imd", "doi:10.1109/wacvw50321.2020.9096940", "IMD2020 real-life manipulations dataset"),
    ("tornes2023receipt", "doi:10.1007/978-3-031-41682-8_28", "receipt forgery dataset (Find it again)"),
    ("qu2023doctamper", "doi:10.1109/cvpr52729.2023.00575", "DocTamper tampered-text dataset and detector"),
    ("yu2023stfd", "doi:10.1109/icassp49357.2023.10095070", "screenshot text-forgery dataset STFD"),
    ("yu2025fsts", "arxiv:2511.12658", "structured data synthesis for text-image forgery localisation"),
    ("xu2026reality", "doi:10.1109/tifs.2026.3705334", "human-crafted tampered-text dataset"),
    ("qu2024textsleuth", "arxiv:2412.14816", "explainable tampered-text detection"),
    ("ronfleux2026docqt", "doi:10.1007/978-3-032-36023-6_7", "document forgery localisation and JPEG quantisation tables"),
    ("dhouib2026doctamper", "doi:10.1007/978-3-032-37196-6_7", "efficient document tampering localisation"),
    ("zhang2026textfake", "arxiv:2606.01050", "AI-generated images of text-rich content"),
    ("zhao2026docforge", "arxiv:2603.01433", "document forgery benchmark"),
    ("du2025forensichub", "doi:10.52202/085713-2167", "unified forgery benchmark and codebase"),
    ("chen2025unmask", "doi:10.1145/3719027.3744809", "document tampering under recapturing"),
    ("venkatesh2026screenshot", "doi:10.1109/iccvbic71195.2026.11688551", "screenshot-tailored multi-feature forensics"),
    ("smith2007tesseract", "doi:10.1109/icdar.2007.4376991", "OCR engine used for word boxes"),
    ("friedman2001", "doi:10.1214/aos/1013203451", "gradient boosting"),
    ("pedregosa2011", "arxiv:1201.0490", "scikit-learn"),
    ("torralba2011bias", "doi:10.1109/cvpr.2011.5995347", "dataset bias"),
    ("kapoor2023leakage", "doi:10.1016/j.patter.2023.100804", "data leakage in ML evaluation"),
    ("fawcett2006roc", "doi:10.1016/j.patrec.2005.10.010", "ROC analysis and AUC"),
    ("wilson1927", "doi:10.1080/01621459.1927.10502953", "binomial confidence interval"),
]


def crossref_doi(doi):
    j = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]
    return j


def openalex_abstract(doi):
    try:
        j = json.loads(get("https://api.openalex.org/works/https://doi.org/" + doi))
        inv = j.get("abstract_inverted_index")
        if not inv:
            return ""
        pos = {}
        for w, ps in inv.items():
            for p in ps:
                pos[p] = w
        return " ".join(pos[i] for i in sorted(pos))
    except Exception:
        return ""


def arxiv_id(aid):
    r = arxiv(aid, 1)
    # arXiv id search via all: may not return the exact paper; use id_list instead
    import urllib.request, xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(get("http://export.arxiv.org/api/query?id_list=" + aid))
    e = root.find("a:entry", ns)
    return {"title": " ".join(e.find("a:title", ns).text.split()),
            "authors": [a.find("a:name", ns).text for a in e.findall("a:author", ns)],
            "year": int(e.find("a:published", ns).text[:4]),
            "abstract": " ".join(e.find("a:summary", ns).text.split()), "id": aid}


def fmt_author(a):
    fam, giv = a.get("family", ""), a.get("given", "")
    return f"{fam}, {giv}".strip(", ")


refs = []
for key, ident, used in M:
    kind, val = ident.split(":", 1)
    rec = {"key": key, "used_for": used}
    text = ""
    try:
        if kind == "doi":
            j = crossref_doi(val)
            ab = re.sub(r"<[^>]+>", "", j.get("abstract", "") or "") or openalex_abstract(val)
            rec.update({"title": re.sub(r"<[^>]+>", "", j["title"][0]), "authors": [fmt_author(a) for a in j.get("author", [])],
                        "year": (j.get("issued", {}).get("date-parts") or [[None]])[0][0],
                        "venue": (j.get("container-title") or [""])[0], "volume": j.get("volume"), "issue": j.get("issue"),
                        "pages": j.get("page"), "doi": val, "arxiv": None, "url": None})
            text = f'{rec["title"]}\n{", ".join(rec["authors"])} ({rec["year"]}). {rec["venue"]}. doi:{val}\n\nABSTRACT (as returned by Crossref/OpenAlex):\n{ab}\n'
            rec["read_depth"] = "abstract" if ab else "metadata"
        else:
            a = arxiv_id(val)
            rec.update({"title": a["title"], "authors": [f'{n.split()[-1]}, {" ".join(n.split()[:-1])}' for n in a["authors"]],
                        "year": a["year"], "venue": "arXiv preprint", "volume": None, "issue": None, "pages": None,
                        "doi": None, "arxiv": val, "url": f"https://arxiv.org/abs/{val}"})
            text = f'{a["title"]}\n{", ".join(a["authors"])} ({a["year"]}). arXiv:{val}\n\nABSTRACT (as returned by arXiv):\n{a["abstract"]}\n'
            rec["read_depth"] = "abstract"
    except Exception as ex:
        print("FAILED", key, ex)
        continue
    open(os.path.join(HERE, "sources", key + ".txt"), "w", encoding="utf8").write(text)
    refs.append(rec)
    print(f'{key:24s} {rec["read_depth"]:9s} {rec["year"]} {rec["title"][:70]}')
    time.sleep(0.3)
json.dump(refs, open(os.path.join(HERE, "references.json"), "w"), indent=1, ensure_ascii=False)
print(len(refs), "references written")
