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
- Choice per item: lowest WAPE on the last 3 periods, then refitted on the full history
- Stock-out periods are excluded from fitting and from accuracy (not treated as true demand)

| Item | Periods | Stock-out periods excluded | Method chosen | Basis |
|---|---|---|---|---|
| LS-400 Lounge set Fano | 14 | 2026-05 | SES (alpha=0.9) | lowest hold-out WAPE |
| PA-120 Parasol 3m grey | 6 | - | SES (alpha=0.1) | lowest hold-out WAPE |

## 2. Forecast table

**LS-400 Lounge set Fano** (SES)

| Period | 2026-11 | 2026-12 | 2027-01 | 2027-02 | 2027-03 | 2027-04 | Total |
|---|---|---|---|---|---|---|---|
| Forecast | 60 | 60 | 60 | 60 | 60 | 60 | 360 |

Same periods last year: 988 (forecast is -63.6 % vs last year)

**PA-120 Parasol 3m grey** (SES)

| Period | 2026-11 | 2026-12 | 2027-01 | 2027-02 | 2027-03 | 2027-04 | Total |
|---|---|---|---|---|---|---|---|
| Forecast | 35 | 35 | 35 | 35 | 35 | 35 | 212 |

Same periods last year: not available

## 3. Accuracy and bias (hold-out)

| Item | Method | Hold-out forecast | Actual | WAPE | MAPE | Bias |
|---|---|---|---|---|---|---|
| LS-400 Lounge set Fano | MA | 423 / 423 / 423 | 171 / 66 / 58 | 329.8 % | 438.8 % | 329.8 % |
| LS-400 Lounge set Fano | SES (chosen) | 321 / 321 / 321 | 171 / 66 / 58 | 226.4 % | 309.1 % | 226.4 % |
| PA-120 Parasol 3m grey | MA | 27 / 27 / 27 | 41 / 36 / 35 | 26.8 % | 26.4 % | -26.8 % |
| PA-120 Parasol 3m grey | SES (chosen) | 35 / 35 / 35 | 41 / 36 / 35 | 6.9 % | 6.5 % | -6.9 % |

WAPE = sum|A - F| / sum A. Bias = (sum F - sum A) / sum A, positive means over-forecast. Stock-out periods in the hold-out are left out of the scores.

## 4. Items to review

- **LS-400 Lounge set Fano**: no seasonal model (needs 24 periods); hold-out WAPE 226.4 %; hold-out bias 226.4 %; forecast total -63.6 % vs same periods last year, check plausibility
- **PA-120 Parasol 3m grey**: under 12 periods of history; no seasonal model (needs 24 periods)

## Data-quality warnings

- Line 20: duplicate row for PA-120 Parasol 3m grey 2026-09, quantities summed.
- PA-120 Parasol 3m grey: no row for 2026-07, filled with 0. Check whether these were real zero months.

## Interpretation

- Do not order on the LS-400 number. With 14 months there is no seasonal model, so the best flat method forecasts 60 a month, 64 % below the same months last year (988). The hold-out WAPE of 226 % says the same thing.
- Send at least 24 months of LS-400 history. The script then fits Holt-Winters, which captures the March to June peak; until then, plan from last year's months plus growth and review by hand.
- May 2026 was excluded as a stock-out, not counted as low demand.
- PA-120 forecasts about 35 a month with a 7 % hold-out WAPE, but on six months of history and with July filled as 0 (no row). Confirm July was a real zero month; the duplicate September rows were summed.
