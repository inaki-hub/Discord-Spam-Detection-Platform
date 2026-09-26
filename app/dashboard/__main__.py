from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.config import PROJECT_ROOT


def main() -> None:
    script = Path(__file__).resolve().parent / "streamlit_app.py"
    env = os.environ.copy()
    root = str(PROJECT_ROOT.resolve())
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script),
        "--server.address=127.0.0.1",
        "--server.headless=true",
    ]
    try:
        code = subprocess.call(cmd, cwd=root, env=env)
    except KeyboardInterrupt:
        print("Dashboard detenido (Ctrl+C).")
        raise SystemExit(0) from None
    raise SystemExit(code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Dashboard detenido (Ctrl+C).")
        raise SystemExit(0) from None
