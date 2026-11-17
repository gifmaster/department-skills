# Worked example: cs-staffing-forecast

## Request

> How many agents do we need on the phones on Monday 30 November? Our forecast per half hour is in the file. AHT is 5.5 minutes, target 80% answered in 30 seconds, shrinkage 30%.

## Command (run from the skill's automation folder)

```
python3 scripts/erlang.py assets/intervals_template.csv --aht 330 --answer-time 30
```

## Output

# Staffing requirement (Erlang C)

Target 80% answered within 30 s, AHT 330 s, 30-minute intervals, max occupancy 85%, shrinkage 30%.

## Headline

| Metric | Value |
|---|---|
| Contacts | 430 |
| Workload (hours of handling) | 39.4 |
| Agent hours on queue (sum of required agents) | 62.5 |
| Paid hours after shrinkage | 89.3 |
| Full-day equivalents (7.4 h) | 12.1 |
| Peak agents on queue / scheduled | 10 / 15 |
| Contact-weighted service level | 86.3% |
| Average occupancy | 63.1% |

## Per interval

| Interval | Contacts | Erlangs | Agents | Service level | ASA s | Occupancy | Scheduled | Set by |
|---|---|---|---|---|---|---|---|---|
| 2026-11-30 08:00 | 14 | 2.57 | 5 | 88.6% | 19 | 51.3% | 8 | service level |
| 2026-11-30 08:30 | 22 | 4.03 | 7 | 89.3% | 16 | 57.6% | 10 | service level |
| 2026-11-30 09:00 | 31 | 5.68 | 9 | 88.8% | 15 | 63.1% | 13 | service level |
| 2026-11-30 09:30 | 36 | 6.60 | 10 | 87.8% | 16 | 66.0% | 15 | service level |
| 2026-11-30 10:00 | 38 | 6.97 | 10 | 83.6% | 24 | 69.7% | 15 | service level |
| 2026-11-30 10:30 | 35 | 6.42 | 10 | 89.6% | 13 | 64.2% | 15 | service level |
| 2026-11-30 11:00 | 33 | 6.05 | 9 | 84.4% | 23 | 67.2% | 13 | service level |
| 2026-11-30 11:30 | 28 | 5.13 | 8 | 85.5% | 22 | 64.2% | 12 | service level |
| 2026-11-30 12:00 | 24 | 4.40 | 7 | 84.3% | 25 | 62.9% | 10 | service level |
| 2026-11-30 12:30 | 26 | 4.77 | 8 | 89.9% | 14 | 59.6% | 12 | service level |
| 2026-11-30 13:00 | 29 | 5.32 | 8 | 82.9% | 27 | 66.5% | 12 | service level |
| 2026-11-30 13:30 | 29 | 5.32 | 8 | 82.9% | 27 | 66.5% | 12 | service level |
| 2026-11-30 14:30 | 27 | 4.95 | 8 | 87.9% | 17 | 61.9% | 12 | service level |
| 2026-11-30 15:00 | 24 | 4.40 | 7 | 84.3% | 25 | 62.9% | 10 | service level |
| 2026-11-30 15:30 | 19 | 3.48 | 6 | 86.1% | 23 | 58.1% | 9 | service level |
| 2026-11-30 16:00 | 15 | 2.75 | 5 | 85.4% | 26 | 55.0% | 8 | service level |

Scheduled = agents / (1 - shrinkage), rounded up per interval. Headcount needs depend on shift patterns, breaks and working time rules (11-hour daily rest, weekly rest day, collective agreement).

## Data quality warnings

- Line 14 (2026-11-30 14:00): contacts missing or not a number, row skipped
- Line 17: duplicate interval 2026-11-30 15:00 (first on line 16), later row ignored
- Gap in intervals between 2026-11-30 13:30 and 2026-11-30 14:30 (missing interval rows?)

## Erlang C limits

- Assumes callers never abandon or retry, so with long queues it overstates the staff needed; an Erlang A model with patience data is more accurate there.
- Assumes steady random arrivals within each interval and one contact per agent at a time (not valid for chat concurrency or email backlog work).
- Results are only as good as the volume forecast and AHT; test +10% AHT and volume as a sensitivity check.

## Interpretation

- You need 5 to 10 agents on the phones at any time, peaking at 10 from 09:30 to 11:00, which means 15 people scheduled in those half hours once 30% shrinkage is added.
- Across the day that is 62.5 agent hours on the queue and 89.3 paid hours, about 12 full days of 7.4 hours.
- Every interval meets the target with some headroom (contact-weighted 86.3% in 30 seconds) at 51% to 70% occupancy, so the plan is not over-tight.
- The 14:00 row is blank and 15:00 appears twice: the 14:00 half hour is missing from the totals, so add a forecast for it before you build shifts.
- Erlang C ignores callers hanging up, so treat this as a safe upper estimate.
