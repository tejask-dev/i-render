"""Offline regression for provider choice, semantic repair, photo recovery and excluded donors.

Run from the repository root with .venv/bin/python -m eval.check_recognition.
"""

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx


async def check(directory):
    from backend import main, store, vision
    from backend.templates import TEMPLATES

    store.initialize()
    prompts = directory / "prompts"
    shutil.copytree(vision.PROMPTS, prompts)
    copied_prompt = prompts / "local_sketch_parts.md"
    image = Path("eval/inputs/wheelbot.jpg").read_bytes()
    files = {"image": ("drawing.jpg", image, "image/jpeg")}
    calls = []
    local_unavailable = False
    configured = "gemini-2.5-flash"

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
            with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
                before = len(calls)
                assert (await client.post("/api/sketch", data={"brief_id": bid, "provider": "gemini"}, files=files)).status_code == 503
                assert len(calls) == before


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as work, patch.dict(os.environ, {
        "GEMINI_API_KEY": "test-only", "GEMINI_MODEL": "", "RENDI_STATE_DIR": work
    }):
        asyncio.run(check(Path(work)))
    print("PASS default local, offline cache, edited prompt, Gemini list and repair, saved JPEGs, exclusions and recall (mock providers)")
