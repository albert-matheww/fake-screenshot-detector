"""The individual checks. Each returns a CheckResult dict with a status in
  "finding"        the check ran and found an inconsistency
  "clear"          the check ran and found nothing
  "not_applicable" the check could not examine this screenshot (and says why)

A check that could not look must say so: "not_applicable" is never counted as a pass.
Whether a check's finding is allowed to move the verdict ("live") or is only shown ("advisory") is decided in gates.py.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

import semantic
import textforensics as tf

MIN_WORDS_FOR_TEXT_CHECKS = 15
MIN_OCR_CONF = 60.0


CATEGORY = {"file_metadata": "file", "content_logic": "content", "layout_grid": "visual", "rendering": "visual",
            "v1.ela": "visual", "v1.ghost": "visual", "v1.quant": "visual", "v1.noise": "visual", "v1.clone": "visual"}


def category(check_id: str) -> str:
    return "content" if check_id.startswith("typed.") else CATEGORY.get(check_id, "content")


def result(check_id: str, name: str, status: str, findings: Optional[List[Dict[str, Any]]] = None, why: str = "",
           regions: Optional[List[Dict[str, Any]]] = None, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    findings = findings or []
    sev_rank = {"high": 3, "medium": 2, "low": 1}
    top = max((sev_rank.get(f.get("severity"), 0) for f in findings), default=0)
    return {"id": check_id, "name": name, "category": category(check_id), "status": status, "severity": {3: "high", 2: "medium", 1: "low", 0: None}[top],
            "findings": findings, "why": why, "regions": regions or [], "detail": detail or {}}


def _confident(words: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [w for w in words if (w.get("conf") is None or w.get("conf", 100) >= MIN_OCR_CONF)]


# --------------------------------------------------------------------------- generic checks

def file_metadata(ctx) -> Dict[str, Any]:
    f = semantic.check_metadata(ctx["image"])
    return result("file_metadata", "File metadata", "finding" if f else "clear", f,
                  detail={"capture": ctx["capture"]["notes"]})


def content_logic(ctx) -> Dict[str, Any]:
    words = _confident(ctx["words"])
    if len(words) < MIN_WORDS_FOR_TEXT_CHECKS:
        return result("content_logic", "Content consistency (dates, totals, checksums, markers)", "not_applicable",
                      why=f"Only {len(words)} confidently read words (need {MIN_WORDS_FOR_TEXT_CHECKS}).")
    f = semantic.check_text(words)
    return result("content_logic", "Content consistency (dates, totals, checksums, markers)", "finding" if f else "clear", f)


def layout_grid(ctx) -> Dict[str, Any]:
    words = ctx["words"]
    cols = semantic.numeric_columns(words) if len(words) >= 8 else []
    if not any(len(c) >= 8 for c in cols):
        return result("layout_grid", "Number column spacing", "not_applicable",
                      why="No evenly laid-out column of at least eight numbers was found.")
    f = semantic.check_layout_grid(words) + semantic.check_status_bar_duplicate(words, ctx["capture"]["width"], ctx["capture"]["height"])
    regions = []
    for x in f:
        box = (x.get("evidence") or {}).get("box")
        if box:
            regions.append({"x": int(box[0]), "y": int(box[1]), "w": int(box[2]), "h": int(box[3]),
                            "text": x["evidence"].get("text", ""), "score": 0.0, "source": "rule", "level": "suspicious",
                            "reasons": [x["message"]]})
    return result("layout_grid", "Number column spacing", "finding" if f else "clear", f, regions=regions)


def rendering_consistency(ctx) -> Dict[str, Any]:
    """The word-level rendering model. Measured on real edits it is weak (see README); it is advisory unless a gate says otherwise."""
    import analysis_model as am  # lazy: loads the model

    if am.MODEL is None:
        return result("rendering", "Word rendering consistency", "not_applicable", why="The word-level model is not loaded.")
    X, kept, info = tf.image_word_features(ctx["rgb_img"], ctx["words"])
    if X.shape[0] < am.MIN_MEASURED_WORDS:
        return result("rendering", "Word rendering consistency", "not_applicable",
                      why=f"Only {X.shape[0]} words could be measured (need {am.MIN_MEASURED_WORDS}).")
    probs = am.MODEL.predict_proba(X)[:, 1]
    order = np.argsort(-probs)
    regions, findings = [], []
    for i in order[:5]:
        if probs[i] < am.THR_LO * 0.75:
            break
        wd = kept[i]
        regions.append({"x": int(wd["left"]), "y": int(wd["top"]), "w": int(wd["width"]), "h": int(wd["height"]),
                        "text": wd["text"], "score": round(float(probs[i]), 4),
                        "level": "evidence" if probs[i] >= am.THR_HI else ("suspicious" if probs[i] >= am.THR_LO else "weak"),
                        "reasons": tf.explain_word(X[i])})
    top = float(probs.max())
    if top >= am.THR_LO:
        wd = regions[0]
        findings.append({"id": "render.word_outlier", "severity": "high" if top >= am.THR_HI else "medium",
                         "message": f'The word "{wd["text"]}" is rendered differently from the words around it '
                                    f'({"; ".join(wd["reasons"][:2]) or "see details"}).',
                         "evidence": {"probability": round(top, 4), "box": [wd["x"], wd["y"], wd["w"], wd["h"]]}})
    return result("rendering", "Word rendering consistency", "finding" if findings else "clear", findings, regions=regions,
                  detail={"measured_words": int(X.shape[0]), "top_probability": round(top, 4),
                          "thresholds": {"suspicious": am.THR_LO, "evidence": am.THR_HI},
                          "pixel_reliability": ctx["capture"]["pixel_reliability"]})


# --------------------------------------------------------------------------- typed checks

_AMT = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})(?![\d])")


def _line_amounts(line: str) -> List[float]:
    return [float(m.replace(",", "")) for m in _AMT.findall(line)]


def typed_payment(ctx) -> Dict[str, Any]:
    words = _confident(ctx["words"])
    text = "\n".join(semantic.rows_from_words(words))
    low = text.lower()
    f: List[Dict[str, Any]] = []
    m = re.search(r"upi (?:transaction|ref(?:erence)?)\.? ?(?:id|no|number)?\W{0,6}(\d[\d ]{8,20}\d)", low)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        if len(digits) not in (12,):
            f.append({"id": "pay.upi_ref_length", "severity": "medium",
                      "message": f"The UPI reference has {len(digits)} digits; UPI references normally have 12.",
                      "evidence": {"digits": len(digits)}})
    ok = re.search(r"\b(completed|successful|success|paid)\b", low)
    bad = re.search(r"\b(failed|declined|reversed|cancelled|canceled|pending)\b", low)
    if ok and bad and re.search(r"\bpayment (successful|completed)\b", low) and re.search(r"\b(payment|transaction) (failed|declined)\b", low):
        f.append({"id": "pay.status_contradiction", "severity": "medium",
                  "message": "The receipt shows both a successful and a failed payment status.", "evidence": {}})
    if not (m or ok or bad):
        return result("typed.payment_receipt", "Payment receipt checks", "not_applicable",
                      why="No UPI reference or payment status was read confidently.")
    return result("typed.payment_receipt", "Payment receipt checks", "finding" if f else "clear", f)


_NUMTOK = re.compile(r"(?<![\w.,/:])(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?![\w/:])")
_DATETIME = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}:\d{2}(?::\d{2})?|\d{9,}|\b\d{1,2}\s?(?:st|nd|rd|th)?\s(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b(?:\s\d{2,4})?|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s\d{1,2}\b(?:,?\s\d{4})?", re.I)


_BROKEN = re.compile(r"\d+\s?[-\u2013]\s?\d{2}\b|(?<![\w.,/:])0\d+(?![\w./:,])")   # "57-42" (a lost decimal point) and "05" (0.5 read without its point)
_ANYTOK = re.compile(r"#|(?<![\w.,/:])(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?![\w/:])")


def _row_numbers(line: str) -> List[float]:
    """The numeric columns of a statement row. Dates, times and long reference numbers are removed first; a number that was clearly
    misread (a lost decimal point, a leading zero) becomes NaN so that the row is treated as a gap and not as a wrong link."""
    t = _DATETIME.sub(" ", line)
    t = _BROKEN.sub(" # ", t)
    return [float("nan") if m.group(0) == "#" else float(m.group(1).replace(",", "")) for m in _ANYTOK.finditer(t)]


def typed_bank(ctx) -> Dict[str, Any]:
    """Running balance. Each row has an amount (or a debit and a credit column) and the balance after it. Two orders are tried, oldest first
    (the balance changes by the amount of the later row) and newest first (by the amount of the earlier row), and the order that fits is used."""
    lines = semantic.rows_from_words(_confident(ctx["words"]))
    parsed = [_row_numbers(ln) for ln in lines]
    counts = [len(p) for p in parsed if len(p) >= 2]
    if len(counts) < 5:
        return result("typed.bank_statement", "Bank statement checks", "not_applicable",
                      why="Fewer than five rows with an amount and a running balance were read.")
    width = 3 if sum(c >= 3 for c in counts) > len(counts) / 2 else 2        # debit, credit, balance or amount, balance
    rows: List[Optional[Tuple[float, float]]] = []
    for p in parsed:
        if len(p) >= width and width == 3:
            debit, credit, bal = p[-3:]
            if any(x != x for x in (debit, credit, bal)) or (debit > 0) == (credit > 0):
                rows.append(None)                  # both or neither: the row cannot be read as one movement
            else:
                rows.append((debit if debit > 0 else credit, bal))
        elif len(p) >= 2 and width == 2:
            rows.append(None if any(x != x for x in p[-2:]) else (p[-2], p[-1]))
        elif len(p) >= 1 and any("." in str(x) for x in p):
            rows.append(None)                      # an amount or a balance that could not be read: a gap, not a link
    real = [r for r in rows if r is not None]
    if len(real) < 5:
        return result("typed.bank_statement", "Bank statement checks", "not_applicable",
                      why="Fewer than five rows with an amount and a running balance were read.")

    def links(newest_first: bool) -> List[bool]:
        out = []
        for i in range(1, len(rows)):
            if rows[i] is None or rows[i - 1] is None:
                continue
            amt = rows[i - 1][0] if newest_first else rows[i][0]
            out.append(abs(abs(rows[i][1] - rows[i - 1][1]) - amt) <= 0.011)
        return out
    asc, desc = links(False), links(True)
    consistent = desc if sum(desc) > sum(asc) else asc
    n = len(consistent)
    if n < 4:
        return result("typed.bank_statement", "Bank statement checks", "not_applicable",
                      why="Too few consecutive rows could be read to test the running balance.")
    fails = [i for i, c in enumerate(consistent) if not c]
    share = 1 - len(fails) / n
    if share < 0.5:
        return result("typed.bank_statement", "Bank statement checks", "not_applicable",
                      why="The rows do not follow a balance-after-amount layout, so the running balance cannot be tested.")
    f = []
    # one changed balance breaks two consecutive links (into it and out of it); one changed amount breaks one
    contiguous = fails and fails[-1] - fails[0] == len(fails) - 1
    if fails and contiguous and len(fails) <= 2 and n - len(fails) >= 3:
        f.append({"id": "bank.running_balance", "severity": "medium",
                  "message": "The running balance breaks at one place (the previous balance plus or minus the amount does not give the balance shown) "
                             "while the other rows follow it.",
                  "evidence": {"rows": [i + 2 for i in fails], "consistent_share": round(share, 2), "newest_first": consistent is desc}})
    return result("typed.bank_statement", "Bank statement checks", "finding" if f else "clear", f)


def typed_order(ctx) -> Dict[str, Any]:
    words = _confident(ctx["words"])
    f = [x for x in semantic.check_text(words) if x["id"].startswith("arith.")]
    text = "\n".join(semantic.rows_from_words(words)).lower()
    if not re.search(r"\b(sub ?total|grand total|order total|total)\b", text):
        return result("typed.order_invoice", "Order or invoice arithmetic", "not_applicable", why="No subtotal or total line was read.")
    return result("typed.order_invoice", "Order or invoice arithmetic", "finding" if f else "clear", f)


_CHAT_TIME = re.compile(r"(\d{1,2}):(\d{2})([AaPp][Mm])?[.,]?")


def _chat_times(words, width, height):
    """Message times in reading order, as minutes since midnight. Handles 24-hour times and 12-hour times written with or without
    a space before AM or PM ("8:43PM", "8:43 PM"). Ignores the status bar (top 7% of the image) and, in a landscape window, the
    left third, which holds the list of chats with their last-message times and not the messages themselves."""
    ws = sorted(words, key=lambda w: (w["top"], w["left"]))
    out = []
    for i, w in enumerate(ws):
        m = _CHAT_TIME.fullmatch(w["text"].strip())
        if not m:
            continue
        if height and w["top"] < 0.07 * height:
            continue
        if width and height and width > height and w["left"] < 0.33 * width:
            continue
        h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
        if not ap:                                   # "8:43" and "PM" may be two words on the same row
            for nx in ws[i + 1:i + 4]:
                if abs((nx["top"] + nx["height"] / 2) - (w["top"] + w["height"] / 2)) <= 0.5 * w["height"] and 0 <= nx["left"] - (w["left"] + w["width"]) <= 3 * w["height"]:
                    if nx["text"].strip().lower().rstrip(".,") in ("am", "pm"):
                        ap = nx["text"].strip().lower()[0] + "m"
                    break
        if mi > 59 or h > 24 or (ap and not 1 <= h <= 12):
            continue
        if ap:
            h = h % 12 + (12 if ap == "pm" else 0)
        out.append((w["top"], h * 60 + mi))
    return out


def typed_chat(ctx) -> Dict[str, Any]:
    cap = ctx.get("capture") or {}
    times = _chat_times(_confident(ctx["words"]), cap.get("width"), cap.get("height"))
    if len(times) < 5:
        return result("typed.chat", "Chat timestamp order", "not_applicable", why="Fewer than five message times were read.")
    mins = [t for _, t in times]
    drops = [i for i in range(1, len(mins)) if mins[i] + 10 < mins[i - 1] and mins[i - 1] - mins[i] < 600]
    f = []
    if drops:
        f.append({"id": "chat.time_order", "severity": "low",
                  "message": f"{len(drops)} message time(s) go backwards within the conversation (a day break would explain this).",
                  "evidence": {"positions": drops[:5]}})
    return result("typed.chat", "Chat timestamp order", "finding" if f else "clear", f)


def typed_message(ctx) -> Dict[str, Any]:
    words = _confident(ctx["words"])
    text = "\n".join(semantic.rows_from_words(words))
    m = re.search(r"\b(otp|code|pin)\b\D{0,25}(\d{4,8})\b", text, re.I)
    if not m:
        return result("typed.message_alert", "Message and OTP format", "not_applicable", why="No one-time code was read.")
    f = []
    codes = set(re.findall(r"\b\d{4,8}\b", text))
    if len(re.findall(r"\b(otp|verification code)\b", text, re.I)) >= 1 and len(m.group(2)) not in (4, 5, 6, 8):
        f.append({"id": "msg.otp_length", "severity": "low", "message": f"The one-time code has {len(m.group(2))} digits, which is unusual.",
                  "evidence": {}})
    return result("typed.message_alert", "Message and OTP format", "finding" if f else "clear", f)


from . import legacy_cues  # noqa: E402  (after result() is defined; legacy_cues imports this module)

GENERIC: List[Callable] = [file_metadata, content_logic, layout_grid, rendering_consistency] + legacy_cues.CHECKS
TYPED: Dict[str, Callable] = {
    "payment_receipt": typed_payment, "bank_statement": typed_bank, "order_invoice": typed_order,
    "chat": typed_chat, "message_alert": typed_message,
}
ALL_IDS = ["file_metadata", "content_logic", "layout_grid", "rendering"] + legacy_cues.IDS + [f"typed.{t}" for t in TYPED]
