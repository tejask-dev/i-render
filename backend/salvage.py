"""A bill of candidate components for a low-voltage tabletop robot."""

import json
import re
from collections import Counter
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data"
SOURCES = json.loads((DATA / "salvage_map.json").read_text())
BLOCKED = SOURCES.pop("never_salvage")
KEYS = {key: entry["display"] for key, entry in SOURCES.items()} | BLOCKED
REQUIREMENTS = json.loads((DATA / "function_requirements.json").read_text())
SUGGESTIONS = {
    "dc_motor": "A geared DC motor sized to the mount and matched to the driver’s voltage and stall-current limits.",
    "wheel": "A toy wheel with the correct axle bore and diameter.",
    "motor_driver": "A dual motor-driver module rated for the motors’ stall current, such as a suitable DRV8833 breakout.",
    "battery_pack": "A finished enclosed low-voltage supply rated for the whole load, with a matching connector.",
    "servo": "A positional hobby servo sized for the joint travel, torque and available current.",
    "microcontroller": "A controller with enough compatible pins for the selected functions, such as an Arduino Nano.",
    "led": "A known low-current indicator LED with documented forward voltage and current.",
    "resistor_220": "A current-limiting resistor per LED. Verify 220 Ω suits the supply and LED ratings.",
    "speaker": "A small passive speaker with impedance and power ratings matched to the amplifier.",
    "audio_amp": "A compatible low-voltage audio amplifier module with an audio source.",
    "ultrasonic_sensor": "A distance-sensor module with a logic level compatible with the controller.",
    "small_display": "A small compatible display, such as an SSD1306 OLED breakout.",
    "fan": "A guarded low-voltage fan for a stationary airflow effect.",
}
HAZARDOUS_NAME = re.compile(
    r"microwave|\bcrt\b|cathode.?ray|(?:disposable|single.use|flash) camera|"
    r"\blithium\b|li[ -]?(?:ion|po)\b|\bswollen\b|\bcorroded\b|\bleaking\b",
    re.I,
)
POWER_SUPPLY_NAME = re.compile(r"\bpsu\b|\bpower[ _-]*suppl(?:y|ies)\b|\batx[ _-]*supply\b", re.I)
BLOCK_NOTE = "Excluded from salvage. Leave this item intact."
SHARED = {"microcontroller", "battery_pack"}
DETACHED_CHECK = {
    "computer_fan": "Set aside. Add it manually only after verifying it is already loose, intact and labelled for low-voltage DC. Leave power supplies closed.",
    "cd_dvd_drive": "Set aside. Add it manually only after verifying it is already detached, disconnected, intact and labelled for low-voltage DC. Leave the laser and power supply intact.",
}


def screen_donor(item: dict) -> dict:
    """Reapply the exclusions and physical-inspection rule to stored detections."""
    label = item.get("label")
    raw_name = item.get("raw_name") or ""
    if label == "mains_power_supply" or POWER_SUPPLY_NAME.search(raw_name):
        return {**item, "blocked": True, "candidate_parts": {},
                "condition_note": "Power supply excluded. Leave its enclosure closed and its internal parts in place."}
    if label in BLOCKED or HAZARDOUS_NAME.search(raw_name) or item.get("blocked"):
        return {**item, "blocked": True, "candidate_parts": {},
                "condition_note": item.get("condition_note") or BLOCK_NOTE}
    photo = item.get("box_2d") is not None or item.get("confidence") is not None
    if label in DETACHED_CHECK and photo and not item.get("blocked"):
        return {**item, "blocked": True, "candidate_parts": {},
                "condition_note": item.get("condition_note") or DETACHED_CHECK[label]}
    return item


def inventory_item(label, raw_name, *, box=None, confidence=None, condition=None):
    """Apply the same exclusions to manual picks, model labels and saved items."""
    if label not in KEYS or (label not in BLOCKED and confidence is not None and confidence < 0.65):
        label = "other"
    if condition and condition.lower().strip(" .") in {
        "none", "intact", "looks intact", "appears intact", "no visible damage",
        "no visible issues", "no damage visible", "undamaged", "good condition"
    }:
        condition = None
    blocked = label in BLOCKED or bool(HAZARDOUS_NAME.search(raw_name)) or bool(condition)
    if blocked:
        note = f"{condition} — {BLOCK_NOTE}" if condition and BLOCK_NOTE not in condition else condition or BLOCK_NOTE
    elif label == "other":
        note = "Unidentified item. No components counted."
    elif not SOURCES[label]["parts"]:
        note = "No compatible removable component is assumed for this item."
    else:
        note = None
    candidates = {} if blocked or label == "other" else SOURCES[label]["parts"]
    return screen_donor({"label": label, "raw_name": raw_name, "box_2d": box, "condition_note": note,
                         "confidence": confidence, "blocked": blocked, "candidate_parts": candidates})


