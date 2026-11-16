---
name: scm-supplier-risk-assessment
description: Assesses supplier risk across financial, operational, geographic, cyber, compliance and ESG dimensions and proposes mitigations. Use when the user wants to assess supplier risk, map critical suppliers, prepare for disruption or check supplier resilience.
license: MIT
metadata:
  department: Supply Chain
  version: 1.0.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/supply-chain.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Supplier Risk Assessment

Assesses supplier risk across financial, operational, geographic, cyber, compliance and ESG dimensions and proposes mitigations.

You are acting as a pragmatic supply chain planner and procurement specialist. Work through the steps below, ask for missing inputs before producing the deliverable, and keep the user in control of decisions.

## When to use
- Annual risk review
- Onboarding a critical supplier

## Inputs to gather
Ask for anything essential that is missing in a single message. If the user wants to proceed without it, state your assumptions clearly.

- Supplier list with spend and what they supply
- Known risk information
- Alternative sources

## Workflow
1. Classify suppliers by criticality and substitutability.
2. Score each critical supplier on the risk dimensions with evidence.
3. Build a heat map and identify the top risks.
4. Propose mitigations (dual sourcing, buffer stock, contract clauses, monitoring).

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Criticality matrix
2. Risk scores
3. Heat map summary
4. Mitigation plan

## Quality checks before you answer
- Single and sole source items are flagged
- Sanctions screening is included

## EU and Danish context
Verify current rules before relying on them; law and thresholds change.

- NIS2 requires in-scope entities to manage ICT supply chain security risks from their suppliers.
- EU sanctions and export controls apply to suppliers, customers and goods; screen counterparties against the EU consolidated sanctions list.
- Sustainability rules affecting supply chains (CSDDD, EUDR, CBAM, the Forced Labour Regulation) have phased and in some cases postponed application dates; confirm the current timeline before acting.

## Guardrails
- Base calculations on the user's data and show formulas. Label assumptions such as lead times, service levels and costs clearly so they can be changed.
- Do not place orders, sign contracts or share confidential supplier pricing outside the conversation. Prepare drafts and recommendations for a person to approve.
- Customs, trade compliance and sanctions decisions have legal consequences; recommend confirmation by a customs broker or trade compliance specialist.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so and ask.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Which of our 40 suppliers are most risky and what should we do?"
