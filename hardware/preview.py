#!/usr/bin/env python3
"""Writes preview.png: assembled front and back views (vertex depth map). Needs only numpy."""
import json
import struct
import zlib
from pathlib import Path

import numpy as np

import rendi_shell as rs
from verify import STL, read_stl

SCALE = 4  # pixels per mm


def view(points, sign):
    """Orthographic view along Y; sign=+1 looks at the front, -1 at the back."""
    w, h = int(90 * SCALE), int(124 * SCALE)
    depth = np.full((h, w), -np.inf)
    px = np.clip(((points[:, 0] * sign + 45) * SCALE).astype(int), 0, w - 1)
    pz = np.clip(((122 - points[:, 2]) * SCALE).astype(int), 0, h - 1)
    for dx in (0, 1, 2):
        for dz in (0, 1, 2):
            np.maximum.at(depth, (np.clip(pz + dz, 0, h - 1), np.clip(px + dx, 0, w - 1)),
                          points[:, 1] * sign)
    shade = np.where(np.isfinite(depth), 60 + 195 * np.clip((depth + 45) / 90, 0, 1), 0)
    return shade.astype(np.uint8)


def main():
    manifest = json.loads((STL / "manifest.json").read_text())
    pts = []
    for name in rs.PARTS:
        verts, _ = read_stl(STL / f"{name}.stl")
        m = manifest[name]
        pts.append((verts - np.array(m["shift"])) @ np.array(m["rotation"]))
    pts = np.concatenate(pts)
    img = np.concatenate([view(pts, 1), view(pts, -1)], axis=1)
    raw = b"".join(b"\x00" + row.tobytes() for row in img)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", img.shape[1], img.shape[0], 8, 0, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    (Path(__file__).resolve().parent / "preview.png").write_bytes(png)


if __name__ == "__main__":
    main()
