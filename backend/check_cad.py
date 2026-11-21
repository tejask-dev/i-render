"""Checks for cad.py and templates.py, run against the files they really write.

    python backend/check_cad.py              # exports to a temp dir, then removes it
    python backend/check_cad.py --keep DIR   # leaves DIR/<template>/model.glb + model.stl

Exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import struct
import sys
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh
from pydantic import ValidationError

try:
    from . import cad, templates
except ImportError:
    import cad
    import templates

# eval/expected.json from spec 03b section 11
EXPECTED = {
    "wheelbot": {"min_parts": 4, "max_parts": 12, "must_have": {"wheel": 2},
                 "functions": ["drive"], "height_mm": [160, 240]},
    "armbot": {"min_parts": 5, "must_have": {"arm_link": 2, "servo_mount": 1},
               "functions": ["grab"]},
    "blobbot": {"min_parts": 2, "functions": ["light_up"]},
}
DEFAULT_SIZE_CM = 20
BUILD_BUDGET_S = 3.0
GENUS = {"wheel": 1, "arm_link": 2, "servo_mount": 2}   # through-holes per primitive


def close(a, b, tol):
    return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), atol=tol, rtol=0))


def glb_json(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, length = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF" and version == 2 and length == len(data), "bad GLB header"
    chunk_length, chunk_type = struct.unpack("<I4s", data[12:20])
    assert chunk_type == b"JSON"
    return json.loads(data[20:20 + chunk_length])


def glb_parts(path: Path) -> dict[str, trimesh.Trimesh]:
    """Part meshes from a GLB, welded and mapped back to source mm (Z up)."""
    scene = trimesh.load(path, force="scene")
    parts = {}
    for name, mesh in scene.geometry.items():
        mesh = mesh.copy()
        mesh.merge_vertices(merge_norm=True, merge_tex=True)
        x, y, z = (mesh.vertices * 1000.0).T
        mesh.vertices = np.column_stack([-x, z, y])
        parts[name] = mesh
    return parts


def as_manifold(mesh: trimesh.Trimesh) -> Manifold:
    solid = Manifold(Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                          tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))
    assert not solid.is_empty(), f"not a valid solid: {solid.status()}"
    return solid


def bodies(mesh: trimesh.Trimesh) -> int:
    """Separate solid pieces; sealed internal voids (negative volume) do not count."""
    return sum(piece.volume() > 0 for piece in as_manifold(mesh).decompose())


def genus(mesh: trimesh.Trimesh) -> int:
    assert mesh.is_watertight, "mesh is not watertight"
    return 1 - mesh.euler_number // 2


def rod_x(radius: float, length: float, centre) -> Manifold:
    return Manifold.cylinder(length, radius, radius, 32, True).rotate([0, 90, 0]).translate(list(centre))


def export(raw: dict, size_cm: int, out_dir: Path) -> dict:
    return cad.export_model(cad.RobotSpec.model_validate(raw), size_cm, out_dir)


def part(pid: str, primitive: str, dims: list, pos: list, **extra) -> dict:
    return {"id": pid, "label": pid, "primitive": primitive, "dims_mm": dims, "pos_mm": pos,
            "category": "structure", **extra}


def spec_of(*parts: dict, **extra) -> dict:
    return {"robot_name": "Check", "parts": list(parts), "functions": [],
            "assumptions": [], "confidence": 0.5, **extra}


# --- checks ------------------------------------------------------------------

def check_templates_match_eval(_: Path) -> str:
    assert set(templates.TEMPLATES) == {"wheelbot", "armbot", "blobbot"}
    for name, raw in templates.TEMPLATES.items():
        spec = cad.RobotSpec.model_validate(raw)
        want = EXPECTED[name]
        assert want["min_parts"] <= len(spec.parts) <= want.get("max_parts", 20), name
        for primitive, count in want.get("must_have", {}).items():
            assert sum(p.primitive == primitive for p in spec.parts) >= count, (name, primitive)
        assert set(want["functions"]) <= {f.name for f in spec.functions}, name
    return "3 templates validate and meet the 03b eval expectations"


def check_template_exports(out: Path) -> str:
    lines = []
    for name, raw in templates.TEMPLATES.items():
        started = time.perf_counter()
        result = export(raw, DEFAULT_SIZE_CM, out / name)
        elapsed = time.perf_counter() - started
        assert elapsed < BUILD_BUDGET_S, f"{name} took {elapsed:.2f}s"

        # Returned spec: JSON-ready, exactly the 03b fields, still a valid RobotSpec.
        json.dumps(result, allow_nan=False)
        assert set(result) == {"robot_name", "parts", "functions", "assumptions", "confidence"}
        normalized = cad.RobotSpec.model_validate(result)
        assert result == export(result, DEFAULT_SIZE_CM, out / name), f"{name} not idempotent"
        # Templates are drawn at 20 cm with attached parts, so nothing may be altered.
        assert result["assumptions"] == raw["assumptions"], result["assumptions"]
        for before, after in zip(raw["parts"], result["parts"]):
            assert close(before["pos_mm"], after["pos_mm"], 1e-9), before["id"]
            assert close(before["dims_mm"], after["dims_mm"], 1e-9), before["id"]

        ids = [p.id for p in normalized.parts]
        by_id = {p.id: p for p in normalized.parts}

        # GLB structure: one named mesh + node per part, normals, category material.
        doc = glb_json(out / name / "model.glb")
        assert [m["name"] for m in doc["meshes"]] == ids, "mesh names"
        mesh_nodes = {n["name"]: n for n in doc["nodes"] if "mesh" in n}
        assert sorted(mesh_nodes) == sorted(ids), "node names"
        for node in mesh_nodes.values():
            assert not {"matrix", "translation", "rotation", "scale"} & set(node), "node transform"
        for index, mesh in enumerate(doc["meshes"]):
            (node,) = [n for n in doc["nodes"] if n.get("mesh") == index]
            assert node["name"] == mesh["name"], "node and mesh names differ"
            assert mesh["extras"]["part_id"] == mesh["name"]
            (primitive,) = mesh["primitives"]
            assert {"POSITION", "NORMAL"} <= set(primitive["attributes"])
            material = doc["materials"][primitive["material"]]
            category = by_id[mesh["name"]].category
            assert material["name"] == category
            linear = material["pbrMetallicRoughness"]["baseColorFactor"][:3]
            srgb = [c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in linear]
            hex_colour = cad.CATEGORY_COLOURS[category]
            assert close([int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)], srgb, 3 / 255), category

        # GLB geometry: metres, Y up, resting on Y = 0, each part where the spec says.
        scene = trimesh.load(out / name / "model.glb", force="scene")
        low, high = scene.bounds
        assert abs(low[1]) < 2e-6, f"GLB min Y {low[1]}"
        meshes = glb_parts(out / name / "model.glb")
        for pid, mesh in meshes.items():
            p = by_id[pid]
            assert close(mesh.bounds.mean(axis=0), p.pos_mm, 1e-2), f"{pid} centre {mesh.bounds.mean(axis=0)}"
            assert genus(mesh) == GENUS.get(p.primitive, 0), f"{pid} genus {genus(mesh)}"
            assert mesh.volume > 0

        # STL: millimetres, Z up, on the ground, one closed printable body.
        stl = trimesh.load(out / name / "model.stl", force="mesh")
        assert stl.is_watertight and stl.is_winding_consistent and stl.volume > 0
        assert abs(stl.bounds[0][2]) < 1e-3, f"STL min Z {stl.bounds[0][2]}"
        assert close(stl.extents, (high - low)[[0, 2, 1]] * 1000, 1e-2), "GLB and STL sizes differ"
        height = float(stl.extents[2])
        assert abs(height - DEFAULT_SIZE_CM * 10) <= 0.25 * DEFAULT_SIZE_CM * 10
        if "height_mm" in EXPECTED[name]:
            assert EXPECTED[name]["height_mm"][0] <= height <= EXPECTED[name]["height_mm"][1]
        assert bodies(stl) == 1, f"{name} union has {bodies(stl)} separate bodies"
        assert stl.volume < sum(m.volume for m in meshes.values()), "union did not merge overlaps"
        lines.append(f"{name}: {len(ids)} named meshes, STL {np.round(stl.extents, 1).tolist()} mm, "
                     f"{len(stl.faces)} tris, 1 body, {elapsed * 1000:.0f} ms")
    return "; ".join(lines)


def check_glb_orientation(out: Path) -> str:
    assert round(float(np.linalg.det(cad._GLTF_AXES))) == 1, "axis change must not mirror"
    export(templates.TEMPLATES["wheelbot"], DEFAULT_SIZE_CM, out / "wheelbot")
    scene = trimesh.load(out / "wheelbot" / "model.glb", force="scene")
    centre = {name: mesh.bounds.mean(axis=0) for name, mesh in scene.geometry.items()}
    assert max(centre, key=lambda n: centre[n][1]) == "antenna", "+Y is not up"
    assert centre["eye_left"][2] > centre["head"][2], "front does not face +Z"
    assert centre["wheel_right"][0] < 0 < centre["wheel_left"][0], "robot's right is not -X"
    assert float(scene.extents[1]) < 0.5, "GLB is not in metres"
    return "GLB is metres, +Y up, front +Z, robot's right -X (unmirrored)"


def check_wheel_holes(out: Path) -> str:
    result = export(templates.TEMPLATES["wheelbot"], DEFAULT_SIZE_CM, out / "wheelbot")
    meshes = glb_parts(out / "wheelbot" / "model.glb")
    union = as_manifold(trimesh.load(out / "wheelbot" / "model.stl", force="mesh"))
    hole = cad.HUB_HOLE_MM
    wheels = [p for p in result["parts"] if p["primitive"] == "wheel"]
    assert len(wheels) == 2
    for p in wheels:
        d, w = p["dims_mm"]
        mesh = meshes[p["id"]]
        assert genus(mesh) == 1, f"{p['id']} has no through-hole"
        assert close(mesh.extents, [w, d, d], 1e-2), mesh.extents
        ideal = math.pi * ((d / 2) ** 2 - (hole / 2) ** 2) * w
        assert abs(mesh.volume - ideal) / ideal < 0.01, (mesh.volume, ideal)
        # A Ø4.6 axle slides through the Ø5 bore; a Ø5.6 one does not.
        for label, solid in (("part", as_manifold(mesh)), ("STL union", union)):
            assert (solid ^ rod_x(2.3, w + 10, p["pos_mm"])).volume() < 1e-6, f"{p['id']} bore blocked in {label}"
            assert (solid ^ rod_x(2.8, w, p["pos_mm"])).volume() > 1.0, f"{p['id']} bore too wide in {label}"
    return f"both wheels have an open Ø{hole:g} mm bore in the GLB part and in the STL union"


def check_every_primitive(out: Path) -> str:
    cases = [   # primitive, dims, expected unrotated extents
        ("box", [30, 20, 200], [30, 20, 200]),
        ("rounded_box", [40, 30, 20], [40, 30, 20]),
        ("cylinder", [30, 12], [30, 30, 12]),
        ("sphere", [36], [36, 36, 36]),
        ("cone", [30, 0, 40], [30, 30, 40]),
        ("wheel", [60, 20], [20, 60, 60]),
        ("arm_link", [80, 16, 6], [80, 16, 6]),
        ("servo_mount", [], [32.5, 12.5, 22]),
        ("motor_mount", [], [15, 26, 18]),
        ("antenna", [50], [6, 6, 53]),
    ]
    assert {c[0] for c in cases} == set(cad.DIM_RANGES) == set(cad.Primitive.__args__)
    parts = [part(f"p{i}", primitive, dims, [i * 70 - 315, 0, extents[2] / 2])
             for i, (primitive, dims, extents) in enumerate(cases)]
    result = export(spec_of(*parts), DEFAULT_SIZE_CM, out / "primitives")
    assert result["assumptions"] == [], result["assumptions"]
    assert result["parts"][8]["dims_mm"] == [cad.MOTOR_DEFAULT_MM], "motor_mount default"
    meshes = glb_parts(out / "primitives" / "model.glb")
    for i, (primitive, _, extents) in enumerate(cases):
        mesh = meshes[f"p{i}"]
        assert close(mesh.extents, extents, 1e-2), f"{primitive} extents {mesh.extents}"
        assert genus(mesh) == GENUS.get(primitive, 0), f"{primitive} genus {genus(mesh)}"
        assert abs(mesh.bounds[0][2]) < 1e-2, f"{primitive} is off the ground"
    box, rounded = meshes["p0"], meshes["p1"]
    assert abs(box.volume / (30 * 20 * 200) - 1) < 1e-4
    assert 0.9 * 40 * 30 * 20 < rounded.volume < 40 * 30 * 20, "rounded_box is not filleted"
    stl = trimesh.load(out / "primitives" / "model.stl", force="mesh")
    assert stl.is_watertight and bodies(stl) == len(cases)
    return "all 10 primitives export watertight with the expected size and hole count"


def check_validation_rejects(_: Path) -> str:
    good = templates.TEMPLATES["wheelbot"]
    cad.RobotSpec.model_validate(good)

    def edit(fn) -> dict:
        raw = copy.deepcopy(good)
        fn(raw)
        return raw

    def set_part(index: int, **fields):
        return edit(lambda raw: raw["parts"][index].update(fields))

    bad = {
        "NaN dimension": set_part(0, dims_mm=[float("nan"), 90, 80]),
        "infinite dimension": set_part(0, dims_mm=[100, float("inf"), 80]),
        "NaN position": set_part(0, pos_mm=[0, float("nan"), 58]),
        "infinite rotation": set_part(0, rot_deg=[0, 0, float("inf")]),
        "negative dimension": set_part(0, dims_mm=[100, -90, 80]),
        "zero dimension": set_part(7, dims_mm=[0, 22]),
        "absurd dimension": set_part(0, dims_mm=[100, 90, 1e9]),
        "absurd position": set_part(0, pos_mm=[0, 0, 1e7]),
        "absurd rotation": set_part(0, rot_deg=[0, 0, 1e6]),
        "too few dims": set_part(7, dims_mm=[70]),
        "too many dims": set_part(9, dims_mm=[20, 20]),
        "dims on servo_mount": set_part(0, primitive="servo_mount"),
        "2D position": set_part(0, pos_mm=[0, 0]),
        "4 rotations": set_part(0, rot_deg=[0, 0, 0, 0]),
        "unknown primitive": set_part(0, primitive="torus"),
        "unknown category": set_part(0, category="weapon"),
        "bad id": set_part(4, id="Antenna!"),
        "duplicate id": set_part(1, id="body"),
        "unknown attach_to": set_part(1, attach_to="torso"),
        "self attach": set_part(1, attach_to="head"),
        "attach loop": set_part(0, attach_to="eye_left"),
        "unknown function part": edit(lambda raw: raw["functions"][0]["parts"].append("jetpack")),
        "unknown function name": edit(lambda raw: raw["functions"][0].update(name="teleport")),
        "no parts": edit(lambda raw: raw.update(parts=[], functions=[])),
        "21 parts": spec_of(*[part(f"p{i}", "box", [10, 10, 10], [i * 12, 0, 5]) for i in range(21)]),
        "7 assumptions": edit(lambda raw: raw.update(assumptions=["a"] * 7)),
        "confidence above 1": edit(lambda raw: raw.update(confidence=1.5)),
        "NaN confidence": edit(lambda raw: raw.update(confidence=float("nan"))),
    }
    for label, raw in bad.items():
        try:
            cad.RobotSpec.model_validate(raw)
        except ValidationError:
            continue
        raise AssertionError(f"accepted a spec with {label}")

    spec = cad.RobotSpec.model_validate(good)
    sizes = [0, 2, 151, -20, 20.5, True, "20", None, float("nan")]
    for size in sizes:
        try:
            cad.normalize_spec(spec, size)
        except cad.CadError:
            continue
        raise AssertionError(f"accepted size_cm={size!r}")
    for size in cad.SIZE_CM_RANGE:
        cad.normalize_spec(spec, size)
    return f"rejects {len(bad)} malformed specs and {len(sizes)} bad sizes"


def check_normalization(out: Path) -> str:
    wheelbot = templates.TEMPLATES["wheelbot"]

    # Clamp: an over-wide wheel and a hair-thin eye come back inside the 03b ranges.
    raw = copy.deepcopy(wheelbot)
    raw["parts"][7]["dims_mm"] = [70, 900]
    raw["parts"][2]["dims_mm"] = [16, 0.01]
    result = export(raw, DEFAULT_SIZE_CM, out / "clamp")
    assert result["parts"][7]["dims_mm"] == [70, 60] and result["parts"][2]["dims_mm"] == [16, 1]
    assert any("Clamped eye_left, wheel_left" in note for note in result["assumptions"])

    # Scale: the same drawing at 40 cm doubles, at 8 cm shrinks; the hub bore stays Ø5.
    for size_cm in (8, 40):
        result = export(wheelbot, size_cm, out / f"scale{size_cm}")
        stl = trimesh.load(out / f"scale{size_cm}" / "model.stl", force="mesh")
        assert abs(stl.extents[2] - size_cm * 10) <= 0.25 * size_cm * 10, stl.extents
        assert abs(stl.bounds[0][2]) < 2e-3 and stl.is_watertight
        assert any("Scaled" in note for note in result["assumptions"])
        assert len(result["assumptions"]) <= cad.MAX_ASSUMPTIONS
        wheel = result["parts"][7]
        assert close(wheel["dims_mm"], np.array([70, 22]) * size_cm / 19.7, 0.01)
        mesh = glb_parts(out / f"scale{size_cm}" / "model.glb")["wheel_left"]
        assert genus(mesh) == 1
        assert (as_manifold(mesh) ^ rod_x(2.3, 200, wheel["pos_mm"])).volume() < 1e-6

    # Within 25% of the brief nothing is rescaled.
    assert export(wheelbot, 24, out / "noscale")["parts"] == export(wheelbot, 20, out / "noscale")["parts"]

    # Ground snap: a model drawn 37 mm in the air (or underground) lands on Z = 0.
    for lift in (37.0, -500.0):
        raw = copy.deepcopy(wheelbot)
        for p in raw["parts"]:
            p["pos_mm"][2] += lift
        result = export(raw, DEFAULT_SIZE_CM, out / "ground")
        assert result["parts"] == export(wheelbot, DEFAULT_SIZE_CM, out / "ground")["parts"]

    # Float check: a head hovering 30 mm above the body is pulled down, its children follow,
    # and the note fits inside a full assumptions list.
    raw = copy.deepcopy(wheelbot)
    raw["assumptions"] = [f"guess {i}" for i in range(cad.MAX_ASSUMPTIONS)]
    for index in (1, 2, 3, 4):      # head, eyes, antenna
        raw["parts"][index]["pos_mm"][2] += 30
    result = export(raw, DEFAULT_SIZE_CM, out / "float")
    by_id = {p["id"]: p for p in result["parts"]}
    assert close(by_id["head"]["pos_mm"], [0, 0, 126], 2e-3), by_id["head"]["pos_mm"]
    assert close(by_id["antenna"]["pos_mm"], [0, 0, 175.5], 2e-3), by_id["antenna"]["pos_mm"]
    assert len(result["assumptions"]) == cad.MAX_ASSUMPTIONS
    assert result["assumptions"][:5] == raw["assumptions"][:5]
    assert result["assumptions"][5].startswith("guess 5") and "moving head." in result["assumptions"][5]
    stl = trimesh.load(out / "float" / "model.stl", force="mesh")
    assert bodies(stl) == 1, "nudged head is still detached"

    # Round parts whose boxes overlap but whose surfaces miss are still joined up.
    ball = spec_of(part("a", "sphere", [100], [0, 0, 150]),
                   part("b", "sphere", [100], [72, 0, 78], attach_to="a"))
    result = export(ball, DEFAULT_SIZE_CM, out / "ball")
    assert any("moving b." in note for note in result["assumptions"]), result["assumptions"]
    assert bodies(trimesh.load(out / "ball" / "model.stl", force="mesh")) == 1

    # Rotation order is X, then Y, then Z; pos_mm stays the bounding-box centre.
    spun = spec_of(part("a", "box", [10, 20, 200], [0, 0, 100]),
                   part("b", "box", [10, 20, 30], [40, 0, 10], rot_deg=[90, 0, 90]),
                   part("c", "cone", [30, 6, 60], [-60, 0, 30], rot_deg=[35, 20, 10]))
    result = export(spun, DEFAULT_SIZE_CM, out / "rot")
    meshes = glb_parts(out / "rot" / "model.glb")
    assert close(meshes["b"].extents, [30, 10, 20], 1e-2), meshes["b"].extents
    for p in result["parts"]:
        assert close(meshes[p["id"]].bounds.mean(axis=0), p["pos_mm"], 1e-2), p["id"]

    # Extent limit: parts flung kilometres apart by scaling are refused, not exported.
    wide = spec_of(part("a", "box", [10, 10, 2], [-4000, 0, 1]), part("b", "box", [10, 10, 2], [4000, 0, 1]))
    try:
        export(wide, 150, out / "wide")
    except cad.CadError:
        assert not (out / "wide").exists(), "refused model still wrote files"
    else:
        raise AssertionError("exported a model beyond the extent limit")
    return "clamp, scale-to-brief, ground snap, gap closing, X-Y-Z rotation and extent limit behave"


def check_all_sizes(out: Path) -> str:
    worst = 0.0
    for name, raw in templates.TEMPLATES.items():
        for size_cm in (3, 8, 12, 20, 30, 45, 80, 150):
            started = time.perf_counter()
            result = export(raw, size_cm, out / "sizes")
            worst = max(worst, time.perf_counter() - started)
            cad.RobotSpec.model_validate(result)
            stl = trimesh.load(out / "sizes" / "model.stl", force="mesh")
            assert stl.is_watertight and stl.volume > 0, (name, size_cm)
            assert bodies(stl) == 1, (name, size_cm, bodies(stl))
            assert abs(stl.bounds[0][2]) < 2e-3, (name, size_cm)
            assert float(np.abs(stl.bounds).max()) <= cad.MAX_EXTENT_MM
            assert set(glb_parts(out / "sizes" / "model.glb")) == {p["id"] for p in result["parts"]}
            off_brief = abs(stl.extents[2] - size_cm * 10) > 0.25 * size_cm * 10
            assert off_brief == any("cm tall, not" in note for note in result["assumptions"]), (name, size_cm)
    assert worst < BUILD_BUDGET_S
    return f"3 templates x 8 brief sizes (3-150 cm) export one watertight grounded body; slowest {worst * 1000:.0f} ms"


def check_deterministic(out: Path) -> str:
    digests = []
    for run in ("a", "b"):
        cad._shape.cache_clear()
        for name, raw in templates.TEMPLATES.items():
            export(raw, DEFAULT_SIZE_CM, out / run / name)
            for filename in ("model.glb", "model.stl"):
                digests.append(hashlib.sha256((out / run / name / filename).read_bytes()).hexdigest())
            assert sorted(f.name for f in (out / run / name).iterdir()) == ["model.glb", "model.stl"]
    assert digests[:6] == digests[6:], "exports differ between runs"
    return "repeat exports are byte-identical and leave only model.glb + model.stl"


CHECKS = [
    check_templates_match_eval,
    check_template_exports,
    check_glb_orientation,
    check_wheel_holes,
    check_every_primitive,
    check_validation_rejects,
    check_normalization,
    check_all_sizes,
    check_deterministic,
]


def run(keep: Path | None) -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for check in CHECKS:
            name = check.__name__.removeprefix("check_")
            try:
                print(f"PASS {name}: {check(Path(tmp) / name)}")
            except Exception:
                failures += 1
                print(f"FAIL {name}\n{traceback.format_exc()}")
        if keep is not None:
            for name, raw in templates.TEMPLATES.items():
                export(raw, DEFAULT_SIZE_CM, keep / name)
            print(f"kept sample exports in {keep}")
    print(f"{len(CHECKS) - failures}/{len(CHECKS)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep", type=Path, help="write the three template exports here")
    sys.exit(run(parser.parse_args().keep))
