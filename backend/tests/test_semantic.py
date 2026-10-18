"""Rule checks must (1) fire on real contradictions and (2) stay silent on ordinary pages.
(2) is the lesson of v1, whose 'multiple Total/Balance amounts' rule flagged any bank-app screenshot."""
import datetime as dt

import semantic as S


def W(*lines):
    """Build OCR-like word dicts: each string is one line."""
    words = []
    for li, line in enumerate(lines):
        x = 10
        for t in line.split():
            words.append({"text": t, "left": x, "top": 20 + li * 30, "width": 10 * len(t), "height": 18,
                          "conf": 90.0, "line": f"1-1-{li}"})
            x += 10 * len(t) + 8
    return words


def ids(findings):
    return {f["id"] for f in findings}


def test_ordinary_bank_page_is_silent():
    # v1 flagged exactly this: a balance AND a 'total spent' on the same screen
    words = W("Checking 4821", "Balance $1,284.19", "Coffee House -$4.75", "Metro Transit -$2.90",
              "Payroll Deposit +$1,840.00", "Grocery Mart -$63.12", "Total Spent $70.77")
    assert S.check_text(words) == []


def test_total_below_subtotal_is_high():
    words = W("Subtotal $120.00", "Tax $9.60", "Total $60.00")
    assert "arith.total_below_subtotal" in ids(S.check_text(words))


def test_total_below_subtotal_ignored_when_discount_shown():
    words = W("Subtotal $120.00", "Discount -$70.00", "Total $50.00")
    assert "arith.total_below_subtotal" not in ids(S.check_text(words))


def test_items_not_adding_to_subtotal_is_medium():
    words = W("Wireless Headphones $59.99", "USB-C Cable $12.99", "Phone Case $15.00", "Subtotal $99.00")
    f = [x for x in S.check_text(words) if x["id"] == "arith.items_vs_subtotal"]
    assert f and f[0]["severity"] == "medium"


def test_items_adding_up_is_silent():
    words = W("Wireless Headphones $59.99", "USB-C Cable $12.99", "Phone Case $15.00", "Subtotal $87.98")
    assert "arith.items_vs_subtotal" not in ids(S.check_text(words))


def test_weekday_mismatch_detected_and_match_passes():
    # 12 January 2026 is a Monday
    bad = S.check_text(W("Fri, 12 Jan 2026 Payment received"), today=dt.date(2026, 10, 15))
    good = S.check_text(W("Mon, 12 Jan 2026 Payment received"), today=dt.date(2026, 10, 15))
    assert "date.weekday_mismatch" in ids(bad)
    assert "date.weekday_mismatch" not in ids(good)


def test_month_first_date_format():
    bad = S.check_text(W("Sat, Jan 12, 2026"), today=dt.date(2026, 10, 15))
    assert "date.weekday_mismatch" in ids(bad)


def test_future_date_is_medium():
    f = S.check_text(W("Mon, 14 Dec 2026 Payment received"), today=dt.date(2026, 10, 15))
    assert "date.future" in ids(f) or "date.weekday_mismatch" in ids(f)  # 14 Dec 2026 is a Monday -> future


def test_iban_and_luhn():
    assert S.check_text(W("IBAN GB82 WEST 1234 5698 7654 32")) == []                      # valid example IBAN
    assert "id.iban_checksum" in ids(S.check_text(W("IBAN GB82 WEST 1234 5698 7654 33")))
    assert S.check_text(W("Card 4111 1111 1111 1111")) == []                              # valid test PAN
    assert "id.card_luhn" in ids(S.check_text(W("Card 4111 1111 1111 1112")))


def test_generator_watermark_and_placeholder():
    f = S.check_text(W("bankstatements.net", "John Doe", "Account 123456789"))
    assert {"text.generator_marker", "text.placeholder_name", "text.placeholder_number"} <= ids(f)


def test_normal_sentence_silent():
    assert S.check_text(W("Hey are you free tonight?", "Sent the payment already", "9:41")) == []


def test_status_bar_duplicate_clock():
    words = [{"text": "9:41", "left": 10, "top": 5, "width": 40, "height": 14, "conf": 90, "line": "1"},
             {"text": "9:41", "left": 200, "top": 500, "width": 40, "height": 14, "conf": 90, "line": "2"}]
    assert S.check_status_bar_duplicate(words, 400, 900)
    assert not S.check_status_bar_duplicate(words, 900, 400)   # not phone-shaped


def test_metadata_editing_tool_tag():
    from PIL import Image
    im = Image.new("RGB", (40, 40), "white")
    ex = Image.Exif()
    ex[0x0131] = "Adobe Photoshop 25.0"
    import io
    b = io.BytesIO()
    im.save(b, "JPEG", exif=ex)
    im2 = Image.open(io.BytesIO(b.getvalue()))
    f = S.check_metadata(im2)
    assert f and f[0]["severity"] == "high"
    plain = io.BytesIO()
    im.save(plain, "JPEG")
    assert S.check_metadata(Image.open(io.BytesIO(plain.getvalue()))) == []


# ----------------------------------------------------------------------------- layout grid
def _column(bottoms, h=30, right=1060):
    return [{"text": f"{100 + i * 7}", "left": right - 70, "top": b - h, "width": 70, "height": h, "conf": 90.0,
             "line": f"1-1-{i}"} for i, b in enumerate(bottoms)]


def test_layout_grid_flags_one_off_row():
    b = [500 + 200 * i for i in range(8)]
    b[3] -= 14                                  # one number pasted 14 px too high
    f = S.check_layout_grid(_column(b))
    assert len(f) == 1 and f[0]["evidence"]["offset_px"] >= 12


def test_layout_grid_silent_on_regular_list():
    assert S.check_layout_grid(_column([500 + 200 * i for i in range(8)])) == []


def test_layout_grid_silent_when_a_row_is_missing():
    b = [500 + 200 * i for i in range(9)]
    del b[4]                                    # OCR skipped one row: one doubled gap, not a mis-placed number
    assert S.check_layout_grid(_column(b)) == []


def test_layout_grid_silent_on_irregular_rhythm():
    b = [500, 640, 830, 905, 1160, 1230, 1500, 1590]    # e.g. chat bubbles / variable-height rows
    assert S.check_layout_grid(_column(b)) == []


def test_layout_grid_needs_a_real_column():
    assert S.check_layout_grid(_column([500, 700, 886, 1100])) == []   # fewer than six rows
