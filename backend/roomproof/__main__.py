"""Launch the RoomProof service: `.venv/bin/python -m backend.roomproof` from the repository root.

Environment only: ROOMPROOF_PAIR_TOKEN (required), GEMINI_API_KEY, GEMINI_MODEL, TINYFISH_API_KEY.
ROOMPROOF_HOST defaults to this Mac only; set it to the private-hotspot address for the iPhone to connect.
"""

import os
import sys

import uvicorn


def main():
    if not os.environ.get("ROOMPROOF_PAIR_TOKEN", "").strip():
        sys.exit("Set ROOMPROOF_PAIR_TOKEN before starting RoomProof. The service does not run unpaired.")
    host = os.environ.get("ROOMPROOF_HOST", "").strip() or "127.0.0.1"
    port = os.environ.get("ROOMPROOF_PORT", "").strip() or "8767"
    if not port.isdigit() or not 0 < int(port) < 65536:
        sys.exit("ROOMPROOF_PORT must be a port number.")
    from .app import create_app

    for name, key in (("Gemini", "GEMINI_API_KEY"), ("TinyFish", "TINYFISH_API_KEY")):
        print(f"{name} key: {'present' if os.environ.get(key, '').strip() else 'missing'}")
    if host in ("127.0.0.1", "localhost", "::1"):
        print("Listening on this Mac only. Set ROOMPROOF_HOST to the hotspot address for the iPhone.")
    uvicorn.run(create_app(), host=host, port=int(port), server_header=False)


if __name__ == "__main__":
    main()
