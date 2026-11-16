# Worked example: cs-csat-nps-analysis

## Request

> Here are our NPS answers from September and October after support contacts (we're a Danish energy retailer, this is only a test extract). Did NPS change, which channel is worst, and what are people complaining about?

## Command (run from the skill's automation folder)

```
python3 scripts/nps.py assets/responses_template.csv --min-n 5
```

## Output

# NPS analysis

**NPS 5.9** (95% margin of error +/- 44.6 points, n=17). Promoters 8 (47.1%), passives 2 (11.8%), detractors 7 (41.2%).

## By period

| Period | n | NPS | MoE 95% | Promoters | Passives | Detractors | Small sample |
|---|---|---|---|---|---|---|---|
| 2026-09 | 10 | 0.0 | +/- 55.4 | 4 | 2 | 4 |  |
| 2026-10 | 7 | 14.3 | +/- 73.3 | 4 | 0 | 3 |  |

Change 2026-09 to 2026-10: +14.3 points, NOT statistically meaningful, may be noise (z=0.30).

## Segments (each compared with the rest of the sample)

| Segment | n | NPS | 95% interval | vs rest | Assessment |
|---|---|---|---|---|---|
| chat | 6 | -16.7 | +/- 71.8 | -34.8 | difference vs rest is NOT statistically meaningful |
| email | 6 | -50.0 | +/- 61.1 | -86.4 | difference vs rest is statistically meaningful |
| phone | 5 | 100.0 | +/- 0.0 | +133.3 | difference vs rest is statistically meaningful |

## Comment themes (keyword match, 14 comments)

| Theme | Comments | Share | Avg score | By group |
|---|---|---|---|---|
| staff attitude | 5 | 36% | 8.8 | detractor 1, promoter 4 |
| price and billing | 3 | 21% | 5.0 | detractor 2, passive 1 |
| waiting and response time | 3 | 21% | 4.3 | detractor 2, promoter 1 |
| chatbot and self-service | 2 | 14% | 4.0 | detractor 2 |
| clarity of information | 2 | 14% | 5.5 | detractor 1, passive 1 |
| issue not resolved | 2 | 14% | 5.5 | detractor 2 |

Comments matching no theme (read manually): R007.

A comment can match several themes. Keyword matching is a first pass, so read the comments before drawing conclusions.

## Data quality warnings

- Line 19: duplicate response_id R017, later row ignored
- Line 21 (R019): score missing or not a number (''), row skipped
- Response R018: score 11 outside 0-10, excluded

Method: NPS = %promoters (9-10) - %detractors (0-6). MoE = 1.96 x sqrt((p + d - (p - d)^2) / n) x 100. Segments need n >= 5 to be scored.

## Interpretation

- NPS is +5.9 on 17 valid responses, but the margin of error is +/- 44.6 points, so this extract cannot say whether NPS is good or bad; the full file is needed.
- September to October shows no change worth reporting (z close to 0).
- Phone looks clearly better than the other channels (NPS +80 vs -50 for email), and that gap passes the significance test even at this size, but with 5 to 6 responses per channel I scored segments only because you asked for a minimum of 5; on the full data keep the default 30.
- Detractor comments cluster on billing and price (aconto, regning, invoice) and waiting time, with the chatbot as a smaller theme; staff attitude is mostly praised.
- Three rows were excluded (a duplicate, a score of 11 and a blank score); please check how the survey tool exports them.
