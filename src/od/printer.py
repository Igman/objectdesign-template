"""Printer profile, loaded from `printer.toml` at the repo root.

Edit printer.toml (not this file) to describe your printer; every design,
check and tolerance reads the values exposed here.
"""

from __future__ import annotations

import tomllib

from od import project

CONFIG = project.repo_root() / "printer.toml"

try:
    _cfg = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
except FileNotFoundError:
    raise SystemExit(f"error: {CONFIG} not found. Copy it from the template and describe your printer.") from None
except tomllib.TOMLDecodeError as e:
    raise SystemExit(f"error: {CONFIG} is not valid TOML: {e}") from None


def _get(section: str | None, key: str, kind=float):
    table = _cfg if section is None else _cfg.get(section, {})
    if key not in table:
        where = f"[{section}] " if section else ""
        raise SystemExit(f"error: {CONFIG.name} is missing {where}{key}")
    return kind(table[key])


NAME: str = _get(None, "name", str)
SLICER: str = _get(None, "slicer", str)

# Build volume in mm (X, Y, Z).
BED_X: float = _get("bed", "x")
BED_Y: float = _get("bed", "y")
BED_Z: float = _get("bed", "z")
BED = (BED_X, BED_Y, BED_Z)

# Filaments/materials one print job can use (1 = single material).
MATERIAL_SLOTS: int = _get("materials", "slots", int)

# Default process assumptions.
NOZZLE: float = _get("process", "nozzle")
LAYER: float = _get("process", "layer")
FIRST_LAYER: float = _get("process", "first_layer")
LINE_WIDTH: float = _get("process", "line_width")


def summary() -> str:
    return (
        f"{NAME}: bed {BED_X:g}×{BED_Y:g}×{BED_Z:g} mm, {MATERIAL_SLOTS} material slot(s), "
        f"{NOZZLE:g} mm nozzle, {LAYER:g} mm layers, slicer: {SLICER}"
    )
