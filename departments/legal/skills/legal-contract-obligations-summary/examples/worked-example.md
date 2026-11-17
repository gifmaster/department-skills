# Worked example: Contract notice deadlines

## User request

> Søbro Fødevarer A/S. Here is our contract register. Which notice deadlines are coming up, which have we already missed, and can you give me calendar reminders for Outlook?

## Command run (from the skill folder, on the sample assets)

```
python3 scripts/notice_deadlines.py assets/contracts_template.csv --today 2026-11-16 --ics /tmp/notice-reminders.ics
```

## Output

~~~~text
# Contract notice deadlines (as of 2026-11-16, window 90 days, delivery buffer 5 days)

**9 contracts. Action needed within the window: 3. Missed notice deadlines (contract rolled over): 5.**

## Key dates
| Contract | Counterparty | Auto-renew | Notice | Current term ends | Notice deadline | Send by | Days left | Status |
|---|---|---|---|---|---|---|---:|---|
| IT support agreement | Kolding IT Partner ApS | yes | 1 month | 2026-12-31 | 2026-11-30 (Mon) | 2026-11-25 | 14 | DUE |
| Waste collection | Marius Pedersen A/S | yes | 60 days | 2027-01-31 | 2026-12-02 (Wed) | 2026-11-27 | 16 | DUE |
| Telephony | TDC Erhverv | yes | 1 month | 2027-02-28 | 2027-01-28 (Thu) | 2027-01-22 | 73 | DUE |
| Fleet leasing | LeasePlan Danmark | no | 3 months | 2027-05-31 | 2027-02-28 (Sun) | 2027-02-23 | 196 | ENDS |
| Cleaning services | Rent & Pænt ApS | yes | 30 days | 2027-03-31 | 2027-03-01 (Mon) | 2027-02-24 | 105 | RENEWED |
| Marketing retainer | Bureau Blå ApS | yes | 1 month | 2027-05-31 | 2027-04-30 (Fri) | 2027-04-23 | 165 | RENEWED |
| Packaging supply agreement | NordPack AB | yes | 6 months | 2028-01-31 | 2027-07-31 (Sat) | 2027-07-26 | 257 | RENEWED |
| Office lease Vesterbrogade | Ejendomsselskabet Vester ApS | yes | 3 months | 2027-12-31 | 2027-09-30 (Thu) | 2027-09-24 | 318 | RENEWED |
| ERP subscription | Visma e-conomic | yes | 30 days | 2027-12-14 | 2027-11-14 (Sun) | 2027-11-09 | 363 | RENEWED |

## Actions
- **IT support agreement** (DUE): decide renew or terminate; send notice by 2026-11-25. Form: email.
- **Waste collection** (DUE): decide renew or terminate; send notice by 2026-11-27. Form: registered letter.
- **Telephony** (DUE): decide renew or terminate; send notice by 2027-01-22. Form: customer portal.
- **Fleet leasing** (ENDS): no auto-renewal: diary the end date. Form: written notice.
- **Cleaning services** (RENEWED): notice deadline 2026-03-01 missed: renewed 1x, now ends 2027-03-31. Form: email.
- **Marketing retainer** (RENEWED): notice deadline 2026-10-30 missed: renewed 1x, now ends 2027-05-31. Form: email.
- **Packaging supply agreement** (RENEWED): notice deadline 2026-07-31 missed: renewed 1x, now ends 2028-01-31. Deadline falls on a Saturday: aim for receipt by the Friday before. Form: email and registered letter.
- **Office lease Vesterbrogade** (RENEWED): notice deadline 2026-09-30 missed: renewed 1x, now ends 2027-12-31. Form: registered letter.
- **ERP subscription** (RENEWED): notice deadline 2026-11-14 missed: renewed 1x, now ends 2027-12-14. Deadline falls on a Sunday: aim for receipt by the Friday before. Form: customer portal.

## Reminder lines (date | reminder)
```
20261125 | Send notice if terminating: IT support agreement (Kolding IT Partner ApS) | deadline 2026-11-30 | term ends 2026-12-31 | form: email
20261127 | Send notice if terminating: Waste collection (Marius Pedersen A/S) | deadline 2026-12-02 | term ends 2027-01-31 | form: registered letter
20270122 | Send notice if terminating: Telephony (TDC Erhverv) | deadline 2027-01-28 | term ends 2027-02-28 | form: customer portal
20270224 | Send notice if terminating: Cleaning services (Rent & Pænt ApS) | deadline 2027-03-01 | term ends 2027-03-31 | form: email
20270423 | Send notice if terminating: Marketing retainer (Bureau Blå ApS) | deadline 2027-04-30 | term ends 2027-05-31 | form: email
20270531 | Contract ends: Fleet leasing (LeasePlan Danmark) | no auto-renewal
20270726 | Send notice if terminating: Packaging supply agreement (NordPack AB) | deadline 2027-07-31 | term ends 2028-01-31 | form: email and registered letter
20270924 | Send notice if terminating: Office lease Vesterbrogade (Ejendomsselskabet Vester ApS) | deadline 2027-09-30 | term ends 2027-12-31 | form: registered letter
20271109 | Send notice if terminating: ERP subscription (Visma e-conomic) | deadline 2027-11-14 | term ends 2027-12-14 | form: customer portal
```

## Data quality and warnings
- Line 8 (Telephony): renewal_term_months missing, 12 months assumed.
- Line 11 (Coffee machines): no notice period given, deadline not calculated (check the contract).
- Line 12 (Security alarm): start_date 2026-01-01 is after end_date 2025-12-31, skipped (check the dates).
- Line 13 (Packaging supply agreement): duplicates line 2, skipped.

Check each clause for how notice must be given and when it counts as received. Not legal advice.
~~~~

## Interpretation

- Three decisions are due soon: IT support (send notice by 25 November, deadline 30 November), waste collection (by 27 November, a 24-month renewal if missed) and telephony (by 22 January).
- Five contracts have already rolled over because a notice deadline passed. The ERP subscription deadline was only two days ago (14 November), so it now runs to 14 December 2027. If you want to leave, ask Visma whether they will accept late notice.
- The NordPack packaging contract renewed to 31 January 2028. The next deadline, 31 July 2027, is a Saturday and needs both email and registered letter, so send by 26 July.
- Import /tmp/notice-reminders.ics into Outlook: it has one reminder per contract with a 14-day alarm.
- Before relying on the register: the coffee machine contract has no notice period, the security alarm has its start date after its end date, telephony's renewal term was assumed to be 12 months, and NordPack is entered twice.
