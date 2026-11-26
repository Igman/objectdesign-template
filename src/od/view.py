"""Send a design's parts to the OCP CAD Viewer (VS Code extension).

From a design file's __main__ block:   preview(build, Params, VARIANTS)
    python design.py            -> default Params()
    python design.py small      -> VARIANTS["small"]
    python design.py all        -> every variant side by side
From the CLI:   uv run od view <project> [--variant NAME|all]
"""

from __future__ import annotations

import sys

from od import mesh

HELP = """\
OCP CAD Viewer is not running, so there's nothing to show the model in.
  In VS Code press Cmd+K then V (Windows: Ctrl+K then V), or use the Command Palette
  -> "OCP CAD Viewer: Open viewer". Then run this file again. (If the command is missing, run "Developer: Reload Window".)
  Without the viewer: `uv run od render <project>` writes preview PNGs instead."""

ALL = "all"
DEFAULT = "default"
SIDE_BY_SIDE_GAP = 20.0  # mm between variants when showing all
EDGE_COLOR = "#1e1e22"   # feature lines on mesh parts (matches render.EDGE)


def show_parts(parts: dict) -> None:
    objs, names, colors = [], [], []
    for name, obj in parts.items():
        if mesh.is_mesh(obj):
            # The surface, plus its sharp creases as a separate line object
            # ("<name>/edges", toggle it in the viewer tree).
            objs += [mesh.to_shape(obj), mesh.to_edges(obj)]
            names += [name, f"{name}/edges"]
            colors += [None, EDGE_COLOR]
        else:
            objs.append(obj)
            names.append(name)
            colors.append(None)
    # A mesh face has no CAD edges, so the viewer would draw every triangle
    # edge. That switch is global, so only turn it off when every part is a
    # mesh; a CAD part in the same view keeps its edges.
    all_meshes = all(mesh.is_mesh(o) for o in parts.values())

    from ocp_vscode import Camera, get_port, port_check, show

    # ocp_vscode prints tracebacks rather than raising when no viewer is open,
    # so check that one is reachable first.
    port = get_port()
    if port is None or not port_check(port):
        print(HELP, file=sys.stderr)
        sys.exit(1)
    # The viewer's default (Camera.KEEP) keeps the previous camera, which can
    # leave a new model off-screen (e.g. after the startup logo). Reset to fit.
    show(*objs, names=names, reset_camera=Camera.RESET, render_edges=not all_meshes, colors=colors)


def _shift(obj, dx: float):
    if mesh.is_mesh(obj):
        m = obj.copy()
        m.apply_translation((dx, 0, 0))
        return m
    from build123d import Pos

    return Pos(dx, 0, 0) * obj


def variant_parts(build, Params, variants: dict | None, variant: str | None) -> dict:
    """Build the parts for one variant, or all of them laid out along +X."""
    variants = variants or {}
    if variant in (None, "", DEFAULT):
        return build(Params())
    if variant == ALL:
        chosen = variants or {DEFAULT: Params()}
        out, x = {}, 0.0
        for vname, params in chosen.items():
            parts = build(params)
            meshes = {n: mesh.to_trimesh(o) for n, o in parts.items()}
            lo = min(m.bounds[0][0] for m in meshes.values())
            hi = max(m.bounds[1][0] for m in meshes.values())
            for pname, obj in parts.items():
                out[f"{vname}/{pname}"] = _shift(obj, x - lo)
            x += (hi - lo) + SIDE_BY_SIDE_GAP
        return out
    if variant not in variants:
        names = ", ".join([DEFAULT, *variants, ALL])
        raise SystemExit(f"error: unknown variant '{variant}'. Choose one of: {names}")
    return build(variants[variant])


def preview(build, Params, variants: dict | None = None) -> None:
    """Entry point for a design file's __main__ block. Variant = first CLI argument."""
    variant = sys.argv[1] if len(sys.argv) > 1 else None
    show_parts(variant_parts(build, Params, variants, variant))
