#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
export RENDI_STATE_DIR="$PWD/.var/workbench"
base='http://127.0.0.1:8765'
notebook_id=$(printf %s "${RENDI_STATE_DIR:A}" | shasum -a 256 | cut -c1-16)

demo_notebook() {
    local config
    config=$(curl --noproxy '*' -fsS --max-time 3 "$base/api/config" 2>/dev/null) || return 1
    [[ "$(print -r -- "$config" | plutil -extract notebook_id raw -o - - 2>/dev/null)" == "$notebook_id" &&
       "$(print -r -- "$config" | plutil -extract demo_store raw -o - - 2>/dev/null)" == true ]]
}
other_service() {
    echo "Port 8765 is occupied by another service or an older version. Close its server window and double-click Start Demo.command again."
    exit 1
}
mkdir -p .var
touch .var/launcher.lock
zmodload zsh/system
zsystem flock -t 180 -f launch_fd .var/launcher.lock || { echo "Another launch is still setting up this checkout."; exit 1; }
if nc -z 127.0.0.1 8765 >/dev/null 2>&1; then demo_notebook || other_service; fi

py_inputs=$(shasum -a 256 requirements.txt)
if [[ ! -x .venv/bin/uvicorn || ! -f .var/python-inputs || "$(<.var/python-inputs)" != "$py_inputs" ]]; then
    command -v uv >/dev/null || { echo "Install uv (brew install uv), then double-click this file again."; exit 1; }
    [[ -x .venv/bin/python ]] || uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python -r requirements.txt
    print -r -- "$py_inputs" > .var/python-inputs
fi
npm_inputs=$(shasum -a 256 frontend/package.json frontend/package-lock.json)
if [[ ! -x frontend/node_modules/.bin/vite || ! -f .var/npm-inputs || "$(<.var/npm-inputs)" != "$npm_inputs" ]]; then
    command -v npm >/dev/null || { echo "Install Node.js and npm (brew install node), then double-click this file again."; exit 1; }
    npm --prefix frontend ci --include=dev --no-audit --no-fund
    print -r -- "$npm_inputs" > .var/npm-inputs
fi
ui_inputs=$(find frontend \( -name node_modules -o -name dist \) -prune -o -type f ! -name .DS_Store -exec shasum -a 256 {} + | LC_ALL=C sort | shasum -a 256)
if [[ ! -s frontend/dist/index.html || ! -f .var/ui-inputs || "$(<.var/ui-inputs)" != "$ui_inputs" ]]; then
    stage=$(mktemp -d "$PWD/.var/browser-build.XXXXXX")
    trap 'rm -rf -- "$stage"' EXIT
    npm --prefix frontend run build -- --outDir "$stage"
    mkdir -p frontend/dist
    # Publish the index last and keep old hashed assets for already-open tabs.
    rsync -a --exclude=/index.html "$stage/" frontend/dist/
    mv "$stage/index.html" frontend/dist/index.html
    rm -rf -- "$stage"
    trap - EXIT
    print -r -- "$ui_inputs" > .var/ui-inputs
fi

if [[ ! -e "$RENDI_STATE_DIR" && ! -L "$RENDI_STATE_DIR" ]]; then
    .venv/bin/python - <<'PY'
import ctypes
import errno
import os
import tempfile
import zipfile
from pathlib import Path

state = Path(os.environ["RENDI_STATE_DIR"])
with tempfile.TemporaryDirectory(dir=state.parent) as folder:
    seed = Path(folder) / "seed"
    with zipfile.ZipFile("demo/Snack-Scout-backup.zip") as archive:
        archive.extractall(seed)
    if not (seed / "rendi.sqlite3").is_file() or not (seed / "models").is_dir() or not (seed / "photos").is_dir():
        raise SystemExit("The reference notebook is incomplete. Restore demo/Snack-Scout-backup.zip from the repository.")
    # macOS RENAME_EXCL publishes a complete directory only if the destination is still absent.
    rename = ctypes.CDLL(None, use_errno=True).renamex_np
    if rename(os.fsencode(seed), os.fsencode(state), 4):
        error = ctypes.get_errno()
        if error != errno.EEXIST:
            raise OSError(error, os.strerror(error), str(state))
PY
fi
if command -v ollama >/dev/null && ! curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 ollama serve >.var/ollama.log 2>&1 &
fi
if ! demo_notebook; then
    if nc -z 127.0.0.1 8765 >/dev/null 2>&1; then other_service; fi
    .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765 >.var/server.log 2>&1 &
    server_pid=$!
    for attempt in {1..80}; do
        kill -0 "$server_pid" 2>/dev/null || { tail -6 .var/server.log; exit 1; }
        demo_notebook && break
        sleep 0.4
    done
    if ! demo_notebook; then
        kill "$server_pid" 2>/dev/null || true
        echo 'The workbench did not start. See .var/server.log.'
        exit 1
    fi
fi
zsystem flock -u "$launch_fd"
open "$base"
echo "I, Render is open at $base. Keep this window open during judging."
if [[ -n "${server_pid:-}" ]]; then wait "$server_pid"; fi
