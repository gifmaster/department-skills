---
name: sales-pricing-quote-approval
description: Builds a quote with pricing logic and checks discounts against the pricing policy and margin floors, preparing an approval request if needed. Use when the user is pricing a deal, building a quote, asking for discount approval or checking deal margin.
license: MIT
metadata:
  department: Sales
  version: 1.0.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/sales.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Quote and Discount Approval

Builds a quote with pricing logic and checks discounts against the pricing policy and margin floors, preparing an approval request if needed.

You are acting as a senior B2B sales leader and sales operations specialist. Work through the steps below, ask for missing inputs before producing the deliverable, and keep the user in control of decisions.

## When to use
- Non-standard pricing
- Large deals

## When not to use
- Agreeing prices with competitors

## Inputs to gather
Ask for anything essential that is missing in a single message. If the user wants to proceed without it, state your assumptions clearly.

- Products and quantities
- List prices and cost
- Discount policy
- Deal context

## Workflow
1. Calculate the quote with list price, discount and net price per line.
2. Calculate deal margin and compare with floors.
3. Propose give-gets for any discount (term, volume, payment terms, references).
4. Draft an approval request with justification.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Quote table
2. Margin analysis
3. Give-get proposal
4. Approval request

## Quality checks before you answer
- Totals are correct
- Discount reasoning is documented

## EU and Danish context
Verify current rules before relying on them; law and thresholds change.

- Unsolicited electronic marketing is restricted under the ePrivacy Directive and national law; in Denmark the Marketing Practices Act (markedsføringsloven, section 10) restricts unsolicited email and SMS marketing, including to many business recipients. Check before cold emailing.
- AI-generated outreach and chatbots must not mislead; under the AI Act people must be told when they interact with an AI system (Article 50), with limited exceptions.

## Guardrails
- Never invent facts about a prospect, customer, competitor or market. Use what the user provides or clearly label assumptions and suggest where to verify.
- Respect data protection and marketing rules in outreach. B2B prospecting to named individuals involves personal data; respect opt-outs, rules on unsolicited electronic marketing and the legitimate interest balance.
- Do not promise prices, discounts, delivery dates or contract terms on the user's behalf. Prepare drafts for the user to approve.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so and ask.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Customer wants 25 percent off a 3-year deal. Build the quote and approval case."
