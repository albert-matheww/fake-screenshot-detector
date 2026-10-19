"""Tests of the v3 design: routing, gating, fail-safe verdicts, typed checks and compare mode."""
import io

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app import app as flask_app
from screencheck import checks, compare, gates, router, verdict
from screencheck.common import wilson


def _img(rows, w=640, h=420, bg=(250, 250, 252), size=24):
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=size)
    for i, r in enumerate(rows):
        d.text((24, 16 + i * (size + 20)), r, font=f, fill=(20, 20, 30))
    return img


def _png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _words(texts, top0=20, step=40, left=20, h=22):
    return [{"text": t, "left": left, "top": top0 + i * step, "width": 8 * len(t), "height": h, "conf": 95.0, "line": f"1-1-{i}"}
            for i, t in enumerate(texts)]


# ---------------------------------------------------------------- routing

def test_content_router_recognises_obvious_types():
    pay = _words(["Paid", "to", "Alex", "UPI", "transaction", "ID", "123456789012", "Completed"])
    assert router.route_content(pay)["type"] == "payment_receipt"
    bank = _words(["Account", "statement", "Available", "balance", "Debit", "Credit", "IFSC"])
    assert router.route_content(bank)["type"] == "bank_statement"
    otp = _words(["Your", "OTP", "is", "482913", "Do", "not", "share", "valid", "for", "10", "minutes"])
    assert router.route_content(otp)["type"] == "message_alert"


def test_content_router_abstains_without_evidence():
    assert router.route_content(_words(["hello", "world"]))["type"] is None


def test_unvalidated_routers_never_enable_typed_checks(monkeypatch):
    monkeypatch.setattr(router, "router_gate", lambda: {"content": {"validated": False}, "structure": {"validated": False}})
    r = router.route(np.zeros((400, 300, 3), np.uint8), _words(["Paid", "to", "Alex", "UPI", "transaction", "ID", "Completed"]))
    assert r["typed_checks_enabled"] is False
    assert r["status"] in ("tentative", "unknown")


def test_validated_content_router_can_enable_typed_checks(monkeypatch):
    monkeypatch.setattr(router, "router_gate", lambda: {"content": {"validated": True}, "structure": {"validated": False}})
    r = router.route(np.zeros((400, 300, 3), np.uint8), _words(["Paid", "to", "Alex", "UPI", "transaction", "ID", "Completed", "UTR", "Google", "Pay"]))
    assert r["type"] == "payment_receipt" and r["typed_checks_enabled"] is True


# ---------------------------------------------------------------- gates

def test_gate_needs_enough_genuine_images_and_low_false_alarms():
    assert gates.decide(5, 0)[0] is False                       # too few images: advisory, however clean
    assert gates.decide(23, 0)[0] is True                       # 0 of 23: upper bound 0.14
    assert gates.decide(23, 3)[0] is False                      # 3 of 23: upper bound 0.32
    assert gates.decide(200, 10)[0] is True                     # 5%: upper bound well below 0.15
    live, hi, why = gates.decide(10, 0)
    assert not live and "10 more" in why


def test_wilson_interval_is_sane():
    lo, hi = wilson(0, 23)
    assert lo == 0.0 and 0.13 < hi < 0.15


# ---------------------------------------------------------------- verdict policy

def _chk(cid, status, severity=None, live=True, category="content", msg="x"):
    return {"id": cid, "name": cid, "category": category, "status": status, "severity": severity,
            "findings": [{"id": "f", "severity": severity, "message": msg}] if status == "finding" else [],
            "gate": {"status": "live" if live else "advisory"}, "regions": [], "detail": {}}


ROUTE_OK = {"type": "payment_receipt", "label": "Payment receipt or transfer", "status": "confident", "router_validated": True}
ROUTE_UNKNOWN = {"type": "unknown", "label": "Unknown type", "status": "unknown", "router_validated": False}


