"""Validate the current example catalog and its migration on a private copy of the demo notebook."""

import json
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backend import store


def projects():
    with closing(store.connect()) as db:
        rows = db.execute("SELECT id,plan_id,payload FROM projects ORDER BY id").fetchall()
    examples = {key: json.loads(raw) for key, plan_id, raw in rows if plan_id is None}
    real = {key: (plan_id, raw) for key, plan_id, raw in rows if plan_id is not None}
    return examples, real


def check(work):
    seed_file = work / "seed_projects.json"
    seed_file.write_bytes(store.SEED_PROJECTS.read_bytes())
    with zipfile.ZipFile(store.ROOT / "demo" / "Snack-Scout-backup.zip") as backup:
        backup.extractall(work)
    with patch.multiple(store, STATE=work, FILES=work / "models", PHOTOS=work / "photos", SEED_PROJECTS=seed_file):
        _, original_projects = projects()
        assert original_projects, "The portable demo must include a saved project."
        store.initialize()
        actual = json.loads(seed_file.read_text(encoding="utf-8"))
        expected = {}
        for key, record in actual.items():
            if key not in original_projects:
                expected[key] = {field: record[field] for field in ("project_name", "note", "outcome", "keywords")}
                expected[key]["seeded"] = True
        assert projects() == (expected, original_projects)

        # Use an independent catalog, so editable titles, search phrases and IDs can all change.
        fixture = {"project_name": "Fixture lamp", "note": "Original description.",
                   "outcome": "worked", "keywords": "catalogfixture"}
        first_id = "example-742"
        seed_file.write_text(json.dumps({first_id: fixture, "retired-example": fixture}))
        store.initialize()
        revised = {**fixture, "project_name": "Renamed fixture", "note": "New description."}
        collision = next(iter(original_projects))
        seed_file.write_text(json.dumps({first_id: {**revised, "seeded": False}, collision: fixture}))
        store.initialize()
        store.initialize()
        expected = {first_id: {**revised, "seeded": True}}
        assert projects() == (expected, original_projects)
        assert any(hit["project_name"] == revised["project_name"] and hit["note"] == revised["note"]
                   and hit["seeded"] and hit["project_id"] is None for hit in store.search("catalogfixture"))

        # Even a malformed record after a valid edit must leave the previous catalog intact.
        for invalid in ("", json.dumps({first_id: fixture, "invalid": {"project_name": ""}})):
            seed_file.write_text(invalid)
            try:
                store.initialize()
            except ValueError:
                pass
            else:
                raise AssertionError("Expected an invalid seed catalog to be rejected.")
            assert projects() == (expected, original_projects)

        seed_file.write_text("{}")
        store.initialize()
        assert projects() == ({}, original_projects)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        check(Path(directory))
    print("PASS current seed catalog, editable titles and IDs, empty catalog, invalid-edit rollback and saved-project isolation")
