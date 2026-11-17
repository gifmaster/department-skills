# Worked example: fin-bank-reconciliation

## User request

> Our October bank rec for account 5820 (Danske Bank drift) does not balance. Bank closing balance is 150.371,58 and the ledger says 350.073,00. Bank export and e-conomic export attached. What is going on?

## Command run (from the skill folder)

```
python3 scripts/reconcile.py assets/bank_statement.csv assets/ledger.csv --bank-balance 150371.58 --ledger-balance 350073.00
```

## Output

# Bank reconciliation at 2026-10-31

Lines: 15 bank, 13 ledger. Unmatched: 7 bank, 4 ledger.
**Unexplained difference: -6,250.00** (NOT explained: check balances, period coverage and opening open items)

## 1. Reconciliation statement

| Item | DKK |
|---|---|
| Balance per bank statement | 150,371.58 |
| Add: receipts in ledger not yet in bank | 123,300.00 |
| Less: payments in ledger not yet in bank | -8,952.00 |
| Less: receipts in bank not in ledger | -28,615.40 |
| Add: payments in bank not in ledger | 120,218.82 |
| Computed balance per ledger | 356,323.00 |
| Balance per ledger (given) | 350,073.00 |
| Unexplained difference | -6,250.00 |

## 2. Matched summary

| Match type | Matches | Bank lines | Ledger lines | Bank amount |
|---|---|---|---|---|
| 1:1 | 6 | 6 | 6 | -178,660.00 |
| 1:many | 1 | 1 | 2 | 15,600.00 |
| fuzzy | 1 | 1 | 1 | -7,315.00 |

One-to-many and fuzzy matches (check these):

| Match | Type | Side | Date | Text | Amount |
|---|---|---|---|---|---|
| M7 | 1:2 | bank | 2026-10-17 | Indbet. Vestergaard fak 10244 10245 | 15,600.00 |
| M7 | 1:2 | ledger | 2026-10-16 | Vestergaard 10244 | 9,600.00 |
| M7 | 1:2 | ledger | 2026-10-16 | Vestergaard 10245 | 6,000.00 |
| M8 | fuzzy | bank | 2026-10-02 | Tryg forsikring police 4471 | -7,315.00 |
| M8 | fuzzy | ledger | 2026-10-20 | Tryg forsikring 4471 | -7,315.00 |

## 3. Unmatched items by category

| ID | Side | Date | Text | Amount | Category | Age (days) | Flags |
|---|---|---|---|---|---|---|---|
| B12 | bank | 2026-10-24 | Cloudnest BV EUR 1.200,00 | -8,973.60 | Amount difference (FX, fee or rounding) | 7 | possible amount difference vs L11 (-21.60) |
| L11 | ledger | 2026-10-24 | Cloudnest NL-2026-1188 EUR 1200 @7.46 | -8,952.00 | Amount difference (FX, fee or rounding) | 7 | possible amount difference vs B12 (-21.60) |
| B5 | bank | 2026-10-09 | Gebyr udl. overførsel | -125.00 | Bank fees | 22 |  |
| B6 | bank | 2026-10-13 | Overf. Skattekonto | -96,800.00 | Error: possible sign error | 18 | possible sign error vs L5 |
| L5 | ledger | 2026-10-13 | Skattekonto | 96,800.00 | Error: possible sign error | 18 | possible sign error vs B6 |
| B11 | bank | 2026-10-22 | Renter | -1,840.22 | Interest | 9 |  |
| B13 | bank | 2026-10-28 | Indbet. REF 10250 | 18,750.00 | Missing in ledger | 3 |  |
| B15 | bank | 2026-10-31 | Nets kortindløsning | 9,865.40 | Missing in ledger | 0 |  |
| L1 | ledger | 2026-07-12 | Uidentificeret indbetaling | 2,500.00 | Old item (over 60 days) | 111 | old item, 111 days |
| B8 | bank | 2026-10-15 | Kontorgrej A/S 55871 | -12,480.00 | Possible duplicate | 16 | possible duplicate of B7 |
| L13 | ledger | 2026-10-30 | Ribe Tømrer 10248 | 24,000.00 | Timing (in ledger, not yet in bank) | 1 |  |

## 4. Flags

- Possible sign errors: B6 -96,800.00 vs L5 96,800.00. A sign error in the ledger moves the difference by twice the amount.
- Possible amount differences: B12 vs L11 difference -21.60
- Possible duplicates: B7 and B8 (bank, -12,480.00)
- Items older than 60 days: L1 Uidentificeret indbetaling 2,500.00 (111 days)

## Data quality and assumptions

- ledger line 15: missing amount, row skipped
- Some rows were skipped; their amounts are not in the matching and may explain the unexplained difference.
- Sign convention assumed: positive = money in, negative = money out, in both files.
- Matching window 5 days, one-to-many up to 3 lines, fuzzy similarity >= 0.50 within 45 days.
- Proposed correcting entries are NOT produced by this script; draft them for review from the categories above.

## Interpretation

- The remaining unexplained difference of -6,250.00 is exactly the ledger line "Grafisk Hus 8812" that has no amount in the export, so the script skipped it. Re-export or fix that line and the difference is fully explained.
- The Skattekonto transfer is booked in the ledger as +96,800 but left the bank as -96,800: a sign error that moves the ledger by 193,600 when corrected.
- Kontorgrej 55871 (-12,480) was debited twice by the bank; ask for a refund or check whether two payment orders were sent.
- Not yet booked in the ledger: REF 10250 (18,750), Nets card settlement (9,865.40), bank fee (125), interest (1,840.22) and an FX difference of 21.60 on Cloudnest. Draft entries for review; confirm REF 10250 in the receivables ledger first.
- The July "uidentificeret indbetaling" (2,500) is 111 days old and was never in the bank: investigate and reverse rather than carry it forward. Ribe Tømrer (24,000) is a normal timing item.
