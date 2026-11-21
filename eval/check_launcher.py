"""Exercise the macOS launcher in a disposable checkout on its own loopback port."""

import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERO = "p_d58d57f4214745ed951e4e9fef7d49b0"


def main():
    with tempfile.TemporaryDirectory(prefix="rendi-launch-") as folder:
        copy = Path(folder)
        for name in ("backend", "frontend", "data", "prompts"):
            shutil.copytree(ROOT / name, copy / name, ignore=shutil.ignore_patterns("node_modules", "dist", "__pycache__"))
        shutil.copy(ROOT / "requirements.txt", copy)
        (copy / "demo").mkdir()
        shutil.copy(ROOT / "demo/Snack-Scout-backup.zip", copy / "demo")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        # The project uses port 8765. Run this copy on a free port and suppress browser windows.
        launcher = (ROOT / "Start Demo.command").read_text().replace("8765", str(port)).replace('open "$base"', ":")
        command = copy / "Start Demo.command"
        command.write_text(launcher)
        command.chmod(0o755)
        base = f"http://127.0.0.1:{port}"
        with (copy / "check.log").open("w+") as log:
            host = subprocess.Popen([command], stdout=log, stderr=log, start_new_session=True)
            try:
                # Two double-clicks before setup completes must share one build and notebook.
                deadline = time.monotonic() + 30
                while not (copy / ".venv").exists():
                    if host.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("The first launcher did not start dependency setup.")
                    time.sleep(.05)
                subprocess.run([command], stdout=log, stderr=log, check=True, timeout=180)
                deadline = time.monotonic() + 20
                while True:
                    try:
                        with urllib.request.urlopen(f"{base}/api/projects/{HERO}", timeout=3) as response:
                            project = json.load(response)
                        break
                    except urllib.error.URLError:
                        if host.poll() is not None or time.monotonic() >= deadline:
                            raise
                        time.sleep(.2)
                assert project["brief"]["project_name"] == "Snack Scout"
                assert project["plan"]["drawer_score"] == 40
                state = copy / ".var/workbench"
                db = state / "rendi.sqlite3"
                identity = db.stat().st_ino
                sentinel = state / "leave-this-file"
                sentinel.write_text("mine")
                with (copy / "frontend/src.js").open("a") as source:
                    source.write('\nconsole.info("warm-build-probe");\n')
                subprocess.run([command], stdout=log, stderr=log, check=True, timeout=60)
                scripts = (copy / "frontend/dist/assets").glob("*.js")
                assert any("warm-build-probe" in script.read_text() for script in scripts)
                assert (copy / "frontend/dist/THIRD_PARTY_LICENSES.txt").is_file()
                assert db.stat().st_ino == identity and sentinel.read_text() == "mine"
                sibling = copy / "sibling"
                sibling.mkdir()
                sibling_command = sibling / command.name
                shutil.copy(command, sibling_command)
                wrong = subprocess.run([sibling_command], capture_output=True, text=True, timeout=15)
                assert wrong.returncode == 1 and "Port" in wrong.stdout
                assert not (sibling / ".var/workbench").exists()
            except BaseException:
                log.seek(0)
                print(log.read()[-8000:])
                raise
            finally:
                if host.poll() is None:
                    os.killpg(host.pid, signal.SIGTERM)
                    host.wait(timeout=12)
    print("Fresh install, concurrent launch, Snack Scout recovery, warm build, preservation and sibling guard passed.")


if __name__ == "__main__":
    main()
