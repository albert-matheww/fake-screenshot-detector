"""Assurance levels, fact extraction and reconciliation with a second source."""
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app import app as flask_app
from screencheck import assurance, fields, reconcile
from screencheck.common import TYPES

SMS = "Rs.2,500.00 debited from A/c XX1234 on 12-10-2026 at 07:45 PM. UPI Ref No 628512345678. Avl Bal Rs.12,345.67"
SHOT = "Paid ₹2,500 to Alex on 12 Oct 2026, 7:46 pm. UPI transaction ID 6285 1234 5678"


def _shot(text):
    f = fields.extract_text(text)
    return {"any": f, "confident": f}


# ---------------------------------------------------------------- fields

def test_extracts_amounts_dates_times_and_references():
    f = fields.extract_text(SMS)
    assert f["amounts"] == [2500.0, 12345.67]
    assert f["dates"] == ["2026-10-12"]
    assert f["times"] == [19 * 60 + 45]
    assert f["refs"] == ["628512345678"]


def test_reference_is_not_read_as_an_amount_and_spaced_digits_are_joined():
    f = fields.extract_text(SHOT)
    assert f["refs"] == ["628512345678"] and f["amounts"] == [2500.0]


@pytest.mark.parametrize("text,iso", [("12/10/2026", "2026-10-12"), ("2026-10-12", "2026-10-12"), ("12th October, 2026", "2026-10-12"),
                                       ("Oct 12, 2026", "2026-10-12"), ("12 Oct 26", "2026-10-12")])
def test_dates_in_common_formats(text, iso):
    assert fields.extract_text(text)["dates"] == [iso]


def test_impossible_date_is_dropped():
    assert fields.extract_text("31/02/2026")["dates"] == []


def test_a_bare_integer_is_not_an_amount():
    assert fields.extract_text("Order 12 items, 2026 total")["amounts"] == []


# ---------------------------------------------------------------- reconcile

def test_matching_sources_corroborate():
    r = reconcile.compare_fields(fields.extract_text(SMS), _shot(SHOT))
    assert r["status"] == "corroborated" and "refs" in r["matched"]


def test_changed_reference_and_amount_is_a_conflict():
    r = reconcile.compare_fields(fields.extract_text(SMS.replace("2,500.00", "9,500.00").replace("628512345678", "628599995678")), _shot(SHOT))
    assert r["status"] == "conflict" and set(r["differs"]) == {"refs", "amounts"}


def test_one_digit_reference_difference_never_corroborates():
    r = reconcile.compare_fields(fields.extract_text(SMS.replace("628512345678", "628512345679")), _shot(SHOT))
    assert r["status"] == "review"


def test_amount_and_date_without_reference_corroborate():
    r = reconcile.compare_fields(fields.extract_text("Rs 2,500.00 on 12-10-2026"), _shot(SHOT))
    assert r["status"] == "corroborated"


def test_amount_alone_is_only_partial():
    r = reconcile.compare_fields(fields.extract_text("Rs 2,500.00 received"), _shot(SHOT))
    assert r["status"] == "partial"


def test_a_value_the_screenshot_does_not_show_is_unclear_not_a_conflict():
    r = reconcile.compare_fields(fields.extract_text(SMS), {"any": fields.extract_text("hello"), "confident": fields.extract_text("hello")})
    assert r["status"] == "nothing_matched" and not r["differs"]


def test_time_within_five_minutes_matches_and_far_apart_differs():
    ok = reconcile.compare_fields({"amounts": [], "dates": [], "refs": [], "upi_ids": [], "times": [19 * 60 + 45]}, _shot(SHOT))
    far = reconcile.compare_fields({"amounts": [], "dates": [], "refs": [], "upi_ids": [], "times": [9 * 60]}, _shot(SHOT))
    assert ok["rows"][3]["status"] == "matched" and far["rows"][3]["status"] == "differs"


def test_source_with_no_facts():
    assert reconcile.reconcile(_shot(SHOT), "hello there")["status"] == "no_facts"


# ---------------------------------------------------------------- assurance

def _check(cid, status, category="content", live=False, sev="medium", msg="m"):
    return {"id": cid, "category": category, "status": status, "severity": sev if status == "finding" else None,
            "findings": [{"severity": sev, "message": msg}] if status == "finding" else [], "gate": {"status": "live" if live else "advisory"}}


def test_level_1_needs_a_content_check_that_examined_the_text():
    a = assurance.assess("inconclusive", [_check("content_logic", "clear", live=True)], 40)
    assert a["level"] == 1 and a["status"] == "consistent"
    assert assurance.assess("inconclusive", [_check("content_logic", "not_applicable")], 40)["level"] == 0
    assert assurance.assess("inconclusive", [_check("content_logic", "clear")], 5)["level"] == 0


