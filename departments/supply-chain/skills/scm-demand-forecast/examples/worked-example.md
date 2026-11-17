# Worked example: baseline forecast for garden furniture

## User request

> Kasper, supply planner at a garden-furniture wholesaler in Kolding: "I need a forecast for November to April for the LS-400 lounge set and the PA-120 parasol so I can place the China order this week. We were out of stock most of May on the lounge set. The parasol only launched in May. How accurate is this?"

## Command

```
python3 scripts/forecast.py assets/demand_history.csv
```

## Output

# Demand forecast (statistical baseline)

**2 items, horizon 6 periods, hold-out 3 periods.** Overlays for known events (campaigns, new customers) are NOT included; add them separately.

## 1. Method and assumptions

- Candidates: moving average (last 3), simple exponential smoothing, Holt-Winters additive (season 12) only with 24+ periods
- Choice per item: lowest WAPE over the last 3 periods, rolling origin (refit at each of the 3 origins, forecasts up to the horizon pooled) when at least 6 periods precede the first origin, otherwise one fixed hold-out; then refitted on the full history
- Stock-out periods are excluded from fitting and from accuracy (not treated as true demand)
- Months without data are treated as missing and excluded like stock-outs, not as zero demand

| Item | Periods | Stock-out periods excluded | Missing months excluded | Method chosen | Basis |
|---|---|---|---|---|---|
| LS-400 Lounge set Fano | 14 | 2026-05 | - | SES (alpha=0.9) | lowest rolling-origin WAPE (3 origins) |
| PA-120 Parasol 3m grey | 6 | - | 2026-07 | SES (alpha=0.1) | lowest hold-out WAPE (single origin) |

## 2. Forecast table

**LS-400 Lounge set Fano** (SES)

| Period | 2026-11 | 2026-12 | 2027-01 | 2027-02 | 2027-03 | 2027-04 | Total |
|---|---|---|---|---|---|---|---|
| Forecast | 60 | 60 | 60 | 60 | 60 | 60 | 360 |

Same periods last year: 988 (forecast is -63.6 % vs last year)

**PA-120 Parasol 3m grey** (SES)

| Period | 2026-11 | 2026-12 | 2027-01 | 2027-02 | 2027-03 | 2027-04 | Total |
|---|---|---|---|---|---|---|---|
| Forecast | 38 | 38 | 38 | 38 | 38 | 38 | 229 |

Same periods last year: not available

## 3. Accuracy and bias (hold-out)

| Item | Method | Evaluation | Hold-out forecast | Actual | Errors scored | WAPE | MAPE | Bias |
|---|---|---|---|---|---|---|---|---|
| LS-400 Lounge set Fano | MA | rolling, 3 origins | 423 / 336 / 178 | 171 / 66 / 58 | 6 | 344.2 % | 402.2 % | 344.2 % |
| LS-400 Lounge set Fano | SES (chosen) | rolling, 3 origins | 321 / 186 / 78 | 171 / 66 / 58 | 6 | 196.2 % | 227.4 % | 196.2 % |
| PA-120 Parasol 3m grey | MA | single origin | 41 / 41 / 41 | 41 / 36 / 35 | 3 | 9.8 % | 10.3 % | 9.8 % |
| PA-120 Parasol 3m grey | SES (chosen) | single origin | 39 / 39 / 39 | 41 / 36 / 35 | 3 | 7.7 % | 7.8 % | 3.4 % |

WAPE = sum|A - F| / sum A. Bias = (sum F - sum A) / sum A, positive means over-forecast. Rolling origin: the forecast shown per period is the one-step-ahead forecast; the scores pool every (origin, step) forecast. Stock-out and missing periods are left out of the scores.

## 4. Items to review

- **LS-400 Lounge set Fano**: no seasonal model (needs 24 periods); hold-out WAPE 196.2 %; hold-out bias 196.2 %; forecast total -63.6 % vs same periods last year, check plausibility
- **PA-120 Parasol 3m grey**: under 12 periods of history; no seasonal model (needs 24 periods); 1 missing month(s) in history

## Data-quality warnings

- Line 20: duplicate row for PA-120 Parasol 3m grey 2026-09, quantities summed.
- PA-120 Parasol 3m grey: no data for 2026-07, treated as missing (left out of fitting and scores). Use --fill-zero if these were real zero months.

## Interpretation

- Do not order on the LS-400 number. With 14 months there is no seasonal model, so the best flat method forecasts 60 a month, 64 % below the same months last year (988). The rolling-origin WAPE of 196 % over the last 3 months says the same thing.
- Send at least 24 months of LS-400 history. The script then fits Holt-Winters, which captures the March to June peak; until then, plan from last year's months plus growth and review by hand.
- May 2026 was excluded as a stock-out, not counted as low demand.
- PA-120 forecasts about 38 a month with a 7.7 % hold-out WAPE, but on six months of history, so only a single hold-out was possible. July had no row and was treated as missing, not as zero; if July really sold nothing, rerun with --fill-zero. The duplicate September rows were summed.
