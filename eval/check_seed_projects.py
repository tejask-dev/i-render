"""Check seed edits on a restored notebook. Run with .venv/bin/python -m eval.check_seed_projects."""

import json
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backend import store


def check(work):
    data = json.loads(store.SEED_PROJECTS.read_text())
    seed_file = work / "seed_projects.json"
    seed_file.write_text(json.dumps(data))
    with zipfile.ZipFile(store.ROOT / "demo" / "Snack-Scout-backup.zip") as backup:
        backup.extractall(work)
    with patch.multiple(store, STATE=work, FILES=work / "models", PHOTOS=work / "photos", SEED_PROJECTS=seed_file):
        with closing(store.connect()) as db:
            real = db.execute("SELECT id,plan_id,payload FROM projects WHERE plan_id IS NOT NULL").fetchall()
            initial_ids = db.execute("SELECT id FROM projects WHERE plan_id IS NULL ORDER BY id").fetchall()
        assert real and initial_ids == [("Desk Rover",), ("Glow Owl",)]
        store.initialize()
        assert store.search("gearbox")[0]["note"] == data["Desk Rover"]["note"]
        data["Desk Rover"].update(project_name="Rover II", note="Revised gearbox entry.", seeded=False)
        del data["Glow Owl"]
        data[real[0][0]] = {**data["Desk Rover"], "project_name": "Collision"}
        seed_file.write_text(json.dumps(data))
        store.initialize()
        store.initialize()
        hits = store.search("gearbox")
        assert any(h["project_name"] == "Rover II" and h["note"] == "Revised gearbox entry."
                   and h["seeded"] and h["project_id"] is None for h in hits)
        assert not any(h["project_name"] == "Glow Owl" for h in store.search("owl"))
        assert any(h["project_id"] == real[0][0] and not h["seeded"] for h in store.search("Snack Scout"))
        with closing(store.connect()) as db:
            assert db.execute("SELECT id FROM projects WHERE plan_id IS NULL").fetchall() == [("Desk Rover",)]
            assert real == db.execute("SELECT id,plan_id,payload FROM projects WHERE plan_id IS NOT NULL").fetchall()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        check(Path(directory))
    print("PASS restored examples, edited wording, ID stability, two restarts, example provenance and user project isolation")
