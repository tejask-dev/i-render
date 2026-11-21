import hashlib
import json
import os
import shutil
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import cad, salvage, speech, store, vision
from .templates import TEMPLATES


@asynccontextmanager
async def lifespan(app):
    store.initialize()
    yield


app = FastAPI(title="I, Render", lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"],
)
MAX_IMAGE = 10 * 1024 * 1024


@app.middleware("http")
async def local_requests(request: Request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                {"detail": "Send this request from the local workbench."},
                status_code=403,
            )
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_IMAGE + 65536:
            return JSONResponse(
                {"detail": "Choose an image under 10 MB."}, status_code=413
            )
    return await call_next(request)


@app.exception_handler(KeyError)
async def missing(request, exc):
    return JSONResponse(
        {"detail": "This saved item could not be found."}, status_code=404
    )


@app.exception_handler(vision.VisionError)
async def vision_failure(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)


Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
Action = Literal[
    "drive",
    "walk",
    "light_up",
    "make_sound",
    "grab",
    "spin",
    "sense_distance",
    "display_face",
    "fly_ish",
]


class Brief(BaseModel):
    project_name: Text
    scale: Literal["handheld", "desktop", "floor", "wearable"]
    approx_size_cm: int = Field(ge=3, le=150)
    vibe: list[Text] = Field(min_length=1, max_length=3)
    adventure_aura: str = Field(min_length=1, max_length=600)
    must_do: list[Action] = Field(min_length=1, max_length=9)
    user_notes: str = Field(default="", max_length=600)


Provider = Literal["local", "gemini"]


class PlanRequest(BaseModel):
    spec_id: Text
    inventory_id: Text
    brief_id: Text
    excluded_indices: list[Annotated[int, Field(strict=True, ge=0, le=14)]] = Field(default_factory=list, max_length=15)


class SaveRequest(BaseModel):
    plan_id: Text
    outcome: Literal["planned"] = "planned"


class SpeakRequest(BaseModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=1200, pattern=r"\S")]


@app.get("/api/config")
async def config():
    source = await vision.vision_source()
    return {
        "vision_available": bool(source),
        "vision_providers": {"local": bool(source), "gemini": bool(os.environ.get("GEMINI_API_KEY", "").strip())},
        "vision_source": source,
        "local_voice_available": speech.available(),
        "elevenlabs_voice_available": speech.elevenlabs_settings() is not None,
        "notebook_id": hashlib.sha256(os.fsencode(store.STATE)).hexdigest()[:16],
        "demo_store": store.STATE == (store.ROOT / ".var" / "workbench").resolve(),
        "templates": [
            {"id": k, "label": v["robot_name"]} for k, v in TEMPLATES.items()
        ],
        "salvage_keys": [{"id": k, "label": v} for k, v in salvage.KEYS.items()],
    }


@app.post("/api/transcribe")
async def transcribe(audio: Annotated[UploadFile, File()]):
    return {"text": await speech.transcribe(await audio.read(2 * 1024 * 1024 + 1))}


@app.post("/api/speak", response_class=Response, responses={200: {"content": {"audio/mpeg": {}}}})
async def speak(request: SpeakRequest):
    audio = await speech.synthesize(request.text.strip())
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/brief", status_code=201)
def create_brief(brief: Brief):
    return {"brief_id": store.put("brief", brief.model_dump())}


@app.get("/api/brief/latest")
def latest_brief():
    key, brief = store.get("brief", latest=True)
    return {"brief_id": key, **brief}


async def jpeg(file):
    content = await file.read(MAX_IMAGE + 1)
    if len(content) > MAX_IMAGE:
        raise HTTPException(413, "Choose an image under 10 MB.")
    return await run_in_threadpool(vision.read_image, content)


def usable_cached_result(kind, result, brief):
    if kind == "inventory":
        return isinstance(result, list) and len(result) <= 15 and all(
            isinstance(item, dict) and isinstance(item.get("label"), str)
            and isinstance(item.get("raw_name"), str) and vision.valid_box(item.get("box_2d"))
            and type(item.get("confidence")) in (int, float) and 0 <= item["confidence"] <= 1
            and isinstance(item.get("blocked"), bool) and isinstance(item.get("candidate_parts"), dict)
            for item in result
        )
    try:
        spec = cad.RobotSpec.model_validate(result)
    except ValidationError:
        return False
    names = {f.name for f in spec.functions}
    return spec.confidence >= 0.3 and names.issuperset(brief.get("must_do", []))


