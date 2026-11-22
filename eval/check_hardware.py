"""Verify /api/hardware lists the parts the plan will source, in a private notebook."""
import asyncio
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import httpx

from backend import main, salvage, store

BRIEF = {"project_name": "Check Rover", "scale": "desktop", "approx_size_cm": 20, "vibe": ["curious"],
         "adventure_aura": "Roll across the desk.", "user_notes": ""}


async def model(client, must_do, template="wheelbot"):
    brief = (await client.post("/api/brief", json={**BRIEF, "must_do": must_do})).raise_for_status().json()["brief_id"]
    sketch = (await client.post("/api/sketch", data={"brief_id": brief, "template": template})).raise_for_status().json()
    return brief, sketch["spec_id"]


async def hardware(client, brief, spec):
    return (await client.get("/api/hardware", params={"spec_id": spec, "brief_id": brief})).raise_for_status().json()


async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as client:
        # A rover that drives and lights its eyes: exact counts, abilities and holding parts.
        brief, spec = await model(client, ["drive", "light_up"])
        hw = await hardware(client, brief, spec)
        needs = {row["need"]: row for row in hw["needs"]}
        assert {need: row["qty"] for need, row in needs.items()} == {
            "dc_motor": 2, "wheel": 2, "motor_driver": 1, "battery_pack": 1, "led": 2, "resistor_220": 2}, needs
        assert needs["dc_motor"]["functions"] == ["drive"] and needs["led"]["functions"] == ["light_up"]
        assert sorted(needs["wheel"]["parts"]) == ["Left wheel", "Right wheel"]
        assert sorted(needs["dc_motor"]["parts"]) == ["Left motor mount", "Right motor mount"]
        assert needs["motor_driver"]["parts"] == [] and needs["battery_pack"]["parts"] == []
        for need, row in needs.items():
            assert row["suggestion"] == salvage.SUGGESTIONS[need] and row["name"] == salvage._name(need)

        # Every ability the robot lacks is an idea; shared parts already on the list are not repeated.
        ideas = {idea["function"]: {n["need"]: n["qty"] for n in idea["needs"]} for idea in hw["extras"]}
        assert set(ideas) == set(salvage.REQUIREMENTS) - {"drive", "light_up"}, ideas
        assert ideas["walk"] == {"servo": 4, "microcontroller": 1}
        assert ideas["spin"] == {"dc_motor": 1}
        assert all("battery_pack" not in parts for parts in ideas.values()), "battery pack is already shared"

        # The parts list matches what an empty-drawer plan says to source, unit for unit.
        inventory = (await client.post("/api/junk", data={"items": "[]"})).raise_for_status().json()
        plan = (await client.post("/api/plan", json={"brief_id": brief, "spec_id": spec,
                                                      "inventory_id": inventory["inventory_id"]})).raise_for_status().json()
        sourced = Counter()
        for row in plan["plan"]["to_source"]:
            sourced[row["need"]] += row["qty"]
        assert dict(sourced) == {need: row["qty"] for need, row in needs.items()}, (dict(sourced), needs)

        # An ability with no part in the drawing still needs its components, and is no longer an idea.
        brief2, spec2 = await model(client, ["drive", "sense_distance"])
        hw2 = await hardware(client, brief2, spec2)
        needs2 = {row["need"]: row["qty"] for row in hw2["needs"]}
        assert needs2.get("ultrasonic_sensor") == 1 and needs2.get("microcontroller") == 1, needs2
        assert "sense_distance" not in {idea["function"] for idea in hw2["extras"]}

        # Errors: unknown model, a model from another interview, missing parameters.
        unknown = await client.get("/api/hardware", params={"spec_id": "s_missing", "brief_id": brief})
        assert unknown.status_code == 404, unknown.status_code
        crossed = await client.get("/api/hardware", params={"spec_id": spec, "brief_id": brief2})
        assert crossed.status_code == 409, crossed.status_code
        assert (await client.get("/api/hardware", params={"spec_id": spec})).status_code == 422


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        with patch.multiple(store, STATE=work, FILES=work / "models", PHOTOS=work / "photos"):
            store.initialize()
            asyncio.run(check())
    print("PASS hardware parts match plan sourcing unit for unit; abilities, holding parts, ideas, requested-only abilities and 404/409/422 errors")
