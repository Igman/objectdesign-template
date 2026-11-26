---
name: iterate
description: Change an existing design in projects/ (new feature, dimension change, fix after a test print) and re-verify it. Use when the user asks to modify, adjust, fix or extend an existing design.
---

Follow the **Changing an existing design** workflow in AGENTS.md.

1. Identify the project (`uv run od list` if unclear). Read its README brief and `design.py`.
2. If the request changes the brief (dimensions, materials, mating parts), update the brief, and confirm with the user if anything is ambiguous.
3. `git switch -c design/<project>-<short-change>` (unless you're already on a branch for this change).
4. Make the change. Keep existing `Params` names stable, add new ones for new features, and update `verify()`.
5. Review loop: `uv run od check <project>` → `uv run od render <project>` → Read the contact sheet → fix and repeat.
6. Add a README **Changelog** line, commit, and report what changed (old vs new values) plus the contact-sheet path.

If the request comes from a failed test print (bad fit, warping, too weak), ask what happened and with which filament, and consider whether a shared value in `src/od/tol.py` should change instead of this one design.

Arguments (project and change): $ARGUMENTS
