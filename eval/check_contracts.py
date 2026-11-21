"""Export the two Pydantic contracts and verify all four shared payloads."""

import argparse
import json
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from backend import cad, main, salvage, store

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "prompts" / "schemas"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def model_contracts(write):
    if write:
        SCHEMAS.mkdir(parents=True, exist_ok=True)
    for filename, title, model in (
        ("project_brief", "ProjectBrief", main.Brief),
        ("robot_spec", "RobotSpec", cad.RobotSpec),
    ):
        path = SCHEMAS / (filename + ".json")
        schema = {"$schema": DRAFT, **model.model_json_schema(), "title": title}
        if write:
            path.write_text(json.dumps(schema, indent=2) + "\n")
        elif json.loads(path.read_text()) != schema:
            raise ValueError(f"{path.name} differs from {model.__name__}. Regenerate with --write-models.")


def check():
    from jsonschema import Draft202012Validator

    validators = {}
    for name in ("project_brief", "robot_spec", "inventory", "build_plan"):
        schema = json.loads((SCHEMAS / (name + ".json")).read_text())
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(schema)

    with tempfile.TemporaryDirectory() as folder, patch.object(store, "STATE", Path(folder)):
        with ZipFile(ROOT / "demo" / "Snack-Scout-backup.zip") as archive:
            (store.STATE / "rendi.sqlite3").write_bytes(archive.read("rendi.sqlite3"))
        with closing(store.connect()) as db:
            projects = db.execute("SELECT id FROM projects WHERE plan_id IS NOT NULL").fetchall()
        assert projects, "The portable notebook must contain a saved project"
        for (project_id,) in projects:
            saved = main.project(project_id)
            validators["project_brief"].validate(saved["brief"])
            validators["robot_spec"].validate(saved["spec"])
            cad.RobotSpec.model_validate(saved["spec"])
            validators["inventory"].validate(saved["inventory"])
            validators["build_plan"].validate(saved["plan"])
            for labels in ([], ["rc_car", "flashlight", "microwave"]):
                items = salvage.manual_inventory(labels)
                validators["inventory"].validate({"items": items})
                validators["build_plan"].validate(salvage.build_plan(saved["spec"], items, []))
    source_plan = salvage.build_plan({"functions": [{"name": "drive"}]}, [], [])
    source_plan["allocations"][0]["item_index"] = 0
    assert not validators["build_plan"].is_valid(source_plan), "A missing unit cannot also have a donor"
    print("PASS: four shared contracts match the saved project, manual donors and empty drawer.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-models", action="store_true", help="Regenerate only the two Python model exports.")
    args = parser.parse_args()
    model_contracts(args.write_models)
    if not args.write_models:
        check()
