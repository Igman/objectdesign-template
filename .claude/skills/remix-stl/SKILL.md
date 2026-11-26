---
name: remix-stl
description: Start a design from an existing STL file, either remixing the mesh (cut/add geometry) or re-creating it as a clean parametric build123d model. Use when the user provides or references an STL to modify, adapt or rebuild.
---

Follow the **Starting from an STL** workflow in AGENTS.md.

1. Inspect the STL first: `uv run python -c "from od import mesh; m = mesh.load('<file>'); print(m.bounds, m.extents, m.is_watertight, len(m.faces))"`. If it isn't watertight, try `mesh.repair()`.
2. Ask the user (AskUserQuestion) which approach to take, with your recommendation:
   - **Remix**: small changes to an existing model (holes, mounts, scaling, merging). The result is a mesh, so there's no STEP.
   - **Re-create**: rebuild it parametrically, using the STL as a dimensional reference. Recommend this if the design will keep evolving or needs precise mating features.
   Also ask for the STL's source URL, author and license if they're unknown.
3. Remix: `uv run od new <name> --from-stl <file>`, then edit the remix template. Re-create: `uv run od new <name>`, copy the STL into `refs/`, and measure it with `od.mesh`.
4. Write the brief (including the **Source** section) and confirm it with the user before modeling.
5. Model it, then run the review loop (check → render → Read the contact sheet → fix). For re-creations, render the reference STL and the new model and compare their dimensions.
6. Commit on a `design/<name>-initial` branch and report.

Arguments (STL path and what to change): $ARGUMENTS
