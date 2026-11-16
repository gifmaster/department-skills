# Worked example: ABC-XYZ on spare parts

## User request

> Mette, aftersales planner at a pump manufacturer in Odense: "Can you do an ABC-XYZ on a sample of our spare parts? Six months of consumption from Navision, quantities per month plus standard cost. VP-440 is the new seal kit that only started in September. Tell me how to manage each group."

## Command

```
python3 scripts/abcxyz.py assets/abcxyz_consumption.csv
```

## Output

# ABC-XYZ segmentation

**3 items segmented, 1 with too little history.** Window 2026-05 to 2026-10 (6 periods). Total value 77,585.

## 1. Thresholds used

- ABC on value (quantity x unit value, run-rate scaled to the window): A up to 80 % cumulative, B up to 95 %, C above
- XYZ on CoV = population SD / mean, zero periods included: X below 0.50, Y below 1.00, Z from 1.00
- Intermittent if zero periods >= 30 %; lumpy if also CoV of non-zero periods >= 0.70
- Items with fewer than 6 periods of history are listed separately

## 2. Segmentation table

| Item | Qty | Value | Share | Cum. | Mean/period | SD | CoV | Zero periods | Pattern | Segment |
|---|---|---|---|---|---|---|---|---|---|---|
| VP-110 Impeller bronze 160 | 12 | 31,800 | 41.0 % | 41.0 % | 2.00 | 2.08 | 1.04 | 50 % | intermittent | **AZ** |
| VP-220 Bearing 6205-2RS | 820 | 31,160 | 40.2 % | 81.1 % | 136.67 | 12.80 | 0.09 | 0 % | smooth | **BX** |
| VP-330 O-ring kit NBR | 225 | 14,625 | 18.9 % | 100.0 % | 37.50 | 58.79 | 1.57 | 17 % | erratic | **CZ** |

### 9-box (count / value / share of value)

|  | X | Y | Z |
|---|---|---|---|
| A | 0 / 0 / 0.0 % | 0 / 0 / 0.0 % | 1 / 31,800 / 41.0 % |
| B | 1 / 31,160 / 40.2 % | 0 / 0 / 0.0 % | 0 / 0 / 0.0 % |
| C | 0 / 0 / 0.0 % | 0 / 0 / 0.0 % | 1 / 14,625 / 18.9 % |

## 3. Policies per segment

- **AZ** (VP-110 Impeller bronze 160): No normal-distribution safety stock: small fixed buffer agreed with sales/service, order to demand, ask for consignment
- **BX** (VP-220 Bearing 6205-2RS): Reorder point or min-max, 95 % CSL, periodic review
- **CZ** (VP-330 O-ring kit NBR): Order on demand or delist; keep only labelled insurance stock if critical
- Intermittent or lumpy demand (VP-110 Impeller bronze 160): use min-max or Croston-type logic, not a normal safety stock

## 4. Delisting candidates and items handled separately

- No demand in the last 6 periods: none
- CZ items to consider for order on demand or delisting: VP-330 O-ring kit NBR
- Too little history (not ranked, classify by hand or merge with a predecessor item):
  - VP-440 Seal kit v2: 2 periods from 2026-09, qty 23, value 10,235, run-rate value 30,705

## Data-quality warnings

- Line 4 (VP-110 Impeller bronze 160 2026-07): missing unit_value, 2,650.00 from another row used.
- Line 17 (VP-330 O-ring kit NBR 2026-08): negative quantity -90 (return or sign error), netted into the period.

## Interpretation

- With only three ranked items the ABC cut-offs are coarse: the bearing lands in B at 81.1 % cumulative, only 1 point past the A limit. On the full range the same rules give a more typical split.
- The impeller is AZ and intermittent (zero in half the months): hold a small agreed buffer rather than a statistical safety stock.
- The O-ring kit only looks CZ because of the -90 in August. If that is a return booked as consumption, correct it and rerun: with +90 it becomes a stable CX item and the bearing moves into A, which shows how sensitive a small sample is.
- VP-440 has two months of history and is not ranked. Its run-rate value (about 30,700) would put it near the top, so plan it together with the item it replaced.
