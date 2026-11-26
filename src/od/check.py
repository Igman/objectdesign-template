"""Design checks: geometry validity, printability warnings and the project's verify()."""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field

from od import mesh, printer


@dataclass
class Report:
    variant: str
    parts: dict = field(default_factory=dict)   # name -> measurements
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    verify: str = "not run"

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "variant": self.variant,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "verify": self.verify,
            "parts": self.parts,
        }


def check_parts(project, variant: str, params) -> Report:
    r = Report(variant)
    try:
        parts = project.build(params)
    except Exception:
        r.errors.append("build() raised:\n" + traceback.format_exc(limit=6))
        return r

    lo_all, hi_all = None, None
    for name, obj in parts.items():
        info: dict = {"kind": "mesh" if mesh.is_mesh(obj) else type(obj).__name__}
        if not mesh.is_mesh(obj):
            try:
                info["brep_valid"] = bool(obj.is_valid)
                info["solids"] = len(obj.solids())
                if not obj.is_valid:
                    r.errors.append(f"{name}: B-rep is not valid")
                if info["solids"] == 0:
                    r.errors.append(f"{name}: contains no solids (is it a 2D sketch or a face?)")
                elif info["solids"] > 1:
                    r.warnings.append(
                        f"{name}: {info['solids']} separate solids (intended? unfused pieces print as separate objects)"
                    )
            except Exception as e:  # noqa: BLE001
                r.errors.append(f"{name}: could not inspect B-rep: {e}")
        try:
            m = mesh.to_trimesh(obj)
        except Exception as e:  # noqa: BLE001
            r.errors.append(f"{name}: tessellation failed: {e}")
            continue
        lo, hi = m.bounds
        size = hi - lo
        info.update(
            watertight=bool(m.is_watertight),
            volume_mm3=round(float(m.volume), 2),
            triangles=int(len(m.faces)),
            bbox_min=[round(float(x), 3) for x in lo],
            bbox_max=[round(float(x), 3) for x in hi],
            size=[round(float(x), 3) for x in size],
        )
        if not m.is_watertight:
            r.errors.append(f"{name}: mesh is not watertight")
        if m.volume <= 0:
            r.errors.append(f"{name}: non-positive volume ({m.volume:.3f}); inverted normals?")
        r.parts[name] = info
        lo_all = lo if lo_all is None else lo_all.clip(max=lo)
        hi_all = hi if hi_all is None else hi_all.clip(min=hi)

    if lo_all is not None:
        size = hi_all - lo_all
        if abs(lo_all[2]) > 0.01:
            r.warnings.append(
                f"lowest point is z={lo_all[2]:.3f}, not 0: parts should sit on the bed (z=0) in print orientation"
            )
        if size[0] > printer.BED_X or size[1] > printer.BED_Y or size[2] > printer.BED_Z:
            r.warnings.append(
                f"overall size {size[0]:.1f}×{size[1]:.1f}×{size[2]:.1f} mm exceeds the "
                f"{printer.NAME} bed {printer.BED_X:.0f}×{printer.BED_Y:.0f}×{printer.BED_Z:.0f} mm"
            )
        # Single-material printers print every part in the same filament, so only
        # multi-material setups can run out of slots.
        if printer.MATERIAL_SLOTS > 1 and len(parts) > printer.MATERIAL_SLOTS:
            r.warnings.append(
                f"{len(parts)} parts > {printer.MATERIAL_SLOTS} material slots on the {printer.NAME}"
            )

    if not hasattr(project.module, "verify"):
        r.verify = "not defined"
        r.warnings.append("no verify(): key dimensions from the brief are not being checked")
        return r
    try:
        project.verify(parts, params)
        r.verify = "passed"
    except AssertionError as e:
        r.verify = "failed"
        r.errors.append(f"verify(): {e or 'assertion failed'}")
    except Exception:
        r.verify = "error"
        r.errors.append("verify() raised:\n" + traceback.format_exc(limit=6))
    return r
