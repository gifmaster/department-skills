# Worked example: Access review

## User request

> Quarterly access review for Fjordvej Logistik ApS before our ISAE 3402 audit. Here are the M365 and ERP user exports, the HR list from Danløn and our role matrix. Can you find the problems and give me lists I can send to the managers?

## Command run (from the skill folder, on the sample assets)

```
python3 scripts/access_review.py assets/accounts_template.csv --hr assets/hr_template.csv --role-map assets/role_map_template.json --today 2026-11-16
```

## Output

~~~~text
# Access review (as of 2026-11-16)

**16 accounts reviewed against 12 HR records.** Leavers still enabled: 2 | Orphaned: 1 | Shared/generic: 3 | Admin on daily account: 2 | Dormant: 3 | Role mismatches: 3

## 1. Leavers and orphaned or shared accounts
| System | Account | Person | Finding | Detail |
|---|---|---|---|---|
| M365 | rasmus.friis | Rasmus Friis | LEAVER | leaver, ended 2026-10-31, still enabled 16 days later |
| M365 | rasmus.friis | Rasmus Friis | LOGIN-AFTER-END | login on 2026-11-03 after end date: investigate as possible security event |
| M365 | info | Info Fjordvej | SHARED | shared or generic account, no named owner |
| M365 | test.user | Test User | SHARED | shared or generic account, no named owner |
| M365 | nanna.krog | Nanna Krog | LEAVER | leaving 2026-11-30 (in 14 days): schedule disable |
| ERP | LAGER | Lager terminal | SHARED | shared or generic account, no named owner |
| ERP | NAVCONSULT | Erp Partner | ORPHANED | no HR match |

## 2. Excess access (role map)
| System | Account | Person | Finding | Detail |
|---|---|---|---|---|
| M365 | adm-jonas | Jonas Vinther | ROLE-MISMATCH | role(s) not in role map for IT supporter: Global Administrator |
| ERP | MKJAER | Mette Kjær | ROLE-MISMATCH | role(s) not in role map for CFO: SUPER |
| ERP | ITHOMSEN | Ida Thomsen | ROLE-MISMATCH | role(s) not in role map for Payroll officer: Sales |

## 3. Privileged access
| System | Account | Person | Finding | Detail |
|---|---|---|---|---|
| M365 | kim.ravn | Kim Ravn | ADMIN-DAILY | admin rights on a personal daily account: use a separate admin account |
| ERP | MKJAER | Mette Kjær | ADMIN-DAILY | admin rights on a personal daily account: use a separate admin account |

Admin accounts in total: 4 (M365/kim.ravn, M365/adm-jonas, ERP/MKJAER, ERP/NAVCONSULT).

## 4. Dormant accounts
| System | Account | Person | Finding | Detail |
|---|---|---|---|---|
| M365 | test.user | Test User | DORMANT | never logged in |
| ERP | PBECH | Peter Bech | DORMANT | last login 2026-07-02 (137 days ago) |
| ERP | ALUND | Anja Lund | DORMANT | last login unknown (invalid date) |

## 5. Attestation lists per department
Manager: mark each line KEEP or REMOVE and return by the agreed date. Unconfirmed access is removed.

### Finance
| Attesting manager | Person | System | Account | Role | Admin | Last login | Findings | KEEP/REMOVE |
|---|---|---|---|---|---|---|---|---|
| Lars Winther | Mette Kjær | ERP | MKJAER | SUPER | yes | 2026-11-13 | ADMIN-DAILY, ROLE-MISMATCH | |
| Lars Winther | Mette Kjær | M365 | mette.kjaer | User |  | 2026-11-14 | OK | |
| Mette Kjær | Ida Thomsen | ERP | ITHOMSEN | Sales / Payroll |  | 2026-11-14 | ROLE-MISMATCH | |
| Mette Kjær | Søren Holm | ERP | SHOLM | Accountant / Vendor payments |  | 2026-11-14 | OK | |