def manual_inventory(keys: list[str]) -> list[dict]:
    if not isinstance(keys, list) or len(keys) > 15:
        raise ValueError("Select up to 15 drawer items.")
    if any(not isinstance(key, str) or key not in KEYS for key in keys):
        raise ValueError("Choose listed drawer items.")
    return [inventory_item(key, KEYS[key]) for key in keys]


def build_plan(spec: dict, items: list[dict], memory: list[dict]) -> dict:
    names = list(dict.fromkeys(f["name"] for f in spec["functions"])) or ["light_up"]
    needs = Counter()
    for name in names:
        for part, qty in REQUIREMENTS[name].items():
            # Distinct moving functions need distinct actuators. A rated supply/controller may be shared.
            needs[part] = max(needs[part], qty) if part in SHARED else needs[part] + qty

    drawer = []
    remaining = needs.copy()
    for item_index, stored_item in enumerate(items):
        item = screen_donor(stored_item)
        label = item.get("label")
        if label not in SOURCES or item.get("blocked") or item.get("condition_note"):
            continue
        source = SOURCES[label]
        for part, available in source["parts"].items():
            used = min(remaining[part], available)
            if used:
                drawer.append({"need": part, "qty": used, "source": source["display"],
                               "item_index": item_index, "how": source["how"], "tools": source["tools"]})
                remaining[part] -= used
    shopping = [{"need": part, "qty": qty, "suggestion": SUGGESTIONS[part]}
                for part, qty in remaining.items() if qty]
    total = sum(needs.values())
    score = round(100 * (total - sum(remaining.values())) / total)
    steps = ["Check the model dimensions against the real parts before printing."]
    if drawer:
        steps.append("Inspect each drawer candidate using its fit and rating checks. Move missing or unsuitable parts to your sourcing list.")
    if shopping:
        steps.append("Gather the remaining components on the sourcing list and compare their datasheets and connector sizes.")
    if "fly_ish" in names:
        steps.append("Plan a stationary airflow display with guarded fans. Keep the model secured to the table.")
    steps += ["Dry-fit the unpowered components and check clearances through the intended range of motion.",
              "Have a mentor review power, signal levels, and mounting before testing one function at a time."]
    notes = [f"{hit['project_name']} ({'example, ' if hit.get('seeded') else ''}{hit.get('outcome', 'planned')}): {hit['note']}"
             for hit in memory[:2] if hit.get("project_name") and hit.get("note")]
    return {"from_your_drawer": drawer, "to_source": shopping, "drawer_score": score,
            "steps": steps, "memory_notes": notes}


if __name__ == "__main__":
    one = manual_inventory(["rc_car", "flashlight", "microwave", "old_phone"])
    one.append(inventory_item("loose_motor", "corroded motor"))
    test_spec = {"functions": [{"name": key} for key in ("drive", "spin", "light_up")]}
    result = build_plan(test_spec, one, [])
    assert {r["need"]: r["qty"] for r in result["from_your_drawer"]} == {"dc_motor": 1, "wheel": 2, "led": 1}
    assert {r["need"]: r["qty"] for r in result["to_source"]} == {
        "dc_motor": 2, "motor_driver": 1, "battery_pack": 1, "led": 1, "resistor_220": 2}
    assert result["drawer_score"] == 36
    assert build_plan({"functions": []}, [], [])["drawer_score"] == 0
    all_functions = {"functions": [{"name": name} for name in REQUIREMENTS]}
    all_missing = build_plan(all_functions, [], [])["to_source"]
    assert {r["need"]: r["qty"] for r in all_missing}["servo"] == 6
    assert len(manual_inventory(["rc_car", "rc_car"])) == 2
    air = {"functions": [{"name": "fly_ish"}]}
    old_photo = {"label": "computer_fan", "raw_name": "Computer Fan", "box_2d": [170, 430, 250, 550],
                 "blocked": False, "condition_note": None, "candidate_parts": {"fan": 1}}
    assert build_plan(air, [old_photo], [])["from_your_drawer"] == []
    for label in DETACHED_CHECK:
        photographed = inventory_item(label, KEYS[label], box=[0, 0, 250, 250], confidence=.99)
        assert photographed["blocked"] and photographed["candidate_parts"] == {}
        assert "manually" in photographed["condition_note"]
    assert inventory_item("computer_fan", "Fan on ATX power supply", box=[0, 0, 10, 10])["blocked"]
    old_psu = {"label": "loose_motor", "raw_name": "ATX PSU fan motor", "candidate_parts": {"dc_motor": 1}}
    assert screen_donor(old_psu)["candidate_parts"] == {} and screen_donor(old_psu)["blocked"]
    assert inventory_item("computer_fan", "Fan", condition="Corroded")["candidate_parts"] == {}
    assert build_plan(air, manual_inventory(["computer_fan"]), [])["from_your_drawer"][0]["qty"] == 1
