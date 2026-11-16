# Worked example: savings from 12 months of AP spend

## User request

> Thomas, CFO at a home-goods e-commerce and wholesale company in Taastrup: "Here is an AP extract of our top indirect and logistics suppliers for this year. Where can we save? The board wants a number."

## Command

```
python3 scripts/spend.py assets/ap_spend.csv
```

## Output

# Spend analysis

**Total spend 2,359,300 on 18 lines, 2026-01-15 to 2026-09-30. 16 supplier names grouped into 13 suppliers; 7 suppliers make up 80 % of spend.**

## 1. Spend overview

### Supplier normalisation

- Grouped as **Lyreco Danmark A/S**: LYRECO DK; Lyreco Danmark A/S
- Grouped as **Smurfit Westrock Danmark A/S**: Smurfit Westrock Danmark A/S; Smurfit Westrok Danmark
- Grouped as **Ahlsell Danmark ApS**: Ahlsell DK ApS; Ahlsell Danmark ApS
- Fuzzy merge: 'smurfit westrok' into 'smurfit westrock' (similarity 0.97)
- Not merged, please confirm: DSV A/S / DSV Road A/S (words contained, 0.55); Lyreco Danmark A/S / Staples / Lyreco (words contained, 0.60)

### Supplier Pareto

| Supplier | Spend | Share | Cumulative | Tail |
|---|---|---|---|---|
| Smurfit Westrock Danmark A/S | 637,500 | 27.0 % | 27.0 % |  |
| DSV Road A/S | 412,000 | 17.5 % | 44.5 % |  |
| DSV A/S | 286,000 | 12.1 % | 56.6 % |  |
| Würth Danmark A/S | 192,000 | 8.1 % | 64.7 % |  |
| Schur Pack Danmark A/S | 187,000 | 7.9 % | 72.7 % |  |
| PostNord Danmark A/S | 158,000 | 6.7 % | 79.4 % |  |
| GLS Denmark | 141,000 | 6.0 % | 85.3 % |  |
| Ahlsell Danmark ApS | 111,000 | 4.7 % | 90.0 % | yes |
| Jysk Industri-Service ApS | 91,000 | 3.9 % | 93.9 % | yes |
| Lyreco Danmark A/S | 61,100 | 2.6 % | 96.5 % | yes |
| Emballagegruppen ApS | 54,000 | 2.3 % | 98.8 % | yes |
| Amazon EU S.à r.l. | 22,400 | 0.9 % | 99.7 % | yes |
| Staples / Lyreco | 6,300 | 0.3 % | 100.0 % | yes |

Tail spend (suppliers in the last 20 % of spend): 6 suppliers, 345,800 (14.7 %).

## 2. Category breakdown

| Category | Spend | Share | Suppliers | Top supplier (share) | Fragmented |
|---|---|---|---|---|---|
| Freight and logistics | 997,000 | 42.3 % | 4 | DSV Road A/S (41 %) | yes |
| Packaging | 878,500 | 37.2 % | 3 | Smurfit Westrock Danmark A/S (73 %) | yes |
| MRO, tools and fasteners | 303,000 | 12.8 % | 2 | Würth Danmark A/S (63 %) |  |
| Cleaning and facilities | 91,000 | 3.9 % | 1 | Jysk Industri-Service ApS (100 %) |  |
| Office supplies | 67,400 | 2.9 % | 2 | Lyreco Danmark A/S (91 %) |  |
| Uncategorised | 22,400 | 0.9 % | 1 | Amazon EU S.à r.l. (100 %) |  |

Categorisation rules applied:

- Cleaning and facilities: 'rengoring' in description
- Freight and logistics: 'fragt' in description
- Freight and logistics: 'freight' in description
- Freight and logistics: 'pakke' in description
- MRO, tools and fasteners: 'el materiale' in description
- MRO, tools and fasteners: 'skrue' in description
- MRO, tools and fasteners: 'vaerktoj' in description
- Office supplies: 'kontor' in description
- Office supplies: 'office' in description
- Office supplies: 'toner' in description
- Packaging: 'karton' in description
- Packaging: supplier's main category
- Uncategorised: no rule matched

## 3. Opportunities with estimated savings (ESTIMATE, not validated with suppliers)

| Opportunity | Spend base | Low | High | Assumption |
|---|---|---|---|---|
| Consolidate Freight and logistics (4 suppliers, top DSV Road A/S at 41 %) | 997,000 | 49,850 | 99,700 | 5-10 % from consolidation or re-tender |
| Consolidate Packaging (3 suppliers, top Smurfit Westrock Danmark A/S at 73 %) | 878,500 | 43,925 | 87,850 | 5-10 % from consolidation or re-tender |
| Tail spend outside fragmented categories (6 tail suppliers in total) | 291,800 | 14,590 | 43,770 | 5-15 % via catalogue, preferred suppliers or p-card |
| **Total estimate range** |  | **108,365** | **231,320** | before implementation cost |

Estimated range: 108,365 to 231,320 a year on this extract (4.6 % to 9.8 % of spend). These are planning estimates from the percentages above, not promises.

## 4. Next steps

- Confirm the supplier groupings and the pairs listed for review
- Categorise the uncategorised spend (22,400) with a --categories JSON or account map
- Check possible duplicate payments and credit notes listed below
- Validate the savings percentages with contract and price data before quoting a number

## Data-quality warnings

- Line 19 (Smurfit Westrock Danmark A/S): negative amount -18,000 (credit note), netted against the supplier.
- Possible duplicate payment (lines 15 and 16: Würth Danmark A/S 96,000.00 on 2026-09-01); kept in totals, check before acting.

## Interpretation

- Freight and packaging are nearly 80 % of this extract, and both are fragmented, so they are where the savings are.
- For the board, a range: about 108,000 to 231,000 kr a year (4.6 to 9.8 % of this extract), before implementation cost and not yet tested with suppliers. Do not scale it up to total spend without seeing the rest of the data.
- Confirm two groupings before acting: DSV A/S and DSV Road A/S (same group, possibly separate contracts) and "Staples / Lyreco". If DSV is one supplier, freight drops to three suppliers.
- The second Würth invoice (96,000 kr, same date and text) may be a duplicate payment and is worth checking first, since it could be cash back straight away.
- The Amazon spend (22,400 kr) is uncategorised, off-contract spend: a purchasing-policy issue more than a price issue.
