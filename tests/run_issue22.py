#!/usr/bin/env python3
"""Red/green/mutant check for issue #22 against the real pinned U1 firmware."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# FIXPACK_IMAGE / FIXPACK_EVIDENCE let CI prove each firmware release in its own image and folder.
IMAGE = os.environ.get("FIXPACK_IMAGE", "u1-fixpack:local")
EVIDENCE = ROOT / os.environ.get("FIXPACK_EVIDENCE", "docs/evidence") / "issue-22"
FIXTURE = "/work/tests/fixtures/issue22.gcode"
PATCH = "/work/patches/0022-exclude-object-manual-move.patch"


def run_mode(mode):
    command = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", IMAGE,
               "--mode", mode, "--gcode", FIXTURE, "--patch", PATCH,
               "--evidence", "/work/" + str(EVIDENCE.relative_to(ROOT))]
    if mode == "baseline":
        command = [part for part in command if part not in ("--patch", PATCH)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    if completed.returncode:
        raise AssertionError("%s runner failed:\n%s\n%s" %
                             (mode, completed.stdout, completed.stderr))
    return (EVIDENCE / (mode + ".txt")).read_text()


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    baseline = run_mode("baseline")
    patched = run_mode("patched")
    mutant = run_mode("mutant")

    expected_error = "Move out of range on Y axis: 53.641 445.274 7.000 [41.000]"
    assert expected_error in baseline, baseline
    assert "toolhead: X:45.000000 Y:300.500000" in baseline, baseline
    assert "gcode: X:53.641000 Y:445.274000" in baseline, baseline
    assert "firmware_error_count=1" in baseline, baseline

    assert "firmware_error_count=0" in patched, patched
    assert "toolhead: X:45.000000 Y:300.500000" in patched, patched
    assert "gcode: X:45.000000 Y:300.500000" in patched, patched
    assert "M 45.000 300.500 7.000 41.00000" in patched, patched

    assert expected_error in mutant, mutant
    assert "firmware_error_count=1" in mutant, mutant
    print("issue #22 red/green/mutant: PASS")


if __name__ == "__main__":
    main()
