# Screenshots: what is still useful (everything here is optional)

The system no longer depends on a dataset to work. Its checks are rules, compare mode and reconcile mode need no training,
and no verdict is learned. Real screenshots are useful for two things only: *measuring* how often the rule-based checks
raise a false alarm, and trying reconcile mode on real pairs.

Current evidence: 47 genuine real items (23 screenshots, 11 chats, 4 payment lists and 9 bank-statement pages) and 9 edited real screenshots (private, not in the repository), 13 bank SMS texts, 3,932 tampered screenshots from
STFD (academic use only, not redistributed) and 300 genuine Rico app screens (CC-BY-4.0). See `README.md`.

## Worth collecting if you have the time

Counts are screenshots on which the rule actually applied (not files collected), measured on the 47 genuine items held now:

| What | Applied so far | Needed for the gate | Notes |
|---|---|---|---|
| Bank statements or lists with an amount (or debit and credit columns) and a running balance on every row, at least 5 rows | 7 | 15 more | the 9 statement pages gave 7 applicable; the 3 bank screenshots have no running balance |
| Chats with at least 5 readable message times (WhatsApp prints 8:43 PM; Instagram shows none, so it does not help) | 5 | 17 more | 11 chats collected; OCR read at least 5 times in 5 of them |
| Payment receipts with a UPI reference or a status word | 9 | 13 more | transaction lists such as Google Pay history rarely show a reference |
| Orders, invoices or refunds with subtotal and total | 2 | 20 more | |
| SMS, e-mail or notification screens with a one-time code | 0 | 22 | |
| Screens with an evenly spaced column of at least 8 numbers | 14 | 8 more | the layout rule |
| Pairs for reconcile mode: a payment screenshot and the matching bank SMS or statement line | 0 | 10 pairs | try the second-source check on real pairs |
| Real edits with their originals, made by someone other than you | 9 (your own) | 10 pairs | extra compare-mode and reconcile tests |

22 genuine screenshots with no false alarm is the least that gives a 95% upper bound under 15% (20 gives 16%).

## How to use them

```bash
cd backend
python tools/calibrate_gates.py --real-dir <folder of genuine screenshots> --real-labels tools/real_labels.json --write
python tools/eval_reconcile.py <folder>        # mutation test of reconcile mode
```
Add each file name and its type to `tools/real_labels.json` first.
