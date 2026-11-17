# Worked example: Sales forecast

## User request

> We are Nordlys Software ApS. Board meeting next week and I need the Q4 forecast. Target is DKK 4.0m new ARR, we have closed 150k so far (Holbæk Auto is in the export as closed won). Attached: the CRM pipeline export and last year's closed deals with the furthest stage they reached. Today is 16 November.

## Command run (from the skill folder, on the sample assets)

```
python3 scripts/sales_forecast.py assets/pipeline_template.csv --history assets/history_template.csv --period-start 2026-10-01 --period-end 2026-12-31 --today 2026-11-16 --target 4000000
```

## Output

~~~~text
# Sales forecast 2026-10-01 to 2026-12-31 (as of 2026-11-16)

**Commit 1,002,444 | Most likely 1,414,611 | Best case 1,970,000** (includes closed won 150,000; 8 open deals worth 3,265,000 close in the period)

## Forecast range
| Scenario | Forecast | Definition | Gap to target |
|---|---:|---|---:|
| Commit (low) | 1,002,444 | closed won + rep commit deals at historical conversion | 2,997,556 |
| Most likely | 1,414,611 | closed won + historical conversion on all open deals | 2,585,389 |
| Best case (high) | 1,970,000 | closed won + highest of weighted, historical and rep commit at face value | 2,030,000 |

## Method comparison
| Method | Open pipeline | Total incl. closed won |
|---|---:|---:|
| Weighted pipeline (CRM probability) | 1,502,250 | 1,652,250 |
| Historical stage-to-win conversion | 1,264,611 | 1,414,611 |
| Rep commit at face value | 1,820,000 | 1,970,000 |
| Rep commit at historical conversion | 852,444 | 1,002,444 |

- CRM probabilities vs history: 237,639 (CRM more optimistic).
- Rep commit at face value vs risk-adjusted: 967,556.
- Top 2 deals make up 49% of the open part of the most likely figure.

## Conversion rates used
| Stage | Rate | Deals in sample | Source |
|---|---:|---:|---|
| Discovery | 20% | 20 | history |
| Qualification | 24% | 17 | history |
| Proposal | 29% | 14 | history |
| Negotiation | 44% | 9 | history |
| Verbal | 80% | 5 | history |

Median sales cycle of won deals: 74 days (20 closed deals in history).

## Deals closing in the period
| Deal | Stage | Amount | Close | CRM p | Hist | Commit | Weighted | Historical | Flags |
|---|---|---:|---|---:|---:|---|---:|---:|---|
| Fynsk Fragt ApS | Negotiation | 850,000 | 2026-12-15 | 60% | 44% | yes | 510,000 | 377,778 | commit at Negotiation (hist 44%) |
| Roskilde Tandklinik | Discovery | 600,000 | 2026-12-20 | 10% | 20% |  | 60,000 | 120,000 |  |
| Aarhus Isolering A/S | Proposal | 420,000 | 2026-12-10 | 35% | 29% | yes | 147,000 | 120,000 | commit at Proposal (hist 29%) |
| Silkeborg El-Service | Negotiation | 380,000 | 2026-12-05 | 60% | 44% |  | 228,000 | 168,889 |  |
| Vejle Maskinfabrik | Verbal | 310,000 | 2026-11-28 | 90% | 80% | yes | 279,000 | 248,000 |  |
| Køge Bryghus | Proposal | 275,000 | 2026-12-18 | 35% | 29% |  | 96,250 | 78,571 |  |
| Odense Kontormøbler | Negotiation | 240,000 | 2026-11-10 | 60% | 44% | yes | 144,000 | 106,667 | commit at Negotiation (hist 44%); close date passed |
| Nordsjælland Revision | Qualification | 190,000 | 2026-12-15 | 20% | 24% |  | 38,000 | 44,706 |  |

Excluded: 1 deals outside the period (950,000), 1 lost, 1 invalid rows.

## Data quality and warnings
- History line 5 (Hjørring Huse): cycle_days missing for a won deal.
- Line 10 (Herning Tekstil): amount missing or not a number, deal excluded.
- Line 11 (Fynsk Fragt ApS): duplicate of line 2, counted once.
- Only 46 days left in the period vs median won cycle of 74 days: early-stage deals are unlikely to close in time.
~~~~

## Interpretation

- Report a most likely Q4 of DKK 1.41m with a range of 1.00m (commit) to 1.97m (best case). The DKK 4.0m target is not reachable from this pipeline: the gap is at least 2.0m even in the best case.
- CRM probabilities are DKK 238k more optimistic than your own history, mainly because Negotiation deals have closed 44% of the time, not 60%.
- Reps commit DKK 1.82m, but those deals have historically delivered about 0.85m. Fynsk Fragt (850k, Negotiation) and Aarhus Isolering (420k, Proposal) are committed at stages that usually do not close: ask the reps for evidence such as a signed order or agreed contract date.
- Odense Kontormøbler's close date has already passed; update it or move it. Roskilde Tandklinik is in Discovery with 46 days left against a 74-day median cycle, so it should not be in Q4.
- Fix the data before the board pack: Herning Tekstil has no amount and Fynsk Fragt is in the export twice (counted once).