async def recognize(kind, data, source, brief=None):
    model = await vision.gemini_model() if source == "gemini" else vision.LOCAL_MODEL
    prompt_file = vision.sketch_prompt(source) if kind == "sketch" else vision.PROMPTS / "junk_to_inventory.md"
    prompt = prompt_file.read_text()
    key = store.recognition_key(kind, data, brief, source, model, prompt)
    cached = store.recognition(key)
    if cached is not None and usable_cached_result(kind, cached, brief):
        return "cached_" + source, cached
    if source == "local" and not await vision.vision_source():
        raise HTTPException(503, "On-device recognition is offline. Start the local model, use an example sketch or choose drawer items manually.")
    if kind == "sketch":
        result = await vision.analyze_sketch(data, brief, source=source, model=model, prompt=prompt)
    else:
        result = await vision.analyze_junk(data, source=source, model=model, prompt=prompt)
    store.remember_recognition(key, result)
    return source, result


@app.post("/api/sketch")
async def sketch(
    brief_id: str = Form(default=""),
    template: str = Form(default=""),
    provider: Provider = Form(default="local"),
    image: Annotated[UploadFile | None, File()] = None,
):
    if bool(template) == bool(image):
        raise HTTPException(400, "Select one sketch photo or one example.")
    brief = (
        store.get("brief", brief_id)[1]
        if brief_id
        else {"scale": "desktop", "approx_size_cm": 20}
    )
    if template:
        if template not in TEMPLATES:
            raise HTTPException(400, "Unknown example sketch.")
        source, raw = "example", TEMPLATES[template]
    else:
        data = await jpeg(image)
        source, raw = await recognize("sketch", data, provider, brief)
    spec_id = store.new_id("s")
    dest = store.FILES / spec_id
    try:
        model = cad.RobotSpec.model_validate(raw)
        dest.mkdir()
        spec = await run_in_threadpool(
            cad.export_model, model, brief["approx_size_cm"], dest
        )
        spec = vision.with_requested_actions(spec, brief)
        result = {
            "spec_id": spec_id,
            "unresolved_actions": vision.unresolved_actions(spec, brief),
            "spec": spec,
            "source": source,
            "glb_url": f"/files/{spec_id}/model.glb",
            "stl_url": f"/files/{spec_id}/model.stl",
        }
        if image:
            (dest / "sketch.jpg").write_bytes(data)
            result["sketch_url"] = f"/files/{spec_id}/sketch.jpg"
        store.put("sketch", {**result, "brief_id": brief_id}, spec_id)
        return result
    except (ValidationError, ValueError, RuntimeError) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise HTTPException(
            422, "Couldn't build these shapes. Try a simpler drawing or an example."
        ) from exc
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise


@app.post("/api/junk")
async def drawer(
    items: str | None = Form(default=None),
    provider: Provider = Form(default="local"),
    image: Annotated[UploadFile | None, File()] = None,
):
    if (items is not None) == bool(image):
        raise HTTPException(400, "Choose an image or select drawer items.")
    if image:
        data = await jpeg(image)
        source, detected = await recognize("inventory", data, provider)
    else:
        try:
            labels = json.loads(items)
            if (
                not isinstance(labels, list)
                or len(labels) > 15
                or not all(isinstance(x, str) for x in labels)
            ):
                raise ValueError
            detected = salvage.manual_inventory(labels)
        except (KeyError, ValueError, TypeError):
            raise HTTPException(422, "Choose at most 15 known drawer items.")
        source = "manual"
    inventory_id = store.new_id("i")
    inventory = {"items": vision.distinct_detections([salvage.screen_donor(item) for item in detected])}
    photo_path = store.PHOTOS / (inventory_id + ".jpg")
    try:
        if image:
            photo_path.write_bytes(data)
            inventory["photo_url"] = f"/drawer-photo/{inventory_id}"
        result = {"inventory": inventory, "source": source}
        store.put("inventory", result, inventory_id)
        return {"inventory_id": inventory_id, **result}
    except Exception:
        photo_path.unlink(missing_ok=True)
        raise


@app.get("/drawer-photo/{inventory_id}")
def drawer_photo(inventory_id: str):
    _, row = store.get("inventory", inventory_id)
    path = store.PHOTOS / (inventory_id + ".jpg")
    if "photo_url" not in row["inventory"] or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg")


