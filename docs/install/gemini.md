# Install in Google Gemini

## Gemini CLI (code and terminal)

Gemini CLI supports Agent Skills and discovers `SKILL.md` folders in `~/.gemini/skills` (user) and `.gemini/skills` or `.agents/skills` (workspace).

Install straight from GitHub, one department at a time:

```bash
gemini skills install https://github.com/gifmaster/department-skills.git --path departments/finance/skills
```

Or from a local clone:

```bash
./install.sh gemini finance supply-chain       # copies into ~/.gemini/skills
```

Check with `/skills list` inside Gemini CLI. Skills activate automatically when your request matches.

## Gemini app (Gems)

Gems do not read skill folders, so use the portable instructions.

1. Open Gemini → **Gems → New Gem**.
2. Name it after the skill, for example *Variance Analysis*.
3. Open the skill's `PROMPT.md` and paste everything below `<!-- PASTE BELOW THIS LINE -->` into **Instructions**.
4. Optional: under **Knowledge**, upload the skill's `SKILL.md`, plus your own templates or policies. Gems accept up to 10 knowledge files.
5. Save and test with one of the conversation starters.

Pattern for a department assistant: create one Gem per department, paste the instructions of the skill you use most, and upload up to 10 other `SKILL.md` files from that department as knowledge. Then ask, for example, *"Follow the fin-vat-return-prep skill for this data"*.

## Gemini in Google Workspace

Gems you create are available in the Gemini side panel in Gmail, Docs and Sheets where your Workspace edition supports it. Workspace admins control access.

## Troubleshooting

- **Gem ignores the knowledge file:** paste the instructions instead of relying on the file, and name the skill explicitly in your request.
- **CLI does not list skills:** confirm each folder contains `SKILL.md` directly, then restart the session.