def test_clean_verdict_needs_a_live_content_and_a_live_visual_check():
    only_content = [_chk("file_metadata", "clear", category="file"), _chk("content_logic", "clear")]
    assert verdict.decide(ROUTE_OK, only_content, 100)["verdict"] == "inconclusive"
    both = only_content + [_chk("layout_grid", "clear", category="visual")]
    assert verdict.decide(ROUTE_OK, both, 100)["verdict"] == "no_evidence"


def test_unknown_type_never_gives_a_clean_verdict():
    both = [_chk("content_logic", "clear"), _chk("layout_grid", "clear", category="visual")]
    assert verdict.decide(ROUTE_UNKNOWN, both, 100)["verdict"] == "inconclusive"


def test_advisory_signal_moves_towards_inconclusive_never_towards_clear():
    cs = [_chk("content_logic", "clear"), _chk("layout_grid", "clear", category="visual"),
          _chk("rendering", "finding", "high", live=False, category="visual")]
    d = verdict.decide(ROUTE_OK, cs, 100)
    assert d["verdict"] == "inconclusive"
    assert any("Advisory" in c for c in d["caveats"])


def test_live_findings_set_the_verdict_by_severity():
    assert verdict.decide(ROUTE_OK, [_chk("content_logic", "finding", "high")], 100)["verdict"] == "evidence_of_editing"
    assert verdict.decide(ROUTE_OK, [_chk("content_logic", "finding", "medium")], 100)["verdict"] == "suspicious"
    assert verdict.decide(ROUTE_OK, [_chk("content_logic", "finding", "low")], 100)["verdict"] == "inconclusive"


def test_verdict_text_never_claims_authenticity():
    for v in verdict.LABELS.values():
        assert "authentic" not in v.lower() and "genuine" not in v.lower()


def test_not_applicable_is_never_counted_as_a_pass():
    cs = [_chk("content_logic", "clear"), _chk("layout_grid", "not_applicable", category="visual")]
    assert verdict.decide(ROUTE_OK, cs, 100)["verdict"] == "inconclusive"


# ---------------------------------------------------------------- typed checks (called directly)

def _ctx(texts, h=22):
    words = [{"text": x, "left": 20 + 90 * i, "top": 100, "width": 8 * len(x), "height": h, "conf": 95.0, "line": "1-1-1"} for i, x in enumerate(texts)]
    return {"words": words, "capture": {"width": 600, "height": 800}}


def test_upi_reference_length():
    ok = checks.typed_payment(_ctx(["Payment", "successful", "UPI", "transaction", "ID", "123456789012", "To", "Alex"]))
    bad = checks.typed_payment(_ctx(["Payment", "successful", "UPI", "transaction", "ID", "1234567890123", "To", "Alex"]))
    assert ok["status"] == "clear"
    assert bad["status"] == "finding" and bad["findings"][0]["id"] == "pay.upi_ref_length"


def test_bank_running_balance_detects_a_broken_row():
    def row(i, amt, bal, top):
        return [{"text": t, "left": 20 + 90 * j, "top": top, "width": 70, "height": 20, "conf": 95.0, "line": f"1-1-{i}"}
                for j, t in enumerate(["Txn", f"{amt:.2f}", f"{bal:,.2f}"])]
    bals = [1000.0]
    amts = [50.0, 20.0, 75.0, 10.0, 30.0, 45.0]
    for a in amts:
        bals.append(bals[-1] - a)
    good = []
    for i, (a, b) in enumerate(zip(amts, bals[1:])):
        good += row(i, a, b, 20 + 40 * i)
    ctx = {"words": good, "capture": {"width": 600, "height": 800}}
    assert checks.typed_bank(ctx)["status"] == "clear"
    bad = [dict(w) for w in good]
    bad[3 * 3 + 2]["text"] = "9,999.00"      # change one balance
    assert checks.typed_bank({"words": bad, "capture": {"width": 600, "height": 800}})["status"] == "finding"


