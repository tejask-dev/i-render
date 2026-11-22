#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
[[ -x .venv/bin/python ]] || { echo 'Install requirements.txt in .venv before starting RoomProof.'; exit 1; }
exec .venv/bin/python - <<'PY'
import json
import os
import runpy
import secrets
from pathlib import Path

config = Path('.var/roomproof-config.json')
config.parent.mkdir(exist_ok=True)
if not config.exists():
    values = {'ROOMPROOF_PAIR_TOKEN': secrets.token_urlsafe(32), 'GEMINI_API_KEY': '', 'TINYFISH_API_KEY': '', 'ROOMPROOF_HOST': '127.0.0.1'}
    with open(config, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
        json.dump(values, file, indent=2)
try:
    values = json.loads(config.read_text())
    for name in ('ROOMPROOF_PAIR_TOKEN', 'GEMINI_API_KEY', 'GEMINI_MODEL', 'TINYFISH_API_KEY', 'ROOMPROOF_HOST', 'ROOMPROOF_PORT'):
        value = values.get(name, '')
        if not isinstance(value, str):
            raise ValueError('Settings must be strings.')
        if value.strip():
            os.environ.setdefault(name, value.strip())
except (ValueError, OSError) as error:
    raise SystemExit('Could not read the private RoomProof settings. Check .var/roomproof-config.json.') from error
print('RoomProof settings: .var/roomproof-config.json (private; never commit or share).')
runpy.run_module('backend.roomproof', run_name='__main__')
PY
