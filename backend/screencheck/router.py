"""Screenshot type routing with two independent routers.

Router A reads the *words* (keyword/pattern evidence per type).
Router B looks only at the *structure* (layout statistics, theme, status bar) and never at what the words say.
They are combined so that a forger cannot flip the type by editing one thing, and so that disagreement means
"unknown" - which makes the verdict more cautious, never less.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

import semantic

from .common import TYPES, TYPE_LABELS

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_data")

# --------------------------------------------------------------------------- router A: content

_RULES: Dict[str, List[Tuple[str, float]]] = {
    "payment_receipt": [
        (r"\bupi\b", 2), (r"\b(paid to|paid|sent to|received from|money (sent|received)|payment (successful|received|sent|failed))\b", 2),
        (r"\b(transaction|txn|reference|ref)\.? ?(id|no|number)\b", 2), (r"\b(utr|rrn)\b", 2),
        (r"\b(gpay|google pay|phonepe|paytm|bhim|imps|neft|rtgs)\b", 2), (r"\b(debited|credited) (from|to)\b", 1),
        (r"\b(bank reference|completed|successful)\b", 0.5), (r"₹\s?[\d,]+", 0.5),
    ],
    "bank_statement": [
        (r"\b(available |current |closing |opening |ledger )?balance\b", 2), (r"\b(statement|passbook|mini statement)\b", 2),
        (r"\b(debit|credit|withdrawal|deposit|dr|cr)\b", 1), (r"\b(account (number|no)|a/c|ifsc|branch)\b", 2),
        (r"\b(recent transactions|transaction history)\b", 1.5), (r"\b(savings|current) account\b", 1.5),
    ],
    "order_invoice": [
        (r"\b(order|invoice|receipt|bill)\b ?(#|no|id|number|summary|details|total)?", 1.5), (r"\b(sub ?total|grand total|order total|amount due)\b", 2),
        (r"\b(shipping|delivery|tax|gst|vat|qty|quantity|item|items|seller|sold by)\b", 1),
        (r"\b(refund|return|replacement|delivered|arriving|placed on|add to cart|buy now)\b", 1.5),
        (r"\b(amazon|flipkart|swiggy|zomato|myntra|uber|ola|bigbasket)\b", 1.5),
    ],
    "chat": [
        (r"\b(online|typing|last seen|seen|delivered|read|message|type a message|voice call|video call|reply)\b", 1),
        (r"\b(whatsapp|telegram|messenger|imessage|signal|instagram)\b", 1.5), (r"\b(you|today|yesterday)\b", 0.3),
    ],
    "social_post": [
        (r"\b(like|likes|retweet|repost|reposts|comments?|share|follow|following|followers|views)\b", 1.5),
        (r"@\w{3,}", 1.5), (r"\b(twitter|instagram|facebook|linkedin|reddit|youtube|threads|x\.com)\b", 2),
        (r"\b\d+(\.\d+)?[km]\b", 1), (r"#\w{3,}", 1),
    ],
    "message_alert": [
        (r"\b(otp|one[- ]time (password|pin|code)|verification code|do not share|valid for)\b", 2.5),
        (r"\b(inbox|compose|subject|from:|to:|cc:|unread|starred|primary|promotions|spam|draft)\b", 2),
        (r"\b(notification|notifications|alert|security alert|sign[- ]in|new login|your (account|package|order))\b", 1.5),
        (r"\b(sms|text message|rcs|carrier|vi |airtel|jio|bsnl)\b", 1.5), (r"\b(gmail|outlook|yahoo mail)\b", 2),
    ],
    "web_page": [
        (r"\b(search|sign in|log in|cart|wishlist|account|menu|home|dashboard|portfolio|wallet|watchlist|market|overview)\b", 1),
        (r"\b(https?://|www\.|\.com|\.in\b)", 1.5), (r"\b(all categories|deals|prime|customer service|trending|buy again)\b", 1.5),
        (r"\b(bitcoin|btc|ethereum|eth|nifty|sensex|nasdaq|stock|holdings|p&l)\b", 1.5),
    ],
}
_COMPILED = {t: [(re.compile(p, re.I), w) for p, w in rules] for t, rules in _RULES.items()}


def content_scores(words: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    text = "\n".join(semantic.lines_from_words(words))
    return {t: float(sum(w for rx, w in rules if rx.search(text))) for t, rules in _COMPILED.items()}


def route_content(words: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    sc = content_scores(words)
    order = sorted(sc, key=lambda t: -sc[t])
    top, second = sc[order[0]], sc[order[1]]
    conf = top / (top + second + 2.0) if top > 0 else 0.0
    return {"type": order[0] if top >= 2.0 else None, "confidence": round(conf, 3), "scores": {t: round(v, 2) for t, v in sc.items()}}


# --------------------------------------------------------------------------- router B: structure

_TIME_RE = re.compile(r"^\d{1,2}[:.]\d{2}$")
STRUCT_FEATURES = (["aspect", "desktop", "megapixels", "status_bar", "dark", "sat_share", "n_lines", "n_words", "line_h",
                    "numeric_share", "amount_lines", "col_rows", "n_cols", "ink_rows"]
                   + [f"left{i}" for i in range(8)] + [f"right{i}" for i in range(8)] + ["bubble_right", "bubble_left"])


def structure_features(rgb: np.ndarray, words: Sequence[Dict[str, Any]]) -> np.ndarray:
    """Layout statistics that do not depend on what the words mean."""
    h, w = rgb.shape[:2]
    lum = rgb.astype(np.float32).mean(2)
    mx, mn = rgb.max(2).astype(np.float32), rgb.min(2).astype(np.float32)
    sat = (mx - mn) / (mx + 1.0)
    ws = [x for x in words if len(x["text"].strip()) > 0]
    top_zone = [x for x in ws if x["top"] < 0.07 * h and _TIME_RE.match(x["text"].strip())]
    lines = semantic.lines_from_words(ws)
    # line boxes: group by rough row
    rows: Dict[int, List[Dict[str, Any]]] = {}
    for x in ws:
        rows.setdefault(int(round((x["top"] + x["height"] / 2) / max(6, x["height"]))), []).append(x)
    lb = []
    for r in rows.values():
        l = min(x["left"] for x in r)
        rr = max(x["left"] + x["width"] for x in r)
        hh = float(np.median([x["height"] for x in r]))
        lb.append((l / w, rr / w, hh / h))
    lb_a = np.array(lb) if lb else np.zeros((0, 3))
    lh = np.histogram(lb_a[:, 0], bins=8, range=(0, 1))[0] if len(lb_a) else np.zeros(8)
    rh = np.histogram(lb_a[:, 1], bins=8, range=(0, 1))[0] if len(lb_a) else np.zeros(8)
    nl = max(1, len(lb_a))
    bubble_right = float(((lb_a[:, 0] > 0.3) & (lb_a[:, 1] > 0.8)).sum() / nl) if len(lb_a) else 0.0
    bubble_left = float(((lb_a[:, 0] < 0.2) & (lb_a[:, 1] < 0.75)).sum() / nl) if len(lb_a) else 0.0
    digits = sum(sum(c.isdigit() for c in x["text"]) for x in ws)
    chars = max(1, sum(len(x["text"]) for x in ws))
    num_words = sum(1 for x in ws if sum(c.isdigit() for c in x["text"]) / max(1, len(x["text"])) >= 0.5)
    amount_lines = sum(1 for ln in lines if re.search(r"\d[\d,]*\.\d{2}\b|₹|\$|€|£", ln))
    cols = semantic.numeric_columns(ws) if len(ws) >= 8 else []
    ink = (np.abs(np.diff(lum, axis=1)).mean(1) > 6).mean() if w > 1 else 0.0
    feats = [h / w, float(w > h or w >= 1100), w * h / 1e6, float(bool(top_zone)), float(lum.mean() < 110),
             float((sat > 0.5).mean()), len(lines), len(ws), float(np.median([x["height"] for x in ws]) / h) if ws else 0.0,
             num_words / max(1, len(ws)), amount_lines / max(1, len(lines)), max((len(c) for c in cols), default=0), len(cols), float(ink)]
    feats += list(lh / nl) + list(rh / nl) + [bubble_right, bubble_left]
    return np.asarray(feats, dtype=np.float32)


_STRUCT_MODEL = None
_STRUCT_META: Dict[str, Any] = {}
try:  # trained by tools/train_router.py
    import joblib
    _mp = os.path.join(_DIR, "router_structure.joblib")
    _jp = os.path.join(_DIR, "router_structure_meta.json")
    if os.path.exists(_mp) and os.path.exists(_jp):
        _STRUCT_MODEL = joblib.load(_mp)
        with open(_jp) as fh:
            _STRUCT_META = json.load(fh)
        if _STRUCT_META.get("features") != STRUCT_FEATURES:
            _STRUCT_MODEL = None
except Exception:  # noqa: BLE001
    _STRUCT_MODEL = None


def route_structure(rgb: np.ndarray, words: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if _STRUCT_MODEL is None or len(words) < 3:
        return {"type": None, "confidence": 0.0, "probabilities": {}}
    x = structure_features(rgb, words).reshape(1, -1)
    p = _STRUCT_MODEL.predict_proba(x)[0]
    classes = list(_STRUCT_MODEL.classes_)
    probs = {c: float(v) for c, v in zip(classes, p)}
    best = max(probs, key=probs.get)
    return {"type": best, "confidence": round(probs[best], 3), "probabilities": {k: round(v, 3) for k, v in probs.items()}}


# --------------------------------------------------------------------------- fusion

ROUTER_GATE_FILE = os.path.join(_DIR, "router_gate.json")


def router_gate() -> Dict[str, Any]:
    """Per-router validation on real screenshots (written by tools/eval_router.py)."""
    try:
        with open(ROUTER_GATE_FILE) as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {"content": {"validated": False, "reason": "not validated on real screenshots"},
                "structure": {"validated": False, "reason": "not validated on real screenshots"}}


def route(rgb: np.ndarray, words: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A router influences the type only if it has been validated on real screenshots; otherwise its guess is shown
    but not used (the same calibration rule as for the checks)."""
    a = route_content(words)
    b = route_structure(rgb, words)
    gate = router_gate()
    live_a = bool(gate.get("content", {}).get("validated"))
    live_b = bool(gate.get("structure", {}).get("validated"))
    ta, tb = a["type"], b["type"]
    pb = b.get("probabilities", {})
    typ, status, conf = None, "unknown", 0.0
    if live_a and live_b:
        if ta and tb:
            if ta == tb or pb.get(ta, 0.0) >= 0.25:
                typ, status = ta, "confident"
                conf = round(min(1.0, 0.5 * a["confidence"] + 0.5 * pb.get(ta, 0.0) + 0.2), 3)
        elif ta or tb:
            typ, status, conf = ta or tb, "tentative", round(0.5 * (a["confidence"] if ta else b["confidence"]), 3)
    elif live_a:
        if ta:
            typ, status, conf = ta, "confident" if a["confidence"] >= 0.4 else "tentative", a["confidence"]
    elif live_b:
        if tb:
            typ, status, conf = tb, "confident" if b["confidence"] >= 0.6 else "tentative", b["confidence"]
    else:
        # nothing validated: show the content guess as a tentative label only
        if ta:
            typ, status, conf = ta, "tentative", round(0.5 * a["confidence"], 3)
    usable = bool(typ) and status == "confident" and (live_a or live_b)
    return {
        "type": typ or "unknown", "label": TYPE_LABELS.get(typ or "unknown"), "status": status, "confidence": conf,
        "typed_checks_enabled": usable, "router_validated": bool(live_a or live_b),
        "content": a, "structure": b,
        "validation": {k: {kk: v.get(kk) for kk in ("validated", "accuracy", "n", "reason") if kk in v} for k, v in gate.items() if isinstance(v, dict)},
    }
