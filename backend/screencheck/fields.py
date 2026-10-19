"""Pull the checkable facts (amounts, dates, times, reference numbers, UPI ids) out of text.

Used to compare a screenshot with a second, independent source. Dates are read day-first (dd/mm/yyyy), as on Indian bank
and payment screens; a 12-hour time with am/pm is converted to minutes since midnight.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

import semantic

_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"

_RE_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)")
_RE_DMY = re.compile(r"(?<![\d:])(\d{1,2})[/\-.](\d{1,2})[/\-.](20\d{2}|\d{2})(?![\d:])")
_RE_D_MON_Y = re.compile(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?[\s,.\-]+" + _MON + r"\.?[\s,.\-]+(20\d{2}|\d{2})(?!\d)", re.I)
_RE_MON_D_Y = re.compile(_MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})(?!\d)", re.I)
_RE_TIME = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]\.?m\.?)?(?![\d:])", re.I)
_RE_REF = re.compile(r"(?<![\d.,])(\d{4}[ -]\d{4}[ -]\d{4}|\d{10,22})(?![\d])")
_RE_UPI = re.compile(r"\b[a-z0-9][a-z0-9._-]{1,40}@[a-z][a-z0-9]{1,20}\b", re.I)
# an amount has a currency marker (OCR often renders the rupee sign as % or Y), decimals, or Indian/Western grouping
_RE_AMOUNT = re.compile(
    r"(?:(?P<cur>₹|rs\.?|inr|[%¥])\s*)?(?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{1,2}|\d+)(?![\d])", re.I)


def _valid_date(y: int, m: int, d: int) -> Optional[str]:
    if y < 100:
        y += 2000
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def _blank(text: str, spans: List[tuple]) -> str:
    chars = list(text)
    for a, b in spans:
        for i in range(a, b):
            chars[i] = " "
    return "".join(chars)


def extract_text(text: str) -> Dict[str, List[Any]]:
    dates: List[str] = []
    spans: List[tuple] = []

    def add_date(m, iso):
        spans.append(m.span())
        if iso and iso not in dates:
            dates.append(iso)

    for m in _RE_ISO.finditer(text):
        add_date(m, _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _RE_D_MON_Y.finditer(text):
        add_date(m, _valid_date(int(m.group(3)), _MONTHS[m.group(2).lower()[:3]], int(m.group(1))))
    for m in _RE_MON_D_Y.finditer(text):
        add_date(m, _valid_date(int(m.group(3)), _MONTHS[m.group(1).lower()[:3]], int(m.group(2))))
    for m in _RE_DMY.finditer(text):
        add_date(m, _valid_date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
    text1 = _blank(text, spans)

    times: List[int] = []
    tspans = []
    for m in _RE_TIME.finditer(text1):
        h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
        if mi > 59 or h > 23:
            continue
        if ap.startswith("p") and h < 12:
            h += 12
        if ap.startswith("a") and h == 12:
            h = 0
        v = h * 60 + mi
        if v not in times:
            times.append(v)
        tspans.append(m.span())
    text2 = _blank(text1, tspans)

    refs: List[str] = []
    rspans = []
    for m in _RE_REF.finditer(text2):
        digits = re.sub(r"\D", "", m.group(1))
        if digits not in refs:
            refs.append(digits)
        rspans.append(m.span())
    text3 = _blank(text2, rspans)

    upi = []
    for m in _RE_UPI.finditer(text):
        v = m.group(0).lower()
        if v not in upi:
            upi.append(v)

    amounts: List[float] = []
    for m in _RE_AMOUNT.finditer(text3):
        num = m.group("num")
        marked = bool(m.group("cur"))
        if not (marked or "," in num or "." in num):
            continue                      # a bare integer is too ambiguous (counts, years, ids)
        v = round(float(num.replace(",", "")), 2)
        if 0 < v < 1e9 and v not in amounts:
            amounts.append(v)
    return {"amounts": amounts, "dates": dates, "times": times, "refs": refs, "upi_ids": upi}


def extract_words(words: Sequence[Dict[str, Any]]) -> Dict[str, List[Any]]:
    return extract_text("\n".join(semantic.rows_from_words(words)))


def extract_consensus(rgb_img, words: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, List[Any]]]:
    """Read the screenshot twice (as is, and enlarged 2x). A value both reads agree on is `confident`; `any` has every value
    either read produced. A single misread digit therefore cannot turn into a confident wrong value."""
    import textforensics as tf
    from PIL import Image

    first = extract_words(words)
    big = rgb_img.resize((rgb_img.width * 2, rgb_img.height * 2), Image.LANCZOS)
    second = extract_words(tf.ocr_words(big))
    conf, anyv = {}, {}
    for k in first:
        a, b = first[k], second[k]
        conf[k] = [v for v in a if v in b]
        anyv[k] = a + [v for v in b if v not in a]
    return {"confident": conf, "any": anyv}


def fmt_time(v: int) -> str:
    return f"{v // 60:02d}:{v % 60:02d}"


def display(fields: Dict[str, List[Any]]) -> Dict[str, List[str]]:
    return {"amounts": [f"{v:,.2f}" for v in fields["amounts"]], "dates": list(fields["dates"]),
            "times": [fmt_time(v) for v in fields["times"]], "refs": list(fields["refs"]), "upi_ids": list(fields["upi_ids"])}
