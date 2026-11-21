"""Verify a browser revisiting any workbench entry receives the current build."""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx

from backend import main


async def check(dist):
    shell = dist / "index.html"
    shell.write_text('<script src="/assets/index-old.js"></script>')
    assets = dist / "assets"
    assets.mkdir()
    bundle = assets / "index-current.js"
    bundle.write_text("export {};")
    routes = ("/", "/index.html", "/project/saved-project")
    with patch.object(main.workbench, "all_directories", [dist]):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver") as client:
            old = (await client.get("/")).raise_for_status().headers["etag"]
            shell.write_text('<script src="/assets/index-current.js"></script>')
            for route in routes:
                current = await client.get(route, headers={"If-None-Match": old})
                assert current.status_code == 200 and current.content == shell.read_bytes()
                assert current.headers["cache-control"] == "no-cache"
                etag = current.headers["etag"]
                head = await client.head(route)
                assert head.status_code == 200 and not head.content and head.headers["etag"] == etag
                assert head.headers["cache-control"] == "no-cache"
                for method in ("GET", "HEAD"):
                    same = await client.request(method, route, headers={"If-None-Match": etag})
                    assert same.status_code == 304 and not same.content and same.headers["etag"] == etag
                    assert same.headers["cache-control"] == "no-cache"
            asset = (await client.get("/assets/index-current.js")).raise_for_status()
            assert asset.content == bundle.read_bytes() and "cache-control" not in asset.headers


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        asyncio.run(check(Path(directory)))
    print("PASS refreshed workbench HTML, HEAD and conditional 304 on all three entry routes; static assets unchanged")
