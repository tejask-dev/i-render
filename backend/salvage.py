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
ADAPTATIONS = {
    "servo": ("stepper_motor", "Redesign the joint and control system for a matching stepper driver and a position reference."),
    "battery_pack": ("battery_holder", "Add suitable cells. Verify the assembled supply voltage and current rating for the whole load."),
    "led": ("rgb_led", "Use one identified colour channel with a current-limiting resistor sized for its voltage and current rating."),
    "speaker": ("piezo", "A passive piezo needs a suitable drive signal for tones. Spoken audio or recorded music still needs a suitable speaker."),
    "dc_motor": ("vibration_motor", "Redesign the effect and mounting for vibration. A load-bearing rotating axle still needs a motor rated for its torque."),
}
HAZARDOUS_NAME = re.compile(
    r"microwave|\bcrt\b|cathode.?ray|(?:disposable|single.use|flash) camera|"
    r"\blithium\b|li[ -]?(?:ion|po)\b|\b(?:swollen|corroded|leaking|burnt|burned|scorched|cracked|damaged|broken)\b",
    re.I,
)
POWER_SUPPLY_NAME = re.compile(r"\bpsu\b|\bpower[ _-]*suppl(?:y|ies)\b|\batx[ _-]*supply\b", re.I)
MAINS_NAME = re.compile(r"\bmains\b|\bac[ -]powered\b|\b(?:110|115|120|220|230|240)\s*(?:v|vac|volts?)\b", re.I)
INSTALLED_NAME = re.compile(r"\b(?:built[ -]into|(?:installed|embedded|mounted) (?:in|on)|soldered (?:to|onto)|"
                            r"(?:in|inside) (?:an? |the )?(?:sealed|closed|(?:old |intact )?(?:smartphone|phone))|"
                            r"from (?:an? |the )?smoke[ -](?:alarm|detector))\b", re.I)
LOOSE_ADAPTATION_LABELS = {"loose_stepper_motor", "loose_rgb_led", "loose_piezo", "loose_vibration_motor"}
BLOCK_NOTE = "Excluded from salvage. Leave this item intact."
SHARED = {"microcontroller", "battery_pack"}
# Mesh parts built to hold one component. Needs without a host stay function-level electronics.
HOST_PRIMITIVE = {"wheel": "wheel", "dc_motor": "motor_mount", "servo": "servo_mount"}
HOST_CATEGORY = {"speaker": "sound", "ultrasonic_sensor": "sensor"}
LIGHT_NEEDS = {"led", "resistor_220"}
NAMES = {"dc_motor": "DC motor", "led": "LED", "resistor_220": "current-limiting resistor",
         "audio_amp": "audio amplifier", "fly_ish": "airflow display"}
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
    if (label in LOOSE_ADAPTATION_LABELS or label in {"string_lights", "tv_remote"}) and MAINS_NAME.search(raw_name):
        return {**item, "blocked": True, "candidate_parts": {},
                "condition_note": "This description identifies mains power. Leave the device intact."}
    if label in LOOSE_ADAPTATION_LABELS and INSTALLED_NAME.search(raw_name):
        return {**item, "blocked": True, "candidate_parts": {},
                "condition_note": "Use only a separately identified loose component. Leave assembled devices intact."}
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


def _name(key, qty=None):
    text = NAMES.get(key, key.replace("_", " "))
    return text if qty is None else f"{qty} {text}{'s' if qty > 1 else ''}"


def _join(words):
    words = list(words)
    return ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else "".join(words)


def _holds(need, part):
    if need in LIGHT_NEEDS:
        if part.get("category") == "light":
            return True
        # Local sketch recognition represents eyes as decorative spheres, even when light_up names them.
        name = f"{part['id']} {part.get('label', '')}".lower()
        return (part.get("category") == "decor" and part.get("primitive") == "sphere"
                and "eye" in re.findall(r"[a-z]+", name))
    return (need in HOST_PRIMITIVE and part.get("primitive") == HOST_PRIMITIVE[need]) or (
        need in HOST_CATEGORY and part.get("category") == HOST_CATEGORY[need])


