"""Offline regression for provider choice, semantic repair, photo recovery and excluded donors.

Run from the repository root with .venv/bin/python -m eval.check_recognition.
"""

import asyncio
import hashlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import numpy as np
import trimesh
from PIL import Image, ImageDraw


def check_photo_orientation(directory):
    from backend import cad, vision

    paper = Image.new("L", (100, 100), "white")
    ImageDraw.Draw(paper).line((35, 78, 78, 33), fill="black", width=3)
    encoded = io.BytesIO()
    paper.save(encoded, "PNG")
    # The light is to the right of the base. The ink link and the pivot chain rise to the right.
    parts = [("base", [100, 780, 600, 900]), ("light", [480, 680, 560, 780]),
             ("arm", [330, 300, 810, 810])]
    for hinges in ([], [("joint", [500, 560, 570, 630]), ("gripper", [780, 250, 850, 330])]):
        boxes = [{"role": role, "box_2d": box} for role, box in parts + hinges]
        raw = vision._from_boxes({"parts": boxes, "confidence": .95}, {"approx_size_cm": 20}, encoded.getvalue())
        cad.export_model(cad.RobotSpec.model_validate(raw), 20, directory)
        meshes = trimesh.load(directory / "model.glb", force="scene").geometry
        assert meshes["light_2"].bounds[:, 0].mean() > meshes["base_1"].bounds[:, 0].mean()
        arms = [mesh for name, mesh in meshes.items() if name.startswith("arm_")]
        assert len(arms) == (2 if hinges else 1)
        assert all(np.cov(mesh.vertices[:, :2].T)[0, 1] > 0 for mesh in arms)

    # The near wheel shows an oval hub. The narrow tread retains its across-body axle.
    boxes = [{"role": role, "box_2d": rect} for role, rect in (
        ("body_box", [220, 300, 830, 680]), ("wheel", [290, 630, 470, 840]),
        ("wheel", [765, 620, 825, 850]))]
    raw = vision._from_boxes({"parts": boxes, "confidence": .95}, {"approx_size_cm": 20}, encoded.getvalue())
    cad.export_model(cad.RobotSpec.model_validate(raw), 20, directory)
    meshes = trimesh.load(directory / "model.glb", force="scene").geometry
    assert set(meshes) == {"body_box_1", "wheel_2", "wheel_3"}
    body, face, tread = (trimesh.Trimesh(vertices=meshes[k].vertices, faces=meshes[k].faces)
                         for k in ("body_box_1", "wheel_2", "wheel_3"))
    assert np.isclose(face.extents[0], face.extents[1]) and face.extents[2] < .3 * face.extents[1]
    assert face.bounds[1, 2] > body.bounds[1, 2] > face.bounds[0, 2]
    assert np.isclose(tread.extents[2], tread.extents[1]) and tread.extents[0] < .3 * tread.extents[1]
    assert all(trimesh.boolean.intersection([body, wheel], engine="manifold").volume > 0
               for wheel in (face, tread))


