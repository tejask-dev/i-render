"""Check donor allocation offline. Run with python eval/check_allocation.py."""

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import salvage, templates  # noqa: E402

LEGACY_ROW = ("need", "qty", "source", "item_index", "how", "tools")
UNIT_KEYS = {"unit", "need", "functions", "part_id", "part_label", "status",
             "item_index", "item_id", "raw_name", "source", "box_2d"}
ALL_FUNCTIONS = {"robot_name": "Everything", "parts": [],
                 "functions": [{"name": name, "parts": []} for name in salvage.REQUIREMENTS]}


def legacy(spec, items):
    """The quantity-only matcher this plan replaced. Its counts stay the reference."""
    names = list(dict.fromkeys(f["name"] for f in spec["functions"])) or ["light_up"]
    needs = Counter()
    for name in names:
        for part, qty in salvage.REQUIREMENTS[name].items():
            needs[part] = max(needs[part], qty) if part in salvage.SHARED else needs[part] + qty
    drawer, remaining = [], needs.copy()
    for item_index, stored in enumerate(items):
        item = salvage.screen_donor(stored)
        label = item.get("label")
        if label not in salvage.SOURCES or item.get("blocked") or item.get("condition_note"):
            continue
        source = salvage.SOURCES[label]
        for part, available in source["parts"].items():
            used = min(remaining[part], available)
            if used:
                drawer.append({"need": part, "qty": used, "source": source["display"],
                               "item_index": item_index, "how": source["how"], "tools": source["tools"]})
                remaining[part] -= used
    shopping = [{"need": part, "qty": qty, "suggestion": salvage.SUGGESTIONS[part]}
                for part, qty in remaining.items() if qty]
    total = sum(needs.values())
    return drawer, shopping, round(100 * (total - sum(remaining.values())) / total)


def check_invariants(spec, items, stricter=False):
    plan = salvage.build_plan(spec, items, [])
    assert plan == salvage.build_plan(spec, items, []) == json.loads(json.dumps(plan))
    assert set(plan) == {"from_your_drawer", "to_source", "drawer_score", "steps", "memory_notes",
                         "allocations", "held_out"}
    if not stricter:    # lowered stored counts and repeated item ids are the two deliberate departures
        drawer, shopping, score = legacy(spec, items)
        assert [{k: row[k] for k in LEGACY_ROW} for row in plan["from_your_drawer"]] == drawer
        assert [{k: row[k] for k in ("need", "qty", "suggestion")} for row in plan["to_source"]] == shopping
        assert plan["drawer_score"] == score

    units = plan["allocations"]
    parts = {part["id"]: part for part in spec.get("parts") or []}
    used = [u for u in units if u["status"] == "drawer"]
    assert all(set(u) == UNIT_KEYS for u in units)
    assert len({u["unit"] for u in units}) == len(units)
    assert {u["status"] for u in units} <= {"drawer", "source"}
    assert len(used) == sum(row["qty"] for row in plan["from_your_drawer"])
    assert len(units) - len(used) == sum(row["qty"] for row in plan["to_source"])
    hosted = [(u["need"], u["part_id"]) for u in units if u["part_id"]]
    assert len(hosted) == len(set(hosted)), "one mesh part holds one unit of a kind"
    for u in units:
        assert u["functions"] and (u["part_id"] is None) == (u["part_label"] is None)
        assert u["part_id"] is None or parts[u["part_id"]]["label"] == u["part_label"]
        if u["status"] == "source":
            assert u["item_index"] is u["item_id"] is u["raw_name"] is u["source"] is None
    taken = Counter((u["item_index"], u["need"]) for u in used)
    for (index, need), count in taken.items():
        item = salvage.screen_donor(items[index])
        assert not item.get("blocked") and not item.get("condition_note"), item
        assert count <= salvage.SOURCES[item["label"]]["parts"][need], "an object yields each unit once"
    held = {h["item_index"] for h in plan["held_out"]}
    assert not held & {u["item_index"] for u in used}
    assert all((i in held) for i, item in enumerate(items) if salvage.screen_donor(item).get("blocked"))
    for row in plan["from_your_drawer"]:
        mine = [u for u in used if (u["item_index"], u["need"]) == (row["item_index"], row["need"])]
        assert row["part_ids"] == [u["part_id"] for u in mine if u["part_id"]]
        assert row["item_id"] == mine[0]["item_id"] and row["raw_name"] == mine[0]["raw_name"]
    assert 5 <= len(plan["steps"]) <= 8 and all(isinstance(s, str) and s for s in plan["steps"])
    return plan


