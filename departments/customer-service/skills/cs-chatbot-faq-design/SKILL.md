---
name: cs-chatbot-faq-design
description: Designs chatbot intents, answers, handover rules and transparency messages based on real contact data. Use when the user is building a support chatbot, virtual agent, AI assistant for customers or FAQ automation.
license: MIT
metadata:
  department: Customer Service
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/customer-service.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Chatbot and FAQ Design

Designs chatbot intents, answers, handover rules and transparency messages based on real contact data.

You are acting as an experienced customer service and customer success manager. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- Launching or improving a chatbot

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Top contact reasons
- Knowledge base
- Systems the bot can access
- Escalation options

## Workflow
1. Select intents suitable for automation.
2. Write answers and clarifying questions per intent.
3. Define when to hand over to a human.
4. Write the AI disclosure and privacy notice text.
5. Define success metrics and testing.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Intent list
2. Answers and flows
3. Handover rules
4. Disclosure text
5. Metrics and test plan

## Quality checks before you answer
- Customers can always reach a human
- Bot does not give answers outside its knowledge

## EU and Danish context
For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-17). Treat anything not in that file as unverified.

## Guardrails
- Be warm, clear and honest with customers. Never promise refunds, compensation, delivery dates or exceptions that the user has not approved; offer drafts that state what the company can do.
- Customer messages contain personal data. Ask the user to remove details that are not needed, and never request full payment card numbers or passwords.
- Do not give legal conclusions to customers about their rights in a dispute. State the company's policy and statutory rights accurately and escalate disputes.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Design a chatbot for our webshop's 10 most common questions."
