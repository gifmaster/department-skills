# Worked example: fin-credit-collection

## User request

> Write the collection plan for everything overdue today (16 Nov 2026). We are Vestjysk Ventilation ApS. Please add fees and interest where we are allowed to.

## Command run (from the skill folder)

```
python3 scripts/dunning.py assets/overdue_invoices.csv --reference-rate 2.10 --as-of 2026-11-16
```

## Output

# Collection list at 2026-11-16

Overdue, undisputed: **426,100.00** (8 invoices). Disputed: 126,000.00 (1). Not yet due: 92,300.00.
Statutory interest rate used: 10.10% = reference rate 2.10% + 8.00 pp. Interest accrued 4,022.65; fees charged to date 700.00; fees on next reminders 600.00; B2B compensation 1,860.00.

## 1. Prioritised collection list

| # | Customer | Invoice | Amount | Due | Days | Bucket | Reminders | Interest | Next fee | B2B comp. | Claim after next | Score | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Byggefirma Holst ApS | 2026-311 | 84,500.00 | 2026-09-15 | 62 | 61-90 | 1 | 1,449.70 | 100.00 | 310.00 | 86,459.70 | 52.1 | 2nd reminder, firm |
| 2 | Midtjysk Tag A/S | 2026-301 | 18,900.00 | 2026-09-05 | 72 | 61-90 | 2 | 376.55 | 100.00 | 310.00 | 19,886.55 | 44.7 | Final reminder, state next step |
| 3 | Hansen privat | 2026-370 | 4,250.00 | 2026-09-20 | 57 | 31-60 | 3 | 67.03 | 0.00 | 0.00 | 4,617.03 | 40.9 | Reminder limit reached: phone the customer, then decide on debt collection (your decision). |
| 4 | Aarhus Kommune | 2026-362 | 210,000.00 | 2026-10-31 | 16 | 1-30 | 0 | 929.75 | 100.00 | 310.00 | 211,339.75 | 37.1 | 1st reminder, friendly |
| 5 | Nordisk Facility A/S | 2026-330 | 57,000.00 | 2026-10-01 | 46 | 31-60 | 1 | 725.54 | 0.00 | 310.00 | 58,135.54 | 33.6 | Wait: next reminder with fee allowed from 2026-11-20 (10-day rule). |
| 6 | Byggefirma Holst ApS | 2026-347 | 41,250.00 | 2026-10-10 | 37 | 31-60 | 0 | 422.33 | 100.00 | 310.00 | 42,082.33 | 29.8 | 1st reminder, friendly |
| 7 | Café Kronen ApS | 2026-355 | 6,800.00 | 2026-10-25 | 22 | 1-30 | 0 | 41.40 | 100.00 | 310.00 | 7,251.40 | 10.7 | 1st reminder, friendly |
| 8 | Peters VVS | 2026-366 | 3,400.00 | 2026-11-05 | 11 | 1-30 | 0 | 10.35 | 100.00 | 0.00 | 3,510.35 | 5.4 | 1st reminder, friendly |

## 2. Disputed invoices (excluded from fees, interest and compensation)

| Customer | Invoice | Amount | Due | Days | Action |
|---|---|---|---|---|---|
| Ribe Boligselskab | 2026-298 | 126,000.00 | 2026-08-30 | 78 | Disputed: no reminder, fee, interest or compensation. Resolve the dispute and agree the undisputed part. |

## 3. Ageing

| Days overdue | Invoices | Amount | Disputed invoices | Disputed amount |
|---|---|---|---|---|
| 1-30 | 3 | 220,200.00 | 0 | 0.00 |
| 31-60 | 3 | 102,500.00 | 0 | 0.00 |
| 61-90 | 2 | 103,400.00 | 1 | 126,000.00 |
| over 90 | 0 | 0.00 | 0 | 0.00 |

## 4. Data quality and assumptions

- line 8 (Peters VVS): b2b blank or unclear, treated as NOT B2B (no compensation)
- invoice 2026-355 appears twice (lines 5 and 12): possible duplicate, second row skipped
- Reference rate 2.10% supplied by the user: verify the current Danmarks Nationalbank rate for the period (it is fixed each 1 January and 1 July).
- Settings used: reminder fee DKK 100 per reminder, at most 3 fee-bearing reminders, at least 10 days apart. Legal limits (renteloven section 9 b, stk. 2): at most DKK 100 per reminder, at most 3 reminders, at least 10 days apart; verify current values.
- B2B fixed compensation DKK 310 per invoice (renteloven section 9 a, stk. 3; amount set by executive order; verify current value).
- Interest is simple, from the due date, on a 365-day year. Consumer claims without an agreed due date accrue interest only 30 days after a demand. Check with an adviser.
- Priority score = 30 x amount / largest + 40 x min(days / 90, 1) + 15 x min(reminders / max, 1) + 15 x min((customer's open overdue invoices - 1) / 2, 1).
- Fees to date assume each reminder sent carried a fee. Escalation to debt collection or a debtor register is the user's decision.

## Interpretation

- The reference rate of 2.10 % is an illustration only: check Danmarks Nationalbank's current rate for this half-year and re-run, as all interest figures depend on it.
- Overdue and undisputed: 426,100 across 8 invoices. The ranking now weighs age and repeat lateness, so Byggefirma Holst 2026-311 (62 days, two open invoices) comes first with a firm 2nd reminder, and Midtjysk Tag gets the final notice.
- Aarhus Kommune (210,000) is the largest but only 16 days overdue: send the 1st reminder, and check that the invoice went out as an e-invoice with the right EAN number.
- Hansen privat has had 3 reminders: no more fees are allowed. Phone first; whether to hand over to debt collection is your decision. Nordisk Facility's next fee-bearing reminder is allowed from 20 November.
- Ribe Boligselskab (126,000) is disputed and excluded from fees and interest. Invoice 2026-355 appears twice in the export and Peters VVS has no B2B flag, so no compensation is added until confirmed.
