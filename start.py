from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"


def start_process(name: str, command: list[str], cwd: Path) -> subprocess.Popen[str]:
    print(f"[START] {name}: {' '.join(command)}")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=None,
        stderr=None,
    )


def frontend_command() -> list[str]:
    if os.name == "nt":
        return [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "npm run dev",
        ]

    return ["npm", "run", "dev"]


def main() -> int:
    backend = start_process(
        "backend",
        [sys.executable, "-m", "uvicorn", "main:app", "--reload"],
        ROOT,
    )

    frontend: subprocess.Popen[str] | None = None

    try:
        frontend = start_process("frontend", frontend_command(), FRONTEND_DIR)
    except FileNotFoundError as exc:
        print(f"[ERROR] Could not start frontend: {exc}")
        backend.terminate()
        backend.wait(timeout=10)
        return 1

    processes = [backend, frontend]
    stop_requested = False

    def shutdown(signum: int | None = None, frame: object | None = None) -> None:
        nonlocal stop_requested
        stop_requested = True
        print("\n[STOP] Shutting down services...")
        for process in processes:
            if process.poll() is None:
                process.terminate()

        deadline = time.time() + 10
        for process in processes:
            if process.poll() is None:
                remaining = max(0, deadline - time.time())
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    process.kill()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            backend_code = backend.poll()
            frontend_code = frontend.poll()

            if backend_code is not None:
                print(f"[EXIT] backend exited with code {backend_code}")
                return backend_code

            if frontend_code is not None:
                print(f"[EXIT] frontend exited with code {frontend_code}")
                return frontend_code

            time.sleep(0.5)
    finally:
        shutdown()

    return 0 if stop_requested else 1


if __name__ == "__main__":
    raise SystemExit(main())