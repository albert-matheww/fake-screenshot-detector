"""Synthesizes a labeled, on-disk corpus of paired authentic/tampered
screenshot-style images across several common screenshot categories, for use
as an additional pooled training source in tools/train_model.py's
--synthetic flag.

Why this exists: no public dataset of labeled real/fake *screenshots* exists
(see README's "What's NOT implemented" — the bundled model is trained on
receipts/general-photos/found-forgeries instead, a documented domain gap).
tools/calibrate.py already procedurally generates two screenshot-like
categories, but only in-memory and only to hand-tune heuristic weights, not
as a trainable dataset. This tool extends that idea into a real, on-disk,
labeled corpus: more categories, more tamper types, and genuinely
OCR-legible text (via ImageDraw.text + a real font) so the document-text cue
has actual content to validate against instead of abstract line-scribbles.

Categories (chosen as the most common real-world "fake screenshot"
fraud/misinformation targets):
  chat          iMessage/WhatsApp-style message thread (sometimes a group
                thread with a multi-name header and per-message sender
                labels, picked at random)
  bank          bank app balance + transaction list
  payment       "payment sent/received" receipt (Venmo/CashApp/PayPal-style,
                genericized — this is the single most common
                screenshot-fraud pattern: fake proof of payment)
  social        Twitter/X-style post with engagement counts
  ecommerce     order-confirmation screenshot (Amazon-style)
  email         inbox list view (sender/subject/snippet rows) — a common
                phishing-screenshot and fake-notice target
  notification  lock-screen-style notification cards (app/title/body) — the
                "fake push notification" screenshot pattern (e.g. a faked
                "you received $500" alert)
  crypto        wallet balance + holdings list — the same proof-of-payment
                fraud pattern as `payment`, for crypto-specific claims

Every category also independently rolls a light/dark color palette
(`_palette`) each render, so the corpus isn't uniformly light-mode-only —
real screenshots split across both, and a cue that (for example) silently
assumed a white background would otherwise never get exercised against a
dark one.

Tamper types (label=1), applied to a copy of the same authentic render so
the pair differs ONLY by the tamper (isolates its effect, same rationale as
calibrate.py's make_tampered_from):
  0 patch-recompress   a textured region edited and recompressed at a
                       different quality than the rest of the image
  1 copy-move          a textured block duplicated elsewhere in the frame
  2 flat-overwrite     a solid low-texture box drawn over content with new
                       text (hardest case for compression-artifact cues —
                       see README's "Known limitations")
  3 exif-tool          an editing-tool `Software` EXIF tag stamped in,
                       pixel content otherwise unchanged
  4 watermark-inject   a known fake-document-generator watermark or
                       placeholder name/number rendered as real, legible
                       text — exercises forensic.check_document_text
                       specifically, using the exact strings that cue
                       checks for (imported from forensic.py, not
                       duplicated, so this stays in sync with it)
  5 patch+exif         combines 0 and 3 — the most realistic single case
                       (actually edited a number in an editor and exported)

Authentic images (label=0) vary JPEG quality/size and sometimes get a
second, harmless resave pass (simulating re-sharing through another app).
This is deliberately NOT a tamper type: no content changes, so the model
must still see it as label=0 — otherwise it would learn "any recompression
means fake," which is false and would hurt real-world precision.

Usage:
    python3 tools/synthesize_dataset.py --out /path/to/synthetic --count 150

Writes JPEGs under --out/<category>/ plus --out/manifest.csv
(path,label,category,tamper_type), which train_model.py's --synthetic flag
reads directly. Generation is deterministic for a given --seed, so the
corpus can be regenerated (or extended with more categories/tamper types
later) rather than committed to the repo.

Known scope limits, stated plainly rather than left implicit: every
category still shares one rendering engine (Pillow + one bundled font), so
this corpus cannot exercise genuine cross-renderer differences (e.g. real
font-rasterizer mismatches — see forensic.check_font_consistency's
docstring for where that already showed up as a validation gap) and every
layout is one hand-built template per category rather than the huge visual
variety real apps ship across versions/regions. It narrows the
"no screenshot dataset" gap; it does not close it.
"""
import argparse
import csv
import io
import os
import random
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse the exact strings forensic.check_document_text looks for, so the
# watermark-inject tamper is guaranteed to exercise that cue rather than a
# copy that could drift out of sync with it.
from forensic import _GENERATOR_WATERMARKS, _PLACEHOLDER_NAMES  # noqa: E402