def required_units(spec: dict) -> list[dict]:
    """One slot per required unit, joined to the named mesh part that holds it when the model has one."""
    listed = {}
    for function in spec["functions"]:
        listed.setdefault(function["name"], []).extend(function.get("parts") or [])
    parts = {part["id"]: part for part in spec.get("parts") or []}
    slots, claimed = [], set()

    def claim(slot, part_id):
        claimed.add((slot["need"], part_id))
        slot.update(part_id=part_id, part_label=parts[part_id].get("label") or part_id)

    for name, ids in listed.items():
        lights = sum(_holds("led", parts[i]) for i in set(ids) if i in parts) if name == "light_up" else 0
        for need, qty in REQUIREMENTS[name].items():
            if name == "light_up" and need in LIGHT_NEEDS:
                qty = max(qty, lights)
            if name == "drive" and need == "wheel":
                qty = max(qty, sum(part.get("primitive") == "wheel" for part in parts.values()))
            if need in SHARED:
                # Distinct moving functions need distinct actuators. A rated supply/controller may be shared.
                shared = [slot for slot in slots if slot["need"] == need][:qty]
                for slot in shared:
                    slot["functions"].append(name)
                qty -= len(shared)
            for _ in range(qty):
                slot = {"unit": None, "need": need, "functions": [name], "part_id": None, "part_label": None,
                        "status": "source", "item_index": None, "item_id": None, "raw_name": None,
                        "source": None, "box_2d": None}
                slots.append(slot)
                host = next((i for i in ids if i in parts and (need, i) not in claimed
                             and _holds(need, parts[i])), None)
                if host:
                    claim(slot, host)
    # A wheel or mount the function forgot to list still holds exactly one such component.
    for slot in slots:
        if slot["part_id"] is None and slot["need"] in HOST_PRIMITIVE and any(listed[f] for f in slot["functions"]):
            host = next((i for i, part in parts.items() if (slot["need"], i) not in claimed
                         and part.get("primitive") == HOST_PRIMITIVE[slot["need"]]), None)
            if host:
                claim(slot, host)
    numbered = Counter()
    for slot in slots:
        numbered[slot["need"]] += 1
        slot["unit"] = f"{slot['need']}-{numbered[slot['need']]}"
    return slots


def _item_id(item, index):
    """A stored id when the inventory has one. Older inventories are stable lists, so the index stands in."""
    for key in ("item_id", "id"):
        value = item.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and value != "":
            return str(value), True
    return f"item-{index}", False


def _unit_text(units):
    """Quantities with the mesh parts they go to, or the function when the model shows no mount."""
    groups = {}
    for unit in units:
        groups.setdefault(unit["need"], []).append(unit)
    phrases = []
    for need, group in groups.items():
        places = [unit["part_label"] for unit in group if unit["part_id"]]
        places += dict.fromkeys(_name(f) + " function" for unit in group if not unit["part_id"]
                                for f in unit["functions"])
        phrases.append(f"{_name(need, len(group))} ({', '.join(places)})")
    return _join(phrases)


def assembly_steps(spec: dict, slots: list[dict], drawer: list[dict], held_out: list[dict]) -> list[str]:
    """Five to eight steps that name the actual drawer objects, mesh parts and shortfall."""
    if not slots:
        return ["Check the dimensions of the model against your sketch.",
                "Choose the action you want the robot to perform.",
                "Confirm that action in the interview and mark the relevant part on the drawing.",
                "Rescan the drawing and review the part names.",
                "Match the drawer again once the workbench lists the intended action."]
    hosts = list(dict.fromkeys(slot["part_label"] for slot in slots if slot["part_id"]))
    shown = hosts[:4] + ([f"{len(hosts) - 4} more"] if len(hosts) > 4 else [])
    steps = [f"Check the modelled {_join(shown)} against the real parts before printing." if hosts
             else "Check the model dimensions against the real parts before printing."]

    later = []
    missing = [slot for slot in slots if slot["status"] == "source"]
    if missing:
        later.append(f"Source what the drawer lacks: {_unit_text(missing)}. "
                     "Compare datasheets and connector sizes before buying.")
    blocked = [f"drawer item {held['item_index'] + 1} ({held['raw_name']})" for held in held_out if held["blocked"]]
    if blocked:
        named = blocked[:3] + ([f"{len(blocked) - 3} more excluded items"] if len(blocked) > 3 else [])
        later.append(f"Leave {_join(named)} intact and out of the build. "
                     f"Nothing from {'it' if len(blocked) == 1 else 'them'} is counted.")
    if any("fly_ish" in slot["functions"] for slot in slots):
        later.append("Plan a stationary airflow display with guarded fans. Keep the model secured to the table.")

    donors = {}
    for slot in slots:
        if slot["status"] == "drawer":
            donors.setdefault(slot["item_index"], []).append(slot)
    tools = {row["item_index"]: row["tools"] for row in drawer}
    lines = [(f"drawer item {index + 1} ({units[0]['raw_name']}) for {_unit_text(units)}", tools[index])
             for index, units in sorted(donors.items())]
    room = 4 - len(later)
    alone = lines if len(lines) <= room else lines[:room - 1]
    for line, needed in alone:
        steps.append(f"Inspect {line}.{' Tools: ' + ', '.join(needed) + '.' if needed else ''} "
                     "Move anything missing or unsuitable to the sourcing list.")
    if lines[len(alone):]:
        rest = "; ".join(line for line, _ in lines[len(alone):])
        steps.append(f"Inspect the remaining candidates the same way: {rest}." if alone else
                     f"Inspect each candidate: {rest}. Move anything missing or unsuitable to the sourcing list.")
    steps += later

    loose = Counter(slot["need"] for slot in slots if not slot["part_id"])
    if loose and len(steps) < 5:
        root = next((part.get("label") or part["id"] for part in spec.get("parts") or []
                     if part.get("attach_to") is None), None)
        steps.append(f"The model shows no mount for {_join(_name(*pair) for pair in loose.items())}. "
                     f"Decide where each sits"
                     f"{' in ' + root if root else ''} and route the wiring clear of moving parts.")
    steps.append("Dry-fit the unpowered components into those parts and check clearances through the intended "
                 "range of motion." if hosts else
                 "Dry-fit the unpowered components and check clearances through the intended range of motion.")
    steps.append("Have a mentor review power, signal levels, and mounting before anything is powered.")
    names = list(dict.fromkeys(f for slot in slots for f in slot["functions"]))
    waiting = list(dict.fromkeys(f for slot in missing for f in slot["functions"]))
    ready = [name for name in names if name not in waiting]
    steps.append("After the review, test one function at a time."
                 + (f" Drawer candidates cover every unit for: {_join(map(_name, ready))}." if ready else "")
                 + (f" Still waiting on sourced parts: {_join(map(_name, waiting))}." if waiting else ""))
    return steps


