# Refund and returns decision tree (Denmark, consumer sales)
Use: Read for every return, refund, exchange, repair, warranty or reklamation case to pick the route (withdrawal, defect complaint or goodwill) and apply the right deadline, burden of proof, remedy, shipping cost and refund timing.

Sources: forbrugeraftaleloven chapter 4 (§§ 18 to 26, checked on lovguiden.dk and danskelove.dk), købeloven consumer sale rules (section numbers from a secondary overview, marked verify), facts/customer-service.md (last verified 2026-11-16). This is decision support, not a legal opinion: disputed cases go to a person.

## Step 0. Is this a Danish consumer sale?

| Question | If yes | If no |
|---|---|---|
| Buyer is a private person buying mainly outside their trade? | Continue | B2B: consumer rules below do not apply; use the contract and general købeloven rules, escalate |
| Danish law applies (Danish shop, Danish customer, or terms choose Danish law)? | Continue | Check the customer's country: Sweden (ångerrätt), Norway (angrerett; complaint period up to 5 years for durable goods under forbrukerkjøpsloven, verify). Escalate |

## Step 1. Choose the route

Ask in this order. The first "yes" decides the main route, but a customer can have more than one route: always pick the one most favourable to the customer if they qualify.

```
1. Does the customer say something is wrong with the item
   (fault, broken, not as described, missing parts)?
      yes -> ROUTE B: defect complaint (reklamation)
      no  -> 2
2. Was it a distance or off-premises sale (webshop, phone, email, doorstep)
   and is the customer within the withdrawal period (step 2A)?
      yes -> ROUTE A: withdrawal (fortrydelse)
      no  -> 3
3. Does the shop's own returns policy cover it (for example 30-day returns)?
      yes -> ROUTE C1: voluntary policy return
      no  -> ROUTE C2: goodwill (decision for [team lead])
```

Common traps:
- "Used goods cannot be returned" in a policy only limits the voluntary policy. It never removes a defect complaint, and a withdrawal is still possible after the goods were tried, with a possible deduction for diminished value.
- A cracked, broken or failed item after normal use is route B, even outside 14 or 30 days.
- A purchase in a physical shop has no statutory withdrawal right; only the shop's policy (route C) or a defect complaint (route B).

## Step 2A. Route A: withdrawal (fortrydelsesret)

| Point | Rule | Source |
|---|---|---|
| Who has it | Consumers in distance and off-premises sales; exceptions include custom-made goods, perishables, sealed hygiene or health goods once unsealed, sealed recordings or software once unsealed | forbrugeraftaleloven § 18 (check list in § 18, stk. 2) |
| Deadline | 14 days, no reason needed | § 19, stk. 1 |
| Start for goods | The day the customer (or a person they named, not the carrier) gets physical possession; for several items in one order delivered separately, the last item (verify for split deliveries) | § 19, stk. 2 |
| Start postponed | Not before the customer has the withdrawal information on a durable medium | § 19, stk. 3 |
| Customer not informed | Period extended by up to 12 months after the normal 14 days; ends 14 days after the information arrives if given later | § 19, stk. 4 |
| Weekend or holiday | Last day on a Saturday, public holiday, 5 June, 24 or 31 December moves to the next weekday | § 19, stk. 6 |
| How to withdraw | Any clear statement before the deadline; standard form optional. Online contracts need a withdrawal function from 19 Jun 2026 | § 20; Directive (EU) 2023/2673 |
| Burden of proof | Customer must show they withdrew in time | § 20 |
| Return of goods | Customer returns within 14 days of the withdrawal notice unless the shop offered to collect | § 24 |
| Return shipping | Customer pays the direct return cost if told so before purchase; otherwise the shop pays. Bulky goods delivered to the home that cannot be posted: shop collects at its own cost | § 24 |
| Diminished value | Customer liable only for loss in value from handling beyond what is needed to establish the nature, characteristics and functioning of the goods | § 24 |
| Refund amount | All payments, including the standard delivery charge; extra cost of a more expensive delivery option the customer chose can be kept | § 22 |
| Refund timing | Within 14 days of receiving the withdrawal notice; same payment method, no fee | § 22 |
| Withholding | Shop may wait until goods are received or proof of dispatch is shown, whichever is first, unless the shop offered to collect | § 22 |

Calculation for the refund:

```
refund = price paid + standard delivery charge
         - (extra cost of premium delivery chosen, if any)
         - (deduction for diminished value, if handled beyond testing; document it)
```

## Step 2B. Route B: defect complaint (reklamation under købeloven)

