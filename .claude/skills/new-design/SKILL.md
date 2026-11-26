---
name: new-design
description: Create a new 3D-printable design from a text prompt. Scaffolds a project, writes a brief for confirmation, then models it in build123d and runs the review loop. Use when the user asks for a new part, accessory, or object to print.
---

Follow the **New design from a prompt** workflow in AGENTS.md exactly.

1. Choose a short kebab-case project name and run `uv run od new <name>`.
2. Write the **Brief** in `projects/<name>/README.md`. Infer what you reasonably can, and list everything else under *Open questions*. Always settle: key dimensions (and what they mate with), materials/tools (one `build()` part per material), print orientation, mounting/fastening (use `od.tol` hole sizes), and size limits.
3. Confirm the brief with the user via AskUserQuestion (one question per open item, with your recommended answer first). **Don't model until the brief is confirmed.** Update the README status to `confirmed`.
4. Model it in `design.py` following the design.py convention. Put every meaningful dimension in `Params`, and encode the brief's key dimensions in `verify()`.
5. Review loop: `uv run od check <name>` until it's OK → `uv run od render <name>` → Read the contact-sheet PNG and compare it with the brief → fix and repeat.
6. Create a branch `design/<name>-initial` (if not already on one) and commit the project.
7. Report: what was built, the key `Params`, any warnings, and the contact-sheet path. Remind the user they can preview it by running `design.py` in VS Code, and slice it from `uv run od build <name>`.

Arguments (the user's design request): $ARGUMENTS
