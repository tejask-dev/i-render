"""Local persistence for a single maker's workbench."""

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("RENDI_STATE_DIR", ROOT / ".var" / "workbench")).resolve()
FILES = STATE / "models"
PHOTOS = STATE / "photos"
SEED_PROJECTS = ROOT / "data" / "seed_projects.json"


def initialize():
    FILES.mkdir(parents=True, exist_ok=True)
    PHOTOS.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db, db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS objects (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS object_kind ON objects(kind);
        CREATE TABLE IF NOT EXISTS recognition (key TEXT PRIMARY KEY, result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, plan_id TEXT UNIQUE, payload TEXT NOT NULL);
        """)
        seeds = json.loads(SEED_PROJECTS.read_text(encoding="utf-8"))
        if not isinstance(seeds, dict):
            raise ValueError("seed_projects.json must map stable example IDs to project records")
        for key, record in seeds.items():
            fields = ("project_name", "note", "outcome", "keywords")
            if not key.strip() or not isinstance(record, dict) or not all(
                isinstance(record.get(k), str) and record[k].strip() for k in fields
            ):
                raise ValueError(f"Invalid example {key!r} in seed_projects.json; supply {', '.join(fields)}")
            payload = {k: record[k] for k in fields}
            payload["seeded"] = True
            db.execute(
                """INSERT INTO projects(id,plan_id,payload) VALUES (?,NULL,?)
                   ON CONFLICT(id) DO UPDATE SET payload=excluded.payload
                   WHERE projects.plan_id IS NULL AND json_extract(projects.payload, '$.seeded') = 1
                         AND projects.payload != excluded.payload""",
                (key, json.dumps(payload)),
            )
        db.execute(
            """DELETE FROM projects WHERE plan_id IS NULL AND json_extract(payload, '$.seeded') = 1
               AND id NOT IN (SELECT value FROM json_each(?))""",
            (json.dumps(list(seeds)),),
        )


def connect():
    return sqlite3.connect(STATE / "rendi.sqlite3", timeout=8)


def new_id(prefix):
    return f"{prefix}_{uuid4().hex}"


def put(kind, payload, obj_id=None):
    key = obj_id or new_id(kind[0])
    with closing(connect()) as db, db:
        db.execute(
            "INSERT INTO objects VALUES (?,?,?)",
            (key, kind, json.dumps(payload, allow_nan=False)),
        )
    return key


def get(kind, key=None, latest=False):
    with closing(connect()) as db:
        if latest:
            row = db.execute(
                "SELECT id,payload FROM objects WHERE kind=? ORDER BY rowid DESC LIMIT 1",
                (kind,),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT id,payload FROM objects WHERE kind=? AND id=?", (kind, key)
            ).fetchone()
    if row is None:
        raise KeyError(kind)
    return row[0], json.loads(row[1])


def save_project(plan_id, memory):
    key = new_id("p")
    with closing(connect()) as db, db:
        db.execute(
            "INSERT OR IGNORE INTO projects VALUES (?,?,?)",
            (key, plan_id, json.dumps(memory)),
        )
        return db.execute(
            "SELECT id FROM projects WHERE plan_id=?", (plan_id,)
        ).fetchone()[0]


def project_plan(project_id):
    with closing(connect()) as db:
        row = db.execute(
            "SELECT plan_id FROM projects WHERE id=? AND plan_id IS NOT NULL",
            (project_id,),
        ).fetchone()
    if not row:
        raise KeyError("project")
    return get("plan", row[0])[1]


def search(query):
    def terms(s):
        return {
            w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2
        } - {
            "the",
            "and",
            "for",
            "with",
            "from",
            "you",
            "can",
            "that",
            "build",
            "robot",
            "bot",
            "project",
            "make",
        }

    words = terms(query)
    if not words:
        return []
    with closing(connect()) as db:
        rows = db.execute(
            "SELECT id,plan_id,payload FROM projects ORDER BY rowid DESC"
        ).fetchall()
    hits = []
    for key, plan_id, raw in rows:
        record = json.loads(raw)
        overlap = words & terms(
            " ".join([record["project_name"], record["note"], record["keywords"]])
        )
        if overlap:
            result = {k: record[k] for k in ("project_name", "note", "outcome")}
            result["seeded"] = plan_id is None
            result["project_id"] = None if result["seeded"] else key
            hits.append((len(overlap), not result["seeded"], result))
    # Rank by relevance; a maker's actual saved project wins a tie with a seeded example.
    hits.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [hit[2] for hit in hits[:2]]


# Saved detections include classifications and safety decisions from these sources.
RECOGNITION_REVISION = hashlib.sha256(
    b"\x00".join(
        (ROOT / name).read_bytes()
        for name in (
            "backend/vision.py",
            "backend/cad.py",
            "backend/salvage.py",
            "data/salvage_map.json",
        )
    )
).hexdigest()


def recognition_key(kind, image, brief, provider, model, prompt):
    config = json.dumps(
        [RECOGNITION_REVISION, kind, provider, model, brief, prompt], sort_keys=True
    ).encode()
    return hashlib.sha256(config + b"\x00" + image).hexdigest()


def recognition(key):
    with closing(connect()) as db:
        row = db.execute(
            "SELECT result FROM recognition WHERE key=?", (key,)
        ).fetchone()
    try:
        return json.loads(row[0]) if row else None
    except (TypeError, ValueError):
        return None


def remember_recognition(key, result):
    with closing(connect()) as db, db:
        db.execute(
            "INSERT OR REPLACE INTO recognition VALUES (?,?)",
            (key, json.dumps(result, allow_nan=False)),
        )
