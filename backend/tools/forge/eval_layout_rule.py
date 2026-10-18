"""Validate semantic.check_layout_grid on the ScreenForge corpus (word boxes only - no pixels needed).
  (1) false alarms on GENUINE images (all sources, incl. full-size real screenshots)
  (2) firing on our edited images (edits are placed within ~2 px, so this should be near zero)
  (3) recall on SIMULATED hand-placement errors: shift one numeric row of a genuine list by f x text height.
  python tools/forge/eval_layout_rule.py --data ../data/forge_v6"""
import argparse, os, pickle, random, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); BACKEND = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, BACKEND)
import semantic as S  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True)
ap.add_argument("--no-gap-condition", action="store_true", help="ablation: first version of the rule (no check that both neighbouring gaps are near the normal pitch)")
a = ap.parse_args()
GAPS = not a.no_gap_condition
recs = []
for sp in ("train", "val", "test"):
    recs += pickle.load(open(os.path.join(a.data, f"feat_{sp}.pkl"), "rb"))
def W(r): return [{"text": t, "left": l, "top": tp, "width": w, "height": h, "conf": c, "line": ""} for (t, l, tp, w, h, c) in r["words"]]
auth = [r for r in recs if r["label"] == 0]; edit = [r for r in recs if r["label"] == 1]
fa = defaultdict(lambda: [0, 0]); fe = defaultdict(lambda: [0, 0]); eligible = []
for r in auth:
    w = W(r); fa[r["source"]][1] += 1
    if S.check_layout_grid(w, GAPS): fa[r["source"]][0] += 1
    if S.numeric_columns(w): eligible.append((r, w))
for r in edit:
    fe[r["source"]][1] += 1
    if S.check_layout_grid(W(r), GAPS): fe[r["source"]][0] += 1
print("== (1) false alarms on GENUINE images")
for k, (n, t) in sorted(fa.items()): print(f"  {k:7s} {n:3d}/{t:5d}  ({n / max(1, t):.2%})")
tot = sum(v[0] for v in fa.values()), sum(v[1] for v in fa.values()); print(f"  ALL     {tot[0]}/{tot[1]}  ({tot[0] / tot[1]:.2%})")
print("== (2) fires on our edited images (placement error <= ~2 px by construction)")
for k, (n, t) in sorted(fe.items()): print(f"  {k:7s} {n:3d}/{t:5d}  ({n / max(1, t):.2%})")
print(f"== (3) recall on simulated hand-placement errors; {len(eligible)} genuine images have a numeric column")
rng = random.Random(0)
for f in (0.1, 0.2, 0.3, 0.5, 0.8):
    hit = tot_ = 0; right = 0
    for r, w in eligible:
        cols = S.numeric_columns(w)
        rows = max(cols, key=len)
        if len(rows) < 6: continue
        # only columns that are genuinely regular qualify as "grid" (otherwise the rule is meant to stay silent)
        if S.check_layout_grid(w, GAPS): continue
        j = rng.randrange(2, len(rows) - 2) if len(rows) >= 6 else None
        if j is None: continue
        target = rows[j]; h = target["height"]
        w2 = [dict(x) for x in w]
        for x in w2:
            if x["left"] == target["left"] and x["top"] == target["top"] and x["text"] == target["text"]:
                x["top"] += int(round(rng.choice([-1, 1]) * f * h)); break
        res = S.check_layout_grid(w2, GAPS); tot_ += 1
        if res:
            hit += 1; right += int(res[0]["evidence"]["text"] == target["text"])
    print(f"  shift {f:.1f} x height: detected {hit}/{tot_} ({hit / max(1, tot_):.0%}), culprit named correctly {right}/{max(1, hit)}")
