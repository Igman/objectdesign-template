"""Export parts to 3MF (all parts, named), STEP (B-rep parts) and STL (per part)."""

from __future__ import annotations

from pathlib import Path

import trimesh

from od import mesh

FORMATS = ("3mf", "step", "stl")


def export_parts(parts: dict, out_dir: Path, stem: str, formats=FORMATS) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    meshes = {name: mesh.to_trimesh(obj) for name, obj in parts.items()}

    if "3mf" in formats:
        # One object per part: slicers such as Bambu Studio and OrcaSlicer offer to load them as a single
        # multi-part object, and each part can then be assigned its own tool.
        scene = trimesh.Scene()
        for name, m in meshes.items():
            scene.add_geometry(m, node_name=name, geom_name=name)
        p = out_dir / f"{stem}.3mf"
        scene.export(p)
        written.append(p)

    if "stl" in formats:
        for name, m in meshes.items():
            p = out_dir / (f"{stem}.stl" if len(meshes) == 1 else f"{stem}-{name}.stl")
            m.export(p)
            written.append(p)

    if "step" in formats:
        import build123d as bd

        breps = []
        for name, obj in parts.items():
            if mesh.is_mesh(obj):
                continue  # meshes (STL remixes) have no B-rep form
            obj.label = name
            breps.append(obj)
        if breps:
            p = out_dir / f"{stem}.step"
            target = breps[0] if len(breps) == 1 else bd.Compound(label=stem, children=breps)
            bd.export_step(target, p)
            written.append(p)

    return written