def reviewed_items(items, excluded_indices):
    if any(index >= len(items) for index in excluded_indices):
        raise HTTPException(422, "One of the excluded drawer items is missing. Review this inventory again.")
    reviewed = [salvage.screen_donor(item) for item in items]
    for index in excluded_indices:
        reviewed[index] = {**reviewed[index], "user_excluded": True}
    return vision.distinct_detections(reviewed, preserve_indices=True)


@app.post("/api/plan")
def plan(req: PlanRequest):
    _, brief = store.get("brief", req.brief_id)
    _, sketch = store.get("sketch", req.spec_id)
    _, inventory = store.get("inventory", req.inventory_id)
    if sketch["brief_id"] and sketch["brief_id"] != req.brief_id:
        raise HTTPException(409, "This sketch belongs to a different interview.")
    spec = vision.with_requested_actions(sketch["spec"], brief)
    query = " ".join(
        [
            brief["project_name"],
            brief["adventure_aura"],
            *brief["must_do"],
            *(f["name"] for f in spec["functions"]),
        ]
    )
    matched = salvage.build_plan(
        spec, reviewed_items(inventory["inventory"]["items"], req.excluded_indices), store.search(query)
    )
    payload = {**req.model_dump(), "plan": matched}
    return {"plan_id": store.put("plan", payload), "plan": matched}


def reviewed_snapshot(data, spec):
    _, record = store.get("inventory", data["inventory_id"])
    inventory = record["inventory"]
    items = reviewed_items(inventory["items"], data.get("excluded_indices", []))
    saved_plan = data["plan"]
    if items != inventory["items"]:
        saved_plan = {**saved_plan, "allocations": None}
        inventory = {**inventory, "items": items}
    return salvage.with_allocations(saved_plan, spec, items), inventory, record["source"]


@app.post("/api/projects", status_code=201)
def save(req: SaveRequest):
    _, data = store.get("plan", req.plan_id)
    _, brief = store.get("brief", data["brief_id"])
    _, sketch = store.get("sketch", data["spec_id"])
    saved_plan, _, _ = reviewed_snapshot(data, vision.with_requested_actions(sketch["spec"], brief))
    parts = [x["need"] for x in saved_plan["from_your_drawer"]]
    note = (
        "Planned with " + ", ".join(x.replace("_", " ") for x in parts) + "."
        if parts
        else "Saved a plan with a shopping list."
    )
    memory = {
        "project_name": brief["project_name"],
        "note": note,
        "outcome": "planned",
        "seeded": False,
        "keywords": " ".join(
            [
                brief["adventure_aura"],
                *brief["must_do"],
                *parts,
                *(x["name"] for x in sketch["spec"]["functions"]),
            ]
        ),
    }
    return {"project_id": store.save_project(req.plan_id, memory)}


@app.get("/api/projects/{project_id}")
def project(project_id: str):
    data = store.project_plan(project_id)
    _, brief = store.get("brief", data["brief_id"])
    _, sketch = store.get("sketch", data["spec_id"])
    spec = vision.with_requested_actions(sketch["spec"], brief)
    saved_plan, inventory, source = reviewed_snapshot(data, spec)
    return {
        **sketch,
        "project_id": project_id,
        "spec": spec,
        "unresolved_actions": vision.unresolved_actions(spec, brief),
        "excluded_indices": data.get("excluded_indices", []),
        "brief": brief,
        "plan": saved_plan,
        "inventory": inventory,
        "inventory_source": source,
    }


@app.get("/api/memory/search")
def memory(q: str = Query("", max_length=600)):
    return store.search(q)


@app.get("/files/{spec_id}/{name}")
def model_file(spec_id: str, name: str):
    if name == "sketch.jpg":
        _, sketch = store.get("sketch", spec_id)
        path = store.FILES / spec_id / name
        if not sketch.get("sketch_url") or not path.is_file():
            raise HTTPException(404, "No original sketch photo was saved.")
        return FileResponse(path, media_type="image/jpeg")
    if name not in ("model.stl", "model.glb"):
        raise HTTPException(404)
    store.get("sketch", spec_id)
    return FileResponse(
        store.FILES / spec_id / name,
        media_type="model/gltf-binary" if name.endswith(".glb") else "model/stl",
        filename=name,
    )


DIST = store.ROOT / "frontend" / "dist"
workbench = StaticFiles(directory=DIST, html=True, check_dir=False)


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/index.html", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/project/{project_id}", methods=["GET", "HEAD"], include_in_schema=False)
async def app_shell(request: Request):
    response = await workbench.get_response("index.html", request.scope)
    response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/", workbench, name="workbench")
