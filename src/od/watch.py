"""Live preview: keep the OCP CAD Viewer showing the design you're working on.

    uv run od watch [project]

- When the viewer opens (or reopens), it sends the current design to it.
- When you save a design file, that project becomes current and is re-sent.
- When you save shared code in src/od/, the current design is re-sent.

"Current" is the project given on the command line, or else the design.py you
saved most recently. Each send runs `od view` in a fresh process, so edits to
any module are always picked up. Started automatically by the VS Code task
"Live preview" when the folder opens.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from od import project as prj

POLL = 0.5           # seconds between file checks
VIEWER_SETTLE = 1.5  # wait after the viewer appears before sending
OCP_CONFIG = Path.home() / ".ocpconfig"


def _viewer_up() -> bool:
    ports = [3939]
    try:
        services = json.loads(OCP_CONFIG.read_text()).get("services", {})
        ports = [int(p) for p in services] or ports
    except (OSError, ValueError):
        pass
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
    return False


def _snapshot(root: Path) -> dict[Path, float]:
    files = list((root / "projects").glob("*/*.py")) + list((root / "src" / "od").rglob("*.py"))
    out = {}
    for f in files:
        try:
            out[f] = f.stat().st_mtime
        except OSError:
            pass
    return out


def _latest_design(snap: dict[Path, float]) -> str | None:
    designs = [(t, f) for f, t in snap.items() if f.name == "design.py"]
    return max(designs)[1].parent.name if designs else None


def _send(project: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    r = subprocess.run(
        [sys.executable, "-m", "od.cli", "view", project],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"[{stamp}] showed {project}", flush=True)
    else:
        err = (r.stderr.strip().splitlines() or ["unknown error"])[-1]
        print(f"[{stamp}] {project}: build failed: {err}", flush=True)


def run(fixed: str | None = None) -> int:
    root = prj.repo_root()
    snap = _snapshot(root)
    current = fixed or _latest_design(snap)
    if fixed:
        prj.resolve(fixed)  # fail early on a bad name
    print(f"od watch: live preview of {current or '(no projects yet)'}; Ctrl+C to stop", flush=True)

    was_up = False
    try:
        while True:
            up = _viewer_up()
            if up and not was_up and current:
                time.sleep(VIEWER_SETTLE)
                _send(current)
            was_up = up

            new = _snapshot(root)
            changed = [f for f, t in new.items() if snap.get(f) != t]
            snap = new
            if changed:
                designs = [f for f in changed if f.parent.parent.name == "projects"]
                if designs and not fixed:
                    current = max(designs, key=lambda f: new[f]).parent.name
                if current and up:
                    _send(current)
            time.sleep(POLL)
    except KeyboardInterrupt:
        return 0
