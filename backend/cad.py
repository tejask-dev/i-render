"""RobotSpec schema (spec 03b) and the deterministic CAD builder.

Source coordinates are millimetres, Z up, origin on the ground under the
robot, +X = robot's right, +Y = front. export_model() normalizes a validated
spec against the brief's size and writes:

  model.glb  one named mesh per part (mesh/node name = part.id), metres, Y up,
             front facing +Z, coloured by category. Never unioned, so the
             viewer can click parts.
  model.stl  the boolean union of every part, millimetres, Z up.

Solids are built with manifold3d and written with trimesh.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
import trimesh
from manifold3d import Manifold, OpType
from pydantic import BaseModel, Field, model_validator
from trimesh.visual import TextureVisuals
from trimesh.visual.material import PBRMaterial

Primitive = Literal["rounded_box", "box", "cylinder", "sphere", "cone", "wheel",
                    "arm_link", "servo_mount", "motor_mount", "antenna"]
Category = Literal["structure", "motion", "sensor", "light", "sound", "decor"]

CATEGORY_COLOURS = {
    "structure": "#BFD7EA",
    "motion": "#FF8A5B",
    "sensor": "#9B5DE5",
    "light": "#FFD23F",
    "sound": "#3BCEAC",
    "decor": "#F15BB5",
}

# (name, min, max) per dims_mm entry: the clamp ranges from spec 03b section 5.
# Where 03b gives no range (arm_link W/T) the limits keep the Ø3 holes buildable.
# A cone's D_top may be 0 for a true point.
DIM_RANGES: dict[str, tuple[tuple[str, float, float], ...]] = {
    "box": (("L", 2, 500), ("W", 2, 500), ("H", 2, 500)),
    "rounded_box": (("L", 2, 500), ("W", 2, 500), ("H", 2, 500)),
    "cylinder": (("D", 2, 300), ("H", 1, 500)),
    "sphere": (("D", 2, 300),),
    "cone": (("D_base", 1, 300), ("D_top", 0, 300), ("H", 1, 300)),
    "wheel": (("D", 10, 200), ("W", 3, 60)),
    "arm_link": (("L", 10, 300), ("W", 4, 60), ("T", 1, 30)),
    "servo_mount": (),
    "motor_mount": (("D_motor", 10, 30),),
    "antenna": (("L", 5, 150),),
}

SIZE_CM_RANGE = (3, 150)        # ProjectBrief.approx_size_cm (spec 03a)
MAX_ASSUMPTIONS = 6
MAX_INPUT_DIM_MM = 10_000.0     # sanity bound before clamping
MAX_INPUT_POS_MM = 5_000.0
MAX_INPUT_ROT_DEG = 3_600.0
MAX_EXTENT_MM = 3_000.0         # the finished model must fit inside ±3 m
SCALE_TOLERANCE = 0.25          # rescale when height is >25% off the brief
ATTACH_OVERLAP_MM = 2.0         # how far a nudged part sinks into its parent
GROUND_TOLERANCE_MM = 1e-3

HUB_HOLE_MM = 5.0
LINK_HOLE_MM = 3.0
MOTOR_DEFAULT_MM = 20.0
MOTOR_MOUNT_LENGTH_MM = 15.0
MOTOR_MOUNT_WALL_MM = 3.0
ANTENNA_STALK_MM = 2.0
ANTENNA_BALL_MM = 6.0

ROUND_SEGMENTS = 48
SPHERE_SEGMENTS = 48
FILLET_SEGMENTS = 24
HOLE_SEGMENTS = 16
SHARP_EDGE_DEG = 40.0

# Z-up millimetres -> glTF metres: +Y up, +Z front, -X right (a pure rotation).
_GLTF_AXES = np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])
_MM_TO_M = 0.001

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class CadError(ValueError):
    """A valid RobotSpec that still cannot be built or exported."""


class Part(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,30}$")
    label: str                      # human name, e.g. "Left wheel"
    primitive: Primitive
    dims_mm: list[FiniteFloat] = Field(max_length=3)    # length depends on primitive
    pos_mm: list[FiniteFloat] = Field(min_length=3, max_length=3)
    rot_deg: list[FiniteFloat] = Field(default_factory=lambda: [0.0, 0.0, 0.0],
                                       min_length=3, max_length=3)
    attach_to: str | None = None    # parent part id
    category: Category
    function: str | None = None     # e.g. "drive", "glow", "look cute"

    @model_validator(mode="after")
    def check_geometry(self):
        ranges = DIM_RANGES[self.primitive]
        names = [name for name, _, _ in ranges]
        optional = self.primitive == "motor_mount" and not self.dims_mm
        if len(self.dims_mm) != len(ranges) and not optional:
            raise ValueError(f"{self.id}: {self.primitive} needs dims_mm {names}, "
                             f"got {len(self.dims_mm)} values")
        for value, (name, low, _) in zip(self.dims_mm, ranges):
            if value < 0 or (value == 0 and low > 0):
                raise ValueError(f"{self.id}: {name} must be positive, got {value}")
            if value > MAX_INPUT_DIM_MM:
                raise ValueError(f"{self.id}: {name} is over {MAX_INPUT_DIM_MM:g} mm")
        if any(abs(v) > MAX_INPUT_POS_MM for v in self.pos_mm):
            raise ValueError(f"{self.id}: pos_mm is outside ±{MAX_INPUT_POS_MM:g} mm")
        if any(abs(v) > MAX_INPUT_ROT_DEG for v in self.rot_deg):
            raise ValueError(f"{self.id}: rot_deg is outside ±{MAX_INPUT_ROT_DEG:g}")
        return self


class Function(BaseModel):
    name: Literal["drive", "walk", "light_up", "make_sound", "grab", "spin",
                  "sense_distance", "display_face", "fly_ish"]
    parts: list[str]                # part ids involved


class RobotSpec(BaseModel):
    robot_name: str
    parts: list[Part] = Field(min_length=1, max_length=20)
    functions: list[Function]
    assumptions: list[str] = Field(max_length=MAX_ASSUMPTIONS)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_refs(self):
        parents = {p.id: p.attach_to for p in self.parts}
        if len(parents) != len(self.parts):
            raise ValueError("duplicate part ids")
        for p in self.parts:
            if p.attach_to is not None and p.attach_to not in parents:
                raise ValueError(f"{p.id}.attach_to unknown")
        for pid in parents:
            seen, cursor = {pid}, parents[pid]
            while cursor is not None:
                if cursor in seen:
                    raise ValueError(f"{pid}.attach_to forms a loop")
                seen.add(cursor)
                cursor = parents[cursor]
        for f in self.functions:
            for pid in f.parts:
                if pid not in parents:
                    raise ValueError(f"function {f.name} references unknown {pid}")
        return self


# --- primitives: each returns a solid in mm, Z up -------------------------

def _cylinder(d: float, h: float, segments: int = ROUND_SEGMENTS) -> Manifold:
    return Manifold.cylinder(h, d / 2, d / 2, segments, True)


def _box(l: float, w: float, h: float) -> Manifold:
    return Manifold.cube([l, w, h], True)


def _rounded_box(l: float, w: float, h: float) -> Manifold:
    r = min(l, w, h) * 0.15
    corner = Manifold.sphere(r, FILLET_SEGMENTS)
    return Manifold.batch_hull([
        corner.translate([sx * (l / 2 - r), sy * (w / 2 - r), sz * (h / 2 - r)])
        for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)
    ])


def _sphere(d: float) -> Manifold:
    return Manifold.sphere(d / 2, SPHERE_SEGMENTS)


def _cone(d_base: float, d_top: float, h: float) -> Manifold:
    return Manifold.cylinder(h, d_base / 2, d_top / 2, ROUND_SEGMENTS, True)


def _wheel(d: float, w: float) -> Manifold:
    # Axle along X so the wheel rolls toward +Y; the hub hole goes right through.
    hole = _cylinder(HUB_HOLE_MM, w + 2, HOLE_SEGMENTS)
    return (_cylinder(d, w) - hole).rotate([0, 90, 0])


def _arm_link(l: float, w: float, t: float) -> Manifold:
    # Slot-shaped link lying along X with a pivot hole through each rounded end.
    hole_d = min(LINK_HOLE_MM, w * 0.6)
    span = l - w
    if span > 0:
        end = _cylinder(w, t)
        link = Manifold.batch_hull([end.translate([-span / 2, 0, 0]),
                                    end.translate([span / 2, 0, 0])])
    else:
        link = _box(l, w, t)
    hole = _cylinder(hole_d, t + 2, HOLE_SEGMENTS)
    for x in ((-span / 2, span / 2) if span >= 2 * hole_d else (0.0,)):
        link -= hole.translate([x, 0, 0])
    return link


def _servo_mount() -> Manifold:
    # SG90 cradle: 23 x 12.5 x 22 block, pocket open at the top, two screw ears.
    ears = _box(32.5, 12.5, 2.5).translate([0, 0, -9.75])
    pocket = _box(19, 8.5, 18).translate([0, 0, 3])
    screw = _cylinder(2, 6, HOLE_SEGMENTS).translate([0, 0, -9.75])
    return (_box(23, 12.5, 22) + ears - pocket
            - screw.translate([-13.875, 0, 0]) - screw.translate([13.875, 0, 0]))


def _motor_mount(d: float = MOTOR_DEFAULT_MM) -> Manifold:
    # U-bracket open at the top; the motor lies along X toward the wheel.
    wall, length = MOTOR_MOUNT_WALL_MM, MOTOR_MOUNT_LENGTH_MM
    height = wall + 0.75 * d
    block = _box(length, d + 2 * wall, height).translate([0, 0, height / 2])
    axis_z = wall + d / 2
    motor = _cylinder(d, length + 2).rotate([0, 90, 0]).translate([0, 0, axis_z])
    opening = _box(length + 2, d, d).translate([0, 0, axis_z + d / 2])
    return block - motor - opening


def _antenna(l: float) -> Manifold:
    # l is the stalk length; the ball is centred on its tip.
    stalk = Manifold.cylinder(l, ANTENNA_STALK_MM / 2, ANTENNA_STALK_MM / 2, HOLE_SEGMENTS)
    ball = Manifold.sphere(ANTENNA_BALL_MM / 2, HOLE_SEGMENTS).translate([0, 0, l])
    return stalk + ball


_BUILDERS = {
    "box": _box,
    "rounded_box": _rounded_box,
    "cylinder": _cylinder,
    "sphere": _sphere,
    "cone": _cone,
    "wheel": _wheel,
    "arm_link": _arm_link,
    "servo_mount": _servo_mount,
    "motor_mount": _motor_mount,
    "antenna": _antenna,
}


@lru_cache(maxsize=512)
def _shape(primitive: str, dims: tuple[float, ...],
           rot: tuple[float, ...]) -> tuple[Manifold, tuple[float, float, float]]:
    """Rotated solid with its bounding box centred on the origin, plus half extents."""
    solid = _BUILDERS[primitive](*dims)
    if any(rot):
        solid = solid.rotate(list(rot))     # X, then Y, then Z, as 03b section 4
    if solid.is_empty() or solid.volume() <= 0:
        raise CadError(f"{primitive} {list(dims)} produced no solid")
    x0, y0, z0, x1, y1, z1 = solid.bounding_box()
    solid = solid.translate([-(x0 + x1) / 2, -(y0 + y1) / 2, -(z0 + z1) / 2])
    return solid, ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)


def _half_extents(part: dict) -> np.ndarray:
    return np.array(_shape(part["primitive"], tuple(part["dims_mm"]), tuple(part["rot_deg"]))[1])


def _part_solid(part: dict, pos: list[float] | None = None) -> Manifold:
    solid, _ = _shape(part["primitive"], tuple(part["dims_mm"]), tuple(part["rot_deg"]))
    return solid.translate(list(part["pos_mm"] if pos is None else pos))


# --- normalization (spec 03b section 8) -----------------------------------

def _round(value: float) -> float:
    return round(float(value), 3) + 0.0     # + 0.0 turns -0.0 into 0.0


def _clamp_dims(part: dict) -> bool:
    ranges = DIM_RANGES[part["primitive"]]
    dims = part["dims_mm"] or ([MOTOR_DEFAULT_MM] if part["primitive"] == "motor_mount" else [])
    clamped = [min(max(value, low), high) for value, (_, low, high) in zip(dims, ranges)]
    part["dims_mm"] = [_round(value) for value in clamped]
    return clamped != list(dims)


def _bounds(parts: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    centres = np.array([p["pos_mm"] for p in parts], dtype=float)
    halves = np.array([_half_extents(p) for p in parts])
    return centres - halves, centres + halves


def _ground_snap(parts: list[dict]) -> None:
    low, _ = _bounds(parts)
    shift = float(low[:, 2].min())
    if abs(shift) > GROUND_TOLERANCE_MM:
        for p in parts:
            p["pos_mm"][2] -= shift


def _attach_floating(parts: list[dict]) -> list[str]:
    """Slide parts that do not really touch their parent into it; returns the ids moved.

    03b compares bounding boxes with a 2 mm allowance. That lets round or
    clamped parts sit a hair apart and print as loose pieces, so this tests the
    solids themselves.
    """
    by_id = {p["id"]: p for p in parts}
    children: dict[str, list[str]] = {pid: [] for pid in by_id}
    for p in parts:
        if p["attach_to"] is not None:
            children[p["attach_to"]].append(p["id"])

    def depth(p: dict) -> int:
        return 0 if p["attach_to"] is None else 1 + depth(by_id[p["attach_to"]])

    moved = []
    for part in sorted(parts, key=depth):       # parents settle before children
        if part["attach_to"] is None:
            continue
        parent = by_id[part["attach_to"]]
        parent_solid = _part_solid(parent)
        start = np.array(part["pos_mm"], dtype=float)
        offset = start - np.array(parent["pos_mm"], dtype=float)

        def touches(fraction: float) -> bool:
            placed = _part_solid(part, list(start - offset * fraction))
            return (placed ^ parent_solid).volume() > 1e-6

        distance = float(np.linalg.norm(offset))
        if touches(0.0) or distance == 0 or not touches(1.0):
            continue
        # Bisect along the line to the parent's centre for first contact, then sink in.
        apart, contact = 0.0, 1.0
        for _ in range(20):
            middle = (apart + contact) / 2
            if touches(middle):
                contact = middle
            else:
                apart = middle
        shift = -offset * min(1.0, contact + ATTACH_OVERLAP_MM / distance)
        stack = [part["id"]]
        while stack:                            # the part's own children ride along
            pid = stack.pop()
            by_id[pid]["pos_mm"] = [c + s for c, s in zip(by_id[pid]["pos_mm"], shift)]
            stack.extend(children[pid])
        moved.append(part["id"])
    return moved


def _add_notes(assumptions: list[str], notes: list[str]) -> list[str]:
    merged = list(assumptions)
    if not notes:
        return merged
    if len(merged) + len(notes) <= MAX_ASSUMPTIONS:
        return merged + notes
    combined = " ".join(notes)
    if len(merged) < MAX_ASSUMPTIONS:
        return merged + [combined]
    merged[-1] = f"{merged[-1]} {combined}"
    return merged


def normalize_spec(spec: RobotSpec, size_cm: int) -> RobotSpec:
    """Clamp, scale to the brief, ground and attach; returns a new RobotSpec in real mm."""
    if isinstance(size_cm, bool) or not isinstance(size_cm, int):
        raise CadError(f"size_cm must be a whole number of centimetres, got {size_cm!r}")
    if not SIZE_CM_RANGE[0] <= size_cm <= SIZE_CM_RANGE[1]:
        raise CadError(f"size_cm must be {SIZE_CM_RANGE[0]}-{SIZE_CM_RANGE[1]}, got {size_cm}")

    raw = spec.model_dump()
    parts = raw["parts"]
    notes = []

    clamped = {p["id"] for p in parts if _clamp_dims(p)}

    low, high = _bounds(parts)
    height = float(high[:, 2].max() - low[:, 2].min())
    target = size_cm * 10.0
    if abs(height - target) > SCALE_TOLERANCE * target:
        factor = target / height
        for p in parts:
            p["dims_mm"] = [d * factor for d in p["dims_mm"]]
            p["pos_mm"] = [c * factor for c in p["pos_mm"]]
        clamped |= {p["id"] for p in parts if _clamp_dims(p)}
        notes.append(f"Scaled the model x{factor:.2f} to match the {size_cm} cm brief.")
    if clamped:
        notes.append(f"Clamped {', '.join(sorted(clamped))} to the buildable size range.")

    _ground_snap(parts)
    moved = _attach_floating(parts)
    if moved:
        names = ", ".join(moved) if len(moved) <= 4 else f"{len(moved)} parts"
        notes.append(f"Closed gaps between attached parts by moving {names}.")
        _ground_snap(parts)

    for p in parts:
        p["pos_mm"] = [_round(c) for c in p["pos_mm"]]
        p["rot_deg"] = [_round(a) for a in p["rot_deg"]]

    low, high = _bounds(parts)
    if not (np.isfinite(low).all() and np.isfinite(high).all()):
        raise CadError("model has non-finite geometry")
    if max(float(np.abs(low).max()), float(np.abs(high).max())) > MAX_EXTENT_MM:
        raise CadError(f"model extends beyond ±{MAX_EXTENT_MM:g} mm after normalization")
    if abs(float(low[:, 2].min())) > 2 * GROUND_TOLERANCE_MM:
        raise CadError("model is not resting on the ground plane")
    height = float(high[:, 2].max() - low[:, 2].min())
    if abs(height - target) > SCALE_TOLERANCE * target:
        notes.append(f"Fixed and limited part sizes leave the model about "
                     f"{height / 10:.0f} cm tall, not {size_cm} cm.")

    raw["assumptions"] = _add_notes(raw["assumptions"], notes)
    return RobotSpec.model_validate(raw)


# --- export ----------------------------------------------------------------

def _linear_rgba(hex_colour: str) -> list[float]:
    # glTF base colours are linear; the brand hex values are sRGB.
    srgb = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb] + [1.0]


def _glb_bytes(parts: list[Part], solids: list[Manifold]) -> bytes:
    materials = {
        category: PBRMaterial(name=category, baseColorFactor=_linear_rgba(colour),
                              metallicFactor=0.0, roughnessFactor=0.8)
        for category, colour in CATEGORY_COLOURS.items()
    }
    scene = trimesh.Scene()
    for part, solid in zip(parts, solids):
        data = solid.calculate_normals(0, SHARP_EDGE_DEG).to_mesh64()
        props = np.asarray(data.vert_properties, dtype=np.float64)
        mesh = trimesh.Trimesh(vertices=props[:, :3] @ _GLTF_AXES.T * _MM_TO_M,
                               faces=np.asarray(data.tri_verts, dtype=np.int64),
                               vertex_normals=props[:, 3:6] @ _GLTF_AXES.T,
                               process=False)
        mesh.visual = TextureVisuals(material=materials[part.category])
        mesh.metadata.update({"part_id": part.id, "label": part.label,
                              "primitive": part.primitive, "category": part.category})
        scene.add_geometry(mesh, node_name=part.id, geom_name=part.id)
    return scene.export(file_type="glb")


def _as_trimesh(solid: Manifold) -> trimesh.Trimesh:
    data = solid.to_mesh64()
    return trimesh.Trimesh(vertices=np.asarray(data.vert_properties, dtype=np.float64)[:, :3],
                           faces=np.asarray(data.tri_verts, dtype=np.int64), process=False)


def _stl_bytes(solids: list[Manifold]) -> tuple[bytes, str | None]:
    note = None
    try:
        union = Manifold.batch_boolean(solids, OpType.Add)
        if union.is_empty() or not math.isfinite(union.volume()) or union.volume() <= 0:
            raise CadError("empty union")
        mesh = _as_trimesh(union)
        bodies = sum(piece.volume() > 0 for piece in union.decompose())
        if bodies > 1:
            note = f"The STL has {bodies} separate solid pieces. Preview their placement and supports in your slicer."
    except Exception:
        mesh = trimesh.util.concatenate([_as_trimesh(s) for s in solids])
        note = "The solids could not be joined. The STL contains separate shells that may overlap. Inspect and repair it in your slicer before printing."
    return mesh.export(file_type="stl"), note


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def export_model(spec: RobotSpec, size_cm: int, out_dir: Path) -> dict:
    """Write out_dir/model.glb and out_dir/model.stl; return the normalized spec as JSON data.

    Raises CadError (a ValueError) when size_cm is out of range or the
    normalized model cannot be built within the extent limit.
    """
    normalized = normalize_spec(spec, size_cm)
    solids = [_part_solid(part.model_dump()) for part in normalized.parts]
    glb = _glb_bytes(normalized.parts, solids)
    stl, print_note = _stl_bytes(solids)
    if print_note and not any(print_note in existing for existing in normalized.assumptions):
        normalized.assumptions = _add_notes(normalized.assumptions, [print_note])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_atomic(out_dir / "model.glb", glb)
    _write_atomic(out_dir / "model.stl", stl)
    return normalized.model_dump(mode="json")
