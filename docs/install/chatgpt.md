# Install in ChatGPT and OpenAI Codex

## ChatGPT Skills (recommended where available)

ChatGPT supports skills in the same `SKILL.md` format. Availability depends on your plan and, for business workspaces, on whether an admin has enabled skills.

1. Download a skill zip from [`dist/skills/`](../../dist/skills/), for example `fin-variance-analysis.zip`.
2. In ChatGPT open **Skills → Create → Upload from your computer** and choose the zip.
3. ChatGPT scans the upload; most skills are available as soon as the scan finishes.
4. Use it by asking for the task, or by mentioning the skill by name.

To share with colleagues in a workspace, use the sharing options in Skills, and keep this repository as the master copy.

## Custom GPTs and Projects (any paid plan)

Use `PROMPT.md` when skills are not available, or when you want a dedicated assistant for one task.

1. Open the skill folder and then `PROMPT.md`.
2. Copy everything **below** the line `<!-- PASTE BELOW THIS LINE -->`.
3. **Custom GPT:** Explore GPTs → Create → Configure → paste into *Instructions*. Add the conversation starters listed at the end of the text. Optionally upload `SKILL.md` under *Knowledge*.
4. **Project:** open the project → Instructions → paste.

The pasted text is under 8,000 characters for every skill, which fits the instruction field.

A practical pattern is one GPT per department: paste the most used skill as instructions, and upload the other skills' `SKILL.md` files as knowledge so the GPT can follow them on request.

## OpenAI Codex (CLI and IDE extension)

Codex discovers skills from `SKILL.md` folders. User-level skills live in `~/.agents/skills` (older versions used `~/.codex/skills`), and repository skills in `.agents/skills`.

```bash
./install.sh codex legal it          # copies into ~/.agents/skills
```

For an older Codex version, install into the legacy folder:

```bash
SKILLS_DIR=~/.codex/skills ./install.sh custom legal it
```

Restart Codex, then list skills with `/skills` or mention one with `$` followed by its name, for example `$it-incident-postmortem`.

## Troubleshooting

- **Upload rejected:** check that the zip contains one folder with a `SKILL.md` inside. If your workspace blocks uploads, ask an admin to enable skills.
- **Instructions too long in another tool:** `PROMPT.md` sections are independent; remove the *Conversation starters* or *EU and Danish context* section first if a tool has a lower limit.
