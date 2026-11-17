# Worked example: Data subject request tracker

## User request

> Can you check our log of data subject requests (indsigtsanmodninger and others) and tell me which ones are late or about to be? Today is 16 November 2026.

## Command run (from the skill folder, on the sample assets)

```
python3 scripts/dsar_deadline.py assets/dsar_log_template.csv --today 2026-11-16
```

## Output

~~~~text
# Data subject request tracker (as of 2026-11-16)

**Overdue 2 | Due within warning window 1 | Open 3 | Closed late 1 | Closed on time 1**

| Request | Type | Received | Deadline | Extended | Applies | Status | Days | Extension possible |
|---|---|---|---|---|---|---|---:|---|
| DSR-2026-034 | access | 2026-09-10 | 2026-10-10 | - | 2026-10-10 | OVERDUE | 37 over | no, extension already recorded (notified 2026-10-15, after the first-month deadline: not valid) |
| DSR-2026-031 | access | 2026-10-03 | 2026-11-03 | - | 2026-11-03 | OVERDUE | 13 over | no (first month has passed) |
| DSR-2026-032 | erasure | 2026-10-20 | 2026-11-20 | - | 2026-11-20 | due soon | 4 left | yes, notify the data subject with reasons by 2026-11-20 |
| DSR-2026-033 | access | 2026-08-31 | 2026-09-30 | 2026-11-30 | 2026-11-30 | open | 14 left | already extended |
| DSR-2026-038 | access | 2026-10-31 | 2026-11-30 | - | 2026-11-30 | open | 14 left | yes, notify the data subject with reasons by 2026-11-30 |
| DSR-2026-037 | objection | 2026-11-12 | 2026-12-12 | - | 2026-12-12 | open | 26 left | yes, notify the data subject with reasons by 2026-12-12 |
| DSR-2026-036 | access | 2026-07-01 | 2026-08-01 | 2026-10-01 | 2026-10-01 | closed late | 4 late | n/a (closed) |
| DSR-2026-035 | rectification | 2026-09-15 | 2026-10-15 | - | 2026-10-15 | closed on time |  | n/a (closed) |

## Overdue: action today
- DSR-2026-034: 37 days overdue (deadline 2026-10-10). Respond without further delay: send a holding reply today (acknowledge, apologise, give a firm date), then the full response. Extension is no longer available. Record the cause of the delay; a complaint to Datatilsynet is a real risk.
- DSR-2026-031: 13 days overdue (deadline 2026-11-03). Respond without further delay: send a holding reply today (acknowledge, apologise, give a firm date), then the full response. Extension is no longer available. Record the cause of the delay; a complaint to Datatilsynet is a real risk.

## Due soon
- DSR-2026-032: due 2026-11-20 (4 days). Extension: yes, notify the data subject with reasons by 2026-11-20.

## Data quality and warnings
- Line 5 (DSR-2026-034): extension notified 2026-10-15, after the first-month deadline 2026-10-10: extension not valid.
- Line 9 (DSR-2026-038): identity verified (2026-10-28) before received (2026-10-31): check dates.
- Line 10 (DSR-2026-039): received_date missing, deadline cannot be calculated.
- Line 11: request_id DSR-2026-033 duplicates line 4, skipped.

Legal information, not legal advice. Clock runs from receipt unless --clock-start verification is used.
~~~~

## Interpretation

- Two requests are overdue. DSR-2026-034 is 37 days late: the extension letter went out on 15 October, after the 10 October deadline, so the extension is not valid. DSR-2026-031 is 13 days late. Send holding replies with a firm date today, then the full responses.
- DSR-2026-032 (erasure) is due on 20 November. If it cannot be finished, you can still extend, but only by telling the data subject the reasons by 20 November.
- DSR-2026-033 was validly extended and is due on 30 November. DSR-2026-036 was answered 4 days late; record why.
- Fix the log: DSR-2026-039 has no received date, DSR-2026-033 is entered twice, and DSR-2026-038 shows identity verified before the request was received.
- This is legal information, not legal advice; the clock runs from receipt, so check current EDPB guidance if you want to start it from identity verification.