def test_typed_checks_say_not_applicable_when_they_cannot_look():
    assert checks.typed_bank(_ctx(["hello", "world"]))["status"] == "not_applicable"
    assert checks.typed_chat(_ctx(["hi"]))["status"] == "not_applicable"
    assert checks.typed_order(_ctx(["hi", "there"]))["status"] == "not_applicable"


def test_every_result_carries_a_category():
    r = checks.result("typed.chat", "x", "clear")
    assert r["category"] == "content"
    assert checks.result("rendering", "x", "clear")["category"] == "visual"


# ---------------------------------------------------------------- compare mode

def test_compare_finds_a_changed_number_and_ignores_a_resave():
    a = _img(["Order total", "Amount 1,284.19", "Reference 88231907", "Paid on Monday"], size=30)
    b = _img(["Order total", "Amount 7,284.19", "Reference 88231907", "Paid on Monday"], size=30)
    r = compare.compare_bytes(_png(a), _png(b))
    assert r["status"] == "differences_found" and r["regions"]
    same = compare.compare_bytes(_png(a), _png(a))
    assert same["status"] == "no_difference"
    buf = io.BytesIO()
    a.save(buf, "JPEG", quality=80)
    resaved = compare.compare_bytes(_png(a), buf.getvalue())
    assert resaved["regions"] == []