TAMPER_NAMES: Dict[int, str] = {
    0: "patch-recompress", 1: "copy-move", 2: "flat-overwrite",
    3: "exif-tool", 4: "watermark-inject", 5: "patch+exif",
}
_EDITING_TOOLS = ["Adobe Photoshop 25.0", "GIMP 2.10", "Pixelmator Pro", "Affinity Photo 2"]

# Fictional brand/name pools — deliberately not real bank/payment-app names,
# since the forensic signal here is pixel/text-pattern based, not brand
# semantics, and synthetic training data has no need to resemble any real
# company.
_BANKS = ["Union Trust Bank", "Harbor Bank", "Meridian Bank", "Cascade Federal", "Northgate Bank"]
_WALLETS = ["CoinVault", "BlockWallet", "ChainKeeper", "LedgerLink", "CryptoNest"]
_MERCHANTS = ["Grocery Mart", "Coffee Corner", "Gas Station", "Online Store", "Rent Payment",
              "Pharmacy", "Streaming Co", "Hardware Shop", "Auto Insurance"]
_CHAT_LINES = ["Hey, are you free tonight?", "Sent the payment already", "Let me check and get back to you",
               "Thanks so much!", "See you at 7", "Can you send that file?", "Sounds good to me",
               "Running a few minutes late", "Call me when you can", "Got it, appreciate it",
               "Happy birthday!", "Where should we meet?"]
_PRODUCTS = ["Wireless Headphones", "Phone Case", "USB-C Cable", "Desk Lamp", "Water Bottle",
             "Notebook Set", "Bluetooth Speaker", "Yoga Mat", "Kitchen Scale"]
_SOCIAL_LINES = ["Just had the best coffee ever", "Can't believe this happened today",
                  "New blog post is live, check it out", "Beautiful morning for a walk",
                  "Finally finished this project", "Throwback to last summer",
                  "Excited to share some news soon", "Best trip of the year so far"]
_EMAIL_SUBJECTS = ["Your order has shipped", "Meeting moved to 3pm", "Invoice for last month",
                    "Password reset requested", "Weekly newsletter", "Re: Project update",
                    "Your statement is ready", "Welcome to the team", "Reminder: appointment tomorrow"]
_EMAIL_SNIPPETS = ["Hi, just following up on this...", "Thanks for reaching out, here's the...",
                    "Please review the attached...", "This is a reminder that...",
                    "We wanted to let you know...", "See the details below..."]
_NOTIF_APPS = ["Messages", "Mail", "Banking", "Wallet", "Calendar", "Reminders"]
_NOTIF_TITLES = ["New message", "Payment received", "Event starting soon", "Delivery update",
                 "New login detected", "Balance alert"]
_NOTIF_BODIES = ["You have a new message from a contact", "You received a payment", "Your event starts in 15 minutes",
                  "Your package is out for delivery", "A new device signed in to your account",
                  "Your balance dropped below your alert threshold"]
_COINS = [("BTC", 20000, 70000), ("ETH", 1500, 4000), ("SOL", 20, 200), ("USDC", 0.99, 1.01)]
_FIRST_NAMES = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Priya", "Wei"]
_LAST_NAMES = ["Carter", "Bennett", "Reyes", "Nguyen", "Patel", "Okafor", "Silva", "Kim", "Novak", "Haddad"]
_PHONE_SIZES = [(390, 844), (412, 915), (414, 896), (400, 760)]


# ---------------------------------------------------------------------------
# Shared render helpers
# ---------------------------------------------------------------------------

def _font(size: int) -> ImageFont.FreeTypeFont:
    # Pillow's own bundled scalable font (>=10.1) — no system-font
    # dependency, so this works identically on macOS dev machines and the
    # python:3.10-slim Docker image alike.
    return ImageFont.load_default(size=size)


def _name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _amount(rng: random.Random, lo=5, hi=2500) -> str:
    return f"${rng.uniform(lo, hi):,.2f}"


