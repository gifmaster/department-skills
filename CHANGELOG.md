# Changelog

## 1.1.0 (2026-11-16)

Based on simulated-use tests of all 168 skills by eight independent testers (average 4.04 of 5; accuracy the weakest dimension).

- Accuracy: corrected AI Act wording after Regulation (EU) 2026/1744 (Art. 4 AI literacy, new Art. 5 bans, Art. 50 dates), pay transparency reporting dates, Danish spam rules (consent for business recipients and LinkedIn messages), cookie supervisor (Digitaliseringsstyrelsen), MAR gate for press releases, DSA mis-citation, GDPR Art. 33 in outage communication, CSRD/CSDDD/EUDR/ESPR/CBAM/Forced Labour dates, Danish VAT, A-tax, renteloven and annual report deadlines, and more.
- New dated facts files per department (`facts/`), shipped in every skill as `references/facts.md`; the repeated EU boilerplate is removed from skills.
- 20 automated skills with tested calculation scripts, templates and worked examples.
- Inputs: deliver with stated assumptions by default, ask only when a missing input would make the answer wrong or risky.
- Language rule: answer in the user's language, Danish drafts for Danish recipients.
- Sharper descriptions with "not for X, use Y" hand-offs to fix trigger clashes; security incidents now route to it-incident-triage with a containment-first step.
- Fixed example requests that the build split at commas.
- Reference packs (content/): NDA playbook, B2B clause bank, Danish and English letter templates (payment demands, breach notices, DSAR responses, breach notifications, reminders, candidate letters, webshop macros), mandatory employment terms checklist (ansættelsesbevisloven section 3 split checked against the act), ROPA and DPIA templates, Danish board minutes, returns decision tree, S&OP executive template, onboarding plan.
- Facts re-checked against official sources (VAT periods, 2026 mileage rates, Forced Labour Regulation, EUDR as amended by 2025/2650, Omnibus I Directive 2026/470, CBAM 2025/2083); no-hire clause rule corrected to ansættelsesklausulloven sections 3 and 4.
- Script improvements: opening reconciling items, weekly or monthly demand input, staffing gap versus available agents, missing months handled in forecasts; every tool checked for valid JSON and documented legal parameters (218 tests).
- After an independent re-test of the 16 weakest skills (overall 3.12 to 3.62, accuracy 3.25 to 4.00): corrected cookie supervisor (Digitaliseringsstyrelsen), renteloven sections (9 a, stk. 3 for compensation; 9 b, stk. 2 for reminder fees), NIS2 size test, December A-tax deadline; added content to S&OP, contract drafting, research memo, NDA, health score and ESG skills; fixed six script issues (legal-limit warnings, double counting, header aliases, suppressed pay gap categories, DSAR extension, one-off cash items).

## 1.0.0 (2026-11-16)

First release.

- 168 skills across eight departments: HR, Finance, Supply Chain, Legal, Sales, Marketing, IT and Customer Service (21 each)
- Two formats per skill: `SKILL.md` (Agent Skills standard) and `PROMPT.md` (portable instructions under 8,000 characters)
- Install guides for Claude, ChatGPT and Codex, Gemini and Gemini CLI, GitHub Copilot and Microsoft 365 Copilot
- Claude Code plugin marketplace with one plugin per department
- Installers for macOS, Linux and Windows
- Upload-ready zips per skill, per pack and for the whole library
- Build, lint, validation and packaging scripts with a CI check