def _donor_components(items):
    """Return candidate quantities capped by catalog yields and objects held out of the build."""
    components, held_out, seen = [], [], {}
    screened = [screen_donor(item) for item in items]
    excluded_ids = {_item_id(item, i)[0] for i, item in enumerate(screened)
                    if (item.get("blocked") or item.get("user_excluded")) and _item_id(item, i)[1]}
    for item_index, item in enumerate(screened):
        label = item.get("label")
        item_id, explicit = _item_id(item, item_index)
        raw_name = item.get("raw_name") or KEYS.get(label, "unidentified item")
        held = {"item_index": item_index, "item_id": item_id, "raw_name": raw_name, "label": label,
                "blocked": bool(item.get("blocked"))}
        if explicit and item_id in seen:
            held_out.append({**held, "reason": f"Same object as drawer item {seen[item_id] + 1}. Counted once."})
            continue
        if explicit:
            seen[item_id] = item_index
        if not item.get("blocked") and (item.get("user_excluded") or (explicit and item_id in excluded_ids)):
            held_out.append({**held, "reason": "This object was excluded from the inventory."})
            continue
        if item.get("duplicate_of") is not None:
            reason = item.get("condition_note") or "Repeated inventory detection. Counted once."
            held_out.append({**held, "reason": reason})
            continue
        if label not in SOURCES or item.get("blocked") or item.get("condition_note"):
            reason = item.get("condition_note") or (BLOCK_NOTE if item.get("blocked")
                                                    else "Unidentified item. No components counted.")
            held_out.append({**held, "reason": reason})
            continue
        source = SOURCES[label]
        donor = {"item_index": item_index, "item_id": item_id, "raw_name": raw_name,
                 "source": source["display"], "box_2d": item.get("box_2d")}
        # Legacy inventories omitted this field. An explicit count can only lower the map's yield.
        stored = item.get("candidate_parts", source["parts"])
        if isinstance(stored, dict):
            for part, limit in source["parts"].items():
                count = stored.get(part)
                if type(count) is int and count > 0:
                    components.append((donor, part, min(count, limit), source))
    return components, held_out


def _with_alternatives(shopping, slots, components):
    used = Counter((u["item_index"], u["need"]) for u in slots if u["status"] == "drawer")
    eligible_missing = Counter(u["need"] for u in slots if u["status"] == "source"
                               and (u["need"] != "dc_motor" or u["functions"] == ["spin"]))
    rows = []
    for row in shopping:
        need = row["need"]
        options = []
        if need in ADAPTATIONS:
            substitute, note = ADAPTATIONS[need]
            remaining = min(row["qty"], eligible_missing[need])
            for donor, part, available, _ in components:
                if part == substitute:
                    qty = min(remaining, available - used[donor["item_index"], part])
                    if qty > 0:
                        options.append({**donor, "component": part, "qty": qty, "note": note})
                        remaining -= qty
                if remaining == 0:
                    break
        rows.append({**row, "alternatives": options})
    return rows


