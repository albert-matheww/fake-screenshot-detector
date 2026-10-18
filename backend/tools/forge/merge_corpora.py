"""Merge ScreenForge corpora (feature pickles) into one directory. Image paths are made absolute so each
source corpus keeps its own img/ tree.   python tools/forge/merge_corpora.py --dst D SRC1 SRC2 ..."""
import argparse, os, pickle

ap = argparse.ArgumentParser()
ap.add_argument("--dst", required=True)
ap.add_argument("src", nargs="+")
a = ap.parse_args()
os.makedirs(a.dst, exist_ok=True)
for split in ("train", "val", "test"):
    out = []
    for s in a.src:
        s = os.path.abspath(s)
        for r in pickle.load(open(os.path.join(s, f"feat_{split}.pkl"), "rb")):
            if not os.path.isabs(r["path"]):
                r["path"] = os.path.join(s, r["path"])
            out.append(r)
    pickle.dump(out, open(os.path.join(a.dst, f"feat_{split}.pkl"), "wb"), protocol=4)
    print(split, len(out))
