"""Mesh helpers: tessellation, STL loading and remix booleans (manifold3d).

build123d's B-rep kernel is slow and fragile with large triangle meshes, so STL
remixes go through manifold3d instead:

    from od import mesh
    base = mesh.load("refs/original.stl")
    with BuildPart() as cut: ...                       # new geometry in build123d
    result = mesh.difference(base, cut.part)           # -> trimesh.Trimesh

Parts returned from build() may be build123d Shapes or trimesh.Trimesh objects.
"""

from __future__ import annotations

import os
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

# Tessellation used for exports, checks and renders.
LINEAR_TOL = 0.01    # mm chordal deviation
ANGULAR_TOL = 0.05   # rad (~3 deg)

# Creases sharper than this are drawn as feature lines (renders + viewer).
SHARP_EDGE_DEG = 25.0


def is_mesh(obj) -> bool:
    return isinstance(obj, trimesh.Trimesh)


def to_trimesh(obj, linear: float = LINEAR_TOL, angular: float = ANGULAR_TOL) -> trimesh.Trimesh:
    """Convert a build123d Shape (or pass through a Trimesh) to a Trimesh."""
    if is_mesh(obj):
        return obj
    verts, faces = obj.tessellate(linear, angular)
    if not faces:
        raise ValueError("shape tessellated to an empty mesh")
    return trimesh.Trimesh(
        np.array([(v.X, v.Y, v.Z) for v in verts], dtype=np.float64),
        np.array(faces, dtype=np.int64),
        process=True,
    )


def load(path: str | os.PathLike) -> trimesh.Trimesh:
    """Load an STL/3MF/OBJ as a single mesh, merging duplicate vertices."""
    m = trimesh.load(Path(path), force="mesh", process=True)
    if not isinstance(m, trimesh.Trimesh):
        raise ValueError(f"could not load {path} as a mesh")
    return m


def to_manifold(obj) -> mf.Manifold:
    m = to_trimesh(obj)
    man = mf.Manifold(
        mf.Mesh(
            vert_properties=np.asarray(m.vertices, dtype=np.float32),
            tri_verts=np.asarray(m.faces, dtype=np.uint32),
        )
    )
    if man.status() != mf.Error.NoError:
        raise ValueError(
            f"mesh is not manifold ({man.status()}); try repair(): it must be watertight"
        )
    return man


def from_manifold(man: mf.Manifold) -> trimesh.Trimesh:
    out = man.to_mesh()
    return trimesh.Trimesh(
        np.asarray(out.vert_properties)[:, :3], np.asarray(out.tri_verts), process=True
    )


def union(*objs) -> trimesh.Trimesh:
    result = to_manifold(objs[0])
    for o in objs[1:]:
        result = result + to_manifold(o)
    return from_manifold(result)


def difference(base, *cutters) -> trimesh.Trimesh:
    result = to_manifold(base)
    for o in cutters:
        result = result - to_manifold(o)
    return from_manifold(result)


def intersection(*objs) -> trimesh.Trimesh:
    result = to_manifold(objs[0])
    for o in objs[1:]:
        result = result ^ to_manifold(o)
    return from_manifold(result)


def sharp_edges(m: trimesh.Trimesh, angle_deg: float = SHARP_EDGE_DEG) -> np.ndarray:
    """Boolean mask over m.face_adjacency: True where the crease exceeds angle_deg.

    These are the "real" feature lines of a triangle mesh (corners, rims,
    chamfers), as opposed to the edges between triangles of one flat or gently
    curved surface. Used by renders and the viewer so both draw the same lines.
    """
    if not len(m.face_adjacency):
        return np.zeros(0, dtype=bool)
    return m.face_adjacency_angles > np.radians(angle_deg)


def feature_edges(m: trimesh.Trimesh, angle_deg: float = SHARP_EDGE_DEG) -> np.ndarray:
    """Sharp-crease segments of a mesh, shape (n, 2, 3)."""
    mask = sharp_edges(m, angle_deg)
    return m.vertices[m.face_adjacency_edges[mask]]


def repair(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Best-effort fix for downloaded STLs (duplicate verts, holes, normals)."""
    m = m.copy()
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.update_faces(m.unique_faces())
    m.remove_unreferenced_vertices()
    trimesh.repair.fill_holes(m)
    trimesh.repair.fix_normals(m)
    return m


def to_shape(m: trimesh.Trimesh, crease_deg: float = SHARP_EDGE_DEG):
    """Mesh -> build123d Face holding the triangulation (viewer only, not for CAD).

    The OCP viewer shades a triangulated face by averaging triangle normals at
    each shared vertex. On a raw mesh that blends across sharp corners and
    makes flat areas look blotchy, so vertices are first split along creases
    sharper than crease_deg: flat faces then shade flat, curves shade smooth.
    """
    import build123d as bd
    from OCP.BRep import BRep_Builder
    from OCP.gp import gp_Pnt
    from OCP.Poly import Poly_Triangle, Poly_Triangulation
    from OCP.TopoDS import TopoDS_Face

    shaded = trimesh.graph.smooth_shade(m, angle=np.radians(crease_deg))
    tri = Poly_Triangulation(len(shaded.vertices), len(shaded.faces), False)
    for i, (x, y, z) in enumerate(shaded.vertices.tolist(), 1):
        tri.SetNode(i, gp_Pnt(x, y, z))
    for i, (a, b, c) in enumerate(shaded.faces.tolist(), 1):
        tri.SetTriangle(i, Poly_Triangle(a + 1, b + 1, c + 1))  # OCCT is 1-based
    face = TopoDS_Face()
    BRep_Builder().MakeFace(face, tri)
    return bd.Face(face)


def to_edges(m: trimesh.Trimesh, angle_deg: float = SHARP_EDGE_DEG):
    """The mesh's feature lines (see feature_edges) as a build123d Compound of edges."""
    import build123d as bd

    return bd.Compound([bd.Edge.make_line(tuple(p), tuple(q)) for p, q in feature_edges(m, angle_deg).tolist()])
