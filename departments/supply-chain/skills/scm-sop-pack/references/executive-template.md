# One-page executive S&OP template
Use: Read when building the executive summary page of an S&OP or IBP pack; follow the layout, use the KPI definitions and formulas exactly, and carry the decision log over from last month.

Rule: the executive page fits on one page (about 400 words plus the tables). Detail goes in the appendix sections of the pack. All numbers come from the user's data; label assumptions. Example names and figures are fictional.

## 1. Page layout

```
[Company] S&OP executive review, [month YYYY]      Cycle: [n]   Horizon: [3 to 18] months
Prepared by: [demand planner / supply planner / finance]      Meeting: [date]

A. Three messages                     (3 bullets, one line each, most important first)
B. Decisions needed today             (table, max 3 decisions)
C. KPI panel                          (table, actual vs target vs last month, RAG)
D. Scenarios                          (table, base / upside / downside)
E. Key risks and opportunities        (max 4 bullets, each with owner)
F. Decision log follow-up             (open items from last month)
```

### A. Three messages

1. [Demand: what changed versus last plan and why, in units and DKK]
2. [Supply: biggest gap or constraint, which family and month]
3. [Finance: plan versus budget revenue and margin, and the main driver]

Write each as a finding, not a heading. Example: "Demand for Family B is up 12% for Q2 after a new retail listing; capacity on Line 2 is short by 1,800 hours in April and May."

### B. Decisions needed today

| # | Decision | Option 1 | Option 2 | Option 3 | Volume impact | Cost impact | Service impact | Recommendation |
|---|---|---|---|---|---|---|---|---|
| 1 | [for example close the Line 2 gap in Apr and May] | [overtime] | [outsource] | [accept lower fill rate on low-margin SKUs] | [units] | [DKK] | [fill rate %] | [option and why] |
| 2 | | | | | | | | |
| 3 | | | | | | | | |

### C. KPI panel

| KPI | Actual [month] | Target | Last month | 3-month trend | RAG | Comment |
|---|---|---|---|---|---|---|
| Forecast accuracy (1 minus WAPE), lag [1] | [ ] % | [ ] % | [ ] % | [up/down/flat] | | |
| Forecast bias | [ ] % | within +/- [5] % | [ ] % | | | |
| OTIF | [ ] % | [ ] % | [ ] % | | | |
| Fill rate (units) | [ ] % | [ ] % | [ ] % | | | |
| Days of inventory | [ ] days | [ ] days | [ ] days | | | |
| Capacity utilisation (bottleneck) | [ ] % | [ ] % | [ ] % | | | |
| Plan versus budget revenue | [ ] % | 0 % | [ ] % | | | |

RAG rule (default, change to company policy): green on or better than target; amber within [5] % of target; red worse than that.

### D. Scenarios

