# Worked example: sales-pipeline-review

## Request

> Pipeline meeting tomorrow at 9. Q4 target is DKK 4.2m. Export from Pipedrive attached, today is 16 November. Where do we stand and which deals need attention?

## Command (run from the skill's automation folder)

```
python3 scripts/pipeline.py assets/pipeline_template.csv --today 2026-11-16 --target 4200000
```

## Output

# Pipeline review

Today 2026-11-16. Period 2026-10-01 to 2026-12-31. Stale after 14 days without activity.

## Pipeline health summary

| Metric | Value |
|---|---|
| Won in period | 760,000 (2 deals) |
| Target | 4,200,000 |
| Remaining to target | 3,440,000 |
| Open pipeline closing in period | 5,820,000 (9 deals) |
| Weighted open pipeline in period | 2,260,000 |
| Won + weighted | 3,020,000 (72% of target) |
| Coverage (open in period / remaining target) | 1.69x |
| Open pipeline dated after the period | 0 (1 deal) |

## Stage ageing (open deals)

| Stage | Deals | Amount | Weighted in period | Median age days | Mean age days | Median days since activity |
|---|---|---|---|---|---|---|
| Discovery | 2 | 2,080,000 | 208,000 | 30 | 30 | 8 |
| Qualification | 1 | 260,000 | 52,000 | 88 | 88 | 75 |
| Proposal | 4 | 1,150,000 | 460,000 | 72 | 70 | 12 |
| Negotiation | 3 | 2,330,000 | 1,540,000 | 157 | 151 | 3 |

Age is days since the deal was created; time in the current stage needs stage history from the CRM.

## By owner

| Owner | Won in period | Open in period | Weighted in period | Open deals | Flagged |
|---|---|---|---|---|---|
| Anders | 0 | 2,990,000 | 1,348,000 | 4 | 2 |
| Jonas | 410,000 | 990,000 | 344,000 | 3 | 3 |
| Mette | 350,000 | 1,840,000 | 568,000 | 3 | 2 |

## Flagged deals

| Deal | Owner | Stage | Amount | Close date | Flags |
|---|---|---|---|---|---|
| Fyn Fødevarer - BI projekt | Jonas | Proposal | 540,000 | 2026-11-05 | close date in the past (2026-11-05); stale: 19 days since activity; close date pushed 36 days |
| Sønderborg Plast - ERP integration | Anders | Negotiation | 780,000 | 2026-11-28 | stale: 26 days since activity; close date pushed 28 days |
| Aalborg Akustik - support | Jonas | Qualification | 260,000 | 2026-12-31 | no next step; stale: 75 days since activity |
| Lolland Agro - sensorer | Jonas | Proposal | 190,000 | 2026-12-18 | no next step; stale: 42 days since activity |
| Nordvind Energi - drift | Mette | Discovery | 1,200,000 | 2026-12-20 | no next step |
| Gudenå Vand - målerdata | Anders | Discovery | 880,000 | 2026-12-30 | no next step |
| Vejle Varme - fjernaflæsning | Mette | Proposal | 0 | 2027-01-20 | amount missing |

## Deals that decide the period

| Deal | Owner | Stage | Amount | Probability | Close date | Share of remaining | Cumulative | Flags |
|---|---|---|---|---|---|---|---|---|
| Nordvind Energi - drift | Mette | Discovery | 1,200,000 | 10% | 2026-12-20 | 35% | 35% | no next step |
| Brandt Logistik - WMS | Anders | Negotiation | 910,000 | 60% | 2026-12-12 | 26% | 61% | - |
| Gudenå Vand - målerdata | Anders | Discovery | 880,000 | 10% | 2026-12-30 | 26% | 87% | no next step |
| Sønderborg Plast - ERP integration | Anders | Negotiation | 780,000 | 70% | 2026-11-28 | 23% | 110% | stale: 26 days since activity; close date pushed 28 days |

## Data quality warnings

- Deal Vejle Varme - fjernaflæsning: amount missing or not a number, counted as 0
- Line 15: duplicate deal 'Holm Medico - kvalitetssystem', later row ignored

## Interpretation

- Won so far is DKK 760k, so DKK 3.44m remains; open pipeline closing in Q4 is DKK 5.82m, a coverage of 1.69x, which is thin this late in the quarter.
- Won plus weighted pipeline is DKK 3.02m, 72% of target, so on current probabilities the quarter lands about DKK 1.2m short.
- Four deals decide the quarter: Nordvind Energi (1.2m) and Gudenå Vand (0.88m) are still in Discovery with no next step, Brandt Logistik (0.91m) looks healthy, and Sønderborg Plast (0.78m) has had no activity for 26 days and was already pushed once.
- Fyn Fødevarer has a close date in the past, has been pushed 36 days and is stale: ask Jonas for a new date or close it lost.
- Fix the duplicate Holm Medico row and add an amount to Vejle Varme (it closes in January, so it does not affect Q4).
