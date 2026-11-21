"""Local Qwen or configured Gemini image analysis for the demo."""

import asyncio
import base64
import io
import json
import math
import os
import re
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from pydantic import ValidationError

from .salvage import KEYS, REQUIREMENTS, inventory_item

register_heif_opener()
PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
LOCAL = "http://127.0.0.1:11434"
LOCAL_MODEL = "qwen3-vl:4b-instruct"
MAX_UPLOAD = 10 * 1024 * 1024


class VisionError(ValueError):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class InvalidModelOutput(VisionError):
    def __init__(self, message):
        super().__init__(422, message)


def read_image(data: bytes) -> bytes:
    if len(data) > MAX_UPLOAD:
        raise VisionError(413, "Choose a photo under 10 MB.")
    try:
        with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP", "HEIF"]) as original:
            if original.width * original.height > 50_000_000:
                raise VisionError(413, "Resize the photo to 50 megapixels or less.")
            original.draft("RGB", (3072, 3072))
            original.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
            rotated = ImageOps.exif_transpose(original)
            if "A" in rotated.getbands() or "transparency" in rotated.info:
                rgba = rotated.convert("RGBA")
                rgb = Image.new("RGB", rgba.size, "white")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
            else:
                rgb = rotated.convert("RGB")
            buf = io.BytesIO()
            rgb.save(buf, format="JPEG", quality=86)
            return buf.getvalue()
    except VisionError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise VisionError(400, "Choose a readable JPEG, PNG, WebP or HEIC photo.") from exc


async def vision_source() -> str | None:
    """The default provider only inspects the local machine."""
    try:
        async with httpx.AsyncClient(timeout=1.5, trust_env=False) as client:
            result = await client.get(LOCAL + "/api/tags")
            result.raise_for_status()
            if any(m.get("name") == LOCAL_MODEL for m in result.json()["models"]):
                return "local"
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


