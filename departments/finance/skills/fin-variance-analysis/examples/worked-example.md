# Worked example: fin-variance-analysis

## User request

> Explain Q3 actual vs budget for Aalborg Pumpeteknik A/S. Board wants a short explanation; materiality DKK 100k or 10 %.

## Command run (from the skill folder)

```
python3 scripts/variance.py assets/budget_actual.csv --abs-threshold 100000 --pct-threshold 10
```

## Output

# Variance analysis, actual vs budget

Result: budget 3,995,000, actual 3,317,300, variance **-677,700** (A). Revenue 17,791,500 vs 17,850,000; costs 14,474,200 vs 13,855,000.
Material variances: 8 of 13 lines (|variance| >= 100,000, or >= 10.0% and >= 10,000).

## 1. Variance table

| Line | Type | Budget | Actual | Variance | Var % | F/A | Material |
|---|---|---|---|---|---|---|---|
| Sales standard pumps | revenue | 10,000,000 | 11,132,000 | 1,132,000 | 11.3% | F | yes |
| Sales premium pumps | revenue | 3,900,000 | 2,743,500 | -1,156,500 | -29.7% | A | yes |
| Sales spare parts | revenue | 2,700,000 | 2,736,000 | 36,000 | 1.3% | F |  |
| Service contracts | revenue | 1,250,000 | 1,180,000 | -70,000 | -5.6% | A |  |
| Cost of goods standard pumps | cost | 6,000,000 | 7,268,000 | 1,268,000 | 21.1% | A | yes |
| Cost of goods premium pumps | cost | 2,250,000 | 1,627,500 | -622,500 | -27.7% | F | yes |
| Cost of goods spare parts | cost | 1,215,000 | 1,232,500 | 17,500 | 1.4% | A |  |
| Freight | cost | 410,000 | 512,300 | 102,300 | 25.0% | A | yes |
| Salaries | cost | 2,950,000 | 2,987,400 | 37,400 | 1.3% | A |  |
| Marketing | cost | 380,000 | 214,600 | -165,400 | -43.5% | F | yes |
| IT and software | cost | 260,000 | 301,900 | 41,900 | 16.1% | A | yes |
| Rent | cost | 330,000 | 330,000 | 0 | 0.0% | - |  |
| Travel | cost | 60,000 | 0 | -60,000 | -100.0% | F | yes |

## 2. Material variances and drivers

| Line | Variance | Var % | F/A | Drivers |
|---|---|---|---|---|
| Cost of goods standard pumps | 1,268,000 | 21.1% | A | volume 900,000, unit cost 368,000 (unit cost 1,580.00 vs 1,500.00 per unit) |
| Sales premium pumps | -1,156,500 | -29.7% | A | volume -1,170,000, price 13,500 (price 2,612.86 vs 2,600.00 per unit) |
| Sales standard pumps | 1,132,000 | 11.3% | F | volume 1,500,000, price -368,000 (price 2,420.00 vs 2,500.00 per unit) |
| Cost of goods premium pumps | -622,500 | -27.7% | F | volume -675,000, unit cost 52,500 (unit cost 1,550.00 vs 1,500.00 per unit) |
| Marketing | -165,400 | -43.5% | F | no quantities: ask the budget owner (timing, one-off, rate?) |
| Freight | 102,300 | 25.0% | A | no quantities: ask the budget owner (timing, one-off, rate?) |
| Travel | -60,000 | -100.0% | F | no quantities: ask the budget owner (timing, one-off, rate?) |
| IT and software | 41,900 | 16.1% | A | no quantities: ask the budget owner (timing, one-off, rate?) |

## 3. Reconciliation checks

| Check | Expected | Calculated | Result |
|---|---|---|---|
| sum of line profit effects = result variance | -677,700.00 | -677,700.00 | OK |
| price + volume = variance on lines with quantities | 674,500.00 | 674,500.00 | OK |
| control total 'Operating result (from P&L report)' budget = revenue - cost | 3,995,000.00 | 3,995,000.00 | OK |
| control total 'Operating result (from P&L report)' actual = revenue - cost | 3,269,100.00 | 3,317,300.00 | FAIL |

## 4. Data quality and assumptions

- line 14 (Travel): budget or actual missing; treated as 0, check the source
- control total 'Operating result (from P&L report)' (actual) 3,269,100.00 differs from computed 3,317,300.00 by 48,200.00: a line is missing, duplicated or has a sign error
- Cost sign convention: positive. F/A follows the profit effect: revenue above budget and cost below budget are favourable.
- Price/volume split uses budget price for volume and actual quantity for price; driver amounts are signed like the variance (actual - budget). Mix is not separated.

## Interpretation

- Operating result is 677,700 below budget on the lines provided. But the reconciliation check fails: the P&L report shows an actual result of 3,269,100, 48,200 lower than the lines add up to, because the Travel actual is blank in the file. Fix that before the board sees it.
- Standard pumps sold 600 more units (+1.5m volume) but at 80 below budget price (-368k), while unit cost rose 80 (+368k adverse): extra volume was bought with discounts and absorbed by higher cost.
- Premium pumps were 450 units short (-1.17m revenue), partly offset by 675k lower cost of goods.
- Freight (+102k) and IT (+42k, 16 %) are adverse; Marketing is 165k under budget, likely timing. Ask the owners to confirm before calling it a saving.
