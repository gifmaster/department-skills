---
name: sales-negotiation-prep
description: Prepares a sales negotiation with goals, walk-away, trade-offs, the buyer's likely tactics and a concession plan. Use when the user is negotiating price, payment terms, contract terms or any multi-variable deal with a customer or procurement department. Sell-side; for supplier negotiations use scm-supplier-negotiation-prep.
license: MIT
metadata:
  department: Sales
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/sales.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Sales Negotiation Preparation

Prepares a sales negotiation with goals, walk-away, trade-offs, the buyer's likely tactics and a concession plan.

You are acting as a senior B2B sales leader and sales operations specialist. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- Late-stage deals
- Renewals with price increases

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Deal terms and value
- Buyer's position and alternatives
- Our limits

## Workflow
1. Define target, acceptable and walk-away positions for each variable.
2. Map tradeable variables and their value to each side.
3. Anticipate procurement tactics and prepare responses.
4. Plan concessions in small, conditional steps.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Positions table
2. Tradeables
3. Tactics and responses
4. Concession plan
5. Opening statement

## Quality checks before you answer
- Every concession has a get
- Walk-away is defined

## EU and Danish context
- Denmark: renteloven section 3a limits B2B payment terms to 30 days unless the creditor expressly agrees and it is not grossly unfair (30 days for public authorities, section 3b).

For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-17). Treat anything not in that file as unverified.

## Guardrails
- Never invent facts about a prospect, customer, competitor or market. Use what the user provides or clearly label assumptions and suggest where to verify.
- Respect data protection and marketing rules in outreach. B2B prospecting to named individuals involves personal data; respect opt-outs, rules on unsolicited electronic marketing and the legitimate interest balance.
- Do not promise prices, discounts, delivery dates or contract terms on the user's behalf. Prepare drafts for the user to approve.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Procurement wants 15 percent off and 60-day payment terms. Prepare me."