async def check(directory):
    from backend import main, salvage, store, vision
    from backend.templates import TEMPLATES

    store.initialize()
    check_photo_orientation(directory / "orientation")
    prompts = directory / "prompts"
    shutil.copytree(vision.PROMPTS, prompts)
    copied_prompt = prompts / "local_sketch_parts.md"
    image = Path("eval/inputs/wheelbot.jpg").read_bytes()
    files = {"image": ("drawing.jpg", image, "image/jpeg")}
    calls = []
    local_unavailable = False
    configured = "gemini-2.5-flash"

    # Close boxes on a single donor count once. Another car beside it is a distinct donor.
    first_box, repeat_box, neighbour = [50, 50, 350, 350], [53, 52, 353, 352], [50, 370, 350, 670]
    def detection(label, box, condition="no_visible_damage", confidence=.95):
        return {"label": label, "raw_name": label, "box_2d": box, "condition": condition, "confidence": confidence}

    safe = [detection("rc_car", first_box), detection("rc_car", repeat_box),
            detection("rc_car", neighbour), detection("flashlight", first_box)]
    damaged = detection("rc_car", repeat_box, condition="corroded", confidence=.55)
    for rows in (safe, [*safe, damaged], [damaged, *safe]):
        with patch.object(vision, "_generate", new=AsyncMock(return_value={"items": rows})):
            found = await vision.analyze_junk(image, source="gemini")
        assert [item["label"] for item in found] == ["rc_car", "rc_car", "flashlight"]
        assert found[1]["box_2d"] == neighbour
        assert bool(found[0]["blocked"]) == (rows is not safe) and not found[1]["blocked"]
        if rows is not safe:
            assert not found[0]["candidate_parts"] and "corroded" in found[0]["condition_note"].lower()

    def service(request):
        url = request.url
        calls.append((request.method, url.host, url.path))
        if url.host == "127.0.0.1":
            assert "x-goog-api-key" not in request.headers
            if url.path == "/api/tags":
                models = [] if local_unavailable else [{"name": vision.LOCAL_MODEL}]
                return httpx.Response(200, json={"models": models})
            assert url.path == "/api/chat"
            boxes = {"parts": [{"role": "wheel", "box_2d": [100, 100, 400, 400]}], "confidence": .9}
            return httpx.Response(200, json={"message": {"content": json.dumps(boxes)}})
        assert url.host == "generativelanguage.googleapis.com"
        assert request.headers["x-goog-api-key"] == "test-only"
        if request.method == "GET":
            assert url.path == "/v1beta/models" and not request.content
            return httpx.Response(200, json={"models": [{"name": "models/" + configured,
                                  "supportedGenerationMethods": ["generateContent"]}]})
        body = json.loads(request.content)
        assert url.path.endswith(f"/{configured}:generateContent")
        assert body["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "image/jpeg"
        if "items" in body["generationConfig"]["responseJsonSchema"]["properties"]:
            output = {"items": [{"label": label, "raw_name": label, "box_2d": box,
                                 "confidence": .95, "condition": "no_visible_damage"}
                                for label, box in [("rc_car", [0, 0, 400, 400]), ("flashlight", [500, 500, 900, 900])]]}
        else:
            # Preserve viable first-pass geometry when its semantic repair returns an invalid shape.
            posts = sum(method == "POST" and host == url.host for method, host, _ in calls)
            output = TEMPLATES["wheelbot"] if posts == 1 else {"parts": []}
        candidate = {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(output)}]}}
        return httpx.Response(200, json={"candidates": [candidate]})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as client:
        http_client = httpx.AsyncClient
        def mocked_client(**kwargs):
            return http_client(transport=httpx.MockTransport(service), **kwargs)
        with patch.object(httpx, "AsyncClient", side_effect=mocked_client), patch.object(vision, "PROMPTS", prompts):
            async def post(path, **kwargs):
                return (await client.post("/api/" + path, **kwargs)).raise_for_status().json()

            config = (await client.get("/api/config")).raise_for_status().json()
            assert config["notebook_id"] == hashlib.sha256(os.fsencode(directory.resolve())).hexdigest()[:16]
            assert config["vision_providers"] == {"local": True, "gemini": True} and config["vision_source"] == "local"
            bid = (await post("brief", json={"project_name": "Test", "scale": "desktop", "approx_size_cm": 10,
                         "vibe": ["playful"], "adventure_aura": "Test", "must_do": ["drive", "make_sound"]}))["brief_id"]
            sketch = await post("sketch", data={"brief_id": bid}, files=files)
            assert sketch["source"] == "local" and sketch["unresolved_actions"] == ["make_sound"]
            assert next(f["parts"] for f in sketch["spec"]["functions"] if f["name"] == "make_sound") == []
            assert (await client.get(sketch["sketch_url"])).content == vision.read_image(image)
            with store.connect() as db:
                db.execute("UPDATE recognition SET result='{}'")
            assert (await post("sketch", data={"brief_id": bid}, files=files))["source"] == "local"
            local_unavailable = True
            cached = await post("sketch", data={"brief_id": bid}, files=files)
            assert cached["source"] == "cached_local"
            copied_prompt.write_text(copied_prompt.read_text() + "\nUse the revised instructions.\n")
            offline = await client.post("/api/sketch", data={"brief_id": bid}, files=files)
            assert offline.status_code == 503
            assert all(host == "127.0.0.1" for _, host, _ in calls)
            local_unavailable = False
            calls.clear()
            remote = await post("sketch", data={"brief_id": bid, "provider": "gemini"}, files=files)
            assert remote["source"] == "gemini" and remote["unresolved_actions"] == ["make_sound"]
            assert [method for method, _, _ in calls] == ["GET", "POST", "POST"]
            inventory = await post("junk", data={"provider": "gemini"}, files=files)
            args = {"brief_id": bid, "spec_id": sketch["spec_id"], "inventory_id": inventory["inventory_id"]}
            assert (await client.post("/api/plan", json={**args, "excluded_indices": [2]})).status_code == 422
            plan = await post("plan", json={**args, "excluded_indices": [0]})
            assert all(r["item_index"] != 0 for r in plan["plan"]["from_your_drawer"])
            saved = await post("projects", json={"plan_id": plan["plan_id"]})
            assert await post("projects", json={"plan_id": plan["plan_id"]}) == saved
            reopened = (await client.get("/api/projects/" + saved["project_id"])).raise_for_status().json()
            assert reopened["sketch_url"] == sketch["sketch_url"] and reopened["excluded_indices"] == [0]
            removed = reopened["inventory"]["items"][0]
            assert removed["user_excluded"] and not removed["blocked"] and removed["condition_note"] is None
            assert reopened["plan"] == plan["plan"]
            held = next(i for i in plan["plan"]["held_out"] if i["item_index"] == 0)
            assert not held["blocked"] and "exclud" in held["reason"].lower()
            assert (await client.get(reopened["inventory"]["photo_url"])).content == vision.read_image(image)
            # A saved photo can predate deduplication and already have an overstated allocation.
            legacy_items = [salvage.inventory_item("rc_car", "RC car", box=box, confidence=.95,
                                condition="Corroded" if i == 1 else None)
                            for i, box in enumerate([first_box, repeat_box, neighbour])]
            old_inventory = store.put("inventory", {"source": "local", "inventory": {"items": legacy_items}})
            original = {**args, "inventory_id": old_inventory, "plan": {**plan["plan"], "drawer_score": 100}}
            old_plan = store.put("plan", original)
            old_project = await post("projects", json={"plan_id": old_plan})
            restored = (await client.get("/api/projects/" + old_project["project_id"])).raise_for_status().json()
            items = restored["inventory"]["items"]
            assert len(items) == 3 and items[0]["blocked"] and items[1]["duplicate_of"] == 0
            assert not items[0]["candidate_parts"] and not items[1]["candidate_parts"] and items[2] == legacy_items[2]
            assert {slot["item_index"] for slot in restored["plan"]["allocations"] if slot["status"] == "drawer"} == {2}
            reviewed = main.reviewed_items([legacy_items[0], {**legacy_items[0], "box_2d": repeat_box}], [1])
            assert reviewed[0]["user_excluded"] and reviewed[1]["duplicate_of"] == 0
            with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
                before = len(calls)
                assert (await client.post("/api/sketch", data={"brief_id": bid, "provider": "gemini"}, files=files)).status_code == 503
                assert len(calls) == before


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as work, patch.dict(os.environ, {
        "GEMINI_API_KEY": "test-only", "GEMINI_MODEL": "", "RENDI_STATE_DIR": work
    }):
        asyncio.run(check(Path(work)))
    print("PASS default local, offline cache, edited prompt, Gemini list and repair, saved JPEGs, exclusions, duplicate photos and legacy recall (mock providers)")
