"""Shared print tolerances and design rules for the printer in printer.toml.

All fit clearances are DIAMETRAL (total) gaps: hole_d = shaft_d + clearance.
For a gap between two flat faces use clearance / 2 per side.

These are starting values. Print `projects/tolerance-test` and tune them here;
every design picks up the change.
"""

from od import printer

# --- Fits (diametral clearance, mm) -----------------------------------------
PRESS = 0.10    # press fit: needs force, stays put
SNUG = 0.20     # snug: assembles by hand, no wobble
SLIDING = 0.30  # sliding: moves freely, minimal play
LOOSE = 0.50    # loose: drops in, visible play

# Holes printed vertically (axis along Z) come out slightly small.
HOLE_COMPENSATION = 0.10


def hole(d: float, fit: float = SNUG) -> float:
    """Diameter for a vertical hole that mates with a shaft of diameter d."""
    return d + fit + HOLE_COMPENSATION


def shaft(d: float, fit: float = SNUG) -> float:
    """Diameter for a shaft that mates with a hole of nominal diameter d."""
    return d - fit


def gap(fit: float = SNUG) -> float:
    """Per-side gap between two flat mating faces."""
    return fit / 2


# --- Walls & features ---------------------------------------------------------
MIN_WALL = 3 * printer.LINE_WIDTH   # ~1.26 mm: three perimeters
WALL = 2.0                          # default structural wall
MIN_FEATURE = 2 * printer.NOZZLE    # smallest reliable XY feature
MIN_EMBOSS_DEPTH = 0.6              # text/logos: >= 3 layers
MAX_OVERHANG_DEG = 45.0             # beyond this, chamfer or add support
MAX_BRIDGE = 20.0                   # mm, unsupported bridge span
BOTTOM_CHAMFER = 0.4                # elephant's-foot relief on bed edges

# --- Fasteners (mm) -----------------------------------------------------------
# Clearance holes for metric screws (normal fit), vertical orientation.
SCREW_CLEARANCE = {"M2": 2.4, "M2.5": 2.9, "M3": 3.4, "M4": 4.5, "M5": 5.5, "M6": 6.6}
# Pilot holes for screwing directly into plastic (self-tapping).
SCREW_PILOT = {"M2": 1.7, "M2.5": 2.1, "M3": 2.6, "M4": 3.5, "M5": 4.3}
# Heat-set threaded inserts (common short inserts: hole diameter, min depth).
HEAT_SET_INSERT = {
    "M2": (3.2, 4.0),
    "M2.5": (3.6, 4.5),
    "M3": (4.0, 5.0),
    "M4": (5.6, 6.0),
    "M5": (6.4, 7.0),
}
# Hex nut traps: across-flats + clearance, thickness.
NUT_TRAP = {"M2": (4.3, 1.8), "M2.5": (5.3, 2.2), "M3": (5.8, 2.6), "M4": (7.3, 3.4), "M5": (8.3, 4.2)}
