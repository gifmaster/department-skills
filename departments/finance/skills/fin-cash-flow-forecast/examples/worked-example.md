# Worked example: fin-cash-flow-forecast

## User request

> Can we get through to February? Bank balance Monday 23 November is 850k, overdraft 500k undrawn, and the bank wants a 250k buffer. Receivables, payables and our fixed payments are in the three files.

## Command run (from the skill folder)

```
python3 scripts/cash13.py assets/receivables.csv --payables assets/payables.csv --recurring assets/recurring.csv --opening 850000 --start 2026-11-23 --min-buffer 250000 --facility 500000
```

## Output

# 13-week cash flow forecast, 2026-11-23 to 2027-02-21

Opening balance 850,000. Receipts 3,034,600, payments -3,229,102, closing week 13 655,498.
**Lowest banking-day balance: -439,252 on 2026-12-30.** Lowest week-end balance: -439,252 (week 6, w/c 2026-12-28). Minimum buffer 250,000.

## 1. Weekly forecast table

| Wk | Dates | Opening | AR receipts | Other in | Suppliers | Recurring out | A-tax + AM | Net | Closing | Low in week | Flag |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 23 Nov to 29 Nov | 850,000 | 55,550 | 18,000 | -12,480 | 0 | 0 | 61,070 | 911,070 | 898,750 |  |
| 2 | 30 Nov to 06 Dec | 911,070 | 0 | 18,000 | -164,210 | -785,000 | -190,000 | -1,121,210 | -210,140 | -210,140 | below buffer, overdraft used |
| 3 | 07 Dec to 13 Dec | -210,140 | 94,500 | 18,000 | -21,310 | 0 | 0 | 91,190 | -118,950 | -210,140 | below buffer, overdraft used |
| 4 | 14 Dec to 20 Dec | -118,950 | 186,250 | 18,000 | -247,552 | 0 | 0 | -43,302 | -162,252 | -162,252 | below buffer, overdraft used |
| 5 | 21 Dec to 27 Dec | -162,252 | 0 | 0 | 0 | 0 | 0 | 0 | -162,252 | -162,252 | below buffer, overdraft used |
| 6 | 28 Dec to 03 Jan | -162,252 | 210,000 | 183,000 | 0 | -480,000 | -190,000 | -277,000 | -439,252 | -439,252 | below buffer, overdraft used |
| 7 | 04 Jan to 10 Jan | -439,252 | 133,400 | 366,000 | -96,400 | -125,000 | 0 | 278,000 | -161,252 | -381,252 | below buffer, overdraft used |
| 8 | 11 Jan to 17 Jan | -161,252 | 412,000 | 183,000 | -19,850 | 0 | 0 | 575,150 | 413,898 | -181,102 | below buffer intra-week, overdraft used |
| 9 | 18 Jan to 24 Jan | 413,898 | 165,000 | 183,000 | 0 | 0 | 0 | 348,000 | 761,898 | 413,898 |  |
| 10 | 25 Jan to 31 Jan | 761,898 | 58,900 | 183,000 | 0 | -480,000 | -190,000 | -428,100 | 333,798 | 333,798 |  |
| 11 | 01 Feb to 07 Feb | 333,798 | 0 | 183,000 | -187,300 | -40,000 | 0 | -44,300 | 289,498 | 289,498 |  |
| 12 | 08 Feb to 14 Feb | 289,498 | 0 | 183,000 | 0 | 0 | 0 | 183,000 | 472,498 | 289,498 |  |
| 13 | 15 Feb to 21 Feb | 472,498 | 0 | 183,000 | 0 | 0 | 0 | 183,000 | 655,498 | 472,498 |  |

Formula: closing = opening + receipts + other in + (negative) payments. 'Low in week' is the lowest end-of-day balance on a banking day.

## 2. Lowest cash point and buffer

- 30 banking day(s) below the 250,000 buffer, first on 2026-11-30, worst -439,252 on 2026-12-30.
- Facility 500,000: headroom at the lowest point 60,748.

## 3. Dated recurring payments