def test_a_live_contradiction_is_level_0():
    a = assurance.assess("suspicious", [_check("content_logic", "finding", live=True, msg="weekday wrong")], 40)
    assert a["level"] == 0 and a["status"] == "contradiction" and "weekday wrong" in a["reasons"]


def test_an_uncalibrated_content_finding_lowers_assurance_but_not_the_verdict():
    a = assurance.assess("inconclusive", [_check("content_logic", "clear", live=True), _check("typed.bank_statement", "finding")], 40)
    assert a["level"] == 0 and a["status"] == "possible_issue"


def test_level_2_needs_corroboration_and_a_conflict_overrides_everything():
    rec_ok = reconcile.compare_fields(fields.extract_text(SMS), _shot(SHOT))
    assert assurance.assess("inconclusive", [_check("content_logic", "clear", live=True)], 40, rec_ok)["level"] == 2
    rec_bad = reconcile.compare_fields(fields.extract_text(SMS.replace("628512345678", "628599995678")), _shot(SHOT))
    a = assurance.assess("inconclusive", [_check("content_logic", "clear", live=True)], 40, rec_bad)
    assert a["level"] == 0 and a["status"] == "conflict"


def test_assurance_never_says_genuine_and_level_3_is_never_reached():
    rec_ok = reconcile.compare_fields(fields.extract_text(SMS), _shot(SHOT))
    for a in (assurance.assess("inconclusive", [_check("content_logic", "clear", live=True)], 40, rec_ok),
              assurance.assess("no_evidence", [_check("content_logic", "clear", live=True)], 40)):
        text = " ".join([a["label"], a["status"], *a["reasons"], a["next_step"] or "", *[r["label"] + " " + r["requirement"] for r in a["ladder"]]]).lower()
        assert "genuine" not in text and "authentic" not in text
        assert not next(r for r in a["ladder"] if r["level"] == 3)["reached"]
        assert a["level"] <= 2


# ---------------------------------------------------------------- API

@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _png_with(text, w=1000, h=300, size=40):
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=size)
    for i, line in enumerate(text.split("\n")):
        d.text((20, 20 + i * (size + 20)), line, font=f, fill=(0, 0, 0))
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def test_analyze_returns_assurance_and_fields(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(_png_with("Paid Rs 2,500.00 on 12-10-2026\nUPI Ref 628512345678")), "a.png")},
                    content_type="multipart/form-data")
    j = r.get_json()
    assert r.status_code == 200 and j["assurance"]["level"] in (0, 1) and "fields" in j and len(j["assurance"]["ladder"]) == 4


def test_analyze_uses_the_type_the_person_chose(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(_png_with("hello world")), "a.png"), "type": "bank_statement"}, content_type="multipart/form-data")
    j = r.get_json()
    assert r.status_code == 200 and j["routing"]["type"] == "bank_statement" and j["routing"]["source"] == "user"


def test_analyze_rejects_an_unknown_type(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(_png_with("x")), "a.png"), "type": "passport"}, content_type="multipart/form-data")
    assert r.status_code == 400 and "Unknown type" in r.get_json()["error"]


