"""Exercise a rehearsal server. Run with .venv/bin/python eval/eval.py [--photos]."""

import argparse
import io
import time
from collections import Counter
from pathlib import Path

import httpx
import trimesh

parser = argparse.ArgumentParser()
parser.add_argument(
    "--photos",
    action="store_true",
    help="Run vision on 3 drawings and reference photos",
)
parser.add_argument("--base", default="http://127.0.0.1:8768")
args = parser.parse_args()
inputs = Path(__file__).with_name("inputs")
client = httpx.Client(base_url=args.base, timeout=240, trust_env=False)


def post(path, **kwargs):
    response = client.post("/api/" + path, **kwargs)
    if response.is_error:
        raise RuntimeError(f"{path}: {response.status_code} {response.text[:450]}")
    return response.json()


def check_sketch(body, target_cm=None):
    assert body["spec"]["parts"] and body["source"] in {
        "gemini",
        "local",
        "example",
        "cached_local",
        "cached_gemini",
    }
    for suffix, magic in (("glb", b"glTF"), ("stl", None)):
        response = client.get(body[f"{suffix}_url"])
        assert response.status_code == 200 and len(response.content) > 200
        if magic:
            assert response.content[:4] == magic
        elif target_cm is not None:
            mesh = trimesh.load(io.BytesIO(response.content), file_type="stl")
            bottom, top = mesh.bounds[:, 2]
            assert abs(bottom) < 0.1 and target_cm * 8 <= top <= target_cm * 12, (bottom, top)
    return body["spec_id"]


def photo(path, filename, **fields):
    image = (filename, (inputs / filename).read_bytes(), "image/jpeg")
    return post(path, files={"image": image}, data=fields)


if __name__ == "__main__":
    config = client.get("/api/config").raise_for_status().json()
    if config.get("demo_store") is not False:
        raise SystemExit(
            f"{args.base} is not a rehearsal notebook. Start a server with "
            "RENDI_STATE_DIR set to a separate directory and pass it with --base."
        )
    brief = {
        "project_name": "Eval Rover",
        "scale": "desktop",
        "approx_size_cm": 20,
        "vibe": ["curious"],
        "adventure_aura": "Explore the desk on wheels.",
        "must_do": ["drive", "light_up"],
    }
    bid = post("brief", json=brief)["brief_id"]
    for template in config["templates"]:
        result = post("sketch", data={"brief_id": bid, "template": template["id"]})
        sid = check_sketch(result)
        if template["id"] == "wheelbot":
            rover = sid
        print(
            "PASS example and geometry:",
            template["id"],
            len(result["spec"]["parts"]),
            flush=True,
        )
    inv = post("junk", data={"items": '["rc_car","flashlight"]'})
    result = post(
        "plan",
        json={"brief_id": bid, "spec_id": rover, "inventory_id": inv["inventory_id"]},
    )
    assert 0 < result["plan"]["drawer_score"] < 100
    saved = post("projects", json={"plan_id": result["plan_id"]})["project_id"]
    assert saved == post("projects", json={"plan_id": result["plan_id"]})["project_id"]
    assert client.get("/api/projects/" + saved).json()["plan"] == result["plan"]
    assert any(
        hit["project_name"] == "Eval Rover" and not hit["seeded"]
        for hit in client.get("/api/memory/search", params={"q": "Eval Rover"}).json()
    )
    print("PASS matched quantities, save, repeat save, load and recall", flush=True)
    if args.photos:
        assert config["vision_available"], "Start the local model or configure Gemini"
        print("Vision provider:", config["vision_source"], flush=True)
        drawings = [
            ("wheelbot", 20, ["drive", "light_up"], "Explore the desk on wheels.", {"wheel": 2}),
            ("armbot", 18, ["grab"], "Pick up foam blocks with a jointed claw.", {"arm_link": 2, "servo_mount": 1}),
            ("blobbot", 12, ["light_up"], "Glow gently on the nightstand.", {"sphere": 1}),
        ]
        for drawing, size, actions, adventure, geometry in drawings:
            sketch_brief = {**brief, "project_name": "Eval " + drawing, "approx_size_cm": size,
                            "must_do": actions, "adventure_aura": adventure}
            brief_id = post("brief", json=sketch_brief)["brief_id"]
            start = time.monotonic()
            result = photo("sketch", drawing + ".jpg", brief_id=brief_id)
            assert result["source"] != "example", result["source"]
            spec_id = check_sketch(result, size)
            parts = result["spec"]["parts"]
            shapes = Counter(p["primitive"] for p in parts)
            assert all(shapes[k] >= qty for k, qty in geometry.items()), (drawing, shapes)
            assert set(actions) <= {f["name"] for f in result["spec"]["functions"]}
            if drawing == "wheelbot":
                live_rover, rover_brief = spec_id, brief_id
            if drawing == "armbot":
                assert any(any(abs(v) > 1 for v in p["rot_deg"]) for p in parts if p["primitive"] == "arm_link")
            if drawing == "blobbot":
                assert max(p["dims_mm"][0] for p in parts if p["primitive"] == "sphere") > size * 3
            print("PASS photo", drawing, result["source"], f"{time.monotonic()-start:.1f}s", dict(shapes), flush=True)

        for filename, expected in (("rc-car.jpg", ["rc_car"]), ("flashlight.jpg", ["flashlight"]),
                                   ("drawer-reference.jpg", ["rc_car", "flashlight"])):
            start = time.monotonic()
            result = photo("junk", filename)
            assert result["source"] in {"gemini", "local", "cached_local", "cached_gemini"}
            items = result["inventory"]["items"]
            assert Counter(i["label"] for i in items if not i["blocked"]) == Counter(expected), items
            for item in items:
                top, left, bottom, right = item["box_2d"]
                assert 0 <= top < bottom <= 1000 and 0 <= left < right <= 1000
            if filename == "drawer-reference.jpg":
                car, light = (next(i for i in items if i["label"] == k) for k in expected)
                assert car["box_2d"][3] < 500 < light["box_2d"][1], items
                matched = post("plan", json={"brief_id": rover_brief, "spec_id": live_rover,
                                             "inventory_id": result["inventory_id"]})["plan"]
                quantities = Counter()
                for row in matched["from_your_drawer"]:
                    quantities[row["need"]] += row["qty"]
                assert quantities == {"dc_motor": 1, "wheel": 2, "led": 1}, quantities
                assert matched["drawer_score"] == 40, matched["drawer_score"]
                print("PASS combined drawer match", dict(quantities), "40% coverage", flush=True)
            print("PASS photo", filename, result["source"], f"{time.monotonic()-start:.1f}s", expected, flush=True)
