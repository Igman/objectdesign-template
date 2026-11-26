---
name: release
description: Release a finished design version, exporting 3MF/STEP/STL to exports/, rendering previews, committing and tagging <project>/vN. Use only when the user says a design version is good or final.
---

1. Confirm which project, and that the user considers this version final (usually after a successful test print).
2. Make sure the README is current: status, print notes (filament, profile, tool assignments) and changelog. Update it from what the user tells you.
3. Run `uv run od release <project>` (add `-m "<message>"` for a meaningful note). It refuses to release if the checks fail. Fix the problems first.
4. Read `projects/<project>/renders/*-sheet.png` to confirm the released renders.
5. Tell the user the tag created, the files in `exports/`, and that they can push with `git push --follow-tags` (don't push unless asked). If they're on a design branch, remind them to merge to main.

Arguments: $ARGUMENTS