def _palette(dark: bool) -> Dict[str, Tuple[int, int, int]]:
    if dark:
        return {
            "bg": (18, 18, 20), "surface": (30, 30, 34),
            "text": (235, 235, 240), "subtext": (162, 162, 170), "border": (55, 55, 60),
            "bubble_in": (44, 44, 48), "bubble_out": (10, 100, 220),
        }
    return {
        "bg": (255, 255, 255), "surface": (246, 247, 248),
        "text": (20, 20, 20), "subtext": (140, 140, 140), "border": (228, 228, 232),
        "bubble_in": (228, 228, 232), "bubble_out": (0, 122, 255),
    }


def _status_bar(d: ImageDraw.ImageDraw, w: int, pal: Dict[str, Tuple[int, int, int]]) -> None:
    d.text((16, 10), "9:41", fill=pal["text"], font=_font(15))
    d.rectangle([w - 46, 12, w - 18, 24], outline=pal["text"], width=1)
    d.rectangle([w - 44, 14, w - 32, 22], fill=pal["text"])


# ---------------------------------------------------------------------------
# Category renderers — each returns a plausible, OCR-legible authentic image
# ---------------------------------------------------------------------------

def render_chat(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.3
    pal = _palette(dark)
    group = rng.random() < 0.25
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    d.rectangle([0, 40, w, 84], fill=pal["surface"])
    d.ellipse([16, 48, 52, 84], fill=(180, 190, 210) if not dark else (90, 100, 130))
    header = f"{_name(rng)}, {_name(rng)}" if group else _name(rng)
    d.text((62, 56), header[:36], fill=pal["text"], font=_font(17))

    participants = [_name(rng) for _ in range(3)]
    y = 100
    for i in range(rng.randint(6, 10)):
        text = rng.choice(_CHAT_LINES)
        sent = i % 2 == 1
        show_sender = group and not sent
        bw_ = min(250, 9 * len(text) + 24)
        bh_ = 52 if show_sender else 38
        x = (w - bw_ - 16) if sent else 16
        color = pal["bubble_out"] if sent else pal["bubble_in"]
        text_color = (255, 255, 255) if sent else pal["text"]
        d.rounded_rectangle([x, y, x + bw_, y + bh_], radius=16, fill=color)
        if show_sender:
            d.text((x + 12, y + 6), rng.choice(participants), fill=pal["subtext"], font=_font(10))
        d.text((x + 12, y + (24 if show_sender else 10)), text, fill=text_color, font=_font(13))
        y += bh_ + 14
        if y > h - 100:
            break
    return img


def render_bank(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.3
    pal = _palette(dark)
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    header_color = rng.choice([(0, 90, 60), (20, 60, 120), (90, 40, 110)])
    d.rectangle([0, 36, w, 130], fill=header_color)
    d.text((20, 48), rng.choice(_BANKS), fill=(255, 255, 255), font=_font(16))
    d.text((20, 78), "Available Balance", fill=(230, 230, 230), font=_font(12))
    d.text((20, 96), _amount(rng, 200, 18000), fill=(255, 255, 255), font=_font(24))

    y = 150
    for _ in range(rng.randint(5, 8)):
        d.rounded_rectangle([16, y, w - 16, y + 54], radius=10, fill=pal["surface"], outline=pal["border"])
        merchant = rng.choice(_MERCHANTS)
        d.text((28, y + 10), merchant, fill=pal["text"], font=_font(14))
        d.text((28, y + 30), f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/2025", fill=pal["subtext"], font=_font(11))
        sign = "-" if rng.random() < 0.85 else "+"
        d.text((w - 110, y + 18), f"{sign}{_amount(rng, 3, 400)}", fill=pal["text"], font=_font(14))
        y += 62
        if y > h - 70:
            break
    return img


def render_payment(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.3
    pal = _palette(dark)
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    cx, cy, r = w // 2, 160, 46
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 180, 100))
    d.line([cx - 18, cy, cx - 4, cy + 16, cx + 20, cy - 16], fill="white", width=6, joint="curve")
    d.text((cx, cy + 70), "Payment Sent", fill=pal["text"], font=_font(18), anchor="mm")
    d.text((cx, cy + 110), _amount(rng, 10, 3000), fill=pal["text"], font=_font(30), anchor="mm")
    d.text((cx, cy + 150), f"To {_name(rng)}", fill=pal["subtext"], font=_font(14), anchor="mm")
    d.line([40, cy + 190, w - 40, cy + 190], fill=pal["border"], width=1)
    d.text((40, cy + 210), f"Transaction ID  {rng.randint(10**9, 10**10 - 1)}", fill=pal["subtext"], font=_font(11))
    d.text((40, cy + 232), f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/2025  {rng.randint(1,12)}:{rng.randint(0,59):02d} PM",
           fill=pal["subtext"], font=_font(11))
    return img


def render_social(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.3
    pal = _palette(dark)
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    d.ellipse([16, 52, 56, 92], fill=(200, 170, 220) if not dark else (110, 90, 130))
    handle = _name(rng).split()[0].lower() + str(rng.randint(10, 999))
    d.text((64, 56), _name(rng), fill=pal["text"], font=_font(15))
    d.text((64, 76), f"@{handle}", fill=pal["subtext"], font=_font(12))

    y = 110
    for _ in range(rng.randint(1, 3)):
        d.text((16, y), rng.choice(_SOCIAL_LINES), fill=pal["text"], font=_font(15))
        y += 26

    y += 20
    # Plain ASCII labels rather than Unicode heart/repost glyphs: Pillow's
    # bundled default font (see _font) doesn't cover those code points and
    # renders them as missing-glyph boxes, not real OCR-able content.
    d.text((16, y), f"Likes {rng.randint(0, 9000)}", fill=pal["subtext"], font=_font(13))
    d.text((130, y), f"Replies {rng.randint(0, 800)}", fill=pal["subtext"], font=_font(13))
    d.text((250, y), f"Reposts {rng.randint(0, 1500)}", fill=pal["subtext"], font=_font(13))
    d.text((16, y + 30), f"{rng.randint(1,12)}:{rng.randint(0,59):02d} {rng.choice(['AM','PM'])}", fill=pal["subtext"], font=_font(11))
    return img


def render_ecommerce(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.3
    pal = _palette(dark)
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    d.rectangle([0, 40, w, 90], fill=(30, 30, 35) if not dark else (8, 8, 10))
    d.text((20, 56), "Order Confirmed", fill=(255, 255, 255), font=_font(18))
    d.text((20, 104), f"Order #{rng.randint(10**8, 10**9 - 1)}", fill=pal["subtext"], font=_font(12))

    y = 130
    total = 0.0
    for _ in range(rng.randint(2, 5)):
        price = rng.uniform(8, 180)
        total += price
        d.text((20, y), rng.choice(_PRODUCTS), fill=pal["text"], font=_font(14))
        d.text((w - 90, y), f"${price:,.2f}", fill=pal["text"], font=_font(14))
        y += 28
    y += 10
    d.line([20, y, w - 20, y], fill=pal["border"], width=1)
    y += 14
    d.text((20, y), "Total", fill=pal["text"], font=_font(15))
    d.text((w - 90, y), f"${total:,.2f}", fill=pal["text"], font=_font(15))
    y += 40
    d.text((20, y), f"Arriving by {rng.randint(1,12):02d}/{rng.randint(1,28):02d}/2025", fill=pal["subtext"], font=_font(12))
    return img


def render_email(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.3
    pal = _palette(dark)
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    d.rectangle([0, 40, w, 84], fill=pal["surface"])
    d.text((20, 54), "Inbox", fill=pal["text"], font=_font(20))

    y = 96
    for _ in range(rng.randint(5, 8)):
        unread = rng.random() < 0.4
        sender = _name(rng)
        d.ellipse([16, y, 44, y + 28], fill=(150, 170, 220) if not dark else (70, 90, 130))
        name_color = pal["text"] if unread else pal["subtext"]
        d.text((54, y), sender, fill=name_color, font=_font(14))
        d.text((w - 74, y + 2), f"{rng.randint(1,12)}:{rng.randint(0,59):02d} {rng.choice(['AM', 'PM'])}",
               fill=pal["subtext"], font=_font(10))
        d.text((54, y + 18), rng.choice(_EMAIL_SUBJECTS), fill=name_color, font=_font(13))
        d.text((54, y + 36), rng.choice(_EMAIL_SNIPPETS), fill=pal["subtext"], font=_font(11))
        y += 62
        d.line([16, y - 8, w - 16, y - 8], fill=pal["border"], width=1)
        if y > h - 70:
            break
    return img


def render_notification(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.5  # lock screens skew dark more often in real usage
    pal = _palette(dark)
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    d.text((w // 2, 130), f"{rng.randint(1,12)}:{rng.randint(0,59):02d}", fill=pal["text"], font=_font(56), anchor="mm")
    d.text((w // 2, 178),
           f"{rng.choice(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])}, {rng.choice(['Jan', 'Feb', 'Mar', 'Apr'])} {rng.randint(1, 28)}",
           fill=pal["subtext"], font=_font(14), anchor="mm")

    y = 220
    for _ in range(rng.randint(2, 4)):
        d.rounded_rectangle([16, y, w - 16, y + 70], radius=16, fill=pal["surface"])
        d.ellipse([28, y + 10, 50, y + 32], fill=(120, 140, 200) if not dark else (80, 100, 150))
        d.text((60, y + 12), rng.choice(_NOTIF_APPS), fill=pal["subtext"], font=_font(11))
        d.text((w - 66, y + 12), "now", fill=pal["subtext"], font=_font(10))
        d.text((28, y + 36), rng.choice(_NOTIF_TITLES), fill=pal["text"], font=_font(13))
        d.text((28, y + 52), rng.choice(_NOTIF_BODIES), fill=pal["subtext"], font=_font(11))
        y += 82
    return img


def render_crypto(rng: random.Random) -> Image.Image:
    w, h = rng.choice(_PHONE_SIZES)
    dark = rng.random() < 0.5
    pal = _palette(dark)
    img = Image.new("RGB", (w, h), pal["bg"])
    d = ImageDraw.Draw(img)
    _status_bar(d, w, pal)
    d.rectangle([0, 36, w, 130], fill=(30, 20, 60) if not dark else (14, 10, 28))
    d.text((20, 48), rng.choice(_WALLETS), fill=(255, 255, 255), font=_font(16))
    d.text((20, 78), "Total Balance", fill=(210, 200, 230), font=_font(12))
    d.text((20, 96), _amount(rng, 500, 85000), fill=(255, 255, 255), font=_font(24))

    y = 150
    for symbol, lo, hi in rng.sample(_COINS, k=rng.randint(2, 4)):
        d.rounded_rectangle([16, y, w - 16, y + 54], radius=10, fill=pal["surface"], outline=pal["border"])
        qty = rng.uniform(0.01, 5.0)
        d.text((28, y + 10), symbol, fill=pal["text"], font=_font(14))
        d.text((28, y + 30), f"{qty:.4f} {symbol}", fill=pal["subtext"], font=_font(11))
        d.text((w - 120, y + 18), f"${qty * rng.uniform(lo, hi):,.2f}", fill=pal["text"], font=_font(14))
        y += 62
        if y > h - 70:
            break
    return img


RENDERERS = {
    "chat": render_chat,
    "bank": render_bank,
    "payment": render_payment,
    "social": render_social,
    "ecommerce": render_ecommerce,
    "email": render_email,
    "notification": render_notification,
    "crypto": render_crypto,
}


# ---------------------------------------------------------------------------
# Tamper application (generic — operates on pixels, not category-aware)
# ---------------------------------------------------------------------------

def apply_tamper(img: Image.Image, tamper_type: int, rng: random.Random) -> Image.Image:
    w, h = img.size
    tampered = img.copy()

    if tamper_type in (0, 5):
        pw, ph = min(140, w // 3), min(50, h // 10)
        px = rng.randint(0, max(1, w - pw))
        py = rng.randint(h // 4, max(h // 4 + 1, h - ph))
        patch = tampered.crop((px, py, px + pw, py + ph)).convert("RGB")
        arr = np.array(patch).astype(np.int16)
        arr[:, :, 0] = np.clip(arr[:, :, 0] + 30, 0, 255)
        patch = Image.fromarray(arr.astype("uint8"))
        pbuf = io.BytesIO()
        patch.save(pbuf, format="JPEG", quality=rng.choice([40, 50, 60]))
        pbuf.seek(0)
        tampered.paste(Image.open(pbuf).convert("RGB"), (px, py))

    elif tamper_type == 1:
        bw_, bh_ = min(110, w // 4), min(50, h // 10)
        src = (rng.randint(0, max(1, w - bw_)), rng.randint(0, max(1, h - bh_)))
        clone = tampered.crop((src[0], src[1], src[0] + bw_, src[1] + bh_))
        dst = (rng.randint(0, max(1, w - bw_)), rng.randint(0, max(1, h - bh_)))
        tampered.paste(clone, dst)

    elif tamper_type == 2:
        d = ImageDraw.Draw(tampered)
        bw_, bh_ = min(170, w // 3), min(44, h // 12)
        bx = rng.randint(0, max(1, w - bw_))
        by = rng.randint(h // 4, max(h // 4 + 1, h - bh_))
        d.rectangle([bx, by, bx + bw_, by + bh_], fill=(250, 250, 250))
        d.text((bx + 8, by + 10), "$9,999.00", fill=(20, 20, 20), font=_font(16))

    elif tamper_type == 4:
        d = ImageDraw.Draw(tampered)
        marker = rng.choice(_GENERATOR_WATERMARKS + _PLACEHOLDER_NAMES + ["123456789"])
        d.text((12, h - 26), marker, fill=(150, 150, 150), font=_font(13))

    # tamper_type == 3 (exif-tool): pixel content unchanged, tag stamped at save time.
    return tampered


def save_authentic(img: Image.Image, rng: random.Random) -> bytes:
    quality = rng.choice([85, 88, 90, 92, 95])
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    data = buf.getvalue()
    if rng.random() < 0.3:
        # Simulate the image being re-shared/re-saved through another app —
        # still label=0: no content changed, only recompressed again. The
        # model must not learn "any second recompression means fake".
        again = Image.open(io.BytesIO(data)).convert("RGB")
        buf2 = io.BytesIO()
        again.save(buf2, format="JPEG", quality=rng.choice([70, 75, 80]))
        data = buf2.getvalue()
    return data


def save_tampered(img: Image.Image, tamper_type: int, rng: random.Random) -> bytes:
    out = io.BytesIO()
    quality = rng.choice([75, 80, 85, 88, 90])
    if tamper_type in (3, 5):
        from PIL.ExifTags import Base
        exif = Image.Exif()
        exif[Base.Software.value] = rng.choice(_EDITING_TOOLS)
        img.save(out, format="JPEG", quality=quality, exif=exif)
    else:
        img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Corpus generation
# ---------------------------------------------------------------------------

def generate(out_dir: str, count_per_category: int, seed: int) -> str:
    manifest_rows: List[dict] = []
    for category, renderer in RENDERERS.items():
        cat_dir = os.path.join(out_dir, category)
        os.makedirs(cat_dir, exist_ok=True)
        for i in range(count_per_category):
            rng = random.Random(f"{seed}_{category}_{i}")
            base_img = renderer(rng)

            auth_bytes = save_authentic(base_img, rng)
            auth_path = os.path.join(cat_dir, f"{i:04d}_authentic.jpg")
            with open(auth_path, "wb") as f:
                f.write(auth_bytes)
            manifest_rows.append({"path": auth_path, "label": 0, "category": category, "tamper_type": ""})

            tamper_type = i % len(TAMPER_NAMES)
            tampered_img = apply_tamper(base_img, tamper_type, rng)
            tampered_bytes = save_tampered(tampered_img, tamper_type, rng)
            tamp_path = os.path.join(cat_dir, f"{i:04d}_tampered_{TAMPER_NAMES[tamper_type]}.jpg")
            with open(tamp_path, "wb") as f:
                f.write(tampered_bytes)
            manifest_rows.append({
                "path": tamp_path, "label": 1, "category": category,
                "tamper_type": TAMPER_NAMES[tamper_type],
            })

    manifest_path = os.path.join(out_dir, "manifest.csv")
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "label", "category", "tamper_type"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="Output directory for generated images + manifest.csv")
    parser.add_argument("--count", type=int, default=150,
                         help="Authentic images generated per category (default 150). Each also gets one "
                              "paired tampered variant, so total images = count * categories * 2.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    manifest_path = generate(args.out, args.count, args.seed)
    total = args.count * len(RENDERERS) * 2
    print(f"Generated {total} images across {len(RENDERERS)} categories "
          f"({args.count} authentic + {args.count} tampered each) -> {args.out}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
