#!/bin/zsh
set -eu
cd "${0:A:h}"
base='http://127.0.0.1:8765'
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
export RENDI_STATE_DIR="$PWD/.var/workbench"
mkdir -p .var
if ! [[ -x .venv/bin/uvicorn && -f frontend/dist/index.html ]]; then
    echo "Setting up the workbench…"
    uv venv --allow-existing --python 3.12 .venv
    uv pip install -r requirements.txt
    npm --prefix frontend ci
    npm --prefix frontend run build
fi
if command -v ollama >/dev/null && ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=1 ollama serve >.var/ollama.log 2>&1 &
fi
demo_notebook() {
    curl -fsS --max-time 2 "$base/api/config" 2>/dev/null | .venv/bin/python -c 'import json,sys; assert json.load(sys.stdin)["demo_store"] is True' 2>/dev/null
}
other_service() {
    echo "Port 8765 is in use by something other than this folder's demo notebook, such as a rehearsal or an older copy."
    echo "Nothing was stopped or changed. Close the Terminal window running that server, or press Control-C in it, then double-click Start Demo.command again."
    exit 1
}
if ! demo_notebook; then
    if nc -z 127.0.0.1 8765 >/dev/null 2>&1; then other_service; fi
    .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765 >.var/server.log 2>&1 &
    server_pid=$!
    for attempt in {1..80}; do
        kill -0 $server_pid 2>/dev/null || { tail -6 .var/server.log; exit 1; }
        demo_notebook && break
        sleep 0.4
    done
    if ! kill -0 $server_pid 2>/dev/null; then tail -6 .var/server.log; exit 1; fi
    if ! demo_notebook; then
        if curl -fsS --max-time 2 "$base/api/config" >/dev/null 2>&1; then other_service; fi
        echo 'See .var/server.log'
        exit 1
    fi
fi
open "$base"
echo "I, Render is open at $base. Keep this window open during judging."
if [[ -n "${server_pid:-}" ]]; then wait "$server_pid"; fi
