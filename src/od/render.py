"""Headless preview renders (no GPU or window needed, identical on Mac and Windows).

A small orthographic painter's-algorithm renderer with flat shading plus
silhouette/sharp-edge lines. It's meant for agents and humans to sanity-check a
design, not for photorealism. Use the OCP CAD Viewer for interactive inspection.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from od import mesh

PALETTE = [
    (66, 133, 196),   # blue
    (230, 145, 56),   # orange
    (95, 170, 95),    # green
    (200, 80, 90),    # red
    (150, 110, 190),  # purple
    (210, 190, 70),   # yellow
    (90, 180, 190),   # teal
]
BG = (246, 246, 244)
EDGE = (30, 30, 34)

# (label, azimuth deg, elevation deg). Azimuth 0 looks from +X, 90 from +Y.
VIEWS = [
    ("iso front-right", -60, 30),
    ("iso back-left", 120, 30),
    ("top (+Z)", -90, 90),
    ("front (-Y)", -90, 0),
    ("right (+X)", 0, 0),
    ("bottom (-Z)", -90, -90),
]


def _basis(az: float, el: float) -> np.ndarray:
    az, el = math.radians(az), math.radians(el)
    d = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    up = np.array([0.0, 0.0, 1.0])
    if abs(d @ up) > 0.999:  # looking straight down/up: keep +Y up on screen
        up = np.array([0.0, 1.0, 0.0]) * (1 if d[2] > 0 else -1)
    x = np.cross(up, d)
    x /= np.linalg.norm(x)
    y = np.cross(d, x)
    return np.stack([x, y, d])  # rows: screen x, screen y, toward viewer


def _part_color(obj, i: int) -> tuple[int, int, int]:
    c = getattr(obj, "color", None)
    if c is not None and not mesh.is_mesh(obj):
        try:
            r, g, b, *_ = tuple(c)
            return int(r * 255), int(g * 255), int(b * 255)
        except (TypeError, ValueError):
            pass
    return PALETTE[i % len(PALETTE)]


def _refine(items, divisions: int = 30):
    """Split large triangles so the painter's-algorithm depth sort works.

    A big face (e.g. a plate's top) sorted by its average depth can be drawn
    over nearby details such as engraved text; smaller pieces sort correctly.
    """
    allv = np.vstack([m.vertices for m, _ in items])
    max_edge = float(np.linalg.norm(allv.max(0) - allv.min(0))) / divisions
    out = []
    for m, rgb in items:
        try:
            m = m.subdivide_to_size(max_edge=max_edge, max_iter=12)
        except Exception:  # noqa: BLE001 - fall back to the original mesh
            pass
        out.append((m, rgb))
    return out


def prepare(parts: dict):
    """Tessellate + refine parts once; pass the result to contact_sheet()/hero()."""
    return _refine([(mesh.to_trimesh(obj), _part_color(obj, i)) for i, obj in enumerate(parts.values())])


def render_view(items, az: float, el: float, size: int = 640, ss: int = 2) -> Image.Image:
    """items: list of (Trimesh, rgb). Returns a size x size image."""
    R = _basis(az, el)
    allv = np.vstack([m.vertices for m, _ in items])
    center = (allv.min(0) + allv.max(0)) / 2
    proj = (allv - center) @ R.T
    extent = max(np.ptp(proj[:, 0]), np.ptp(proj[:, 1]), 1e-6)
    W = size * ss
    scale = W * 0.86 / extent
    light = np.array([-0.35, 0.55, 1.0])
    light /= np.linalg.norm(light)

    prims = []  # (depth, kind, points, color)
    for m, rgb in items:
        v = (m.vertices - center) @ R.T
        n = m.face_normals @ R.T
        front = n[:, 2] > 1e-9
        tri = v[m.faces]
        shade = 0.38 + 0.62 * np.clip(n @ light, 0, 1)
        depth = tri[:, :, 2].mean(1)
        base = np.array(rgb, dtype=float)
        for fi in np.nonzero(front)[0]:
            col = tuple(int(c) for c in np.clip(base * shade[fi], 0, 255))
            prims.append((depth[fi], 0, tri[fi, :, :2], col))
        # Silhouette edges and sharp creases (>25 deg) where a face is visible.
        if len(m.face_adjacency):
            fa = m.face_adjacency
            sil = front[fa[:, 0]] != front[fa[:, 1]]
            sharp = mesh.sharp_edges(m) & (front[fa[:, 0]] | front[fa[:, 1]])
            # Draw each edge just after the nearest visible face it borders, so
            # faces in front of it still cover it and its own faces don't.
            fdepth = np.where(front, depth, -np.inf)
            edepth = np.maximum(fdepth[fa[:, 0]], fdepth[fa[:, 1]]) + 1e-9
            for ei in np.nonzero(sil | sharp)[0]:
                seg = v[m.face_adjacency_edges[ei]]
                prims.append((edepth[ei], 1, seg[:, :2], EDGE))

    prims.sort(key=lambda p: p[0])
    img = Image.new("RGB", (W, W), BG)
    draw = ImageDraw.Draw(img)
    lw = max(1, ss)
    for _, kind, pts, col in prims:
        xy = [(W / 2 + x * scale, W / 2 - y * scale) for x, y in pts]
        if kind == 0:
            draw.polygon(xy, fill=col, outline=col)
        else:
            draw.line(xy, fill=col, width=lw)
    return img.resize((size, size), Image.LANCZOS)


def _font(px: int):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def contact_sheet(parts: dict, title: str, out: Path, size: int = 520, views=VIEWS, items=None) -> Path:
    """Render all views of all parts into one labeled PNG grid.

    Pass `items=prepare(parts)` to reuse tessellation across several renders.
    """
    items = items or prepare(parts)
    cols = 3
    rows = math.ceil(len(views) / cols)
    header = 64
    sheet = Image.new("RGB", (cols * size, rows * size + header), (255, 255, 255))
    d = ImageDraw.Draw(sheet)

    allv = np.vstack([m.vertices for m, _ in items])
    lo, hi = allv.min(0), allv.max(0)
    dims = hi - lo
    small = _font(15)
    d.text((12, 8), title, fill=(0, 0, 0), font=_font(22))
    info = (
        f"size X {dims[0]:.1f} x Y {dims[1]:.1f} x Z {dims[2]:.1f} mm   "
        f"z-min {round(lo[2], 2) + 0.0:.2f}   parts: "
    )
    d.text((12, 38), info, fill=(60, 60, 60), font=small)
    x = 12 + int(d.textlength(info, font=small))
    for name, (_, rgb) in zip(parts, items):
        d.rectangle([x, 41, x + 11, 52], fill=rgb)
        d.text((x + 16, 38), name, fill=(60, 60, 60), font=small)
        x += 16 + int(d.textlength(name + "    ", font=small))

    for i, (label, az, el) in enumerate(views):
        img = render_view(items, az, el, size=size)
        ImageDraw.Draw(img).text((10, 8), label, fill=(80, 80, 80), font=_font(16))
        sheet.paste(img, ((i % cols) * size, header + (i // cols) * size))
        d.rectangle(
            [(i % cols) * size, header + (i // cols) * size,
             (i % cols + 1) * size - 1, header + (i // cols + 1) * size - 1],
            outline=(220, 220, 220),
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def hero(parts: dict, out: Path, size: int = 800, items=None) -> Path:
    """Single iso view, used as the README thumbnail."""
    items = items or prepare(parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    render_view(items, -60, 30, size=size).save(out)
    return out
