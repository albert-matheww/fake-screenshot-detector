# Real-edit validation set: what to create

Every accuracy number in this project comes from *simulated* edits. This set replaces that with edits made by a
person, with real tools. Aim for **at least 20 genuine + 20 edited**; 30 + 30 is better. Everything stays on your machine.

## Ground rules (these keep the test honest)

1. **Make all the edits first, blind.** Don't run the detector between edits and don't adjust an edit because it was
   caught or missed. Evidence from this set is only valid if the detector never influenced it.
2. **Do not reuse the eight images already tested.** They were used to diagnose and improve the detector, so they are
   development data now. Everything below must be new.
3. **Keep the untouched original of every edited screenshot** (in a separate folder; it is not scored). Pairs let us check
   *which* word was flagged.
4. **Don't blur, crop out or cover other people's details to "protect" them** - that is itself an edit and would
   contaminate the genuine set. Keep the set local instead.
5. If you can, have **a friend make some of the edits** who hasn't seen how the detector works. The more independent the
   editor, the more the result is worth.

## Folder layout

```
~/eval/authentic/            genuine screenshots (never touched after capture)
~/eval/edited/               the edited ones (what gets scored)
~/eval/originals_of_edited/  the untouched originals of the edited ones (NOT scored, for reference)
~/eval/ground_truth.csv      one line per file (columns below)
```
Run: `python tools/evaluate_manual.py --authentic-dir ~/eval/authentic --edited-dir ~/eval/edited`

## 1. Genuine screenshots (target: 20-30)

Cover the variety the detector will meet. Tick what you have:

| # | Type | Notes |
|---|---|---|
| ☐ ☐ ☐ | **Payment-app transaction list** (like the ones already tested) | 3+; different scroll positions; include one with a "Failed" row and credits in green |
| ☐ ☐ | **Payment success / receipt screen** | amount, payee, reference ID, date |
| ☐ ☐ | **Bank app balance + transactions** | different bank apps if you can |
| ☐ | **Bank statement page** (PDF/web, screenshotted) | table with debit / credit / balance columns |
| ☐ ☐ | **Chat thread** (WhatsApp / iMessage / Telegram) | one light, one dark |
| ☐ | **Group chat** | names above messages |
| ☐ | **Social post** | name, handle, like/comment counts |
| ☐ ☐ | **E-commerce order / invoice** | items, subtotal, tax, total |
| ☐ | **E-mail** (inbox list and a message) | |
| ☐ | **Notification / lock screen** | |
| ☐ | **SMS with an OTP** | |
| ☐ ☐ | **Desktop / web dashboard** | a laptop screenshot, not a phone |

Vary on purpose: **iPhone and Android** (or whichever you have), **light and dark** mode, **different zoom levels**, and
**how the file travelled**:

| ☐ | Straight from the device (PNG) |
|---|---|
| ☐ | Sent through WhatsApp / Telegram and downloaded back (JPEG, re-compressed) |
| ☐ | Cropped (e.g. status bar removed) |
| ☐ | Re-screenshotted (a screenshot of a screenshot) |

Include a few **messy-but-genuine** ones: mixed bold and regular text on one line, emoji, avatars, very long lists.
These are what cause false alarms.

## 2. Edited screenshots (target: 20-30, each with its original)

Make a grid, not 20 copies of the same edit. Vary **each** of these:

**What you change**

| ☐ | one digit of an amount (₹75 → ₹79) |
|---|---|
| ☐ | a whole amount (₹500 → ₹5,000, adding or removing a "+") |
| ☐ | a name |
| ☐ | a date or time |
| ☐ | a status (Failed → Success / Paid) |
| ☐ | a transaction / reference ID |
| ☐ | a balance or total |
| ☐ | a chat message |
| ☐ | a count (likes, views, followers) |
| ☐ | text **added** where there was none |
| ☐ | text **removed** (covered with background) |
| ☐ | **two** edits on the same screen |

**Tool used** (use at least 5 of these; they leave different traces)

| ☐ | Preview / Markup (Mac) | ☐ | Photoshop / Pixelmator / Affinity |
|---|---|---|---|
| ☐ | Photopea (browser) | ☐ | Canva |
| ☐ | Figma | ☐ | Phone editor (Photos markup, Snapseed, Picsart) |
| ☐ | Paint / Paint.NET / GIMP | ☐ | Any "fake screenshot / fake receipt" website or app |

**How careful the edit is** (do all three levels)

| Level | What it means |
|---|---|
| **Lazy** | Default font, roughly the right size, not aligned |
| **Careful** | Matching font, size and colour; aligned to the row; background patched |
| **Expert** | Copy real digits from elsewhere on the *same* screenshot so the glyphs are identical; match spacing exactly |

**How it was shared afterwards**

| ☐ | exported as lossless PNG | ☐ | exported as JPEG (quality 80-95) |
|---|---|---|---|
| ☐ | sent through WhatsApp/Telegram and downloaded | ☐ | re-screenshotted on the phone |
| ☐ | resized / cropped | | |

**Add 3-5 "can't possibly work" edits on purpose**: change the text with the browser's *Inspect Element* (or a fake-receipt
generator that renders natively) and screenshot the result. The detector is *expected* to miss these. Including them
shows reviewers you know where the limit is, and keeps the measured detection rate honest.

## 3. Ground-truth file

`~/eval/ground_truth.csv`, one line per file:

```
file,label,app,os,theme,edit_tool,what_changed,effort,sharing,original_file,edited_word_or_row
A_01_gpay_list.png,authentic,gpay,ios,dark,,,,png,,
E_01_gpay_list.png,edited,gpay,ios,dark,photopea,amount_one_digit,careful,jpeg90,orig_E_01.png,"row 4: 75 -> 79"
```
`edited_word_or_row` is what lets us check that the detector marked the *right* place, not just that it said "suspicious".

## 4. Minimum set if you only have ~90 minutes

| What | How many |
|---|---|
| Genuine payment-app screens (lists + receipts) | 10 |
| Genuine other apps (bank, chat, order, desktop) | 10 |
| Edited payment-app screens (digit / amount / name / status; lazy + careful + expert) | 12 |
| Edited other apps (chat, order total, date) | 6 |
| "Inspect Element" edits (expected misses) | 3 |

When you have them, tell me where the folders are and I'll run the scoring, break the results down by tool, effort and
sharing, and add the numbers to the README and the deck (including the misses).
