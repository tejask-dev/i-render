"""Check adaptation suggestions and saved projects offline with python -m eval.check_alternatives."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx

from backend import main, salvage, store, templates


def spec(*names):
    return {"functions": [{"name": name, "parts": []} for name in names]}


def options(plan):
    return {row["need"]: row["alternatives"] for row in plan["to_source"]}


def without_options(plan):
    return {**plan, "to_source": [{k: v for k, v in row.items() if k != "alternatives"}
                                 for row in plan["to_source"]]}


def check_matching():
    robot = spec("grab", "drive", "spin", "make_sound", "light_up")
    labels = ["loose_stepper_motor", "tv_remote", "loose_piezo", "loose_vibration_motor"] + ["loose_rgb_led"] * 3
    items = salvage.manual_inventory(labels)
    box = [20, 45, 670, 720]
    items[0].update(item_id="bench-stepper", raw_name="Blue stepper", box_2d=box)
    plan = salvage.build_plan(robot, items, [])
    choices = options(plan)
    assert without_options(plan) == without_options(salvage.build_plan(robot, [], []))
    assert {need: [a["component"] for a in rows] for need, rows in choices.items() if rows} == {
        "servo": ["stepper_motor"], "battery_pack": ["battery_holder"], "speaker": ["piezo"],
        "dc_motor": ["vibration_motor"], "led": ["rgb_led", "rgb_led"]}
    assert choices["servo"][0] == {"component": "stepper_motor", "qty": 1, "item_index": 0,
                                   "item_id": "bench-stepper", "raw_name": "Blue stepper",
                                   "source": "Loose stepper motor", "box_2d": box, "note": salvage.ADAPTATIONS["servo"][1]}
    assert all(a["qty"] == 1 for rows in choices.values() for a in rows)
    assert [a["item_index"] for a in choices["led"]] == [4, 5]

    # Spin receives the exact motor first here. Two drive motors remain missing.
    motors = salvage.manual_inventory(["loose_vibration_motor", "loose_motor"])
    drive_only = salvage.build_plan(spec("spin", "drive"), motors, [])
    assert next(r for r in drive_only["to_source"] if r["need"] == "dc_motor")["qty"] == 2
    assert options(drive_only)["dc_motor"] == []
    covered = salvage.build_plan(spec("light_up"), items + salvage.manual_inventory(["loose_led"] * 2), [])
    assert "led" not in options(covered)

    # One donor yields an indicator plus two RGBs. A different function has a direct claim on one RGB.
    donor = {"display": "Loose test parts", "parts": {"led": 1, "rgb_led": 2}, "how": "Inspect.", "tools": []}
    with (patch.dict(salvage.SOURCES, {"loose_test_parts": donor}),
          patch.dict(salvage.REQUIREMENTS, {"display_face": {"rgb_led": 1}})):
        test_items = [{"label": "loose_test_parts", "candidate_parts": {"led": 1, "rgb_led": 2}}]
        for count in (2, 1):
            test_items[0]["candidate_parts"]["rgb_led"] = count
            shared = salvage.build_plan(spec("light_up", "display_face"), test_items, [])
            assert [r["need"] for r in shared["from_your_drawer"]] == ["led", "rgb_led"]
            assert [a["qty"] for a in options(shared)["led"]] == ([1] if count == 2 else [])

    base = items[0]
    held = [{**base, "item_id": "same"}, {**base, "item_id": "same", "user_excluded": True}]
    for override in ({"blocked": True}, {"condition_note": "Unknown rating"}, {"duplicate_of": 0},
                     {"raw_name": "Motor from ATX PSU"}, {"candidate_parts": None}, {"candidate_parts": []},
                     *({"candidate_parts": {"stepper_motor": n}} for n in (True, 0, -1, 0.5, "1"))):
        held.append({**base, **override, "item_id": f"held-{len(held)}"})
    first = len(held)
    available = {**base, "item_id": "one-object", "candidate_parts": {"stepper_motor": 99, "rgb_led": 9}}
    screened = options(salvage.build_plan(robot, [*held, available, available], []))
    assert [(a["item_index"], a["qty"]) for a in screened["servo"]] == [(first, 1)]
    assert screened["led"] == []
    labels_and_names = [("string_lights", "Mains-powered plug-in string lights"),
                        ("loose_vibration_motor", "Vibration motor inside sealed phone"),
                        ("loose_vibration_motor", "Vibration motor in an old phone"),
                        ("loose_piezo", "Piezo from a smoke alarm"),
                        ("loose_stepper_motor", "230V loose stepper")]
    contradictions = [salvage.inventory_item(key, name, box=box) for key, name in labels_and_names]
    assert all(i["blocked"] and not i["candidate_parts"] for i in contradictions)
    assert not any(options(salvage.build_plan(robot, contradictions, [])).values())
    loose = salvage.inventory_item("loose_piezo", "Loose piezo from the parts drawer", box=box)
    assert options(salvage.build_plan(robot, [loose], []))["speaker"][0]["component"] == "piezo"


async def check_reopen():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as client:
        async def post(route, **kwargs):
            return (await client.post("/api/" + route, **kwargs)).raise_for_status().json()

        async def reopen(project_id):
            return (await client.get(f"/api/projects/{project_id}")).raise_for_status().json()["plan"]

        brief = {"project_name": "Test rover", "scale": "desktop", "approx_size_cm": 15, "vibe": ["playful"],
                 "adventure_aura": "A rover on the desk.", "must_do": ["drive", "light_up"]}
        bid = (await post("brief", json=brief))["brief_id"]
        sid = store.put("sketch", {"brief_id": bid, "spec": templates.TEMPLATES["wheelbot"], "source": "template"})
        iid = (await post("junk", data={"items": json.dumps(["tv_remote", "loose_rgb_led"])}))["inventory_id"]
        request = {"brief_id": bid, "spec_id": sid, "inventory_id": iid, "excluded_indices": [1]}
        result = await post("plan", json=request)
        plan = result["plan"]
        assert options(plan)["battery_pack"][0]["component"] == "battery_holder" and not options(plan)["led"]
        pid = (await post("projects", json={"plan_id": result["plan_id"]}))["project_id"]
        assert await reopen(pid) == plan

        legacy = without_options(plan)
        legacy["steps"] = ["Keep the original assembly notes."]
        # Revisit old and stale payloads with their original allocations and held-out objects.
        stale = {**legacy, "to_source": [{**row, "alternatives": [{"item_index": 1, "qty": 99}]}
                                         for row in legacy["to_source"]]}
        for stored in (legacy, stale):
            old_id = store.put("plan", {**request, "excluded_indices": [], "plan": stored})
            old_project = store.save_project(old_id, {"project_name": "Older rover"})
            refreshed = await reopen(old_project)
            assert without_options(refreshed) == legacy and options(refreshed) == options(plan)
            assert store.get("plan", old_id)[1]["plan"] == stored


if __name__ == "__main__":
    check_matching()
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        with patch.multiple(store, STATE=work, FILES=work / "models", PHOTOS=work / "photos"):
            store.initialize()
            asyncio.run(check_reopen())
    print("PASS five qualified adaptations, exact priority, caps, held donors, spin-only and saved-plan round trip")
