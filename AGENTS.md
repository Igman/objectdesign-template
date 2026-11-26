# AGENTS.md — rules for AI agents in this repo

This repo holds parametric 3D-printable designs (parts, home/office accessories)
written in **build123d** (Python). The target printer and slicer are described in
**`printer.toml`** (bed size, material slots, nozzle). Read it before designing, and
never hard-code printer values: use `od.printer`. The human owner also edits designs
by hand. Keep code readable and parameters obvious.

## Toolchain

- Python 3.14 managed by **uv**. Always run things with `uv run ...`. Never use pip or a global Python.
- Add dependencies with `uv add <pkg>`. That updates `pyproject.toml` + `uv.lock`, and both get committed.
- `od` CLI (source in `src/od/`):

| Command | Purpose |
|---|---|
| `uv run od setup` | Check this machine is ready |
| `uv run od list` | Projects + latest release |
| `uv run od new <name> [--from-stl FILE]` | Scaffold `projects/<name>/` |
| `uv run od check <project> [--json]` | Geometry validity, printability warnings, `verify()` |
| `uv run od view <project> [--variant V\|all]` | Show it in the human's OCP CAD Viewer (`all` = variants side by side) |
| `uv run od watch [project]` | Live preview for the human (VS Code runs it automatically). Agents don't need it |
| `uv run od render <project>` | Contact-sheet PNG → `projects/<name>/build/renders/`, and refreshes the README image `renders/hero.png` |
| `uv run od build <project>` | Export 3MF/STEP/STL → `projects/<name>/build/<variant>/` |
| `uv run od release <project>` | Check, export to `exports/`, render to `renders/`, commit, tag `<project>/vN` |

- Shared library: `od.tol` (fits, walls, fastener holes), `od.printer` (bed, material slots, nozzle; loaded from `printer.toml`),
  `od.mesh` (STL loading + manifold3d booleans), `od.view` (viewer).
  **Never hard-code clearances or screw-hole sizes. Use `od.tol`.**
- Extra parts (threads, fasteners, gears): `bd_warehouse`.

## Project layout

```
projects/<name>/
  design.py      # the design (convention below)
  README.md      # brief, source/license, print notes, changelog
  refs/          # input STLs, photos, drawings (with source + license noted in README)
  build/         # scratch output (gitignored)
  exports/       # released 3MF + STEP + STL (written by `od release` only)
  renders/       # hero.png (README image, refreshed by `od render`) + release contact sheets
  *.3mf          # optional slicer project saved by the human (tool assignments, settings)
```

## design.py convention (required)

```python
@dataclass
class Params:            # every dimension named, with a units/meaning comment
    width: float = 60.0  # overall X size

VARIANTS: dict[str, Params] = {}          # optional presets: {"small": Params(width=40)}

def build(p: Params) -> dict[str, Part]:  # one entry per material/tool, short names
    ...

def verify(parts, p) -> None:             # assert the brief's key dimensions
    ...

if __name__ == "__main__":                # human preview in the OCP CAD Viewer
    from od.view import preview            # `python design.py [variant|all]`
    preview(build, Params, VARIANTS)
```

- **Builder mode** (`with BuildPart():`) is the standard. Algebra mode is fine for small helper pieces.
- Units are mm. Z is up. Model each part **in print orientation, resting on z=0**.
- Derive dependent dimensions from `Params`. Avoid magic numbers in `build()`.
- **Multi-material:** each material/color is its own entry in the dict returned by `build()`, positioned where it belongs in the assembly. The 3MF export keeps them as named objects, so the human can assign a filament/tool to each in the slicer. Keep the part count within `printer.MATERIAL_SLOTS` unless the brief says otherwise.
- Printability: walls ≥ `tol.MIN_WALL`, overhangs ≤ `tol.MAX_OVERHANG_DEG` (chamfer instead of fillet on downward-facing edges), `tol.BOTTOM_CHAMFER` on bed edges, text ≥ `tol.MIN_EMBOSS_DEPTH`. Prefer designs that need no supports.

## Workflows

### New design from a prompt
1. `uv run od new <kebab-name>`.
2. Fill in the **Brief** in the project README: purpose, key dimensions, what it mates with, materials/tools, print orientation, constraints, open questions.
3. **Stop and ask the human to confirm the brief** (and answer the open questions). Don't model before that.
4. Model in `design.py`. Encode the brief's key dimensions in `verify()`.
5. Run the review loop (below) until it's clean.
6. Summarize for the human: what was built, the key parameters, any warnings, and the contact-sheet path.

### Starting from an STL
Decide with the human which approach to take (and record it in the brief):
- **Remix**: keep the mesh and modify it. `uv run od new <name> --from-stl FILE` copies it into `refs/` and uses the remix template: `od.mesh.load()` → build cutters/additions in build123d → `od.mesh.union/difference`. The result is a mesh, so there's no STEP export. Use `od.mesh.repair()` if the source isn't watertight.
- **Re-create**: model it from scratch in build123d, using the STL only as a dimensional reference (load it with `od.mesh.load()` and measure `bounds`, sections, and so on). Prefer this for anything that will keep evolving.
Always record the STL's source URL, author and license in the README **Source** section.

### Changing an existing design
1. Create a branch: `git switch -c design/<project>-<short-change>`.
2. Read the README brief and `design.py` first. Keep the `Params` names stable when possible (the human uses them).
3. Make the change, update `verify()` if dimensions changed, then run the review loop (it refreshes `renders/hero.png`; commit it with the change).
4. Add a line to the README **Changelog**.

### Review loop (mandatory before saying a design is done)
1. `uv run od check <project>`: must report OK. Fix all errors. Address or explain every warning.
   (A bed-size warning is acceptable only if the brief says so, e.g. the part will be split.)
2. `uv run od render <project>`, then **open and look at** the contact-sheet PNG. Confirm the shape matches the brief: features present, nothing floating, correct orientation, parts in the right place.
3. Check the key dimensions: `verify()` passes and the reported sizes make sense.
4. Iterate until clean. Never claim success from code alone.

### Release (only when the human says a version is good, usually after a test print)
`uv run od release <project>`, then remind the human to push: `git push --follow-tags`.

## Git

- Work on a branch per design change (`design/<project>-<change>`). The human merges to main after the print checks out.
- Commit sources, the README, `renders/hero.png` and `pyproject.toml`/`uv.lock`. **Don't commit `build/`.** `exports/` and the contact sheets in `renders/` change only through `od release`.
- Binaries (STL/3MF/STEP/PNG/…) go through **Git LFS** (see `.gitattributes`).
- Never push, force-push or delete tags unless the human asks.

## Mac + Windows

Everything must work on both. Use `pathlib`, no shell-specific scripts, and no absolute paths in designs (use `Path(__file__).parent`).
