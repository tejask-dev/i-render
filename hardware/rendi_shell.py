#!/usr/bin/env python3
"""Rendi droplet shell: parametric geometry -> print-oriented STLs.

See hardware/README.md for dimensions, print files and fit checks.
Needs only numpy (python3 rendi_shell.py). Every part is a signed-distance
function (negative = inside) in ASSEMBLED coordinates, in mm:
    Z up, base on z = 0, +Y = front (face), -Y = back, split plane y = 0.
Parts are meshed with marching tetrahedra (always watertight) and then
rotated so the intended bed face is on z = 0.

Edit the PARAMETERS block and re-run; then run verify.py.
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------- PARAMETERS
HEIGHT = 120.0        # overall height
MAX_DIA = 85.0        # bulb diameter
BULB_Z = 35.0         # height of the widest point above the base (spec: 35-40)
TIP_R = 2.0           # rounded tip radius (spec: tip dia 4)
WALL = 2.4            # shell wall and floor (6 lines on a 0.4 nozzle)

# Join: separate friction ring that straddles the split plane, glued in the back half
RING_CLEAR = 0.20     # radial gap ring <-> inner wall. UNTESTED, tune per printer
RING_T = 1.6          # ring thickness
RING_LIP = 3.0        # engagement into each half (spec: 3 mm lip)
RING_TOP_Z = 106.0    # ring closes with a flat bar here instead of following the sharp tip
RING_CORNER = 0.5     # corner relief where the ring meets the floor (blobs, elephant foot)

# Faceplate opening: oval, tapered so the insert wedges in from the inside
FACE_W = 60.0         # opening width, measured at y = FACE_W_Y (where the sides cut the wall)
FACE_H = 35.0         # opening height, measured at y = FACE_H_Y (where top/bottom cut the wall)
FACE_ZC = 44.0        # opening centre height
FACE_W_Y = 26.0
FACE_H_Y = 37.0
FACE_TAPER_DEG = 7.0  # per side; the opening is wider toward the inside
FACE_FIT = 0.10       # insert undersize per side. UNTESTED, tune per printer
FACE_FLOOR_Y = 25.5   # front surface of the recessed flat eye panel
FACE_FLOOR_T = 1.0    # eye panel thickness (thin so LEDs glow through white PLA)
FACE_WALL_T = 1.2     # insert side wall
FACE_SETBACK = 0.6    # insert rim sits this far below the shell surface
EDGE_BREAK = 0.3      # small chamfer on the sharp rims of the opening and the insert
# raised eyes on the panel: (x, z offset from FACE_ZC, half width, half height)
EYES = [(-13.0, 1.0, 5.5, 7.5), (13.0, 1.0, 5.5, 7.5)]
EYE_RAISE = 0.6

MIC_D = 2.0           # 3 mic holes, front, below the faceplate
MIC_PITCH = 6.0
MIC_BELOW = 6.0       # hole centres this far below the opening's bottom edge

GRILLE_D = 40.0       # speaker grille pattern diameter, back-bottom
GRILLE_ZC = 28.0
GRILLE_HEX = 4.0      # hex hole across flats
GRILLE_PITCH = 5.6    # hole centre spacing (web = pitch - hex)

CABLE_W = 10.0        # cable slot, base, back
CABLE_H = 6.0

GRID_SHELL = 0.6      # mesh resolution for the two halves
GRID_SMALL = 0.4      # mesh resolution for ring and faceplate
# ---------------------------------------------------------------------------

R1 = MAX_DIA / 2.0
Z2 = HEIGHT - TIP_R
TAPER = np.tan(np.radians(FACE_TAPER_DEG))
FAR = 1e3


def _all(*d):
    """Intersection of several distance fields."""
    out = d[0]
    for other in d[1:]:
        out = np.maximum(out, other)
    return out


def _chamfered(a, b, k=None):
    """Intersection of two fields with the shared edge broken by a chamfer."""
    k = EDGE_BREAK if k is None else k
    return _all(a, b, (a + b) * np.sqrt(0.5) + k)


def base_dia():
    return 2.0 * np.sqrt(R1 ** 2 - BULB_Z ** 2)


def _round_cone(r, z):
    """Exact distance to the droplet outline (bulb sphere hulled with the tip sphere)."""
    h = Z2 - BULB_Z
    b = (R1 - TIP_R) / h
    a = np.sqrt(1.0 - b * b)
    qz = z - BULB_Z
    k = -b * r + a * qz
    d_bulb = np.hypot(r, qz) - R1
    d_tip = np.hypot(r, qz - h) - TIP_R
    d_cone = a * r + b * qz - R1
    return np.where(k < 0, d_bulb, np.where(k > a * h, d_tip, d_cone))


def sd_outer(x, y, z):
    return np.maximum(_round_cone(np.hypot(x, y), z), -z)


def sd_cavity(x, y, z, extra=0.0):
    """Inner cavity, optionally shrunk by `extra`."""
    off = WALL + extra
    return np.maximum(_round_cone(np.hypot(x, y), z) + off, off - z)


def sd_wall(x, y, z):
    return np.maximum(sd_outer(x, y, z), -sd_cavity(x, y, z))


def _ellipse(u, v, a, b):
    """Pseudo-distance to an ellipse (exact zero set)."""
    return (np.sqrt((u / a) ** 2 + (v / b) ** 2) - 1.0) * np.minimum(a, b)


def sd_face_frustum(x, y, z, inset=0.0):
    a = FACE_W / 2.0 + (FACE_W_Y - y) * TAPER - inset
    b = FACE_H / 2.0 + (FACE_H_Y - y) * TAPER - inset
    return _ellipse(x, z - FACE_ZC, np.maximum(a, 0.1), np.maximum(b, 0.1))


def mic_z():
    return FACE_ZC - FACE_H / 2.0 - MIC_BELOW


def sd_mics(x, y, z):
    d = FAR
    for i in (-1, 0, 1):
        d = np.minimum(d, np.hypot(x - i * MIC_PITCH, z - mic_z()) - MIC_D / 2.0)
    return np.maximum(d, 10.0 - y)


def sd_grille(x, y, z):
    u, v = x, z - GRILLE_ZC
    cell = np.array([GRILLE_PITCH, GRILLE_PITCH * np.sqrt(3.0)])
    best = FAR
    for ou, ov in ((0.0, 0.0), (cell[0] / 2.0, cell[1] / 2.0)):
        cu = np.round((u - ou) / cell[0]) * cell[0] + ou
        cv = np.round((v - ov) / cell[1]) * cell[1] + ov
        qu, qv = np.abs(u - cu), np.abs(v - cv)
        hexd = np.maximum(qu * (np.sqrt(3.0) / 2.0) + qv / 2.0, qv) - GRILLE_HEX / 2.0
        keep = np.hypot(cu, cv) <= GRILLE_D / 2.0 - GRILLE_HEX / np.sqrt(3.0)
        best = np.minimum(best, np.where(keep, hexd, FAR))
    return np.maximum(best, y + 10.0)


def sd_cable(x, y, z):
    return _all(np.abs(x) - CABLE_W / 2.0, WALL - z, z - WALL - CABLE_H,
                              y + 10.0)


def sd_front(x, y, z):
    opening = np.maximum(sd_face_frustum(x, y, z), 10.0 - y)
    shell = _all(_chamfered(sd_outer(x, y, z), -opening),
                 _chamfered(-sd_cavity(x, y, z), -opening))
    return _all(shell, -y, -sd_mics(x, y, z))


def sd_back(x, y, z):
    return _all(sd_wall(x, y, z), y, -sd_grille(x, y, z),
                              -sd_cable(x, y, z))


def sd_ring(x, y, z):
    off = WALL + RING_CLEAR
    side = _round_cone(np.hypot(x, y), z) + off
    floor = off - z
    outer = _all(side, floor, (side + floor) * np.sqrt(0.5) + RING_CORNER, z - RING_TOP_Z)
    hollow = np.maximum(sd_cavity(x, y, z, RING_CLEAR + RING_T), z - RING_TOP_Z + RING_T)
    return _all(outer, -hollow, np.abs(y) - RING_LIP)


def sd_faceplate(x, y, z):
    back = FACE_FLOOR_Y - FACE_FLOOR_T
    rim = sd_outer(x, y, z) + FACE_SETBACK
    pocket = np.maximum(sd_face_frustum(x, y, z, FACE_FIT + FACE_WALL_T), FACE_FLOOR_Y - y)
    d = _all(_chamfered(sd_face_frustum(x, y, z, FACE_FIT), rim), _chamfered(-pocket, rim),
             back - y)
    for ex, ez, ea, eb in EYES:
        eye = _all(_ellipse(x - ex, z - FACE_ZC - ez, ea, eb),
                                 FACE_FLOOR_Y - 0.2 - y, y - FACE_FLOOR_Y - EYE_RAISE)
        d = np.minimum(d, eye)
    return d


# Print orientation: rows of R map assembled (x, y, z) to printer (X, Y, Z).
R_FRONT_UP = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]   # +y (front) points up, seam on the bed
R_BACK_UP = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]    # -y (back) points up, seam on the bed

# name: (sdf, assembled-space bounds lo/hi, grid step, print rotation)
PARTS = {
    "rendi_front_half": (sd_front, (-R1, 0, 0), (R1, R1, HEIGHT), GRID_SHELL, R_FRONT_UP),
    "rendi_back_half": (sd_back, (-R1, -R1, 0), (R1, 0, HEIGHT), GRID_SHELL, R_BACK_UP),
    "rendi_join_ring": (sd_ring, (-R1, -RING_LIP, 0), (R1, RING_LIP, HEIGHT), GRID_SMALL,
                        R_FRONT_UP),
    "rendi_faceplate": (sd_faceplate, (-FACE_W / 2 - 4, FACE_FLOOR_Y - FACE_FLOOR_T,
                                       FACE_ZC - FACE_H / 2 - 4),
                        (FACE_W / 2 + 4, R1, FACE_ZC + FACE_H / 2 + 4), GRID_SMALL, R_FRONT_UP),
}

_KUHN = [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]


def mesh_sdf(sdf, lo, hi, step):
    """Marching tetrahedra on a regular grid. Returns (vertices, triangles)."""
    pad = 2.37 * step  # non-round offset keeps flat faces off the grid nodes
    axes = [np.arange(l - pad, h + pad + step, step) for l, h in zip(lo, hi)]
    nx, ny, nz = (len(a) for a in axes)
    X, Y, Z = np.meshgrid(*axes, indexing="ij", sparse=True)
    V = np.asarray(sdf(X, Y, Z), dtype=np.float64)
    V = np.broadcast_to(V, (nx, ny, nz))
    inside = V < 0
    c = [inside[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k]
         for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    n_in = sum(a.astype(np.int8) for a in c)
    cubes = np.argwhere((n_in > 0) & (n_in < 8))
    vflat = V.reshape(-1)
    origin = np.array([a[0] for a in axes])

    tri_lo, tri_hi, tri_ref = [], [], []
    for perm in _KUHN:
        offs = np.zeros((4, 3), dtype=np.int64)
        for n, ax in enumerate(perm):
            offs[n + 1:, ax] = 1
        ijk = cubes[:, None, :] + offs[None, :, :]                 # (M, 4, 3)
        ids = (ijk[..., 0] * ny + ijk[..., 1]) * nz + ijk[..., 2]  # (M, 4)
        vals = vflat[ids]
        neg = vals < 0
        cnt = neg.sum(axis=1)
        order = np.argsort(~neg, axis=1, kind="stable")            # inside vertices first
        ids_s = np.take_along_axis(ids, order, axis=1)
        pos_s = np.take_along_axis(ijk, order[..., None], axis=1).astype(np.float64)

        def emit(mask, pairs, n_inside):
            if not mask.any():
                return
            i_s, p_s = ids_s[mask], pos_s[mask]
            ref = p_s[:, n_inside:].mean(axis=1) - p_s[:, :n_inside].mean(axis=1)
            a = np.stack([i_s[:, p[0]] for p in pairs], axis=1)
            b = np.stack([i_s[:, p[1]] for p in pairs], axis=1)
            tri_lo.append(np.minimum(a, b))
            tri_hi.append(np.maximum(a, b))
            tri_ref.append(ref)

        emit(cnt == 1, [(0, 1), (0, 2), (0, 3)], 1)
        emit(cnt == 3, [(3, 0), (3, 1), (3, 2)], 3)
        emit(cnt == 2, [(0, 2), (0, 3), (1, 3)], 2)
        emit(cnt == 2, [(0, 2), (1, 3), (1, 2)], 2)

    lo_id = np.concatenate(tri_lo)
    hi_id = np.concatenate(tri_hi)
    ref = np.concatenate(tri_ref)
    keys = lo_id.astype(np.int64) * (nx * ny * nz) + hi_id
    uniq, inv = np.unique(keys.reshape(-1), return_inverse=True)
    tris = inv.reshape(-1, 3)
    u_lo, u_hi = uniq // (nx * ny * nz), uniq % (nx * ny * nz)

    def node_xyz(i):
        return np.stack([i // (ny * nz), (i // nz) % ny, i % nz], axis=1) * step + origin

    v_lo, v_hi = vflat[u_lo], vflat[u_hi]
    t = np.clip(v_lo / (v_lo - v_hi), 0.01, 0.99)[:, None]
    verts = node_xyz(u_lo) * (1 - t) + node_xyz(u_hi) * t

    p = verts[tris]
    normal = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    flip = np.einsum("ij,ij->i", normal, ref) < 0
    tris[flip] = tris[flip][:, ::-1]
    return _largest_shell(verts, tris)


def _largest_shell(verts, tris):
    """Drop grid-sized specks that marching leaves beside knife edges."""
    label = np.arange(len(verts))
    edges = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    while True:
        new = label.copy()
        np.minimum.at(new, edges[:, 0], label[edges[:, 1]])
        np.minimum.at(new, edges[:, 1], label[edges[:, 0]])
        new = new[new]
        if (new == label).all():
            break
        label = new
    ids, counts = np.unique(label, return_counts=True)
    keep = label == ids[np.argmax(counts)]
    remap = np.cumsum(keep) - 1
    return verts[keep], remap[tris[keep[tris[:, 0]]]]


def to_print(verts, rot):
    """Rotate into print orientation, centre in XY, drop onto z = 0."""
    rot = np.array(rot, dtype=np.float64)
    out = verts @ rot.T
    shift = -np.array([(out[:, 0].min() + out[:, 0].max()) / 2,
                       (out[:, 1].min() + out[:, 1].max()) / 2, out[:, 2].min()])
    return out + shift, rot, shift


def write_stl(path, verts, tris):
    p = verts[tris].astype(np.float32)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, p
    with open(path, "wb") as f:
        f.write(b"Rendi droplet shell (rendi_shell.py)".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        f.write(rec.tobytes())


def main():
    out = Path(__file__).resolve().parent / "stl"
    out.mkdir(exist_ok=True)
    only = sys.argv[1:]
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() and only else {}
    for name, (sdf, lo, hi, step, rot) in PARTS.items():
        if only and name not in only:
            continue
        verts, tris = mesh_sdf(sdf, lo, hi, step)
        pverts, rot_m, shift = to_print(verts, rot)
        write_stl(out / f"{name}.stl", pverts, tris)
        manifest[name] = {"rotation": rot_m.tolist(), "shift": shift.tolist(), "grid": step}
        size = pverts.max(axis=0) - pverts.min(axis=0)
        print(f"{name}.stl  {len(tris)} tris  print bbox {size.round(2).tolist()} mm")
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"flat base dia {base_dia():.1f} mm")


if __name__ == "__main__":
    main()