### IT
| Attesting manager | Person | System | Account | Role | Admin | Last login | Findings | KEEP/REMOVE |
|---|---|---|---|---|---|---|---|---|
| Kim Ravn | Jonas Vinther | M365 | adm-jonas | Global Administrator | yes | 2026-11-03 | ROLE-MISMATCH | |
| Kim Ravn | Jonas Vinther | M365 | jonas.vinther | User |  | 2026-11-16 | OK | |
| Lars Winther | Kim Ravn | M365 | kim.ravn | Global Administrator | yes | 2026-11-16 | ADMIN-DAILY | |

### Sales
| Attesting manager | Person | System | Account | Role | Admin | Last login | Findings | KEEP/REMOVE |
|---|---|---|---|---|---|---|---|---|
| Line Dam | Camilla Berg | M365 | camilla.berg | User |  | 2026-11-14 | OK | |
| Line Dam | Nanna Krog | M365 | nanna.krog | User |  | 2026-11-13 | LEAVER | |
| Line Dam | Rasmus Friis | M365 | rasmus.friis | User |  | 2026-11-03 | LEAVER, LOGIN-AFTER-END | |

### Warehouse
| Attesting manager | Person | System | Account | Role | Admin | Last login | Findings | KEEP/REMOVE |
|---|---|---|---|---|---|---|---|---|
| Lars Winther | Peter Bech | ERP | PBECH | Warehouse |  | 2026-07-02 | DORMANT | |
| Peter Bech | Anja Lund | ERP | ALUND | Warehouse |  | invalid date | DORMANT | |

### Unassigned (IT owner to resolve)
| Attesting manager | Person | System | Account | Role | Admin | Last login | Findings | KEEP/REMOVE |
|---|---|---|---|---|---|---|---|---|
| IT owner | Lager terminal | ERP | LAGER | Warehouse / Item edit |  | 2026-11-14 | SHARED | |
| IT owner | Erp Partner | ERP | NAVCONSULT | SUPER | yes | 2026-09-18 | ORPHANED | |
| IT owner | Info Fjordvej | M365 | info | Shared mailbox |  | 2026-11-15 | SHARED | |
| IT owner | Test User | M365 | test.user | User |  | never | SHARED, DORMANT | |

Active employees with no account in the exports: Line Dam, Lars Winther.

## Data quality and matching warnings
- HR line 10 (Camilla Berg): email missing, name matching only.
- Accounts line 17 (ALUND): unrecognised date '31-13-2026' (use yyyy-mm-dd or dd-mm-yyyy); last login treated as unknown.
- Accounts line 18: ERP/SHOLM duplicates line 12.
- Fuzzy match to verify: M365/adm-jonas 'Jonas Vinther (admin)' -> Jonas Vinther (score 1.0).
- Fuzzy match to verify: M365/camilla.berg 'Camilla Berg' -> Camilla Berg (score 1.0).
- Fuzzy match to verify: ERP/SHOLM 'Soren Holm' -> Søren Holm (score 1.0).
~~~~

## Interpretation

- Most urgent: Rasmus Friis left on 31 October but his M365 account is still enabled 16 days later and was used on 3 November. Disable it today and treat the login as a possible security event (keep the sign-in logs).
- Nanna Krog leaves on 30 November: book the disable for her last working day now.
- ERP NAVCONSULT is an external partner with SUPER rights and no named owner, and LAGER, info@ and test.user are shared accounts. Disable test.user, give LAGER a named owner and remove item edit, and give the partner time-limited access.
- Kim Ravn (M365 Global Administrator) and Mette Kjær (ERP SUPER) use admin rights on their daily accounts; create separate admin accounts. Jonas's admin account has Global Administrator although his role map allows Helpdesk Administrator only.
- Send each manager their table and ask for KEEP or REMOVE. Check the three name-only matches, the duplicate SHOLM row and Anja Lund's invalid last-login date before sending.
