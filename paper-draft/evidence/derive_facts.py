"""Derives report numbers from saved artifacts (no hand-typed values). Output: facts.txt"""
import json, pickle, os, collections, statistics as st, sys, re, subprocess, importlib
ROOT = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector"
sys.path.insert(0, ROOT + "/backend"); sys.path.insert(0, ROOT + "/backend/tools")
out = []
def P(*a): out.append(" ".join(str(x) for x in a))

# ---- v1 audit on 60 genuine screenshots
r = json.load(open(f"{ROOT}/paper-draft/evidence/fp_results.json"))
n = len(r); fp = [x for x in r if x["is_fake"]]
P("V1_AUDIT genuine screenshots:", n, "flagged fake:", len(fp), f"({len(fp)/n:.1%})")
P("V1_AUDIT formats:", dict(collections.Counter(x["fmt"] for x in r)))
for k in ["ela_score","ghost_score","quant_score","noise_score","clone_score","metadata_score","text_score","font_score","edge_score","chrome_score","arithmetic_score"]:
    v=[x["features"][k] for x in r]
    P(f"V1_AUDIT cue {k:17s} mean {st.mean(v):.3f} max {max(v):.3f} nonzero {sum(1 for a in v if a>0)}/{n}")
P("V1_AUDIT fake_score mean %.3f median %.3f max %.3f" % (st.mean(x["fake_score"] for x in r), st.median(x["fake_score"] for x in r), max(x["fake_score"] for x in r)))
P("V1_AUDIT processing ms median", st.median(x["ms"] for x in r), "max", max(x["ms"] for x in r))
t = json.load(open(f"{ROOT}/paper-draft/evidence/tamper_results.json"))
def auc(pos, neg): return sum(1 if p>q else (0.5 if p==q else 0) for p in pos for q in neg)/(len(pos)*len(neg))
m=len(t); P("V1_EDIT image sets:", m)
for v in ["orig_png","edit_png","orig_jpg85","edit_jpg85"]:
    P(f"V1_EDIT {v:11s} flagged {sum(x[v]['is_fake'] for x in t)}/{m}  mean score {st.mean(x[v]['fake_score'] for x in t):.3f}")
P("V1_EDIT AUC edit_png vs orig_png %.3f" % auc([x['edit_png']['fake_score'] for x in t],[x['orig_png']['fake_score'] for x in t]))
P("V1_EDIT AUC edit_jpg85 vs orig_jpg85 %.3f" % auc([x['edit_jpg85']['fake_score'] for x in t],[x['orig_jpg85']['fake_score'] for x in t]))
d=[x['edit_png']['fake_score']-x['orig_png']['fake_score'] for x in t]
P("V1_EDIT paired edit_png-orig_png mean delta %+.4f, edit higher in %d/%d, lower in %d/%d" % (st.mean(d), sum(z>0 for z in d), m, sum(z<0 for z in d), m))
P("V1_EDIT newly flagged vs own original (png):", sum(1 for x in t if x['edit_png']['is_fake'] and not x['orig_png']['is_fake']), "/", m)

# ---- corpus statistics (final corpus v6)
D = f"{ROOT}/data/forge_v6"
tot = {}
for sp in ("train","val","test"):
    recs = pickle.load(open(f"{D}/feat_{sp}.pkl","rb"))
    c = collections.Counter((x["source"], "edit" if x["label"] else "auth") for x in recs)
    words = sum(len(x["y"]) for x in recs); edited_words = sum(int((x["y"]==1).sum()) for x in recs)
    P(f"CORPUS {sp}: images {len(recs)} (edited {sum(x['label'] for x in recs)}), words {words}, edited words {edited_words}; by source/class {dict(sorted(c.items()))}")
    tot[sp] = len(recs)
P("CORPUS total images", sum(tot.values()))
try:
    from tools.forge import tamper
    P("CORPUS usable fonts in edit font bank:", len(tamper.font_bank()), "folds:", dict(sorted(collections.Counter(f['fold'] for f in tamper.font_bank()).items())))
except Exception as e: P("font bank error", e)
rc = open(f"{ROOT}/backend/tools/forge/render_chrome.py").read()
P("CORPUS chrome fonts in render_chrome.FONTS:", len(re.findall(r'^\s*\("[^"]+", ', rc[rc.index("FONTS = ["):rc.index("_FONT_LABEL_TO_STACK")], re.M)))
fams = re.findall(r'^@family\("([a-z_]+)"', rc, re.M) or re.findall(r'family\("([a-z_]+)"', rc)
P("CORPUS chrome families:", len(set(fams)), sorted(set(fams)))
# ---- model
meta = json.load(open(f"{ROOT}/backend/model_data/word_gbm_meta.json"))
P("MODEL features:", len(meta["feature_names"]), "train_images", meta["train_images"], "train_words", meta["train_words"], "thresholds", meta["thresholds"])
P("MODEL test AUC", meta["metrics"]["test"]["auc"], "val AUC", meta["metrics"]["val"]["auc"])
# ---- code size
for f in ["textforensics.py","semantic.py","analysis.py","app.py"]:
    P("CODE", f, sum(1 for _ in open(f"{ROOT}/backend/{f}")), "lines")
for f in ["build_dataset.py","tamper.py","patchbank.py","render_chrome.py","train_text_model.py","eval_real_cv.py","refeaturize.py","compare_legacy.py","eval_layout_rule.py","merge_corpora.py","eval_ood.py"]:
    P("CODE tools/forge/"+f, sum(1 for _ in open(f"{ROOT}/backend/tools/forge/{f}")), "lines")
# ---- environment
def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=30).stdout.strip().splitlines()[0]
    except Exception as e: return str(e)
P("ENV python:", sh(f"{ROOT}/backend/venv/bin/python --version"))
P("ENV tesseract:", sh("tesseract --version 2>&1 | head -1"))
P("ENV chrome:", sh("'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --version 2>/dev/null"))
P("ENV cpu:", sh("sysctl -n machdep.cpu.brand_string"), "| ram bytes:", sh("sysctl -n hw.memsize"))
P("ENV pins:", open(f"{ROOT}/backend/requirements.txt").read().split())
open(f"{ROOT}/paper-draft/evidence/facts.txt","w").write("\n".join(out)+"\n")
print("\n".join(out))
