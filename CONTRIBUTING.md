# Contributing

## Workflow

1. Create a branch. `main` is the released version.
2. Edit the catalogue in `catalogue/<department>.yaml`. Never edit files in `departments/` or `dist/` by hand; they are generated.
3. Rebuild and check:

   ```bash
   python3 scripts/lint_catalogue.py
   python3 scripts/build.py
   python3 scripts/validate.py
   python3 scripts/package.py
   ```

4. Test the changed skill on at least two realistic requests in one chat tool and one agent tool.
5. Update `CHANGELOG.md` and, for a release, `VERSION`.
6. Open a pull request.

## Writing a good skill

- **One job per skill.** If the output has two different audiences, split it.
- **Triggers in the user's words.** Include the phrases people actually type, in English and, where common, Danish (for example *stillingsopslag*, *momsangivelse*).
- **Explain the why.** A step like "challenge every must-have, because inflated requirements shrink the candidate pool" works better than a bare rule.
- **Testable checks.** Each quality check should be something you could verify by reading the output.
- **Careful with law.** Name the act, keep figures that change (fees, thresholds, dates) clearly marked as to be verified, and never invent article numbers.
- **House style.** British English, plain words, no long dashes.

## Adding a department

Copy an existing catalogue file, change `department`, `title`, `prefix` (short and unique), `role` and the skills, and add the department key to `ORDER` in `scripts/build.py`. Each department has exactly 21 skills; change the check in `scripts/validate.py` if you want a different number.
