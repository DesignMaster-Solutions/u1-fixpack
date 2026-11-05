#!/usr/bin/env python3
"""Forum topic 44046 on the real pinned U1 firmware: the stock start line at Y1 vs head offsets.

A head whose Y offset is below -1 mm is sent under position_min (Y 0) by "G0 X85 Y1", with the
reporter's exact numbers (84.900 -0.090); the same head passes at Y5, and the high head passes at Y1.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("FIXPACK_IMAGE", "u1-fixpack:local")
EVIDENCE = ROOT / os.environ.get("FIXPACK_EVIDENCE", "docs/evidence") / "start-line-44046"


def run_case(name):
    out = EVIDENCE / name
    command = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", IMAGE, "--mode", "baseline",
               "--gcode", f"/work/tests/fixtures/start-line-{name}.gcode",
               "--evidence", "/work/" + str(out.relative_to(ROOT))]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    if completed.returncode:
        raise AssertionError("%s runner failed:\n%s\n%s" % (name, completed.stdout, completed.stderr))
    return (out / "baseline.txt").read_text()


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    low_y1, low_y5, high_y1 = run_case("low-y1"), run_case("low-y5"), run_case("high-y1")

    # the reporter's klippy.log: "Move out of range on Y axis: 84.9 -0.09 2.0"
    assert "Move out of range on Y axis: 84.900 -0.090 2.000" in low_y1, low_y1
    assert "firmware_error_count=1" in low_y1, low_y1
    assert "firmware_error_count=0" in low_y5, low_y5
    assert "toolhead: X:184.900000 Y:3.910000" in low_y5, low_y5
    assert "firmware_error_count=0" in high_y1, high_y1
    assert "toolhead: X:185.100000 Y:2.090000" in high_y1, high_y1
    print("topic 44046 start line: low head refused at Y1, passes at Y5, high head passes at Y1: PASS")


if __name__ == "__main__":
    main()
