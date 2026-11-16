# Worked example: fin-journal-entry-testing

## User request

> Run red-flag tests on the March to April journal export from Business Central. Our approval limit is DKK 50,000.

## Command run (from the skill folder)

```
python3 scripts/je_tests.py assets/journal.csv --approval-limit 50000
```

## Output

# Journal entry testing

Population: 20 lines in 10 entries, 2026-03-26 to 2026-04-10, 4 user IDs. Entries with at least one exception: **7**.
Exceptions are facts about postings to follow up, not conclusions about any person. Many have ordinary explanations.

## 1. Tests performed

| Test | Name | Rule | Weight | Entries hit |
|---|---|---|---|---|
| T1 | Weekend or public holiday | Saturday, Sunday or Danish holiday (extra: 06-05,12-24,12-31) | 2 | 3 |
| T2 | Out of hours | time before 07:00 or after 19:00 | 2 | 2 |
| T3 | Round amount | multiple of 1,000 and >= 5,000 | 1 | 3 |
| T4 | Just below approval limit | 45,000 to below 50,000 (10% band) | 3 | 3 |
| T5 | Possible duplicate | same account, amount and text in another entry within 3 days | 3 | 2 |
| T6 | Manual entry to revenue or cash account | manual to accounts starting 1 (revenue) or 58 (cash) | 2 | 5 |
| T7 | New or rare user | user with <= 2 entries in the file | 2 | 2 |

## 2. Ranked exceptions (top 15)

| # | Entry | Date | Time | Posted by (user ID) | Accounts | Description | Amount | Manual | Tests hit | Score |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | JE1002 | 2026-03-28 | 23:41 | MKJ | 2800, 5820 | Kørsel ekstra Nordtrans | 49,800.00 | yes | T1 Saturday; T2 23:41; T4 49,800 (99.6% of limit); T6 cash account 5820 | 9 |
| 2 | JE1008 | 2026-04-08 | 22:10 | MKJ | 2800, 5820 | Kørsel ekstra Nordtrans | 49,900.00 | yes | T2 22:10; T4 49,900 (99.8% of limit); T6 cash account 5820 | 7 |
| 3 | JE1004 | 2026-04-02 | 14:05 | MKJ | 2800, 5820 | Kørsel ekstra Nordtrans | 49,500.00 | yes | T1 Maundy Thursday; T4 49,500 (99.0% of limit); T6 cash account 5820 | 7 |
| 4 | JE1007 | 2026-04-06 | 08:55 | LHA | 1010, 5600 | Kreditnota korrektion | 40,000.00 | yes | T1 Easter Monday; T3 40,000; T6 revenue account 1010; T7 user with 1 entry in file | 7 |
| 5 | JE1005 | 2026-04-01 | 11:20 | PBN | 2750, 6800 | Fakt 7781 Elektro Syd | 125,000.00 | no | T3 125,000; T5 same account, amount and text as entry JE1006 | 4 |
| 6 | JE1006 | 2026-04-01 | 11:22 | PBN | 2750, 6800 | Fakt 7781 Elektro Syd | 125,000.00 | no | T3 125,000; T5 same account, amount and text as entry JE1005 | 4 |
| 7 | JE1009 | 2026-04-09 | 16:45 | TMP01 | 5820, 7300 | Kassedifference | 8,750.00 | yes | T6 cash account 5820; T7 user with 1 entry in file | 4 |

## 3. Follow-up

- For each top entry request the voucher, the approval evidence and the business reason; record the outcome per entry.
- Keep the results to the smallest group that needs them and refer to user IDs, not names (GDPR data minimisation). Take legal or HR advice before acting on any concern about an employee.

## 4. Data quality and assumptions

- line 22 (entry JE1011): missing or invalid date or amount, row skipped
- Weights: T1=2, T2=2, T3=1, T4=3, T5=3, T6=2, T7=2. Score = sum of weights of tests hit per entry.
- Account prefixes and approval limit are company-specific: set them to your chart of accounts and approval policy.

## Interpretation

- Three entries with the same text "Kørsel ekstra Nordtrans" (JE1002, JE1004, JE1008) are each 99 to 99.8 % of the approval limit, manual postings to the bank account, and all three were posted at night, at a weekend or on a public holiday. Together they are 149,200, well above the limit. Request the invoices, delivery evidence, approval trail and the supplier master record.
- JE1005 and JE1006 post the same Elektro Syd invoice 7781 (125,000) two minutes apart: check whether it was paid twice.
- JE1007 is a manual 40,000 posting to revenue on Easter Monday by an infrequent user ID; ask for the credit note and its approval.
- These are facts about postings, not conclusions about anyone. Keep the results to a small group, use user IDs, and take advice before raising any concern with an employee. One row (JE1011) had no date and was not tested.
