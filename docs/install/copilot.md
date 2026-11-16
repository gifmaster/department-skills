# Install in Copilot

There are two different Copilots. GitHub Copilot is for code and agent work; Microsoft 365 Copilot is for chat in Microsoft 365 apps.

## GitHub Copilot (VS Code agent mode, Copilot CLI, Copilot cloud agent)

GitHub Copilot supports Agent Skills in `SKILL.md` format.

**Personal skills** (all your projects): `~/.copilot/skills`

```bash
./install.sh copilot hr it            # macOS or Linux
.\install.ps1 copilot hr it           # Windows
```

**Project skills** (shared with everyone who uses the repository): copy skill folders into `.github/skills/` in that repository and commit them.

```bash
SKILLS_DIR=./.github/skills ./install.sh custom it
```

Copilot also reads `~/.claude/skills` and `.claude/skills`, so if you already installed the skills for Claude Code, do not install them twice.

Use them in VS Code by switching Copilot Chat to **Agent** mode and asking for the task. In Copilot CLI, run `/skills` to list them. Support in Visual Studio and JetBrains IDEs depends on the Copilot version; check GitHub's documentation.

## Microsoft 365 Copilot (Agent Builder)

Microsoft 365 Copilot agents use an instructions field limited to 8,000 characters. Every `PROMPT.md` in this library fits.

1. Open the Microsoft 365 Copilot app and choose **Create agent** (Agent Builder).
2. Select **Configure**.
3. **Name:** the skill title. **Description:** the first sentence of the skill.
4. **Instructions:** paste everything below `<!-- PASTE BELOW THIS LINE -->` from the skill's `PROMPT.md`.
5. **Knowledge (optional):** add the skill's `SKILL.md` and your own SharePoint policies or templates, for example the HR handbook for `hr-policy-question-answerer`.
6. **Starter prompts:** copy the conversation starters from the end of `PROMPT.md`.
7. Create, test and share the agent with your team.

For many skills at once, or for organisation-wide deployment, build declarative agents in Copilot Studio or the Microsoft 365 Agents Toolkit and use `PROMPT.md` as the `instructions` value in the agent manifest.

## Troubleshooting

- **Agent Builder rejects the text:** check you only pasted the part below the marker. If your tenant applies a lower limit, remove the *Conversation starters* section first.
- **Copilot in VS Code does not use a skill:** confirm you are in Agent mode and that the folder name matches the `name` in `SKILL.md`.