| Point | Rule | Source |
|---|---|---|
| What counts | Goods not in conformity with the contract: faulty, not as described, missing parts, wrong item, not fit for normal purpose or durability | købeloven |
| Absolute limit | Complaint within 2 years of delivery (longer only in special cases such as fraud) | købeloven § 83, stk. 1 (verify) |
| Notice | Within a reasonable time after the customer discovered or should have discovered the defect; within 2 months is always timely | købeloven § 81 (verify) |
| Burden of proof, first year | Defect appearing within 1 year of delivery is presumed present at delivery unless the shop proves otherwise (for example misuse) or the presumption does not fit the goods or defect | købeloven § 77 a, stk. 3 (verify) |
| Burden of proof, after 1 year | Customer must show the defect was present at delivery (for example typical manufacturing fault, expert statement) | købeloven (verify) |
| Use and wear | Normal use does not remove the right to complain; normal wear and tear and damage the customer caused are not defects | Practice |

Remedies, in this order:

| Step | Remedy | Conditions | Source |
|---|---|---|---|
| 1 | Repair (afhjælpning) or replacement (omlevering), customer's choice | Shop may refuse the chosen one if impossible or disproportionately costly compared with the other | købeloven §§ 78, 78 a (verify) |
| 1 | Free of charge, within reasonable time and without significant inconvenience | Includes transport and return costs | købeloven § 78 a, stk. 4; § 79 (verify) |
| 2 | Price reduction (forholdsmæssigt afslag) or cancellation (ophævelse) | If repair or replacement is refused, impossible, fails, not done within reasonable time, or the defect is so serious that immediate cancellation is justified | købeloven §§ 78 b, 78 c (verify) |
| 2 | Cancellation only if the defect is not minor | Shop must prove the defect is minor; for a minor defect, price reduction instead | købeloven § 78 b (verify) |
| | Customer may withhold payment until the shop has remedied | | købeloven (verify) |
| | Deduction for use on cancellation | Only in special circumstances (common for vehicles); do not deduct by default | købeloven § 78 c, stk. 2 (verify); Forbrugerklagenævnet practice |

Who pays shipping in route B: the shop, both ways, including the customer's documented return postage.

Refund timing in route B: after cancellation or agreed price reduction, refund without undue delay once the goods are back or the reduction is agreed (internal target: within [5] working days; no fixed statutory number found, verify). On cancellation the customer gets the price paid, including the original delivery charge.

## Step 2C. Routes C1 and C2: voluntary policy and goodwill

| Point | C1 Voluntary returns policy | C2 Goodwill |
|---|---|---|
| Basis | The shop's published terms | No obligation |
| Deadline and condition | As the policy states (for example 30 days, unused) | Decided case by case |
| Who decides | Agent, by the policy | [team lead] or as delegated, within an approved budget |
| Return shipping | As the policy states | Usually customer, unless decided otherwise |
| Refund timing | As the policy promises (target: same as withdrawal, 14 days) | As agreed |
| Options | Refund, exchange, store credit if the policy allows | Exchange, store credit, partial refund, discount on next order |
| Rule | Never word it so it looks like statutory rights are limited | State it is a one-off gesture, without admitting a defect if none is shown |

## Step 3. Decision record (fill for every case)

| Field | Value |
|---|---|
| Order no. and dates (order, delivery, contact) | [ ] |
| Sale type (distance / shop / B2B) | [ ] |
| Customer request in their words | [ ] |
| Route chosen and why | A / B / C1 / C2 |
| Deadline check | [days since delivery] vs [limit] |
| Burden of proof position | [presumption applies / customer must show / not relevant] |
| Remedy offered | [repair / replacement / reduction / cancellation and refund / policy refund / goodwill] |
| Shipping paid by | [shop / customer] and why |
| Refund amount and calculation | [ ] |
| Refund due by | [date] |
| Escalation needed? | [yes, reason / no] |

## Step 4. Escalate instead of deciding when

- the shop suspects misuse but has no evidence
- the customer disputes the route, a deduction, or the remedy
- the claim is over [amount] or involves personal injury or a safety defect (product safety: check GPSR (EU) 2023/988)
- the customer mentions a complaint to Nævnenes Hus or a lawyer (verify current complaint body)
- the sale is cross-border or B2B

## Step 5. Reply building blocks (Danish, du-form)

- Route A: "Du kan selvfølgelig fortryde dit køb. Send varen retur senest [dato], så refunderer vi [beløb] kr. inklusive den oprindelige fragt senest [dato]."
- Route B accepted: "Det skal ikke ske, så vi behandler det som en reklamation. Det koster dig ikke noget, heller ikke fragten. Du kan vælge mellem [reparation / en ny vare]."
- Route B, need evidence: "Vil du sende billeder af fejlen? Så vender vi tilbage senest [dato]."
- Route C2 goodwill: "Selvom varen ikke længere kan returneres efter vores returpolitik, vil vi gerne tilbyde [løsning] som en engangsgestus."
- Never: "Vi tager ikke brugte varer retur" as an answer to a fault.
