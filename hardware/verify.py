#!/usr/bin/env python3
"""Checks the STLs written by rendi_shell.py. Needs only numpy.

Reads the files back from disk (so it tests what the slicer will see):
topology, bounds, volume, bed contact, overhangs, then puts the parts back in
assembled position and checks clearances against the design distance fields.
Exit code 1 if any hard check fails.
"""
import json
import sys
from pathlib import Path

import numpy as np

import rendi_shell as rs

STL = Path(__file__).resolve().parent / "stl"
PLA_G_PER_MM3 = 1.24e-3
fails = []


def check(ok, label):
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        fails.append(label)


def read_stl(path):
    raw = path.read_bytes()
    n = int(np.frombuffer(raw, dtype="<u4", count=1, offset=80)[0])
    assert len(raw) == 84 + 50 * n, "not a binary STL of the declared size"
    rec = np.frombuffer(raw, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")],
                        count=n, offset=84)
    corners = rec["v"].reshape(-1, 3)
    verts, inv = np.unique(corners, axis=0, return_inverse=True)
    return verts.astype(np.float64), inv.reshape(-1, 3)


def topology(verts, tris):
    nv = len(verts)
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    directed = e[:, 0].astype(np.int64) * nv + e[:, 1]
    reverse = e[:, 1].astype(np.int64) * nv + e[:, 0]
    uniq, counts = np.unique(directed, return_counts=True)
    oriented_manifold = bool((counts == 1).all() and np.isin(reverse, uniq).all())
    und = np.unique(np.minimum(directed, reverse))
    # connected shells by label propagation
    label = np.arange(nv)
    while True:
        new = label.copy()
        np.minimum.at(new, e[:, 0], label[e[:, 1]])
        np.minimum.at(new, e[:, 1], label[e[:, 0]])
        new = new[new]
        if (new == label).all():
            break
        label = new
    shells = len(np.unique(label))
    degenerate = int((tris[:, 0] == tris[:, 1]).sum() + (tris[:, 1] == tris[:, 2]).sum()
                     + (tris[:, 0] == tris[:, 2]).sum())
    euler = nv - len(und) + len(tris)
    return oriented_manifold, shells, degenerate, euler


def face_data(verts, tris):
    p = verts[tris]
    cr = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(cr, axis=1) / 2
    normal = cr / np.maximum(2 * area[:, None], 1e-20)
    volume = np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6
    return p, area, normal, volume


def main():
    manifest = json.loads((STL / "manifest.json").read_text())
    assembled = {}
    for name in rs.PARTS:
        verts, tris = read_stl(STL / f"{name}.stl")
        p, area, normal, volume = face_data(verts, tris)
        manifold, shells, degenerate, euler = topology(verts, tris)
        lo, hi = verts.min(axis=0), verts.max(axis=0)
        print(f"\n{name}.stl: {len(tris)} tris, {len(verts)} verts")
        print(f"   print bbox {np.round(hi - lo, 2).tolist()} mm, z from {lo[2]:.3f}")
        print(f"   volume {volume / 1000:.2f} cm3 (~{volume * PLA_G_PER_MM3:.0f} g if solid PLA),"
              f" area {area.sum() / 100:.1f} cm2, genus {1 - euler // 2}")
        check(manifold, "watertight: every edge shared by exactly 2 faces, consistent winding")
        check(shells == 1, f"single connected shell (found {shells})")
        check(degenerate == 0, "no collapsed triangles")
        check(volume > 0, "positive volume (normals point outward)")
        check(abs(lo[2]) < 1e-6 and (hi[:2] - lo[:2]).max() <= 180,
              "sits on z=0 and fits a 180 mm bed")
        zc = p[:, :, 2].mean(axis=1)
        down = normal[:, 2] < 0
        bed = down & (p[:, :, 2].max(axis=1) < 0.05)
        print(f"   bed contact area {area[bed].sum():.0f} mm2")
        check(area[bed].sum() > 100, "has a real flat bed face")
        tilt = np.degrees(np.arccos(np.clip(-normal[:, 2], -1, 1)))  # 0 = flat ceiling
        over = down & ~bed
        a30 = area[over & (tilt < 30)].sum()
        a45 = area[over & (tilt >= 30) & (tilt < 45)].sum()
        hmax = zc[over & (tilt < 30)].max() if a30 > 0 else 0.0
        print(f"   overhang steeper than 45 deg: {a30:.0f} mm2 within 30 deg of flat"
              f" (up to z={hmax:.1f}), {a45:.0f} mm2 at 30-45 deg")
        m = manifest[name]
        assembled[name] = (verts - np.array(m["shift"])) @ np.array(m["rotation"])

    print("\nAssembled-position checks (design SDF sampled at the other part's vertices)")
    def gap(a, b):
        v = assembled[a]
        return float(rs.PARTS[b][0](v[:, 0], v[:, 1], v[:, 2]).min())

    tol = 0.05
    for a, b, want, note in [
        ("rendi_front_half", "rendi_back_half", 0.0, "seam faces touch"),
        ("rendi_back_half", "rendi_front_half", 0.0, "seam faces touch"),
        ("rendi_join_ring", "rendi_front_half", rs.RING_CLEAR, "ring radial clearance"),
        ("rendi_join_ring", "rendi_back_half", rs.RING_CLEAR, "ring radial clearance"),
        ("rendi_front_half", "rendi_join_ring", rs.RING_CLEAR, "ring radial clearance"),
        ("rendi_back_half", "rendi_join_ring", rs.RING_CLEAR, "ring radial clearance"),
        ("rendi_faceplate", "rendi_front_half", 0.0, "taper fit, see README"),
        ("rendi_front_half", "rendi_faceplate", 0.0, "taper fit, see README"),
        ("rendi_faceplate", "rendi_back_half", 1.0, "free"),
        ("rendi_faceplate", "rendi_join_ring", 1.0, "free"),
    ]:
        g = gap(a, b)
        print(f"   {a} -> {b}: min gap {g:+.3f} mm ({note})")
        check(g >= want - tol, f"no interference, gap >= {want:.2f} - {tol} mm mesh tolerance")

    f = assembled["rendi_front_half"]
    on_open = (np.abs(rs.sd_face_frustum(f[:, 0], f[:, 1], f[:, 2])) < 0.02) & (f[:, 1] > 10)
    rim = on_open & (rs.sd_outer(f[:, 0], f[:, 1], f[:, 2]) > -(rs.EDGE_BREAK * 1.5 + 0.4))
    w = np.ptp(f[rim, 0])
    h = np.ptp(f[rim, 2])
    print(f"\nFaceplate opening just inside the outer rim chamfer: {w:.1f} x {h:.1f} mm"
          f" (spec 60 x 35), centre z={(f[rim, 2].min() + f[rim, 2].max()) / 2:.1f}")
    check(abs(w - 60) < 2.5 and abs(h - 35) < 4, "opening close to 60 x 35")
    v = np.concatenate([assembled["rendi_front_half"], assembled["rendi_back_half"]])
    size = np.ptp(v, axis=0)
    foot = v[v[:, 2] < 0.02]
    print(f"Assembled shell: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm,"
          f" flat base dia {2 * np.hypot(foot[:, 0], foot[:, 1]).max():.1f} mm")
    check(abs(size[2] - 120) < 0.5 and abs(size[0] - 85) < 0.5, "120 mm tall, 85 mm max dia")

    print(f"\n{'ALL CHECKS PASSED' if not fails else f'{len(fails)} CHECK(S) FAILED'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
