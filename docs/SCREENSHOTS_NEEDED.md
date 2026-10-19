# Screenshots: what is still useful (everything here is optional)

The system no longer depends on a dataset to work. Its checks are rules, compare mode and reconcile mode need no training,
and no verdict is learned. Real screenshots are useful for two things only: *measuring* how often the rule-based checks
raise a false alarm, and trying reconcile mode on real pairs.

Current evidence: 23 genuine and 9 edited real screenshots (private, not in the repository), 3,932 tampered screenshots from
STFD (academic use only, not redistributed) and 300 genuine Rico app screens (CC-BY-4.0). See `README.md`.

## Worth collecting if you have the time

| What | Why | How many |
|---|---|---|
| Genuine bank-app screenshots with a running balance (at least 5 rows each) | measure the running-balance rule's false alarms; lets it count toward the verdict | 22 |
| Genuine UPI payment receipts (GPay, PhonePe, Paytm, bank apps) | same for the payment rules (have 8) | 14 more |
| Genuine orders, invoices or refunds with subtotal and total | same for the order rules (have 3) | 19 more |
| Pairs for reconcile mode: a payment screenshot and the matching bank SMS or statement line | try the second-source check on real pairs | 10 pairs |
| A few real edits with their originals, made by someone other than you | extra compare-mode and reconcile tests | 10 pairs |

22 genuine screenshots with no false alarm is the least that gives a 95% upper bound under 15% (20 gives 16%).

## How to use them

```bash
cd backend
python tools/calibrate_gates.py --real-dir <folder of genuine screenshots> --real-labels tools/real_labels.json --write
python tools/eval_reconcile.py <folder>        # mutation test of reconcile mode
```
Add each file name and its type to `tools/real_labels.json` first.
