"""Summarise evidence/stfd_pipeline_full.json (the v3 pipeline on all 3,932 STFD tampered screenshots) per edit type."""
import collections, json, os
r = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stfd_pipeline_full.json")))
n = len(r)
print("images", n, "| verdicts", dict(collections.Counter(x["verdict"] for x in r)))
print("automatic type", dict(collections.Counter(str(x["type"]) for x in r).most_common()))
adv = [x for x in r if "rendering" in x["advisory_findings"]]   # the word-rendering model only; the version-1 hints are counted separately below
print("advisory (rendering) flagged", len(adv), f"{len(adv)/n:.3f}", "| marked region meets the edit mask:", sum(x["region_overlaps_mask"] for x in adv), f"{sum(x['region_overlaps_mask'] for x in adv)/len(adv):.3f}")
print("version-1 hints that raised a finding (images)", dict(collections.Counter(c for x in r for c in x["advisory_findings"] if c.startswith("v1."))))
print("live findings (images)", sum(bool(x["live_findings"]) for x in r), "| by check", dict(collections.Counter(c for x in r for c in x["live_findings"])))
print("pixel reliability", dict(collections.Counter(x["pixel_reliability"] for x in r)))
for t in sorted({x["edit_type"] for x in r}):
    s = [x for x in r if x["edit_type"] == t]; a = [x for x in s if "rendering" in x["advisory_findings"]]
    ov = sum(x["region_overlaps_mask"] for x in a)
    print(f"{t}: n={len(s)} suspicious={sum(x['verdict']=='suspicious' for x in s)} live={sum(bool(x['live_findings']) for x in s)} advisory={len(a)} ({len(a)/len(s):.1%}) advisory_meets_mask={ov} ({ov/max(len(a),1):.1%})")
fr = sorted(x["mask_frac"] for x in r)
print("edited area as share of the image: 10th/50th/90th percentile", [round(fr[int(q * n)], 4) for q in (.1, .5, .9)])
