# Worked example: October OTIF for a building-materials manufacturer

## User request

> Henrik, COO at a building-materials manufacturer in Skive: "Our ERP dashboard says OTIF 82 % for October but STARK and Bygma are complaining. Here is a sample of October delivery lines. What is our real OTIF, why are we missing, and what do we fix first?"

## Command

```
python3 scripts/otif.py assets/order_lines.csv
```

## Output

# OTIF and fill-rate analysis

**Line OTIF 52.9 % (9 of 17 lines), order OTIF 46.7 % (7 of 15 orders), fill rate 94.4 %.** Measured against the promised date, as of 2026-10-30.

## 1. KPI definitions

- On time: line completed (cumulative qty reached the in-full level) on or before promised date + 0 day(s); early counts as on time
- In full: total delivered >= ordered x (1 - 0.0 %)
- OTIF line = on time and in full; OTIF order = all lines OTIF; partial deliveries are combined per line
- Fill rate = delivered (capped at ordered) / ordered

## 2. KPI results

| KPI | Line level | Order level |
|---|---|---|
| On time | 58.8 % | 53.3 % |
| In full | 88.2 % | 86.7 % |
| **OTIF** | **52.9 %** | **46.7 %** |
| Fill rate (units) | 94.4 % |  |
| On-time fill rate (units) | 65.0 % |  |

Lines evaluated 17, open (not yet due) 0, partial 3, split deliveries 1, average days late 2.5.

### By customer (worst first)

| Name | Lines | On time | In full | OTIF | Fill rate |
|---|---|---|---|---|---|
| XL-Byg | 3 | 66.7 % | 66.7 % | 33.3 % | 91.9 % |
| STARK | 5 | 40.0 % | 80.0 % | 40.0 % | 87.7 % |
| Bygma | 6 | 66.7 % | 100.0 % | 66.7 % | 100.0 % |
| Davidsen | 3 | 66.7 % | 100.0 % | 66.7 % | 100.0 % |

### By item (worst first)

| Name | Lines | On time | In full | OTIF | Fill rate |
|---|---|---|---|---|---|
| C33 | 5 | 40.0 % | 60.0 % | 20.0 % | 73.0 % |
| A12 | 5 | 60.0 % | 100.0 % | 60.0 % | 100.0 % |
| D90 | 3 | 66.7 % | 100.0 % | 66.7 % | 100.0 % |
| B07 | 4 | 75.0 % | 100.0 % | 75.0 % | 100.0 % |

## 3. Root cause Pareto (missed lines)

| Reason | Lines | Share | Cumulative | Orders |
|---|---|---|---|---|
| stock | 4 | 50.0 % | 50.0 % | SO-8804, SO-8806, SO-8811, SO-8815 |
| (no reason given) | 1 | 12.5 % | 62.5 % | SO-8814 |
| capacity | 1 | 12.5 % | 75.0 % | SO-8812 |
| data | 1 | 12.5 % | 87.5 % | SO-8808 |
| transport | 1 | 12.5 % | 100.0 % | SO-8803 |

Missed lines:

| Order | Line | Customer | Item | Promised | Miss | Days late | Delivered/ordered | Reason |
|---|---|---|---|---|---|---|---|---|
| SO-8803 | 1 | XL-Byg | A12 | 2026-10-05 | late | 2 | 60/60 | transport |
| SO-8804 | 1 | Davidsen | C33 | 2026-10-06 | late | 3 | 25/25 | stock |
| SO-8806 | 1 | Bygma | C33 | 2026-10-08 | late | 5 | 30/30 | stock |
| SO-8808 | 1 | STARK | D90 | 2026-10-13 | late | 1 | 10/10 | data |
| SO-8811 | 1 | XL-Byg | C33 | 2026-10-19 | short | 0 | 30/45 | stock |
| SO-8812 | 1 | STARK | B07 | 2026-10-20 | late | 2 | 70/70 | capacity |
| SO-8814 | 1 | Bygma | A12 | 2026-10-28 | late | 2 | 90/90 | (no reason given) |
| SO-8815 | 1 | STARK | C33 | 2026-10-27 | not delivered | - | 0/35 | stock |

## 4. Action plan inputs

- Start with the top Pareto reason (stock); small samples make the Pareto indicative only.
- Worst customer: XL-Byg; worst item: C33.

## Data-quality warnings

- Order SO-8816 line 1: over-delivered 62 of 60; capped at ordered for fill rate.
- 1 missed line(s) have no reason code; Pareto is incomplete.

## Interpretation

- Strict line OTIF against the promised date is 52.9 %, not 82 %. The dashboard figure is closer to unit fill rate (94.4 %), so check what the ERP actually measures before talking to customers.
- Lateness, not quantity, is the main problem: 58.8 % on time against 88.2 % in full.
- Stock causes half of the misses, and every stock miss is item C33 (20 % OTIF). Review C33's safety stock and reorder point first.
- SO-8814 is late with no reason code, and SO-8816 was over-delivered (62 of 60). Fix the coding so next month's Pareto is complete.
- 17 lines is a small sample; rerun on the full October extract before setting targets.