def test_compare_refuses_different_layouts():
    a = _img(["x"], w=600, h=400)
    b = _img(["x"], w=600, h=900)
    assert compare.compare_bytes(_png(a), _png(b))["status"] == "layout_mismatch"


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_compare_endpoint(client):
    a = _img(["Amount 1,284.19", "Paid on Monday"], size=30)
    b = _img(["Amount 9,284.19", "Paid on Monday"], size=30)
    r = client.post("/compare", data={"original": (io.BytesIO(_png(a)), "o.png"), "suspect": (io.BytesIO(_png(b)), "s.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["status"] == "differences_found"
    assert client.post("/compare", data={"original": (io.BytesIO(_png(a)), "o.png")}, content_type="multipart/form-data").status_code == 400


def test_analyze_response_exposes_routing_checks_and_coverage(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(_png(_img(["Amount 1,284.19", "Reference 88231907 completed"] * 3))), "s.png")},
                    content_type="multipart/form-data")
    b = r.get_json()
    assert b["routing"]["type"] in ("unknown",) or isinstance(b["routing"]["type"], str)
    assert {c["status"] for c in b["checks"]} <= {"finding", "clear", "not_applicable"}
    assert all("gate" in c for c in b["checks"])
    assert set(b["coverage"]) >= {"live_findings", "live_clear", "advisory_findings", "not_applicable"}
    assert b["verify_steps"] and b["limitations"]


# ---------------------------------------------------------------- rows rebuilt from word positions

def _row(items, y, line_prefix, h=24):
    """items: (text, left) pairs on one visual row; every word gets its own Tesseract line key, as happens for far-apart columns."""
    return [{"text": t, "left": x, "top": y, "width": 12 * len(t), "height": h, "conf": 95.0, "line": f"{line_prefix}-{i}"} for i, (t, x) in enumerate(items)]


def test_rows_join_a_label_and_an_amount_that_tesseract_put_in_different_lines():
    import semantic
    words = _row([("Subtotal", 40), ("45.00", 800)], 100, "a") + _row([("Total", 40), ("40.00", 800)], 150, "b")
    assert semantic.rows_from_words(words) == ["Subtotal 45.00", "Total 40.00"]
    assert semantic.lines_from_words(words) != semantic.rows_from_words(words)       # the old grouping kept them apart


def test_total_below_subtotal_is_found_when_label_and_amount_are_far_apart():
    import semantic
    words = _row([("Subtotal", 40), ("45.00", 800)], 100, "a") + _row([("Total", 40), ("40.00", 800)], 150, "b")
    assert any(f["id"] == "arith.total_below_subtotal" for f in semantic.check_text(words))
    ok = _row([("Subtotal", 40), ("45.00", 800)], 100, "a") + _row([("Total", 40), ("47.25", 800)], 150, "b")
    assert not any(f["id"].startswith("arith.") for f in semantic.check_text(ok))


def test_running_balance_break_is_found_with_columns_far_apart():
    bal, amts = [1000.0, 950.0, 900.0, 880.0, 830.0, 780.0, 760.0], [50.0, 50.0, 20.0, 50.0, 50.0, 20.0]
    def doc(balances):
        words = []
        for i in range(1, 7):
            words += _row([(f"{i}Jan", 40), (f"{amts[i - 1]:.2f}", 600), (f"{balances[i]:,.2f}", 800)], 60 + 45 * i, f"r{i}")
        return {"words": words, "capture": {}}
    assert checks.typed_bank(doc(bal))["status"] == "clear"
    bad = list(bal); bad[3] = 980.0
    assert checks.typed_bank(doc(bad))["status"] == "finding"


def test_running_balance_ignores_a_row_whose_amount_could_not_be_read():
    bal, amts = [1000.0, 950.0, 900.0, 880.0, 830.0, 780.0, 760.0, 700.0], [50.0, 50.0, 20.0, 50.0, 50.0, 20.0, 60.0]
    words = []
    for i in range(1, 8):
        cells = [(f"{i}Jan", 40), (f"{amts[i - 1]:.2f}", 600), (f"{bal[i]:,.2f}", 800)]
        if i == 3:
            cells[1] = ("20-00", 600)          # OCR lost the decimal point: this row now has one readable amount
        words += _row(cells, 60 + 45 * i, f"r{i}")
    assert checks.typed_bank({"words": words, "capture": {}})["status"] == "clear"


def _chat(times, width=700, height=1400, left=300, start_top=200):
    words = []
    for i, t in enumerate(times):
        words += _row([(t, left)], start_top + 70 * i, f"c{i}")
    return {"words": words, "capture": {"width": width, "height": height}}


def test_chat_times_glued_to_am_pm_are_read():
    ok = _chat(["8:43PM", "8:44PM", "8:46PM", "8:50PM", "9:02PM", "9:03PM"])
    assert checks.typed_chat(ok)["status"] == "clear"
    bad = _chat(["8:43PM", "8:44PM", "8:46PM", "8:02PM", "9:02PM", "9:03PM"])
    assert checks.typed_chat(bad)["status"] == "finding"


def test_chat_times_with_a_separate_pm_word_and_across_noon_are_read_as_twelve_hour_times():
    words = []
    for i, (t, ap) in enumerate([("11:50", "AM"), ("11:55", "AM"), ("12:03", "PM"), ("12:10", "PM"), ("12:20", "PM"), ("12:21", "PM")]):
        words += _row([(t, 300), (ap, 300 + 12 * len(t) + 8)], 200 + 70 * i, f"c{i}")
    assert checks.typed_chat({"words": words, "capture": {"width": 700, "height": 1400}})["status"] == "clear"


def test_chat_ignores_the_status_bar_clock_and_the_chat_list_of_a_desktop_window():
    ok = _chat(["3:46AM", "3:47AM", "3:50AM", "3:52AM", "9:39AM", "9:40AM"])
    ok["words"] += _row([("5:19", 300)], 20, "bar")              # phone status bar: not a message time
    assert checks.typed_chat(ok)["status"] == "clear"
    desk = _chat(["8:43PM", "8:44PM", "8:46PM", "8:50PM", "9:02PM", "9:03PM"], width=2000, height=1300, left=1500)
    for i, t in enumerate(["5:01PM", "4:44PM", "2:05PM", "12:50PM", "11:31AM"]):
        desk["words"] += _row([(t, 450)], 300 + 90 * i, f"s{i}")  # sidebar list, newest first
    assert checks.typed_chat(desk)["status"] == "clear"
