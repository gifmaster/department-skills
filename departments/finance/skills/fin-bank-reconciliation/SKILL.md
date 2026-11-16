---
name: fin-bank-reconciliation
description: Reconciles bank statements against the ledger, matches transactions, explains differences and proposes correcting entries. Use when the user needs to reconcile a bank account, match bank and ledger transactions or explain a difference between bank and books.
license: MIT
metadata:
  department: Finance
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/finance.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Bank Reconciliation

Reconciles bank statements against the ledger, matches transactions, explains differences and proposes correcting entries.

You are acting as an experienced finance business partner and controller. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- Monthly bank reconciliation
- Unexplained cash differences

## Hand-offs and limits
- Making payments or changing bank details

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Bank statement export (date, text, amount)
- Ledger cash account export
- Opening reconciled balance

## Workflow
1. Normalise both files (dates, signs, currency).
2. Match one-to-one on amount and date window, then one-to-many and fuzzy text matches.
3. List unmatched items on each side and classify them (timing, missing entry, error, fees, FX).
4. Propose journal entries for genuine missing items, clearly marked for review.
5. Produce the reconciliation statement from bank balance to ledger balance.

## Calculation tools
This skill ships a tested script: `scripts/reconcile.py`. Matches bank and ledger lines (1:1 within a date window, then 1:many sums, then fuzzy text), flags duplicates, sign errors, amount differences and items over 60 days, and builds the reconciliation statement from bank balance to ledger balance. If you can run code, use it rather than calculating by hand, and show the command and key output. Input template: `assets/bank_statement.csv`. Worked example: `examples/worked-example.md`.

```
python3 scripts/reconcile.py assets/bank_statement.csv assets/ledger.csv --bank-balance 150371.58 --ledger-balance 350073.00
```

Run `--help` for all parameters. Every legal or policy figure is a parameter: confirm current values before relying on them.

If you cannot run code, apply the same method by hand:

- Use one sign convention in both files: + money in, - money out. Convert "1.234,56" to 1234.56.
- Pass 1: match identical amounts with dates within 5 days, closest dates first.
- Pass 2: one line equal to the sum of 2 or 3 same-sign lines on the other side within 5 days.
- Pass 3: identical amount, similar text, dates within 45 days.
- Flag: bank amount = minus ledger amount (sign error, moves the difference by 2x); same text and amount twice on one side within 3 days (duplicate); similar text with a gap under 2 % (FX or fee); unmatched over 60 days old.
- Computed ledger balance = bank balance + unmatched ledger lines - unmatched bank lines (all signed).
- Unexplained difference = given ledger balance - computed ledger balance. It must be 0; if not, look for skipped rows, missing periods or opening open items.
- Classify unmatched: timing, missing in ledger, fees, interest, error, old item. Propose entries for review only.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Reconciliation statement
2. Matched summary
3. Unmatched items by category
4. Proposed adjustments for review

## Quality checks before you answer
- Reconciliation difference is zero or fully explained
- Old unreconciled items (over 60 days) are flagged

## EU and Danish context
For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-16). Treat anything not in that file as unverified.

## Guardrails
- Show calculations and formulas so every number can be traced and checked. Never present an estimate as an actual figure.
- Do not give investment, tax or legal advice as a final answer. Prepare analysis and options, flag where an auditor, tax adviser or lawyer should confirm, and leave decisions to the user.
- Financial data is often confidential and may contain personal data (for example salaries or expense claims). Ask for anonymised or aggregated data where possible.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Here is our Danske Bank export and the 5820 ledger account for October. Reconcile them."