def build_plan(spec: dict, items: list[dict], memory: list[dict]) -> dict:
    slots = required_units(spec)
    components, held_out = _donor_components(items)
    drawer = []
    for donor, part, available, source in components:
        free = sorted((slot for slot in slots if slot["need"] == part and slot["status"] == "source"),
                      key=lambda slot: slot["part_id"] is None)[:available]
        if not free:
            continue
        for slot in free:
            slot.update(status="drawer", **donor)
        drawer.append({**donor, "need": part, "qty": len(free), "how": source["how"], "tools": source["tools"],
                       "part_ids": [slot["part_id"] for slot in free if slot["part_id"]],
                       "functions": list(dict.fromkeys(f for slot in free for f in slot["functions"]))})
    shopping = []
    for need in dict.fromkeys(slot["need"] for slot in slots):
        missing = [slot for slot in slots if slot["need"] == need and slot["status"] == "source"]
        if missing:
            shopping.append({"need": need, "qty": len(missing), "suggestion": SUGGESTIONS[need],
                             "part_ids": [slot["part_id"] for slot in missing if slot["part_id"]],
                             "functions": list(dict.fromkeys(f for slot in missing for f in slot["functions"]))})
    score = round(100 * sum(slot["status"] == "drawer" for slot in slots) / len(slots)) if slots else 0
    steps = assembly_steps(spec, slots, drawer, held_out)
    notes = [f"{hit['project_name']} ({'example, ' if hit.get('seeded') else ''}{hit.get('outcome', 'planned')}): {hit['note']}"
             for hit in memory[:2] if hit.get("project_name") and hit.get("note")]
    return {"from_your_drawer": drawer, "to_source": _with_alternatives(shopping, slots, components),
            "drawer_score": score, "steps": steps, "memory_notes": notes, "allocations": slots, "held_out": held_out}


def with_allocations(saved: dict, spec: dict, items: list[dict]) -> dict:
    """Refresh suggestions against stored allocations, or rebuild missing/outdated light assignments."""
    def light_assignments(slots):
        return Counter((u["need"], u.get("part_id")) for u in slots if u.get("need") in LIGHT_NEEDS)

    previous = saved.get("allocations")
    if isinstance(previous, list) and light_assignments(previous) == light_assignments(required_units(spec)):
        shopping = saved.get("to_source", [])
        components, _ = _donor_components(items)
        held = {row["item_index"] for row in saved.get("held_out", [])}
        available = [offer for offer in components if offer[0]["item_index"] not in held]
        refreshed = _with_alternatives(shopping, previous, available)
        return saved if refreshed == shopping else {**saved, "to_source": refreshed}
    return {**build_plan(spec, items, []), "memory_notes": saved.get("memory_notes", [])}


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
    rover = {"parts": [{"id": "mount", "label": "Motor mount", "primitive": "motor_mount", "category": "motion"},
                       {"id": "eye", "label": "Eye", "primitive": "sphere", "category": "light"}],
             "functions": [{"name": "spin", "parts": ["mount"]}, {"name": "light_up", "parts": ["eye"]}]}
    joined = build_plan(rover, one, [])
    assert [(u["part_id"], u["item_index"]) for u in joined["allocations"] if u["status"] == "drawer"] == [
        ("mount", 0), ("eye", 1)]
    assert [h["item_index"] for h in joined["held_out"] if h["blocked"]] == [2, 4]
    assert 5 <= len(joined["steps"]) <= 8 and "Microwave" in " ".join(joined["steps"])
    assert with_allocations({"memory_notes": ["kept"]}, rover, one)["memory_notes"] == ["kept"]


    lamps = [{"id": f"eye_{n}", "primitive": "sphere", "category": "decor"} for n in (5, 6, 7)]
    light_ids = [p["id"] for p in lamps]
    part_list = lamps + [{"id": "eye_frame", "primitive": "rounded_box", "category": "structure"},
                         {"id": "button", "primitive": "sphere", "category": "decor"},
                         {"id": "unlisted", "primitive": "sphere", "category": "light"}]
    lights = {"parts": part_list, "functions": [{"name": "light_up", "parts": [
        *light_ids, "eye_5", "eye_frame", "button", "missing"]}]}
    donors = [{**one[1], "item_id": "excluded", "user_excluded": True}, {**one[1], "item_id": "kept"}]
    stale = build_plan({"parts": [], "functions": [{"name": "light_up"}]}, donors, [])
    stale["memory_notes"] = ["original"]
    repaired = with_allocations(stale, lights, donors)
    for component in LIGHT_NEEDS:
        assert [u["part_id"] for u in repaired["allocations"] if u["need"] == component] == light_ids
    assert repaired["from_your_drawer"][0]["item_id"] == "kept" and repaired["held_out"] == stale["held_out"]
    assert repaired["memory_notes"] == ["original"] and with_allocations(repaired, lights, donors) is repaired
