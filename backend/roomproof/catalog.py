"""The four catalog products the service may look up. Nothing else is ever fetched."""

import json
from pathlib import Path
from urllib.parse import urlsplit

CATALOG_PATH = Path(__file__).resolve().parents[2] / "contracts" / "roomproof" / "catalog.json"

# Pinned in code so an edited fixture cannot point a browser run at another page.
ALLOWED_URLS = {
    "ikea-desk": "https://www.ikea.com/ca/en/p/lagkapten-alex-desk-white-s99521435/",
    "ikea-chair": "https://www.ikea.com/ca/en/p/renberget-swivel-chair-bomstad-black-40611094/",
    "jysk-desk": "https://www.jysk.ca/vandborg-writing-desk.html",
    "jysk-chair": "https://www.jysk.ca/gusum-office-chair-black.html",
}
ALLOWED_HOSTS = {"www.ikea.com", "www.jysk.ca"}
IDENTITY_FIELDS = ("id", "retailer", "sku", "name", "category", "closedStorage", "url")


def load_catalog(path=CATALOG_PATH):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or [row.get("id") for row in rows] != list(ALLOWED_URLS):
        raise RuntimeError("RoomProof catalog must list exactly the four contract products.")
    entries = []
    for row in rows:
        entry = {field: row[field] for field in IDENTITY_FIELDS}
        parts = urlsplit(entry["url"])
        if (entry["url"] != ALLOWED_URLS[entry["id"]] or parts.scheme != "https"
                or parts.hostname not in ALLOWED_HOSTS or entry["category"] not in ("desk", "chair")
                or type(entry["closedStorage"]) is not bool
                or not all(isinstance(entry[f], str) and entry[f] for f in ("retailer", "sku", "name"))):
            raise RuntimeError("RoomProof catalog does not match the pinned product pages.")
        entries.append(entry)
    return tuple(entries)


CATALOG = load_catalog()
