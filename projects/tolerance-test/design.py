"""tolerance-test: calibration print for the fit values in src/od/tol.py.

A plate of holes, each a known diametral clearance larger than the nominal
peg diameter, plus a separate loose peg. Try the peg in every hole and note
which clearance gives a press, snug, sliding and loose fit. Then update
PRESS / SNUG / SLIDING / LOOSE (and HOLE_COMPENSATION) in src/od/tol.py.

Holes are NOT compensated here (raw nominal + clearance), so the results
measure your printer directly.

Two materials: `plate` and `peg` can use different tools to test cross-material fits.
"""

from dataclasses import dataclass, field

from build123d import *  # noqa: F403

from od import tol


@dataclass
class Params:
    peg_d: float = 8.0  # nominal peg diameter
    peg_h: float = 14.0  # peg length
    clearances: list[float] = field(  # diametral clearance per hole
        default_factory=lambda: [
            0.0,
            0.05,
            0.10,
            0.15,
            0.20,
            0.25,
            0.30,
            0.40,
            0.50,
            0.60,
        ]
    )
    columns: int = 5
    pitch: float = 16.0  # hole center spacing
    plate_t: float = 6.0  # plate thickness (= fit engagement length)
    margin: float = 6.0
    label_size: float = 3.2
    label_depth: float = 0.6
    gap_to_peg: float = 10.0  # bed spacing between plate and peg


VARIANTS: dict[str, Params] = {}


def _layout(p: Params):
    rows = -(-len(p.clearances) // p.columns)
    w = p.columns * p.pitch + 2 * p.margin
    d = rows * (p.pitch + p.label_size) + 2 * p.margin
    return rows, w, d


def build(p: Params) -> dict[str, Part]:
    _, w, d = _layout(p)
    cell_h = p.pitch + p.label_size
    with BuildPart() as plate:
        Box(w, d, p.plate_t, align=(Align.MIN, Align.MIN, Align.MIN))
        chamfer(plate.edges().group_by(Axis.Z)[0], tol.BOTTOM_CHAMFER)
        for _, c in enumerate(p.clearances):
            r, col = divmod(_, p.columns)
            x = p.margin + (col + 0.5) * p.pitch
            y = d - p.margin - r * cell_h - p.pitch / 2
            with Locations((x, y, p.plate_t)):
                Hole((p.peg_d + c) / 2)
            label_xy = (x, y - p.pitch / 2 - p.label_size * 0.35)
            with BuildSketch(Plane.XY.offset(p.plate_t)) as lbl, Locations(label_xy):
                Text(f"{c:.2f}", p.label_size, align=(Align.CENTER, Align.CENTER))
            extrude(lbl.sketch, amount=-p.label_depth, mode=Mode.SUBTRACT)

    with BuildPart() as peg:
        with Locations((w + p.gap_to_peg + p.peg_d / 2, p.margin + p.peg_d / 2, 0)):
            Cylinder(
                p.peg_d / 2, p.peg_h, align=(Align.CENTER, Align.CENTER, Align.MIN)
            )
        chamfer(peg.edges().group_by(Axis.Z)[-1], 0.8)  # lead-in on top
        chamfer(peg.edges().group_by(Axis.Z)[0], tol.BOTTOM_CHAMFER)

    return {"plate": plate.part, "peg": peg.part}


def verify(parts: dict[str, Part], p: Params) -> None:
    peg_bb = parts["peg"].bounding_box()
    assert abs(peg_bb.size.X - p.peg_d) < 0.01, (
        f"peg diameter {peg_bb.size.X:.3f} != {p.peg_d}"
    )
    assert abs(peg_bb.size.Z - p.peg_h) < 0.01, f"peg length {peg_bb.size.Z:.3f}"
    plate = parts["plate"]
    holes = [f for f in plate.faces() if f.geom_type == GeomType.CYLINDER]
    assert len(holes) == len(p.clearances), (
        f"{len(holes)} holes, expected {len(p.clearances)}"
    )
    got = sorted(round(2 * f.radius, 3) for f in holes)
    want = sorted(round(p.peg_d + c, 3) for c in p.clearances)
    assert got == want, f"hole diameters {got} != {want}"
    assert abs(plate.bounding_box().size.Z - p.plate_t) < 0.01


if __name__ == "__main__":
    # Preview in the OCP CAD Viewer. Optional argument: a variant name, or "all".
    from od.view import preview

    preview(build, Params, VARIANTS)
