"""The gate: run after every change. Usage: python scripts/gate.py [--live]

Steps: pytest -q, python -m evals.report, and with --live python -m app.verify.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, args: list[str]) -> bool:
    start = time.monotonic()
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    secs = time.monotonic() - start
    out = (proc.stdout + proc.stderr).rstrip().splitlines()
    ok = proc.returncode == 0
    last = out[-1] if out else "(no output)"
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {secs:.1f}s  {last}")
    if not ok:
        for line in out[-30:]:
            print(f"    {line}")
    return ok


def main() -> int:
    live = "--live" in sys.argv[1:]
    steps = [
        ("pytest", ["-m", "pytest", "-q"]),
        ("evals", ["-m", "evals.report"]),
    ]
    if live:
        steps.append(("verify (live)", ["-m", "app.verify"]))

    results = [run_step(name, args) for name, args in steps]
    if all(results):
        print("VERDICT: PASS")
        return 0
    print("VERDICT: FAIL. Fix the cause, not the test. Three attempts, then stop and report.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
