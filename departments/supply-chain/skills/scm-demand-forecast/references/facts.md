---
last_verified: 2026-11-17
owner: Alexander Senderovitz (update at least quarterly and after any law change)
---

# Supply Chain: regulatory facts and figures

Dated, sourced figures the skills in this pack rely on. Rule for the assistant: use these values, cite the source line, and say "verify" for anything marked (verify) or not listed here. Figures marked (verify) were checked against secondary sources only.

## Trade, customs and sanctions

| Rule | Value | Source |
|---|---|---|
| Incoterms | Incoterms 2020 (ICC); sea-only rules FAS, FOB, CFR, CIF; use FCA, CPT, CIP, DAP, DPU, DDP for containers handed over inland | ICC |
| EU customs | Union Customs Code; duties and measures in TARIC; Binding Tariff Information via Toldstyrelsen | Regulation (EU) 952/2013 |
| CBAM | Covers specific CN codes for iron and steel, aluminium, cement, fertilisers, hydrogen and electricity, including some downstream articles; 2025 simplification added a 50-tonne a year de minimis per importer across iron and steel, aluminium, fertilisers and cement (not for electricity or hydrogen); exceed it and all that year's imports are covered; check by CN code, not material | Regulation (EU) 2023/956 as amended by Regulation (EU) 2025/2083 |
| Sanctions | Screen counterparties against the EU consolidated list; also origin-based import bans (e.g. Russian and Belarusian wood and steel) that list screening does not catch | EU sanctions regulations |

## Sustainability and due diligence

| Rule | Value | Source |
|---|---|---|
| CSDDD after Omnibus I | Applies to EU companies with more than 5,000 employees and EUR 1.5bn net worldwide turnover (non-EU: EUR 1.5bn EU turnover); SMEs affected through customer contracts; compliance date 26 Jul 2029 (verify) | Directive (EU) 2026/470; Latham & Watkins summary |
| EUDR (deforestation) | Applies from 30 Dec 2026 for large and medium operators and for micro and small operators already covered by the EU Timber Regulation; 30 Jun 2027 for other micro and small (size classes per Directive 2013/34/EU); covers cattle, cocoa, coffee, oil palm, natural rubber, soy, wood (incl. furniture) and derived products | Regulation (EU) 2023/1115 as amended by Regulation (EU) 2025/2650 |
| Forced Labour Regulation | Products made with forced labour banned from being placed on, made available on or exported from the EU market from 14 Dec 2027, all company sizes; directly applicable | Regulation (EU) 2024/3015 |
| Destruction of unsold apparel and footwear (ESPR Art. 25) | Banned for large enterprises from 19 Jul 2026, medium from 19 Jul 2030; micro and small exempt; consumer returns count as unsold | Regulation (EU) 2024/1781 (verify) |
| CSRD after Omnibus I | Only above 1,000 employees and EUR 450m turnover (both); SMEs usually report to customers or under VSME | Directive (EU) 2026/470 |
| Neutrality claims | Product claims of neutral or reduced impact based on offsetting banned from 27 Sep 2026 | Directive (EU) 2024/825 |
| Due diligence method | OECD Due Diligence Guidance for Responsible Business Conduct | OECD |

## Working time and safety (Denmark)

| Rule | Value | Source |
|---|---|---|
| Working time | Average 48-hour week, 11 hours' daily rest, one rest day in each 7 days; collective agreements may set stricter rules | Working Time Directive 2003/88/EC; Danish implementation |
| Manual handling and ergonomics | Working Environment Act and Arbejdstilsynet guidance | arbejdsmiljøloven |

## Planning formulas (reference)

- Safety stock (demand and lead time vary): z x sqrt(LT x sd_d^2 + d^2 x sd_LT^2)
- Reorder point: d x LT + safety stock
- EOQ: sqrt(2 x annual demand x order cost / (unit cost x holding rate))
- OTIF measured against the promised date unless agreed otherwise
