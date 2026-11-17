# Worked example: Licence review

## User request

> Havnens Arkitekter ApS, 10 people. The CFO wants to cut software costs. Here is our subscription list from the reseller and per-user activity from the admin portals. Where can we save, and what do we have to do before which date?

## Command run (from the skill folder, on the sample assets)

```
python3 scripts/licences.py assets/subscriptions_template.csv --usage assets/usage_template.csv --today 2026-11-16
```

## Output

~~~~text
# Licence review (as of 2026-11-16, inactive after 90 days)

**Spend 5,525 per month (66,300 per year). Unused licences 15, waste 1,510 per month (18,120 per year). Savings estimate 12,240 per year with a 5% buffer, 6,172 realisable in the next 12 months given notice deadlines.**

## 1. Licence position
| Product | Licences | Active | Utilisation | Unused | Cost/month | Waste/month | Flags |
|---|---:|---:|---:|---:|---:|---:|---|
| Adobe Acrobat Pro | 5 | 2 | 40% | 3 | 700 | 420 | notice deadline in 30 days |
| Slack Pro | 6 | 0 | 0% | 6 | 390 | 390 | no active users: cancel candidate; notice deadline 2026-11-11 passed: renews 2027-01-10, next exit 2028-01-10 (notice by 2027-11-11) |
| Microsoft 365 Business Premium | 10 | 8 | 80% | 2 | 1,650 | 330 | notice deadline in 75 days |
| Zoom Pro | 3 | 1 | 33% | 2 | 330 | 220 | notice deadline in 15 days |
| Miro Business | 4 | 2 | 50% | 2 | 300 | 150 | notice deadline in 56 days |
| Visio Plan 2 | 2 | - | - | - | 230 | - | notice deadline in 75 days |
| AutoCAD LT | 3 | 4 | 133% | 0 | 1,545 | 0 | 1 more active users than licences (compliance risk) |
| TeamViewer Business | 1 | 1 | 100% | 0 | 230 | 0 |  |
| AnyDesk Standard | 1 | 1 | 100% | 0 | 150 | 0 | notice deadline in 4 days |
| Penneo | 2 | - | - | - | - | - |  |

## 2. Savings opportunities (respecting notice periods)
| Product | Keep | Cut | Saving/year | Earliest effective | Give notice by | Saving next 12 months |
|---|---:|---:|---:|---|---|---:|
| Slack Pro | 0 | 6 | 4,680 | 2028-01-10 | 2027-11-11 | 0 |
| Adobe Acrobat Pro | 3 | 2 | 3,360 | 2027-01-15 | 2026-12-16 | 2,808 |
| Microsoft 365 Business Premium | 9 | 1 | 1,980 | 2027-03-01 | 2027-01-30 | 1,410 |
| Zoom Pro | 2 | 1 | 1,320 | 2026-12-01 | 2026-12-01 | 1,266 |
| Miro Business | 3 | 1 | 900 | 2027-02-10 | 2027-01-11 | 688 |

## 3. Duplicate tools
- chat: Microsoft 365 Business Premium, Slack Pro (combined 2,040 per month)
- remote support: TeamViewer Business, AnyDesk Standard (combined 380 per month)
- video meetings: Microsoft 365 Business Premium, Zoom Pro (combined 1,980 per month)

## 4. Renewals and notice deadlines (next 90 days)
| Product | Next renewal | Notice days | Act by | Days left |
|---|---|---:|---|---:|
| AnyDesk Standard | 2026-12-20 | 30 | 2026-11-20 | 4 |
| Zoom Pro | 2026-12-01 | 0 | 2026-12-01 | 15 |
| Adobe Acrobat Pro | 2027-01-15 | 30 | 2026-12-16 | 30 |
| Miro Business | 2027-02-10 | 30 | 2027-01-11 | 56 |
| Microsoft 365 Business Premium | 2027-03-01 | 30 | 2027-01-30 | 75 |
| Visio Plan 2 | 2027-03-01 | 30 | 2027-01-30 | 75 |

Notice deadline already passed (subscription will renew):
- Slack Pro: renews 2027-01-10; next exit 2028-01-10, give notice by 2027-11-11.

## Data quality and warnings
- Usage line 34: duplicate row for Miro Business / cl@havnens.dk, latest date kept.
- Visio Plan 2: no usage data, utilisation and savings not calculated.
- Line 11 (Penneo): cost_per_licence_month missing, costs and savings not calculated.
- Line 11 (Penneo): notice_days missing, 30 days assumed (check the contract).
- Penneo: no usage data, utilisation and savings not calculated.
- Line 12: Miro Business duplicates line 6 (double billing or duplicate row?), counted once.
- Usage found for 'canva pro' (1 users) but no subscription: unlicensed or shadow IT, check.
~~~~

## Interpretation

- You spend DKK 66,300 a year; 15 licences are unused, which is DKK 18,120 a year of waste. Cutting to active users plus a 5% buffer saves about DKK 12,240 a year, but only about 6,170 lands in the next 12 months because of notice periods.
- Slack has had no active users since April, but its 60-day notice deadline was 11 November, so it renews on 10 January. Give notice by 11 November 2027 at the latest, and ask Slack whether they will reduce seats earlier.
- Act now: AnyDesk notice by 20 November (TeamViewer already covers remote support), Zoom by 1 December (Teams covers video meetings), Acrobat by 16 December (cut 5 to 3).
- Compliance risk: AutoCAD LT has 4 active users on 3 licences. Buy a licence or stop the shared use. Canva is in use without a subscription on the list.
- Data gaps: Penneo has no price or notice period, Visio and Penneo have no usage data, and Miro appears twice on the reseller list (check you are not billed twice).