async def gemini_model() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise VisionError(503, "Gemini requires a team API key. Choose on-device recognition to continue.")
    requested = os.environ.get("GEMINI_MODEL", "").strip()
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    models = []
    try:
        async with asyncio.timeout(7), httpx.AsyncClient(timeout=5, trust_env=False) as client:
            params = {"pageSize": 1000}
            while True:
                response = await client.get(url, params=params, headers={"x-goog-api-key": key})
                response.raise_for_status()
                page = response.json()
                models.extend(row["name"].removeprefix("models/") for row in page["models"]
                              if "generateContent" in row.get("supportedGenerationMethods", []))
                if not page.get("nextPageToken") or requested in models:
                    break
                params["pageToken"] = page["nextPageToken"]
    except (httpx.HTTPError, TimeoutError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise VisionError(503, "Gemini model lookup failed. Check the team key or choose on-device recognition.") from exc
    if requested:
        if requested in models and re.fullmatch(r"[A-Za-z0-9._-]{1,90}", requested):
            return requested
        raise VisionError(503, "The configured Gemini model is unavailable. Check GEMINI_MODEL or choose on-device recognition.")
    candidates = [(int(m[1]), int(m[2] or 0), name) for name in models
                  if (m := re.fullmatch(r"gemini-([0-9]+)(?:[.]([0-9]+))?-flash", name))]
    if not candidates:
        raise VisionError(503, "Choose an available image-capable Gemini model in GEMINI_MODEL or use on-device recognition.")
    return max(candidates)[2]


async def _generate(source, image, instruction, context, schema, *, model=None):
    encoded = base64.b64encode(image).decode("ascii")
    headers = {}
    if source == "gemini":
        model = model or await gemini_model()
        headers["x-goog-api-key"] = os.environ.get("GEMINI_API_KEY", "").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": instruction}]},
            "contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": "image/jpeg", "data": encoded}}, {"text": context}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema, "maxOutputTokens": 7200},
        }
        timeout = 25
    elif source == "local":
        url = LOCAL + "/api/chat"
        payload = {
            "model": LOCAL_MODEL, "stream": False, "think": False, "format": schema,
            "messages": [{"role": "system", "content": instruction},
                         {"role": "user", "content": context, "images": [encoded]}],
            "options": {"temperature": 0, "seed": 13, "num_ctx": 8192, "num_predict": 1800},
            "keep_alive": "15m",
        }
        timeout = 100
    else:
        raise VisionError(503, "Photo vision is unavailable. Choose an example sketch or select drawer items manually.")

    try:
        async with asyncio.timeout(timeout), httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    raise VisionError(503, f"Photo service returned {response.status_code}. Try again or use the manual flow.")
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 350_000:
                        raise VisionError(502, "The photo service returned too much data.")
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise VisionError(504, "Photo analysis timed out. Retry with a closer crop or use the manual flow.") from exc
    except httpx.RequestError as exc:
        raise VisionError(503, "Could not reach the photo service. Choose an example or manual input.") from exc
    try:
        response_data = json.loads(raw)
        if source == "gemini":
            candidate = response_data["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise VisionError(422, "The model could not finish this photo. Try another photo.")
            content = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
        else:
            if response_data.get("done_reason") == "length":
                raise VisionError(422, "The scene was too detailed. Crop to fewer objects.")
            content = response_data["message"]["content"]
        return json.loads(content)
    except VisionError:
        raise
    except (TypeError, KeyError, IndexError, ValueError, AttributeError) as exc:
        raise InvalidModelOutput("The model could not describe this photo reliably. Try a clearer photo.") from exc


BOX_SCHEMA = {"type": "array", "minItems": 4, "maxItems": 4,
              "items": {"type": "integer", "minimum": 0, "maximum": 1000}}


def valid_box(box):
    return (isinstance(box, list) and len(box) == 4 and all(type(v) is int for v in box)
            and 0 <= box[0] < box[2] <= 1000 and 0 <= box[1] < box[3] <= 1000)


def _same_photo_object(first, second):
    label = first.get("detected_label", first.get("label"))
    if label in (None, "other") or label != second.get("detected_label", second.get("label")):
        return False
    a, b = first.get("box_2d"), second.get("box_2d")
    if not valid_box(a) or not valid_box(b):
        return False
    overlap = (max(0, min(a[2], b[2]) - max(a[0], b[0])) *
               max(0, min(a[3], b[3]) - max(a[1], b[1])))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
    # A high intersection-over-union matches detector jitter without joining neighbouring donors.
    return overlap >= .85 * union


def distinct_detections(items, *, preserve_indices=False):
    reviewed = list(items)
    first_indices = []
    for index, item in enumerate(items):
        first = next((i for i in first_indices if _same_photo_object(items[i], item)), None)
        if first is None:
            first_indices.append(index)
            continue
        kept = reviewed[first]
        if kept.get("label") == "other" and item["label"] != "other":
            kept = {**kept, "label": item["label"], "confidence": item["confidence"]}
            if not kept.get("blocked"):
                kept.update(candidate_parts=item["candidate_parts"], condition_note=item.get("condition_note"))
        if item.get("blocked") and not kept.get("blocked"):
            kept = {**kept, "blocked": True, "condition_note": item.get("condition_note"),
                    "candidate_parts": {}}
        if item.get("user_excluded"):
            kept = {**kept, "user_excluded": True}
        reviewed[first] = kept
        if preserve_indices:
            reviewed[index] = {**item, "duplicate_of": first, "candidate_parts": {},
                               "condition_note": f"Same object as drawer item {first + 1}. Counted once."}
    return reviewed if preserve_indices else [reviewed[i] for i in first_indices]


def _objects_schema(key, fields, limit):
    item = {"type": "object", "properties": fields, "required": list(fields)}
    return {"type": "object", "properties": {key: {"type": "array", "maxItems": limit, "items": item}}, "required": [key]}


async def analyze_junk(image: bytes, *, source=None, model=None, prompt=None) -> list[dict]:
    source = source or await vision_source()
    conditions = ["no_visible_damage", "corroded", "swollen", "leaking", "exposed_wires", "missing_parts", "broken", "uncertain"]
    fields = {"label": {"type": "string", "enum": [*KEYS, "other"]}, "raw_name": {"type": "string"},
              "box_2d": BOX_SCHEMA, "confidence": {"type": "number"}, "condition": {"type": "string", "enum": conditions}}
    vocabulary = ", ".join([*KEYS, "other"])
    order = "left,top,right,bottom" if source == "local" else "top,left,bottom,right"
    context = (f"Allowed labels: {vocabulary}. Return label, raw_name, box_2d ([{order}], 0–1000), "
               "confidence and condition. Condition must be one of: " + ", ".join(conditions))
    raw = await _generate(source, image, prompt or (PROMPTS / "junk_to_inventory.md").read_text(),
                          context, _objects_schema("items", fields, 15), model=model)
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list) or len(raw["items"]) > 15:
        raise VisionError(422, "The drawer result was unreadable. Try a closer crop.")
    items = []
    for obj in raw["items"]:
        if not isinstance(obj, dict) or not valid_box(obj.get("box_2d")):
            raise VisionError(422, "The model could not locate an item. Try a closer crop.")
        name, label, confidence, condition = (obj.get(k) for k in ("raw_name", "label", "confidence", "condition"))
        if (not isinstance(name, str) or not name.strip() or not isinstance(label, str)
                or type(confidence) not in (int, float) or not 0 <= confidence <= 1
                or condition not in conditions):
            raise VisionError(422, "The model returned an incomplete identification. Try a clearer photo.")
        a, b, c, d = obj["box_2d"]
        box = [b, a, d, c] if source == "local" else [a, b, c, d]
        note = None if condition == "no_visible_damage" else condition.replace("_", " ").capitalize()
        item = inventory_item(label, name.strip()[:100], box=box, confidence=confidence, condition=note)
        if item["label"] == "other" and label in KEYS:
            item["detected_label"] = label
        items.append(item)
    return distinct_detections(items)