| | Downside | Base | Upside |
|---|---|---|---|
| Key assumption | [for example listing delayed 2 months] | [current plan] | [for example second retailer from June] |
| Demand, units (horizon) | [ ] | [ ] | [ ] |
| Revenue, DKK | [ ] | [ ] | [ ] |
| Gross margin, DKK and % | [ ] | [ ] | [ ] |
| Capacity gap, hours (bottleneck) | [ ] | [ ] | [ ] |
| Inventory at end of horizon, days | [ ] | [ ] | [ ] |
| Fill rate projected | [ ] % | [ ] % | [ ] % |
| Probability (planner's view) | [ ] % | [ ] % | [ ] % |
| Trigger to switch plan | [signal and date] | | [signal and date] |
| Actions if it happens | [ ] | | [ ] |

### E. Key risks and opportunities

| Risk or opportunity | Family / month | Impact (DKK or units) | Likelihood | Owner | Mitigation |
|---|---|---|---|---|---|
| [ ] | [ ] | [ ] | [H/M/L] | [ ] | [ ] |

Include regulatory or supplier risks that affect supply (for example a supplier exposed to EUDR from 30 Dec 2026 or sanctions screening gaps; see facts/supply-chain.md) only where they are real for the business.

### F. Decision log

Carry every open line from last month. Close a line only when the action is done and the effect is visible.

| ID | Date decided | Decision | Option chosen | Owner | Due | Expected effect | Status | Result / comment |
|---|---|---|---|---|---|---|---|---|
| [YYYY-MM-01] | [date] | [ ] | [ ] | [ ] | [date] | [for example fill rate +3 pp on Family B] | Open / Done / Overdue / Dropped | [ ] |

## 2. KPI definitions and formulas

Use the same definitions every month. If the company defines a KPI differently, write its definition in the comment column and keep it fixed.

| KPI | Definition | Formula | Notes |
|---|---|---|---|
| WAPE (weighted absolute percentage error) | Size of forecast error weighted by volume | sum over items of abs(actual - forecast) / sum of actual x 100 | Measure at the level the plan is made (family or SKU) and at a fixed lag, for example the forecast made 1 month before |
| Forecast accuracy | Share of demand forecast correctly | 100 % - WAPE | Can be negative if WAPE is over 100 %; floor at 0 % only if the company does so, and say so |
| Forecast bias | Systematic over- or under-forecasting | sum of (forecast - actual) / sum of actual x 100 | Positive = over-forecast (inventory risk); negative = under-forecast (service risk) |
| OTIF (on time in full) | Orders delivered complete on the promised date | orders delivered on time and in full / total orders delivered x 100 | Measured against the promised date unless agreed otherwise; state the tolerance window (for example 0 days early, 0 days late) |
| Fill rate (unit) | Share of ordered units shipped from stock on first shipment | units shipped on first shipment / units ordered x 100 | State whether line or unit based |
| Days of inventory (days of supply, backward) | How many days of cost of sales the stock covers | inventory value at cost / (cost of goods sold for the period / days in period) | For projections use forward cover: inventory / average forecast daily demand |
| Capacity utilisation | Load as share of available capacity at the bottleneck | required hours (load) / available hours x 100 | Available hours = shifts x hours x efficiency; flag over [85] % as a planning risk |
| Plan versus budget revenue | Gap between the current plan and the approved budget | (plan revenue - budget revenue) / budget revenue x 100 | Show volume, price and mix effects separately in the financial section |
| Volume to revenue reconciliation | Check that units and money agree | sum over families of (units x average net price) = plan revenue | Difference over [1] % must be explained |

Optional supply KPIs for the appendix:

| KPI | Formula |
|---|---|
| Safety stock (demand and lead time vary) | z x sqrt(LT x sd_d^2 + d^2 x sd_LT^2) |
| Reorder point | d x LT + safety stock |
| Supplier OTIF | supplier lines received on time and in full / total supplier lines x 100 |
| Schedule adherence | planned production quantity achieved in the planned period / planned quantity x 100 |

## 3. Pre-meeting checklist

- [ ] Demand, supply and finance numbers come from the same plan version and cut-off date: [date]
- [ ] Volumes reconcile to revenue within [1] %
- [ ] Every supply gap has at least one option with volume, cost and service impact
- [ ] Last month's decision log updated before the meeting
- [ ] KPI definitions unchanged from last month (or the change is stated)
- [ ] Scenarios differ by named assumptions, not by percentage uplifts alone
- [ ] Assumptions listed: lead times, service level targets, costs, prices

## 4. Example (fictional): three messages for "Example Foods ApS"

1. Demand for Family B (frozen ready meals) is up 12% for April to June versus last plan after a new retail listing; Families A and C are unchanged.
2. Line 2 is short by 1,800 hours in April and May at the current shift pattern; without action, fill rate on Family B falls to about 88% against a 96% target.
3. Plan revenue for the year is 3.1% above budget, but gross margin is 0.4 pp below because of the overtime premium in options 1 and 2.