if __name__ == "__main__":
    wheelbot = templates.TEMPLATES["wheelbot"]
    plan = check_invariants(wheelbot, salvage.manual_inventory(["rc_car", "flashlight"]))
    got = {u["unit"]: (u["part_id"], u["item_index"]) for u in plan["allocations"] if u["status"] == "drawer"}
    assert got == {"dc_motor-1": ("mount_left", 0), "wheel-1": ("wheel_left", 0),
                   "wheel-2": ("wheel_right", 0), "led-1": ("eye_left", 1)}, got
    lacking = {u["unit"]: u["part_id"] for u in plan["allocations"] if u["status"] == "source"}
    assert lacking == {"dc_motor-2": "mount_right", "led-2": "eye_right", "motor_driver-1": None,
                       "battery_pack-1": None, "resistor_220-1": None, "resistor_220-2": None}, lacking
    assert plan["drawer_score"] == 40 and len(got) == 4 and len(plan["allocations"]) == 10
    text = " ".join(plan["steps"])
    assert all(word in text for word in ("drawer item 1 (RC car)", "Left motor mount", "drawer item 2 (AA flashlight)",
                                         "1 DC motor (Right motor mount)", "1 LED (Right eye)", "Body"))
    print("PASS baseline: 4 of 10 units, 40%, each joined to a named mesh part;", len(plan["steps"]), "steps")

    armbot = check_invariants(templates.TEMPLATES["armbot"], salvage.manual_inventory(["hobby_servo", "loose_motor"]))
    joins = {u["unit"]: (u["part_id"], u["functions"], u["status"]) for u in armbot["allocations"]}
    assert joins["servo-1"] == ("elbow_servo", ["grab"], "drawer")
    assert joins["servo-2"] == ("shoulder_servo", ["grab"], "source")       # a mount the function left unlisted
    assert joins["dc_motor-1"] == (None, ["spin"], "drawer")                # no motor mount in the model
    blob = check_invariants(templates.TEMPLATES["blobbot"], [])
    assert [u["part_id"] for u in blob["allocations"] if u["need"] == "led"] == ["belly_light", None]
    assert blob["drawer_score"] == 0 and blob["from_your_drawer"] == [] and len(blob["steps"]) >= 5
    print("PASS function-level electronics where the model names no holder; empty drawer stays honest")

    shared = check_invariants({"functions": [{"name": n} for n in ("drive", "walk", "fly_ish", "grab")]}, [])
    packs = [u for u in shared["allocations"] if u["need"] == "battery_pack"]
    brains = [u for u in shared["allocations"] if u["need"] == "microcontroller"]
    assert [u["functions"] for u in packs] == [["drive", "walk", "fly_ish"]]
    assert [u["functions"] for u in brains] == [["walk", "grab"]]
    assert sum(u["need"] == "servo" for u in shared["allocations"]) == 6
    print("PASS a shared supply and controller count once; actuators stay distinct")

    hazards = salvage.manual_inventory(["microwave", "lithium_battery", "mains_power_supply", "rc_car", "old_phone"])
    hazards += [
        salvage.inventory_item("loose_motor", "corroded motor"),
        salvage.inventory_item("computer_fan", "Computer Fan", box=[170, 430, 250, 550], confidence=.99),
        {"label": "loose_motor", "raw_name": "ATX PSU fan motor", "blocked": False,
         "candidate_parts": {"dc_motor": 1}},
        {"label": "loose_led", "raw_name": "LED from a swollen pack", "candidate_parts": {"led": 1}},
        {"label": "loose_wheel", "raw_name": "Wheel", "blocked": True, "candidate_parts": {"wheel": 1}},
        {"label": "loose_motor", "raw_name": "Motor", "candidate_parts": {"dc_motor": 9, "servo": 4}},
        {"label": "rc_car", "raw_name": "Car without wheels", "candidate_parts": {"dc_motor": 1}},
        {"label": "loose_led", "raw_name": "Emptied", "candidate_parts": {}},
    ]
    risky = check_invariants(ALL_FUNCTIONS, hazards, stricter=True)
    sources = Counter((u["item_index"], u["need"]) for u in risky["allocations"] if u["status"] == "drawer")
    assert sources == {(3, "dc_motor"): 1, (3, "wheel"): 2, (10, "dc_motor"): 1, (11, "dc_motor"): 1}, sources
    assert [h["item_index"] for h in risky["held_out"] if h["blocked"]] == [0, 1, 2, 5, 6, 7, 8, 9]
    assert [h["item_index"] for h in risky["held_out"] if not h["blocked"]] == [4]
    steps = " ".join(risky["steps"])
    assert "Leave drawer item 1 (Microwave)" in steps and "guarded fans" in steps and len(risky["steps"]) == 8
    print("PASS excluded items yield nothing, stored counts only lower a yield, safety steps survive the cap")

    twice = [{**salvage.inventory_item("loose_motor", "Motor"), "id": "a"},
             {**salvage.inventory_item("loose_motor", "Motor again"), "id": "a"},
             {**salvage.inventory_item("microwave", "Microwave"), "item_id": 7},
             {**salvage.inventory_item("loose_motor", "Motor inside it"), "item_id": 7},
             *salvage.manual_inventory(["loose_motor", "loose_motor"])]
    once = check_invariants(wheelbot, twice, stricter=True)
    assert [(u["item_index"], u["item_id"]) for u in once["allocations"] if u["status"] == "drawer"] == [
        (0, "a"), (4, "item-4")]
    assert [(h["item_index"], h["blocked"]) for h in once["held_out"]] == [(1, False), (2, True), (3, False)]
    assert "Same object as drawer item 3" in once["held_out"][2]["reason"]
    print("PASS a repeated item id counts once; identical unnumbered items stay separate by index")

    old_items = [{"label": "rc_car", "raw_name": "RC Car", "box_2d": [10, 20, 400, 480], "condition_note": None},
                 {"label": "flashlight", "raw_name": "Flashlight", "condition_note": None, "blocked": False,
                  "confidence": .9, "candidate_parts": {"led": 1}},
                 {"label": "gadget", "raw_name": "Mystery"}, {"raw_name": ""}, {}]
    old_spec = {"functions": [{"name": "drive"}, {"name": "light_up"}, {"name": "drive"}]}
    old = check_invariants(old_spec, old_items)
    assert old["drawer_score"] == 40 and {u["part_id"] for u in old["allocations"]} == {None}
    assert old["allocations"][0]["box_2d"] == [10, 20, 400, 480]
    saved = {"from_your_drawer": [], "to_source": [], "drawer_score": 0, "steps": ["Old"], "memory_notes": ["Kept"]}
    fresh = salvage.with_allocations(saved, wheelbot, old_items)
    assert fresh["memory_notes"] == ["Kept"] and fresh["drawer_score"] == 40 and fresh["allocations"]
    assert salvage.with_allocations(fresh, wheelbot, []) is fresh
    print("PASS inventories and plans saved before item ids and joins still load")

    rng = random.Random(13)
    empty = check_invariants({"functions": []}, [], stricter=True)
    assert empty["allocations"] == empty["to_source"] == [] and empty["drawer_score"] == 0
    assert salvage.inventory_item("loose_motor", "burnt motor")["blocked"]
    later_block = salvage.build_plan(wheelbot, [twice[0], {**twice[0], "blocked": True}], [])
    assert not later_block["from_your_drawer"]
    more_wheels = [{**p, "id": "rear_" + p["id"]} for p in wheelbot["parts"] if p["primitive"] == "wheel"]
    slots = salvage.required_units({**wheelbot, "parts": wheelbot["parts"] + more_wheels})
    assert len({slot["part_id"] for slot in slots if slot["need"] == "wheel"}) == 4
    specs = [*templates.TEMPLATES.values(), ALL_FUNCTIONS]
    for _ in range(24):
        keys = rng.choices(list(salvage.KEYS), k=rng.randint(0, 15))
        items = salvage.manual_inventory(keys)
        for item in rng.sample(items, k=len(items) // 3):
            item.update(box_2d=[0, 0, 100, 100], confidence=.9)
        spec = rng.choice(specs)
        if spec is ALL_FUNCTIONS:
            names = rng.sample(list(salvage.REQUIREMENTS), k=rng.randint(1, 9))
            spec = {"functions": [{"name": name} for name in names]}
        check_invariants(spec, items)
    print("PASS empty functions, damage, four-wheel designs and 24 varied drawer inventories")
