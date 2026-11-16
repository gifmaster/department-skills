# Worked example: inventory policy for a plumbing wholesaler

## User request

> Lars, purchasing manager at a plumbing and heating wholesaler in Aalborg: "Can you set safety stock, reorder point and order quantity for our main items at 95 % service? Order cost is 350 kr, holding 22 % a year. The pump kit is the one we keep running out of, so 90 % is fine there given the price. Last column is what is on the shelf today."

Demand was converted to per day and lead time kept in days before running the script (see the template).

## Command

```
python3 scripts/inventory_params.py assets/inventory_items.csv
```

## Output

# Inventory policy parameters

**8 items.** Proposed average inventory value 250,070; current value (items with stock data) 200,880; change 49,190.

## 1. Parameters per item

| Item | CSL | z | sigma LT | SS calc | Safety stock | Reorder point | EOQ | Order qty | Cycle days | Exp. fill rate |
|---|---|---|---|---|---|---|---|---|---|---|
| HX-210 Hose clamp 20-32 | 95.0 % | 1.645 | 224.8 | 369.8 | 370 | 1,210 | 3,810 | 3,900 | 65 | 99.9 % |
| HX-344 Ball valve 1in | 95.0 % | 1.645 | 105.2 | 173.0 | 173 | 499 | 303 | 310 | 33 | 99.3 % |
| HX-501 Pressure gauge 63mm | 95.0 % | 1.645 | 31.5 | 51.8 | 52 | 136 | 220 | 220 | 55 | 99.7 % |
| HX-722 Brass fitting 3/4 | 95.0 % | 1.645 | 76.5 | 125.8 | 126 | 426 | 1,258 | 1,300 | 43 | 99.9 % |
| HX-901 Pump kit OEM | 90.0 % | 1.282 | 18.6 | 23.9 | 24 | 73 | 24 | 25 | 29 | 96.5 % |
| HX-118 PTFE tape | 95.0 % | 1.645 | 197.8 | 325.4 | 326 | 1,222 | 6,816 | 7,000 | 55 | 99.9 % |
| HX-430 Thermostatic valve | 95.0 % | 1.645 | 150.6 | 247.8 | 248 | 353 | 177 | 180 | 36 | 98.3 % |
| HX-615 Radiator bracket | 95.0 % | 1.645 | 6.9 | 11.3 | 12 | 40 | 258 | 275 | 138 | 99.9 % |

## 2. Formulas used

- sigma LT = sqrt(L x sd_d^2 + d^2 x sd_L^2), demand and lead-time variability combined
- Safety stock = ceil(z x sigma LT); z from cycle service level (CSL)
- Reorder point = ceil(d x L + safety stock)
- EOQ = sqrt(2 x d x 365 x order cost / (unit cost x holding rate)); order qty = max(EOQ, MOQ) rounded up to whole packs
- CSL is the chance of no stock-out per cycle, not the fill rate; expected fill rate = 1 - sigma LT x G(z) / order qty

## 3. Inventory value impact

| Item | Current stock | Current value | Proposed avg stock (SS + Q/2) | Proposed value | Change |
|---|---|---|---|---|---|
| HX-210 Hose clamp 20-32 | 5,200 | 24,960 | 2,320 | 11,136 | -13,824 |
| HX-344 Ball valve 1in | 220 | 25,960 | 328 | 38,704 | 12,744 |
| HX-501 Pressure gauge 63mm | 310 | 29,760 | 162 | 15,552 | -14,208 |
| HX-722 Brass fitting 3/4 | 600 | 13,200 | 776 | 17,072 | 3,872 |
| HX-901 Pump kit OEM | 12 | 28,800 | 36 | 87,600 | 58,800 |
| HX-118 PTFE tape | 9,000 | 28,800 | 3,826 | 12,243 | -16,557 |
| HX-430 Thermostatic valve | 40 | 7,400 | 338 | 62,530 | 55,130 |
| HX-615 Radiator bracket | 1,200 | 42,000 | 150 | 5,232 | -36,768 |
| **Total (items with current stock)** |  | 200,880 |  | 250,070 | 49,190 |

## 4. Items needing manual review

- **HX-901 Pump kit OEM**: lumpy or slow-moving (daily CoV 2.21): normal formula unreliable, or SD is not per day
- **HX-430 Thermostatic valve**: UNITS? lead-time SD exceeds lead time, check both are in days
- **HX-615 Radiator bracket**: UNITS? current stock covers 600 days, check demand is per day not per week/month

## Data-quality warnings

- HX-430 Thermostatic valve: holding_rate 22.00 read as a percentage (22.0 %).
- Line 10 (HX-260 Pipe insulation 22mm): missing unit_cost, row skipped.
- Line 11: duplicate item 'HX-210 Hose clamp 20-32', only the first row is used.

## Interpretation

- Safety stock includes lead-time variability, so ball valves (HX-344) need 173 units: about 80 % of their variance comes from the supplier's 10-day lead-time spread, not from demand.
- Total value rises by about 49,000 kr, driven by the pump kit and HX-430. Hose clamps, gauges, PTFE tape and radiator brackets are overstocked today and free about 81,000 kr between them.
- HX-430 cannot be trusted yet: a lead-time SD of 30 days against a 21-day lead time looks like a unit error. Please confirm before loading it into the ERP.
- HX-615 shows 600 days of cover, so either demand is not per day or the stock is genuinely dead.
- The pump kit is lumpy; 24 units at 90 % is a starting point, not a statistical guarantee. HX-260 was skipped (no unit cost) and the duplicate HX-210 row was ignored.
