"""How often does an edited image have at least one measurable, positively labelled word? (pickle statistics, no model)"""
import pickle, collections
ROOT = "/Users/albertmathew/Desktop/projects/fake-screenshot-detector/data"
for name, d in (("first corpus (OCR confidence threshold 40)", "forge_v0"), ("final corpus (all OCR boxes kept, single glyphs skipped)", "forge_v6")):
    recs = pickle.load(open(f"{ROOT}/{d}/feat_test.pkl", "rb"))
    ed = [r for r in recs if r["label"] == 1]
    has = lambda r: bool((r["y"] == 1).any()) and r["X"].shape[0] == len(r["y"])
    by = collections.defaultdict(list)
    for r in ed: by[r["meta"].get("degrade")].append(has(r))
    print(f"{name}: test edited images {len(ed)}; edited word measurable in {sum(map(has, ed))} ({sum(map(has, ed))/len(ed):.1%}); "
          + ", ".join(f"{k} {sum(v)/len(v):.0%} (n={len(v)})" for k, v in sorted(by.items())))