| Date | Item | Amount |
|---|---|---|
| 2026-11-27 | Counter sales (MobilePay) | 18,000 |
| 2026-11-30 | A-skat and AM-bidrag (salary month 2026-11) | -190,000 |
| 2026-11-30 | Pension | -60,000 |
| 2026-11-30 | Salaries (net) | -420,000 |
| 2026-12-01 | Loan instalment | -40,000 |
| 2026-12-01 | VAT (quarterly) | -265,000 |
| 2026-12-04 | Counter sales (MobilePay) | 18,000 |
| 2026-12-11 | Counter sales (MobilePay) | 18,000 |
| 2026-12-18 | Counter sales (MobilePay) | 18,000 |
| 2026-12-28 | Counter sales (MobilePay) | 18,000 |
| 2026-12-28 | Receipts from new invoicing (estimate) | 165,000 |
| 2026-12-30 | A-skat and AM-bidrag (salary month 2026-12) | -190,000 |
| 2026-12-30 | Pension | -60,000 |
| 2026-12-30 | Salaries (net) | -420,000 |
| 2027-01-04 | Counter sales (MobilePay) | 18,000 |
| 2027-01-04 | Loan instalment | -40,000 |
| 2027-01-04 | Receipts from new invoicing (estimate) | 165,000 |
| 2027-01-04 | Rent (quarterly in advance) | -85,000 |
| 2027-01-08 | Counter sales (MobilePay) | 18,000 |
| 2027-01-08 | Receipts from new invoicing (estimate) | 165,000 |
| 2027-01-15 | Counter sales (MobilePay) | 18,000 |
| 2027-01-15 | Receipts from new invoicing (estimate) | 165,000 |
| 2027-01-22 | Counter sales (MobilePay) | 18,000 |
| 2027-01-22 | Receipts from new invoicing (estimate) | 165,000 |
| 2027-01-29 | A-skat and AM-bidrag (salary month 2027-01) | -190,000 |
| 2027-01-29 | Counter sales (MobilePay) | 18,000 |
| 2027-01-29 | Pension | -60,000 |
| 2027-01-29 | Receipts from new invoicing (estimate) | 165,000 |
| 2027-01-29 | Salaries (net) | -420,000 |
| 2027-02-01 | Loan instalment | -40,000 |
| 2027-02-05 | Counter sales (MobilePay) | 18,000 |
| 2027-02-05 | Receipts from new invoicing (estimate) | 165,000 |
| 2027-02-12 | Counter sales (MobilePay) | 18,000 |
| 2027-02-12 | Receipts from new invoicing (estimate) | 165,000 |
| 2027-02-19 | Counter sales (MobilePay) | 18,000 |
| 2027-02-19 | Receipts from new invoicing (estimate) | 165,000 |

## 4. Data quality and assumptions

- receivables line 7 (Café Kronen ApS): avg_days_late blank, default 0 days used
- receivables line 9 (Vestergaard Ejendomme): missing or invalid amount or due_date, row skipped
- receivables of 48,750 are already overdue on expected date; assumed received on 2026-11-23 (optimistic, check)
- A-tax + AM timing: large employer (last banking day of the salary month). Verify current values and your classification in TastSelv Erhverv; other deadlines can differ.
- Non-banking days follow the Danish calendar (public holidays plus 5 June, 24 and 31 December, Friday after Ascension). Verify.
- Receipts use due date + average days late; they are estimates, not actuals.

## Interpretation

- Yes, but only by using the overdraft: the lowest point is -439,252 on Wednesday 30 December, when December salaries, pension and A-tax leave on the last banking day. Headroom on the 500k facility is then only 60,748.
- Cash is below the 250k buffer on 30 banking days, from the November pay day (30 November) until Nordvind's 412,000 arrives around 14 January (they pay 60 days late).
- Two data points to fix: Vestergaard Ejendomme (72,000) has no due date and is left out, and Ribe Tømrer's 48,750 is already overdue and assumed paid in week 1, which is optimistic.
- A-tax is timed for a large employer; if you are a small employer (10th of the following month) re-run with --atax-timing small, which moves 190,000 out of each pay week.
- Levers: collect Nordvind before December, move the 18 December Stål & Profil payment, and agree the buffer breach with the bank in advance.
