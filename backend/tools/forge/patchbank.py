"""Chrome-rendered text patches (a second, independent "editing engine").

Edits made with Pillow/FreeType could teach a model a FreeType-specific signature. This
module renders thousands of text snippets with Chrome's text engine (transparent
background, genuine browser anti-aliasing, many fonts/weights/sizes) so that edits can also
be made with a *different* rasteriser. The shipped model is trained on Pillow edits only
and this family is used as a held-out, out-of-distribution test (see README).

  python tools/forge/patchbank.py build --out data/patchbank --pages 40 --workers 8
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_chrome as RC  # noqa: E402

COLS, ROWS, CELL_W, CELL_H, DSF = 5, 22, 340, 60, 2
_WORDS = ["Paid", "Sent", "Received", "Success", "Failed", "Pending", "Refund", "Total", "Credit", "Debit", "Done",
          "Approved", "Today", "Order", "Delivered", "Online", "Verified", "Amount", "Balance", "Account", "Cancelled",
          "Seen", "Read", "Yes", "Confirmed", "Transfer", "Deposit", "Salary", "Rent", "Gift", "Alex", "Jordan", "Priya",
          "Morgan", "Taylor", "Wei", "Casey", "Riley", "Completed", "Declined", "Processing", "Shipped", "Reserved"]


def _digits(r: random.Random, n: int) -> str:
    return "".join(r.choice("0123456789") for _ in range(n))


def _text(r: random.Random) -> str:
    k = r.random()
    if k < 0.34:   # money
        cur = r.choice(["$", "$", "", "₹", "€", "£"])
        ip = _digits(r, r.choice([1, 2, 3, 4, 5]))
        ip = ip.lstrip("0") or "0"
        if len(ip) > 3 and r.random() < 0.8:
            ip = f"{int(ip):,}"
        out = f"{cur}{ip}.{_digits(r, 2)}"
        return r.choice(["", "", "-", "+"]) + out
    if k < 0.46:
        return _digits(r, r.choice([4, 6, 8, 10, 12]))
    if k < 0.56:
        return f"{r.randint(1, 28):02d}/{r.randint(1, 12):02d}/{r.randint(2023, 2026)}"
    if k < 0.64:
        return f"{r.randint(1, 12)}:{r.randint(0, 59):02d} {r.choice(['AM', 'PM'])}"
    w = r.choice(_WORDS)
    return r.choice([w, w, w.upper(), w.lower()])


def pattern_of(text: str) -> str:
    """Shape class used to match a patch to the word being replaced: digits -> d, letters kept as case class."""
    out = []
    for ch in text:
        out.append("d" if ch.isdigit() else ("A" if ch.isupper() else ("a" if ch.isalpha() else ch)))
    return "".join(out)


def _page_html(items: List[Dict[str, Any]]) -> str:
    cells = []
    for it in items:
        cells.append(f'<span style="position:absolute;left:{it["x"]}px;top:{it["y"]}px;white-space:nowrap;'
                     f'font-family:{it["stack"]};font-size:{it["size"]}px;font-weight:{it["weight"]};'
                     f'color:{it["color"]};line-height:1.2">{it["text"]}</span>')
    return ("<!doctype html><html><head><meta charset=utf-8></head><body style='margin:0;background:transparent'>"
            + "".join(cells) + "</body></html>")


def _render_page(args: Tuple[int, int, str, str]) -> List[Dict[str, Any]]:
    page, seed, out_dir, chrome = args
    r = random.Random(seed * 7919 + page)
    items = []
    for ri in range(ROWS):
        for ci in range(COLS):
            fam = r.choices(RC.FONTS, weights=[f[2] for f in RC.FONTS])[0]
            dark = r.random() < 0.6
            ink = (tuple(r.randint(0, 90) for _ in range(3)) if dark else tuple(r.randint(170, 255) for _ in range(3)))
            items.append({"x": ci * CELL_W + 8, "y": ri * CELL_H + 8, "text": _text(r), "stack": fam[1].replace('"', "'"),
                          "size": r.choice([11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24, 28, 32, 36]),
                          "weight": r.choice([300, 400, 400, 400, 500, 600, 700]), "family": fam[0],
                          "color": f"rgb{ink}", "dark": dark})
    tmp = tempfile.mkdtemp(prefix="pb_")
    try:
        html = os.path.join(tmp, "p.html")
        open(html, "w").write(_page_html(items))
        png = os.path.join(tmp, "p.png")
        ok = RC._run_chrome(chrome, os.path.join(tmp, "ud"), html, png, COLS * CELL_W, ROWS * CELL_H, DSF)
        if not ok:
            return []
        sheet = Image.open(png).convert("RGBA")
        out: List[Dict[str, Any]] = []
        os.makedirs(os.path.join(out_dir, "patches"), exist_ok=True)
        for k, it in enumerate(items):
            x0, y0 = (it["x"] - 8) * DSF, (it["y"] - 8) * DSF
            cell = np.asarray(sheet.crop((x0, y0, x0 + CELL_W * DSF, y0 + CELL_H * DSF)))
            ys, xs = np.where(cell[..., 3] > 10)
            if len(ys) < 10:
                continue
            crop = cell[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            name = f"p{seed}_{page}_{k}.png"
            Image.fromarray(crop).save(os.path.join(out_dir, "patches", name))
            out.append({"file": name, "text": it["text"], "pattern": pattern_of(it["text"]), "family": it["family"],
                        "weight": it["weight"], "size": it["size"], "dark": it["dark"],
                        "h": int(crop.shape[0]), "w": int(crop.shape[1])})
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build(out_dir: str, pages: int, seed: int, workers: int) -> int:
    os.makedirs(out_dir, exist_ok=True)
    chrome = RC.find_chrome()
    if "--default-background-color=00000000" not in RC.CHROME_FLAGS:   # transparent page background, set once
        RC.CHROME_FLAGS = RC.CHROME_FLAGS + ["--default-background-color=00000000"]
    rows: List[Dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(_render_page, [(p, seed, out_dir, chrome) for p in range(pages)]):
            rows += res
    with open(os.path.join(out_dir, "manifest.jsonl"), "a") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return len(rows)


class Bank:
    def __init__(self, root: str):
        self.root = root
        self.by_pattern: Dict[Tuple[str, bool], List[Dict[str, Any]]] = {}
        self._cache: Dict[str, np.ndarray] = {}
        with open(os.path.join(root, "manifest.jsonl")) as fh:
            for line in fh:
                m = json.loads(line)
                self.by_pattern.setdefault((m["pattern"], m["dark"]), []).append(m)

    def patch(self, name: str) -> np.ndarray:
        if name not in self._cache:
            self._cache[name] = np.asarray(Image.open(os.path.join(self.root, "patches", name)).convert("RGBA"))
        return self._cache[name]

    def find(self, pattern: str, dark: bool, target_h: int, rng: random.Random,
             families: Optional[Sequence[str]] = None, exclude: Optional[Sequence[str]] = None) -> Optional[Dict[str, Any]]:
        cands = self.by_pattern.get((pattern, dark), [])
        if families is not None:
            cands = [c for c in cands if c["family"] in families]
        if exclude:
            cands = [c for c in cands if c["family"] not in exclude]
        near = [c for c in cands if 0.8 * target_h <= c["h"] <= 1.25 * target_h]
        pool = near or []
        return rng.choice(pool) if pool else None


HELD_OUT_FAMILIES = ("Futura", "Optima", "Palatino", "Charter")   # only ever used for TEST-split patch edits


def edit_with_bank(img: Image.Image, words: Sequence[Dict[str, Any]], rng: random.Random, bank: Bank,
                   tries: int = 12, test_fonts: Optional[bool] = None) -> Optional[Dict[str, Any]]:
    """Replace one word with a Chrome-rendered patch of the same shape class (digits re-drawn, as a faker would)."""
    from tools.forge import tamper as T  # lazy: avoids a circular import at module load
    rgb = img.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32).copy()
    H, W, _ = arr.shape
    for _ in range(tries):
        t = T.pick_target(words, rng, W, H)
        if t is None:
            return None
        x, y, w, h = t["left"], t["top"], t["width"], t["height"]
        old = (x, y, x + w, y + h)
        bg, _ = T._ring_stats(arr, *old)
        ink = T._ink_color(arr, old, bg)
        dark = bool(ink.mean() < bg.mean())
        if test_fonts is None:
            m = bank.find(pattern_of(t["text"]), dark, h, rng)
        elif test_fonts:
            m = bank.find(pattern_of(t["text"]), dark, h, rng, families=HELD_OUT_FAMILIES)
        else:
            m = bank.find(pattern_of(t["text"]), dark, h, rng, exclude=HELD_OUT_FAMILIES)
        if m is None:
            continue
        patch = bank.patch(m["file"]).astype(np.float32)
        s = h / float(patch.shape[0])
        if abs(s - 1) > 0.02:
            im = Image.fromarray(patch.astype(np.uint8)).resize((max(2, int(patch.shape[1] * s)), h), Image.LANCZOS)
            patch = np.asarray(im, np.float32)
        ph, pw = patch.shape[:2]
        right = (x + w) > 0.72 * W and rng.random() < 0.8
        nx = x + w - pw if right else x
        ny = y + (h - ph) // 2
        nx, ny = int(max(0, min(W - pw, nx))), int(max(0, min(H - ph, ny)))
        pad = rng.choice([0, 1, 2, 3, 4])
        rect = (max(0, min(x, nx) - pad), max(0, min(y, ny) - pad), min(W, max(x + w, nx + pw) + pad),
                min(H, max(y + h, ny + ph) + pad))
        fill = rng.choices(["flat", "noisy", "gradient", "clonestamp"], weights=[0.35, 0.2, 0.2, 0.25])[0]
        T._fill_rect(arr, rect, fill, rng)
        T._composite(arr, patch[..., 3] / 255.0, nx, ny, np.clip(ink, 0, 255))
        out = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8))
        return {"image": out, "box": tuple(int(v) for v in rect),
                "meta": {"op": "chrome_patch", "fill": fill, "pad": pad, "orig_text": t["text"],
                         "new_text": m["text"], "font": m["family"], "aa": "chrome"}}
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", type=int, default=40)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    n = build(a.out, a.pages, a.seed, a.workers)
    print(f"{n} patches")