def test_reconcile_needs_a_second_source(client):
    r = client.post("/reconcile", data={"image": (io.BytesIO(_png_with("x")), "a.png")}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_reconcile_with_text_conflicting_source_is_a_conflict(client):
    img = _png_with("Paid Rs 2,500.00 on 12-10-2026\nUPI Ref 628512345678")
    r = client.post("/reconcile", data={"image": (io.BytesIO(img), "a.png"), "type": "payment_receipt",
                                        "source_text": "Rs 9,500.00 debited on 12-10-2026 UPI Ref 628599995678"}, content_type="multipart/form-data")
    j = r.get_json()
    assert r.status_code == 200 and j["reconcile"]["status"] in ("conflict", "review", "nothing_matched")
    assert j["assurance"]["level"] == 0 or j["reconcile"]["status"] == "nothing_matched"


def test_reconcile_with_agreeing_source_is_not_a_conflict(client):
    img = _png_with("Paid Rs 2,500.00 on 12-10-2026\nUPI Ref 628512345678")
    r = client.post("/reconcile", data={"image": (io.BytesIO(img), "a.png"), "source_text": "Rs 2,500.00 debited on 12-10-2026 UPI Ref 628512345678"},
                    content_type="multipart/form-data")
    j = r.get_json()
    assert r.status_code == 200 and j["reconcile"]["status"] != "conflict"


# ---------------------------------------------------------------- version-1 hints

def test_v1_cues_can_never_be_live_even_if_calibration_says_so(monkeypatch):
    from screencheck import gates
    monkeypatch.setattr(gates, "_CACHE", {"g": {"checks": {"v1.clone": {"status": "live", "n": 30, "flagged": 0}}}})
    g = gates.gate_for("v1.clone")
    assert g["status"] == "advisory" and not g["uninformative"]


def test_a_hint_that_flags_most_genuine_screenshots_is_marked_uninformative_and_ignored_by_the_verdict(monkeypatch):
    from screencheck import gates, verdict
    monkeypatch.setattr(gates, "_CACHE", {"g": {"checks": {"v1.noise": {"status": "advisory", "n": 23, "flagged": 23}}}})
    g = gates.gate_for("v1.noise")
    assert g["uninformative"] is True and "23 of 23" in g["reason"]
    chk = {**_check("v1.noise", "finding", category="visual"), "name": "Noise", "gate": g}
    route = {"type": "bank_statement", "status": "confident", "label": "x", "router_validated": True}
    d = verdict.decide(route, [chk], 40)
    assert d["coverage"]["advisory_findings"] == 0
    assert not any("Advisory checks" in c for c in d["caveats"])


def test_the_v1_cues_run_and_say_so_for_a_lossless_file(client):
    r = client.post("/analyze", data={"image": (io.BytesIO(_png_with("hello world " * 6)), "a.png")}, content_type="multipart/form-data")
    by = {c["id"]: c for c in r.get_json()["checks"]}
    assert by["v1.ela"]["status"] == "not_applicable" and "lossless" in by["v1.ela"]["why"]
    assert all(by[k]["gate"]["status"] == "advisory" for k in ("v1.ela", "v1.ghost", "v1.quant", "v1.noise", "v1.clone"))


def test_an_amount_with_one_extra_leading_digit_is_review_not_conflict_and_never_corroboration():
    src = fields.extract_text("Rs.8,063.17 debited on 12-10-2026. UPI Ref No 628512345678")
    shot = fields.extract_text("Paid 18,063.17 on 12 Oct 2026. UPI transaction ID 628512345678")   # the rupee sign was read as a 1
    r = reconcile.compare_fields(src, {"any": shot, "confident": shot})
    assert r["status"] == "review" and not r["differs"]
    amount_row = next(x for x in r["rows"] if x["kind"] == "amounts")
    assert amount_row["status"] == "near"


def test_a_clearly_different_amount_is_still_a_conflict():
    src = fields.extract_text("Rs.8,063.17 debited on 12-10-2026. UPI Ref No 628512345678")
    shot = fields.extract_text("Paid 9,999.00 on 12 Oct 2026. UPI transaction ID 628512345678")
    assert reconcile.compare_fields(src, {"any": shot, "confident": shot})["status"] == "conflict"


# ---------------------------------------------------------------- real-data repairs: dates without a year, whole-rupee amounts, lists

def test_day_and_month_without_a_year_is_read_and_matches_a_full_source_date():
    f = fields.extract_text("Mohammed Roshan 16 October\nBava S Restaurant 15 Oct")
    assert "--10-16" in f["dates"] and "--10-15" in f["dates"]
    src = fields.extract_text("Debited Rs:105.00 on 16-10-2026 00:59:19")
    shot = {"any": {**fields.extract_text("Paid 105 16 October"), }, "confident": fields.extract_text("Paid 105 16 October")}
    r = reconcile.compare_fields(src, shot)
    assert next(x for x in r["rows"] if x["kind"] == "dates")["status"] == "matched"
    assert next(x for x in r["rows"] if x["kind"] == "amounts")["status"] == "near"         # a bare 105 can only ever make Rs 105.00 "near"
    assert r["status"] == "review"


def test_a_whole_rupee_amount_with_the_currency_sign_read_as_a_digit_is_review_not_corroboration():
    src = fields.extract_text("Debited Rs:105.00 on 16-10-2026")
    shot = fields.extract_text("Mohammed Roshan 2105\n16 October")                         # the rupee sign came out as a 2
    r = reconcile.compare_fields(src, {"any": shot, "confident": shot})
    assert r["status"] == "review"


def test_a_payment_that_is_not_on_a_long_list_is_not_a_conflict():
    rows = "\n".join(f"Person {i} {100 + 17 * i} 12 October" for i in range(8))
    shot = fields.extract_text(rows)
    src = fields.extract_text("Debited Rs:5.00 on 20-10-2026")
    r = reconcile.compare_fields(src, {"any": shot, "confident": shot})
    assert r["status"] != "conflict"