ROLES = ["base", "body_box", "body_round", "head_box", "head_round", "wheel", "arm", "joint", "gripper", "leg", "eye", "light", "antenna", "accessory"]


def _link_geometry(gray, box, mm_per_pixel):
    t, l, b, r = box
    h, w = gray.shape
    crop = gray[t*h//1000:max(t*h//1000+1, b*h//1000), l*w//1000:max(l*w//1000+1, r*w//1000)]
    yy, xx = np.where(crop < min(180, np.percentile(crop, 85) * .7))
    if len(xx) < 4:
        return [max(10, crop.shape[1]*mm_per_pixel), 6, max(3, crop.shape[0]*mm_per_pixel)], 0
    # Principal axis of the ink gives slanted links a local orientation in the sketch plane.
    points = np.column_stack((xx, yy))
    _, axes = np.linalg.eigh(np.cov(points.T))
    projection = points @ axes
    thickness, length = (np.percentile(projection, 98, axis=0) - np.percentile(projection, 2, axis=0)) * mm_per_pixel
    angle = math.degrees(math.atan2(axes[1, 1], axes[0, 1]))
    return [max(10, length), max(4, thickness*.65), max(3, thickness)], round(angle, 1)


def _from_boxes(raw, brief, image):
    parts = raw.get("parts") if isinstance(raw, dict) else None
    if isinstance(parts, list) and not parts:
        raise VisionError(422, "No clear robot drawing found. Photograph the sketch straight on.")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 10:
        raise InvalidModelOutput("The model returned an invalid list of sketch parts.")
    confidence = raw.get("confidence")
    if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
        raise InvalidModelOutput("The sketch response needs a numeric confidence from 0 to 1.")
    normalized = []
    for p in parts:
        if not isinstance(p, dict) or p.get("role") not in ROLES or not valid_box(p.get("box_2d")):
            raise InvalidModelOutput("Each sketch part needs a valid role and ordered [left,top,right,bottom] box.")
        l, t, r, b = p["box_2d"]
        normalized.append({"role": p["role"], "box_2d": [t, l, b, r]})
    parts = normalized
    assumptions = ["Front-view boxes come from local image recognition.", "Depth, joints and hidden surfaces are estimates.",
                   "Height follows the interview request."]
    arms = [p for p in parts if p["role"] == "arm"]
    joints = [p["box_2d"] for p in parts if p["role"] == "joint"]
    base = next((p["box_2d"] for p in parts if p["role"] == "base"), None)
    claw = next((p["box_2d"] for p in parts if p["role"] == "gripper"), None)
    if len(arms) == 1 and 1 <= len(joints) <= 4 and base and claw:
        # A model can group adjoining links into one box. Resolve the chain from visible pivots.
        prev = (base[0], (base[1] + base[3]) / 2)
        parts.remove(arms[0])
        thick = max(4, np.median([min(b[2]-b[0], b[3]-b[1]) for b in joints]) * .6)
        targets = [((b[0]+b[2])/2, (b[1]+b[3])/2) for b in joints]
        while targets:
            end = min(targets, key=lambda target: math.dist(prev, target))
            targets.remove(end)
            if math.dist(prev, end) > thick * 1.3:
                parts.append({"role": "arm", "pivot_span": (prev, end, thick)})
                prev = end
        wrist = (min(max(prev[0], claw[0]), claw[2]), min(max(prev[1], claw[1]), claw[3]))
        if math.dist(prev, wrist) > thick * 1.8:
            parts.append({"role": "arm", "pivot_span": (prev, wrist, thick)})
        for part in parts:
            if "pivot_span" in part:
                start, end, diameter = part["pivot_span"]
                pad = diameter / 2
                part["box_2d"] = [max(0, round(min(start[0], end[0])-pad)), max(0, round(min(start[1], end[1])-pad)),
                                  min(1000, round(max(start[0], end[0])+pad)), min(1000, round(max(start[1], end[1])+pad))]
        if not any("pivot_span" in p for p in parts):
            parts.extend(arms)
        assumptions.append("Link lengths and angles follow the detected base, hinges and claw.")
    boxes = [p["box_2d"] for p in parts]
    top, bottom = min(b[0] for b in boxes), max(b[2] for b in boxes)
    mid_x = (min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2
    # Normalized X and Y distances span different numbers of pixels on a phone photo.
    with Image.open(io.BytesIO(image)) as im:
        aspect = im.width / im.height
        gray = np.asarray(im.convert("L"))
    z_scale = float(brief.get("approx_size_cm", 20)) * 10 / (bottom - top)
    x_scale = z_scale * aspect
    def trunk_priority(i):
        t, l, b, r = boxes[i]
        role = parts[i]["role"]
        return (role == "base" and bool(claw), role.startswith("body") or role == "base", (b - t) * (r - l))
    trunk = max(range(len(parts)), key=trunk_priority)
    ids = [f"{p['role']}_{i + 1}" for i, p in enumerate(parts)]
    head = next((i for i, p in enumerate(parts) if p["role"].startswith("head")), trunk)
    parents = {trunk: None}
    structure = {i for i, p in enumerate(parts) if p["role"] not in {"eye", "light", "antenna", "accessory"}}
    def separation(pair):
        a, b = (boxes[i] for i in pair)
        dy = max(0, b[0]-a[2], a[0]-b[2])
        dx = max(0, b[1]-a[3], a[1]-b[3]) * aspect
        return (dx*dx + dy*dy, (b[0]+b[2]-a[0]-a[2])**2 + ((b[1]+b[3]-a[1]-a[3])*aspect)**2)
    while pending := structure - parents.keys():
        child, parent = min(((c, a) for c in sorted(pending) for a in parents), key=separation)
        parents[child] = parent
    result = []
    for i, p in enumerate(parts):
        role, (t, l, b, r) = p["role"], boxes[i]
        width, height = max(2, (r - l) * x_scale), max(2, (b - t) * z_scale)
        depth = max(2, min(width, height) * 0.65)
        primitive, dims, category = "rounded_box", [width, depth, height], "structure"
        parent = parents.get(i, head if role in {"eye", "light", "antenna"} else trunk)
        front_offset, angle = 0, 0
        if role in {"body_round", "head_round"}:
            primitive, dims = "sphere", [(width + height) / 2]
        elif role == "wheel":
            primitive, dims, category = "wheel", [max(10, height), min(60, max(3, width * 0.5))], "motion"
        elif role == "arm":
            if "pivot_span" in p:
                (y1, x1), (y2, x2), thick = p["pivot_span"]
                dx, dy = (x2-x1)*x_scale, (y2-y1)*z_scale
                dims = [max(10, math.hypot(dx, dy)), max(4, thick*z_scale*.65), max(3, thick*z_scale)]
                angle = round(math.degrees(math.atan2(dy, dx)), 1)
            else:
                dims, angle = _link_geometry(gray, boxes[i], z_scale*1000/gray.shape[0])
            primitive, category = "arm_link", "motion"
        elif role in {"joint", "gripper", "leg"}:
            category = "motion"
            if role == "joint":
                primitive, dims = "sphere", [min(width, height)]
        elif role == "antenna":
            primitive, dims, category = "antenna", [max(5, min(150, height))], "decor"
        elif role in {"eye", "light"}:
            primitive, dims, category = "sphere", [min(width, height)], "light" if role == "light" else "decor"
            pt, pl, pb, pr = boxes[parent if parent is not None else trunk]
            pw, ph = (pr - pl) * x_scale, (pb - pt) * z_scale
            front_offset = (pw + ph) / 4 if parts[parent if parent is not None else trunk]["role"].endswith("round") else min(pw, ph) * 0.325
        elif role == "accessory":
            category = "decor"
        result.append({
            "id": ids[i], "label": role.replace("_", " ").title() + f" {i+1}", "primitive": primitive,
            "dims_mm": [round(n, 1) for n in dims],
            "pos_mm": [round(((l + r) / 2 - mid_x) * x_scale, 1), round(front_offset, 1),
                       round((bottom - (t + b) / 2) * z_scale, 1)],
            "rot_deg": [0, angle, 0], "attach_to": None if parent is None else ids[parent],
            "category": category, "function": None,
        })
    role_map = {"drive": ["wheel"], "walk": ["leg"], "light_up": ["light", "eye"], "grab": ["arm", "gripper"],
                "sense_distance": ["eye"], "display_face": ["eye", "head_box", "head_round"]}
    names = list(dict.fromkeys(n for n in brief.get("must_do", []) if n in REQUIREMENTS))
    for role, name in (("wheel", "drive"), ("leg", "walk"), ("light", "light_up"), ("gripper", "grab")):
        if name not in names and any(p["role"] == role for p in parts):
            names.append(name)
    functions = [{"name": name, "parts": [ids[i] for i, p in enumerate(parts) if p["role"] in role_map.get(name, [])]}
                 for name in names]
    if any(p["role"] == "wheel" for p in parts):
        assumptions.append("Wheel bores are modelled at 5 mm. Measure the actual donor axle before printing.")
    if "grab" in names and any(p["role"] == "arm" for p in parts):
        anchor = next((i for i, p in enumerate(parts) if p["role"] == "joint"), trunk)
        pos = result[anchor]["pos_mm"].copy()
        pos[1] -= 4
        result.append({"id": "estimated_servo_mount", "label": "Estimated servo mount", "primitive": "servo_mount",
                       "dims_mm": [], "pos_mm": pos, "rot_deg": [0, 0, 0], "attach_to": ids[anchor],
                       "category": "motion", "function": "grab"})
        next(f for f in functions if f["name"] == "grab")["parts"].append("estimated_servo_mount")
        assumptions.append("A servo mount was estimated at an arm joint; verify its placement and fit.")
    return {
        "robot_name": brief.get("project_name") or "Sketch bot", "parts": result, "functions": functions,
        "assumptions": assumptions,
        "confidence": confidence,
    }


def sketch_prompt(source):
    return PROMPTS / ("local_sketch_parts.md" if source == "local" else "sketch_to_spec.md")


def with_requested_actions(spec, brief):
    """A requested function with no visible part still belongs in the sourcing plan."""
    names = {f["name"] for f in spec["functions"]}
    missing = [name for name in dict.fromkeys(brief.get("must_do", [])) if name not in names]
    if missing:
        return {**spec, "functions": [*spec["functions"], *({"name": name, "parts": []} for name in missing)]}
    return spec


def unresolved_actions(spec, brief):
    grounded = {f["name"] for f in spec["functions"] if f["parts"]}
    return list(dict.fromkeys(name for name in brief.get("must_do", []) if name not in grounded))


async def analyze_sketch(image: bytes, brief: dict, *, source=None, model=None, prompt=None) -> dict:
    from .cad import RobotSpec

    with Image.open(io.BytesIO(image)) as shot:
        lo, hi = shot.convert("L").getextrema()
    if hi - lo < 12:
        raise VisionError(422, "The page looks blank. Use a darker pen or better lighting.")
    source = source or await vision_source()
    if source == "local":
        fields = {"role": {"type": "string", "enum": ROLES}, "box_2d": BOX_SCHEMA}
        schema = _objects_schema("parts", fields, 10)
        schema["properties"]["confidence"] = {"type": "number", "minimum": 0, "maximum": 1}
        schema["required"].append("confidence")
        context = ("Return confidence and parts with role and box_2d. Allowed roles: " + ", ".join(ROLES))
    else:
        schema = RobotSpec.model_json_schema()
        allowed = ("project_name", "scale", "approx_size_cm", "vibe", "adventure_aura", "must_do")
        context = "Use this brief as design data: " + json.dumps({k: brief[k] for k in allowed if k in brief})
    prompt = prompt or sketch_prompt(source).read_text()
    partial = None
    for attempt in range(2):
        try:
            raw = await _generate(source, image, prompt, context, schema, model=model)
            candidate = _from_boxes(raw, brief, image) if source == "local" else raw
            spec = RobotSpec.model_validate(candidate)
            if spec.confidence < 0.3:
                raise VisionError(422, "The sketch is unclear. Use a darker pen or photograph it closer.")
            spec = spec.model_dump(mode="json")
            complete = with_requested_actions(spec, brief)
            if complete is not spec and not attempt:
                partial = complete
                raise InvalidModelOutput("Include every requested function from the brief, with visible part IDs or empty parts if unresolved.")
            return complete
        except (ValidationError, InvalidModelOutput) as exc:
            if attempt:
                if partial is not None:
                    return partial
                raise VisionError(422, "Could not turn this sketch into valid geometry. Try a clearer photo or choose an example.") from exc
            detail = str(exc)
            if isinstance(exc, ValidationError):
                errors = exc.errors(include_input=False, include_url=False, include_context=False)
                detail = json.dumps(errors[:4])[:550]
            context += "\nPrevious result failed geometry validation. Correct these fields: " + detail
        except VisionError:
            if partial is not None:
                return partial
            raise
    raise AssertionError("unreachable")
