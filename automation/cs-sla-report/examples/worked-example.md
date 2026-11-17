# Worked example: cs-sla-report

## Request

> We're a 40-person Danish IT support company. Here is the ticket export for the two weeks around Easter, taken 15 April at midnight. SLA is business hours Mon-Fri 08-16: P1 1h response / 8h resolution, P2 4h / 16h, P3 8h / 40h. How did we do, and which tickets breached?

## Command (run from the skill's automation folder)

```
python3 scripts/sla.py assets/tickets_template.csv --as-of "2026-04-15 00:00"
```

## Output

# SLA report

Tickets created 2026-03-30 to 2026-04-14. Backlog measured at 2026-04-15 00:00. Times in business hours (Europe/Copenhagen).

Closed days excluded from the clock: 2026-04-02 Skaertorsdag, 2026-04-03 Langfredag, 2026-04-06 2. paaskedag.

## Headline metrics

| Metric | Value |
|---|---|
| Tickets | 16 |
| Open at as-of time | 3 |
| First response SLA attainment | 78.6% (11 met, 3 breached) |
| Resolution SLA attainment | 83.3% (10 met, 2 breached) |
| First response median / p90 (h) | 0.50 / 2.23 (n=14) |
| Resolution median / p90 (h) | 7.96 / 13.95 (n=12) |

## By priority

| Priority | Tickets | FR target h | FR median | FR p90 | FR attainment | Res target h | Res median | Res p90 | Res attainment |
|---|---|---|---|---|---|---|---|---|---|
| HASTER | 1 | none | 0.50 | 0.50 | - (0/0) | none | 14.00 | 14.00 | - (0/0) |
| P1 | 3 | 1 | 1.21 | 1.97 | 33.3% (1/3) | 8 | 6.42 | 8.42 | 50.0% (1/2) |
| P2 | 6 | 4 | 0.46 | 2.92 | 83.3% (5/6) | 16 | 3.38 | 9.45 | 80.0% (4/5) |
| P3 | 6 | 8 | 0.75 | 2.02 | 100.0% (5/5) | 40 | 10.50 | 24.00 | 100.0% (5/5) |

## By channel

| Channel | Tickets | FR median | FR p90 | FR attainment | Res median | Res p90 | Res attainment | Open |
|---|---|---|---|---|---|---|---|---|
| chat | 4 | 0.50 | 4.37 | 66.7% | 7.25 | 11.05 | 66.7% | 1 |
| email | 8 | 0.71 | 2.19 | 87.5% | 8.92 | 20.50 | 85.7% | 1 |
| phone | 4 | 0.25 | 0.45 | 66.7% | 3.92 | 11.98 | 100.0% | 1 |

## Backlog (open tickets)

Open: 3. Age (calendar): under 1 day 2, 1-3 days 0, 3-7 days 1, over 7 days 0.

| Ticket | Priority | Channel | Created | Age calendar h | Age business h | First response | Resolution |
|---|---|---|---|---|---|---|---|
| T1012 | P2 | chat | 2026-04-09 10:00 | 134.0 | 30.0 | met | breached (open) |
| T1015 | P3 | email | 2026-04-14 09:00 | 15.0 | 7.0 | met | pending |
| T1016 | P1 | phone | 2026-04-14 14:00 | 10.0 | 2.0 | breached (open) | pending |

## Breaches

| Ticket | Priority | Channel | Metric | Status | Actual h | Target h | Over by h |
|---|---|---|---|---|---|---|---|
| T1012 | P2 | chat | resolution | breached (open) | 30.00 | 16 | 14.00 |
| T1004 | P2 | chat | first response | breached | 5.33 | 4 | 1.33 |
| T1008 | P1 | email | first response | breached | 2.17 | 1 | 1.17 |
| T1016 | P1 | phone | first response | breached (open) | 2.00 | 1 | 1.00 |
| T1008 | P1 | email | resolution | breached | 8.92 | 8 | 0.92 |

## Data quality warnings

- Line 13: duplicate ticket_id T1011, later row ignored
- Ticket T1009: resolved without a recorded first response, excluded from first response metrics
- Ticket T1010: resolved_at (2026-04-07 12:30) before created_at (2026-04-07 13:00), resolution excluded
- Priority value(s) with no SLA target: HASTER. Counted in volumes, left out of attainment. Add them with --targets.

Method: attainment = met / (met + breached); open tickets past target count as breached, open tickets within target are pending. Median and p90 use linear interpolation. Holidays are computed Danish public holidays (Store Bededag only up to 2023), verify against your contract.

## Interpretation

- Over the Easter fortnight we met first response SLA on 78.6% of measured tickets and resolution SLA on 83.3%; the median first response was 30 business minutes, so the typical ticket is handled fast and the problem sits in a few outliers.
- P1 is the weak spot: 1 of 3 first responses met. T1008 arrived by email at 08:05 and waited over 2 hours, and T1016 (phone) is still unanswered at export time.
- T1012 (P2 chat) has been open for 30 business hours against 16, so it already counts as a breach even though it is not closed.
- Skaertorsdag, Langfredag and 2. paaskedag were excluded from the clock, which is why T1005 shows 2.25 hours, not 5 calendar days.
- Before this goes to customers: fix T1010 (solved before created), decide how to count T1009 (solved with no recorded reply), add a target for the "Haster" priority, and confirm the export is in Danish local time.
