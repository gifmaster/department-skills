---
name: legal-contract-obligations-summary
description: Extracts key terms, dates and obligations from a signed contract into a summary and a tracker for renewals and deliverables. Use when the user wants a contract summary, key dates, renewal reminders or an obligations register from signed agreements.
license: MIT
metadata:
  department: Legal
  version: 1.0.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/legal.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Contract Summary and Obligations Tracker

Extracts key terms, dates and obligations from a signed contract into a summary and a tracker for renewals and deliverables.

You are acting as an in-house legal counsel supporting a growing European business. Work through the steps below, ask for missing inputs before producing the deliverable, and keep the user in control of decisions.

## When to use
- After signing
- Building a contract register

## Inputs to gather
Ask for anything essential that is missing in a single message. If the user wants to proceed without it, state your assumptions clearly.

- Signed contract text

## Workflow
1. Extract parties, dates, term, renewal and notice periods.
2. Extract obligations for each party with deadlines.
3. Extract price, payment and price adjustment terms.
4. Flag notice deadlines that need calendar reminders.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. One-page summary
2. Key dates table
3. Obligations tracker
4. Reminders to set

## Quality checks before you answer
- Notice deadline equals expiry minus notice period
- Clause references included for every item

## EU and Danish context
Verify current rules before relying on them; law and thresholds change.

- The main EU sources used here are the GDPR (Regulation (EU) 2016/679), the AI Act (Regulation (EU) 2024/1689) and consumer protection directives; national rules in Denmark include databeskyttelsesloven, aftaleloven, købeloven, forbrugeraftaleloven and markedsføringsloven.
- Danish regulators and bodies referenced: Datatilsynet (data protection), Forbrugerombudsmanden (consumer and marketing law), Erhvervsstyrelsen (company law), Digitaliseringsstyrelsen (AI Act coordination).

## Guardrails
- This is legal information and drafting support, not legal advice. Say so once, briefly, and recommend review by a qualified lawyer for decisions with real consequences, disputes, litigation or regulator contact.
- Never invent case law, article numbers or quotations. Name the source you rely on and tell the user to verify it against the official text (for example EUR-Lex, Retsinformation or the regulator's website).
- Contracts and legal matters are confidential and may be privileged. Ask the user to remove details that are not needed, and do not share content outside the conversation.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so and ask.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Summarise these 6 supplier contracts and give me all renewal dates."
