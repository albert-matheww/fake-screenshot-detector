"""Rule-based checks that read what a screenshot *says* (and what its file claims).

Pixel analysis cannot see a native-rendered fake (a DOM edit in browser devtools, a
generator site that renders the page itself). Those fakes can still contradict
themselves, so this module looks for contradictions a real document cannot contain.

Every finding has a severity:
  high    near-conclusive on its own (a real document essentially never does this)
  medium  strongly suspicious, but OCR error or an unusual-but-legal layout is possible
  low     worth a human glance

Design rule learnt the hard way (see README, "What went wrong with v1"): a rule only
ships if it is silent on ordinary pages. The v1 'multiple Total/Balance amounts' rule
fired on any bank-app screenshot showing both a balance and a total and was removed.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Dict, List, Optional, Sequence

from PIL import ExifTags

# ----------------------------------------------------------------------------- file-level

_EDITING_TOOLS = ["photoshop", "gimp", "paint.net", "pixelmator", "affinity", "canva", "snapseed", "picsart",
                  "lightroom", "figma", "sketch", "illustrator", "photopea", "fotor", "pixlr", "meitu"]


def check_metadata(image) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        exif = image.getexif()
    except Exception:  # noqa: BLE001
        return out
    fields: Dict[str, str] = {}
    for tag_id, value in (exif or {}).items():
        if isinstance(value, bytes):
            value = value.decode(errors="replace")
        fields[str(ExifTags.TAGS.get(tag_id, tag_id))] = str(value)[:200]
    software = fields.get("Software", "")
    if any(t in software.lower() for t in _EDITING_TOOLS):
        out.append({"id": "metadata.editing_software", "severity": "high",
                    "message": f'The file\'s Software tag names an image editor: "{software}". '
                               "Real screenshot exporters do not write this tag.",
                    "evidence": {"Software": software}})
    if "Make" in fields or "Model" in fields:
        out.append({"id": "metadata.camera_tags", "severity": "low",
                    "message": "Camera Make/Model tags are present on something submitted as a screenshot "
                               "(it may be a photo of a screen).", "evidence": {k: fields[k] for k in ("Make", "Model") if k in fields}})
    if any(k.lower().startswith("gps") for k in fields):
        out.append({"id": "metadata.gps", "severity": "low", "message": "The file carries GPS location metadata.",
                    "evidence": {}})
    return out


# ----------------------------------------------------------------------------- text rules

_GENERATOR_WATERMARKS = [
    "bankstatements.net", "bank statements.net", "thepaystubs", "paystubcreator", "stubcreator", "makereceipt",
    "receiptmakerly", "docutemplates", "specimen", "sample statement", "not a real bank statement",
    "for novelty purposes only", "for entertainment purposes only", "this is not a real", "template only",
    "demo purposes only", "not a real document", "not an official document", "fake receipt", "prank",
]
_PLACEHOLDER_NAMES = ["john doe", "jane doe", "john smith", "test user", "sample name", "lorem ipsum"]
_PLACEHOLDER_NUMBER_RE = re.compile(r"(?<!\d)(\d)\1{7,}(?!\d)|123456789|987654321")

_MONEY = r"(?:[$€£₹]\s?)?(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2})"
_MONEY_RE = re.compile(_MONEY)
_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_DATE_WD_RE = re.compile(
    r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+(?:(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?"
    r"|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?)\s*(\d{4})?",
    re.I)
_IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?)\b")
_CARD_RE = re.compile(r"\b(\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4})\b")
_TIME_RE = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])")


def lines_from_words(words: Sequence[Dict[str, Any]]) -> List[str]:
    by: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for w in words:
        k = w.get("line", "")
        if k not in by:
            by[k] = []
            order.append(k)
        by[k].append(w)
    return [" ".join(x["text"] for x in sorted(by[k], key=lambda z: z["left"])) for k in order]


def rows_from_words(words: Sequence[Dict[str, Any]]) -> List[str]:
    """Rebuild the text rows of a screenshot from the word positions.

    Tesseract's own line identifiers put a label on the left and its amount on the far right of the same row into different
    lines (the usual layout of an invoice or a statement), so the arithmetic and running-balance rules would never see them
    together. A row here is every word whose vertical centre lies within half a text height of the row's, left to right."""
    ws = [w for w in words if w["text"].strip()]
    if not ws:
        return []
    med = sorted(w["height"] for w in ws)[len(ws) // 2]
    rows: List[Dict[str, Any]] = []
    for w in sorted(ws, key=lambda z: z["top"] + z["height"] / 2.0):
        cy = w["top"] + w["height"] / 2.0
        if rows and abs(cy - rows[-1]["cy"]) <= 0.5 * max(8.0, min(med, float(w["height"]))):
            r = rows[-1]
            r["words"].append(w)
            r["cy"] = sum(x["top"] + x["height"] / 2.0 for x in r["words"]) / len(r["words"])
        else:
            rows.append({"cy": cy, "words": [w]})
    return [" ".join(x["text"] for x in sorted(r["words"], key=lambda z: z["left"])) for r in rows]


def _luhn(num: str) -> bool:
    ds = [int(c) for c in num if c.isdigit()]
    if len(ds) < 12:
        return False
    s = 0
    for i, d in enumerate(reversed(ds)):
        if i % 2:
            d *= 2
            d -= 9 if d > 9 else 0
        s += d
    return s % 10 == 0


def _iban_ok(iban: str) -> bool:
    s = re.sub(r"\s", "", iban).upper()
    if not (15 <= len(s) <= 34):
        return False
    r = s[4:] + s[:4]
    try:
        return int("".join(str(int(c, 36)) for c in r)) % 97 == 1
    except ValueError:
        return False


def _amount(line: str) -> Optional[float]:
    vals = _MONEY_RE.findall(line)
    if not vals:
        return None
    try:
        return float(vals[-1].replace(",", ""))
    except ValueError:
        return None


def check_text(words: Sequence[Dict[str, Any]], today: Optional[_dt.date] = None) -> List[Dict[str, Any]]:
    today = today or _dt.date.today()
    out: List[Dict[str, Any]] = []
    if not words:
        return out
    lines = rows_from_words(words)
    text = "\n".join(lines)
    low = text.lower()

    for m in _GENERATOR_WATERMARKS:
        if m in low:
            out.append({"id": "text.generator_marker", "severity": "high",
                        "message": f'The image contains a fake-document-generator marker: "{m}".', "evidence": {"marker": m}})
    for n in _PLACEHOLDER_NAMES:
        if n in low:
            out.append({"id": "text.placeholder_name", "severity": "medium",
                        "message": f'The image contains a placeholder name ("{n}").', "evidence": {"name": n}})
    if _PLACEHOLDER_NUMBER_RE.search(re.sub(r"[\s-]", "", low)):
        out.append({"id": "text.placeholder_number", "severity": "medium",
                    "message": "A number looks like a placeholder (long run of one digit, or 123456789).", "evidence": {}})

    # --- arithmetic: only the unambiguous invariants.
    subtotal = total = None
    items: List[float] = []
    unreadable_item = False       # a line between the first item and the subtotal that has digits but no readable price (OCR often drops a decimal point)
    for ln in lines:
        l = ln.lower()
        a = _amount(ln)
        if a is None:
            if items and subtotal is None and re.search(r"\d", ln) and not re.search(r"\b(tax|vat|gst|shipping|delivery|discount|fee|tip|balance|total|date|time)\b", l):
                unreadable_item = True
            continue
        if re.search(r"\bsub\s?-?total\b", l):
            subtotal = a
        elif re.search(r"\b(grand total|order total|total due|amount due|total amount|total)\b", l) and not re.search(
                r"\b(total (spent|saved|income|expenses|debits|credits)|balance)\b", l):
            total = a
        elif not re.search(r"\b(tax|vat|gst|shipping|delivery|discount|fee|tip|balance|total)\b", l):
            items.append(a)
    if subtotal is not None and total is not None and total + 0.005 < subtotal and not re.search(
            r"\b(discount|coupon|promo|credit|saved)\b", low):
        out.append({"id": "arith.total_below_subtotal", "severity": "high",
                    "message": f"Total ({total:,.2f}) is smaller than Subtotal ({subtotal:,.2f}) although no discount "
                               "or credit line is shown.", "evidence": {"total": total, "subtotal": subtotal}})
    if subtotal is not None and len(items) >= 3 and not unreadable_item and abs(sum(items) - subtotal) > 0.011 and not re.search(
            r"\b(discount|coupon|promo|qty|x\s?\d)\b", low):
        out.append({"id": "arith.items_vs_subtotal", "severity": "medium",
                    "message": f"The listed item prices add up to {sum(items):,.2f}, but the Subtotal says {subtotal:,.2f}.",
                    "evidence": {"items_sum": round(sum(items), 2), "subtotal": subtotal}})

    # --- weekday / date consistency (a classic edit leaves the weekday untouched)
    for m in _DATE_WD_RE.finditer(text):
        wd = _WEEKDAYS[m.group(1).lower()[:3]]
        day = int(m.group(2) or m.group(5))
        mon = _MONTHS[(m.group(3) or m.group(4)).lower()[:3]]
        yr = int(m.group(6)) if m.group(6) else None
        if yr and 1 <= day <= 31:
            try:
                d = _dt.date(yr, mon, day)
            except ValueError:
                out.append({"id": "date.invalid", "severity": "high",
                            "message": f'"{m.group(0).strip()}" is not a real calendar date.', "evidence": {}})
                continue
            if d.weekday() != wd:
                real = d.strftime("%A")
                out.append({"id": "date.weekday_mismatch", "severity": "high",
                            "message": f'"{m.group(0).strip()}": {d.isoformat()} was a {real}, not the weekday shown.',
                            "evidence": {"date": d.isoformat(), "actual_weekday": real}})
            elif d > today + _dt.timedelta(days=1):
                out.append({"id": "date.future", "severity": "medium",
                            "message": f'A transaction/message date ({d.isoformat()}) lies in the future.', "evidence": {}})

    for m in _IBAN_RE.finditer(text):
        if not _iban_ok(m.group(1)):
            out.append({"id": "id.iban_checksum", "severity": "medium",
                        "message": f"IBAN {m.group(1)} fails the standard mod-97 checksum.", "evidence": {}})
    for m in _CARD_RE.finditer(text):
        if not _luhn(m.group(1)):
            out.append({"id": "id.card_luhn", "severity": "medium",
                        "message": "A full card number fails the Luhn checksum.", "evidence": {}})

    bad_times = [m.group(0) for m in _TIME_RE.finditer(text) if int(m.group(1)) > 24 or int(m.group(2)) > 59]
    if bad_times and not re.search(r"\d+:\d{2}:\d{2}:\d", text):
        out.append({"id": "time.invalid", "severity": "low",
                    "message": f"Impossible clock time(s) shown: {', '.join(bad_times[:3])} (OCR error is possible).",
                    "evidence": {}})
    return out



# ----------------------------------------------------------------------------- layout grid

def _is_numeric(w: Dict[str, Any]) -> bool:
    t = w["text"]
    digits = sum(c.isdigit() for c in t)
    return len(t) >= 2 and digits / float(len(t)) >= 0.5 and 10 <= w["height"] <= 120


def numeric_columns(words: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Columns of >= 6 same-size numbers sharing a right edge, one number per row, top to bottom."""
    nums = [w for w in words if _is_numeric(w)]
    if len(nums) < 6:
        return []
    nums.sort(key=lambda w: w["left"] + w["width"])
    clusters: List[List[Dict[str, Any]]] = []
    for w in nums:                      # cluster on right edge only; heights are filtered afterwards
        r = w["left"] + w["width"]
        if clusters:
            ref = clusters[-1]
            if abs(r - sum(x["left"] + x["width"] for x in ref) / len(ref)) <= 0.4 * w["height"]:
                ref.append(w)
                continue
        clusters.append([w])
    out = []
    for col in clusters:
        if len(col) < 6:
            continue
        med_h = sorted(w["height"] for w in col)[len(col) // 2]
        col = [w for w in col if 0.75 <= w["height"] / med_h <= 1.33]   # same text size: drops totals/headers
        if len(col) < 6:
            continue
        col = sorted(col, key=lambda w: w["top"] + w["height"])
        h = sorted(w["height"] for w in col)[len(col) // 2]
        rows = [col[0]]
        for w in col[1:]:   # one number per row: drop same-row neighbours
            if (w["top"] + w["height"]) - (rows[-1]["top"] + rows[-1]["height"]) > 0.8 * h:
                rows.append(w)
        if len(rows) >= 6:
            out.append(rows)
    return out


def check_layout_grid(words: Sequence[Dict[str, Any]], require_normal_gaps: bool = True) -> List[Dict[str, Any]]:
    """List UIs (payment history, statements, order lines) put one number per row in a column with a perfectly
    regular row pitch. A value pasted in by hand rarely lands exactly on that grid.

    Digits have no descenders, so the BOTTOM of a numeric word is its baseline: stable across glyphs, unlike
    its top or centre. For a column of >= 6 numbers each interior row's deviation from the midpoint of its two
    neighbours is ~0 on an untouched list. One row sitting well off the grid, while the rest of the column is
    regular, is flagged. An edited row shifts its two neighbours by half as much, so the culprit must dominate
    them. Silent when the column's own rhythm is irregular (chat bubbles, variable-height rows): that is not
    evidence of anything.
    """
    out: List[Dict[str, Any]] = []
    for rows in numeric_columns(words):
        h = sorted(w["height"] for w in rows)[len(rows) // 2]
        b = [w["top"] + w["height"] for w in rows]
        dev = [0.0] + [b[k] - (b[k - 1] + b[k + 1]) / 2.0 for k in range(1, len(rows) - 1)] + [0.0]
        interior = list(range(1, len(rows) - 1))
        j = max(interior, key=lambda k: abs(dev[k]))
        others = [abs(dev[k]) for k in interior if k not in (j - 1, j, j + 1)]
        if len(others) < 3:
            continue
        noise, spread = sorted(others)[len(others) // 2], max(others)
        neigh = max(abs(dev[j - 1]), abs(dev[j + 1]))
        pitch = sorted(b[k + 1] - b[k] for k in range(len(b) - 1))[(len(b) - 1) // 2]
        d1, d2 = b[j] - b[j - 1], b[j + 1] - b[j]
        # a row OCR skipped (or a header gap) doubles ONE pitch; a mis-placed number leaves both gaps near normal
        normal_gaps = 0.6 * pitch <= d1 <= 1.4 * pitch and 0.6 * pitch <= d2 <= 1.4 * pitch
        if (abs(dev[j]) >= max(5.0, 0.2 * h) and noise <= max(1.5, 0.05 * h) and spread <= max(3.0, 0.1 * h)
                and abs(dev[j]) >= 1.5 * neigh and (normal_gaps or not require_normal_gaps)):
            w = rows[j]
            out.append({"id": "layout.column_off_grid", "severity": "medium",
                        "message": f'The numbers in this column are evenly spaced (about {pitch:.0f} px apart), but '
                                   f'"{w["text"]}" sits {abs(dev[j]):.0f} px off that grid - a typical sign of a '
                                   "hand-placed value.",
                        "evidence": {"text": w["text"], "offset_px": round(abs(dev[j]), 1), "pitch_px": pitch,
                                     "box": [w["left"], w["top"], w["width"], w["height"]]}})
    return out


# ----------------------------------------------------------------------------- status bar

def check_status_bar_duplicate(words: Sequence[Dict[str, Any]], width: int, height: int) -> List[Dict[str, Any]]:
    """The phone status-bar clock repeated verbatim in the body = composited/duplicated chrome."""
    if height < width * 1.2 or not words:
        return []
    strip = max(24, int(height * 0.06))
    top, other = [], []
    for w in words:
        m = re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", w["text"].strip())
        if m:
            (top if w["top"] < strip else other).append(m.group(0))
    dup = sorted(set(top) & set(other))
    if dup:
        return [{"id": "chrome.duplicate_clock", "severity": "low",
                 "message": f"The status-bar clock ({dup[0]}) is repeated verbatim in the body - possible "
                            "screenshot-of-a-screenshot or pasted device chrome.", "evidence": {}}]
    return []


def run_all(image, words: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    w, h = image.size
    return check_metadata(image) + check_text(words) + check_status_bar_duplicate(words, w, h) + check_layout_grid(words)
