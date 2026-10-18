# Screenshots needed to finish validating the detector

All counts are measured against what the project has today: **23 genuine real screenshots** (payment receipts 8,
bank statements 3, orders/invoices 3, web pages 3, social posts 2, SMS/e-mail/notifications 3, chats 1) and **9 edited
screenshots** (with their originals). Nothing below needs a model change: each item switches a check on or lets it be
measured. Everything must be a REAL screenshot taken on a real device or app, never a generated one, and the genuine
ones must be untouched. Keep them private; they are only scored on your machine.

## A. Genuine screenshots (switch the checks on)

A check may influence a verdict only after it has been measured on enough genuine real screenshots
(`backend/tools/calibrate_gates.py`). Today only file metadata and general content logic are calibrated.

| What | Why | Have | Need |
|---|---|---|---|
| Any mix of types, at least 8 of each type, labelled by type | Validate the type router (`tools/eval_router.py` needs 60 labelled, accuracy >= 0.85) | 23 | **37 more** (bank 5, web 5, orders 5, chats 7, social 6, SMS/e-mail/notification 5, plus a few of any type). Include screenshots from apps and layouts not yet seen. |
| Bank statements or transaction lists with an amount and a running balance on each row (at least 5 rows) | Calibrate the running-balance check | 0 | **20** |
| Screens with a column of at least 8 numbers, evenly spaced (statements, lists, order histories) | Calibrate the number-column check (also helps the router) | 2 | **18** |
| Payment receipts with a UPI reference (GPay, PhonePe, Paytm, bank apps) | Calibrate the payment checks | 8 | **12** |
| Orders, invoices, refunds with subtotal/tax/total | Calibrate the order arithmetic check | 2 | **18** |
| Chat conversations with at least 5 visible message times | Calibrate the chat timestamp check | 0 | **20** |
| SMS, e-mail or notification screens showing a one-time code | Calibrate the OTP check | 0 | **20** |

Spread them over: PNG originals, WhatsApp/Telegram-shared JPEGs, and at least two phones or operating systems.

## B. Real edits (measure whether the checks catch anything)

The first real-edit result (9 edits) was too small and every edit was made by one person. To measure the checks and the
rendering model fairly:

- **100 edited screenshots, each paired with its untouched original.**
- Made by **at least 3 different people**, with **at least 5 different tools** (Canva, Photoshop or Photopea, a phone
  editor, browser Inspect Element, an AI image editor).
- At least **12 per type**, covering: changed digit, changed whole amount, changed name or date or status, added or
  removed row, pasted banner or logo, and a few edits made in Inspect Element.
- Each edit saved three ways: as exported, as a WhatsApp-shared copy, and as a screenshot of the edited screen.
- The people who capture and edit are different, and nobody runs the detector until every file exists (protocol in
  `docs/REAL_EDIT_TEST_PLAN.md`).

## C. For compare mode

Nothing more is needed: it works whenever a genuine copy exists. Useful extra test material: five of your genuine
screenshots each re-captured on a second device (to see how it behaves across devices).

## How to apply them

```bash
cd backend
python tools/eval_router.py --real-dir <folder> --real-labels tools/real_labels.json --write-gate
python tools/calibrate_gates.py --real-dir <folder> --real-labels tools/real_labels.json --write
```

Put the new screenshots in one folder and add each file name and its type (payment_receipt, bank_statement, order_invoice, chat, social_post, message_alert or web_page) to `tools/real_labels.json` first.
