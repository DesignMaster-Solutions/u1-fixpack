#!/usr/bin/env python3
"""Stock-firmware workaround for u1-klipper#18: an M400 before every part-fan M106/M107.

Until the #18 patch is in your firmware, the U1 switches the part fan when it reads the
command, seconds before the move the slicer put it in front of. M400 makes the firmware
finish the queued moves first, so the fan switches where the slicer meant it to. The cost
is a short stop of the toolhead at each part-fan change (tests/run_fan_m400.py measures both).

Snapmaker Orca / OrcaSlicer: Others > Post-processing scripts, add
    python3 /path/to/fan_m400.py
The slicer passes the G-code path and the file is edited in place. Fans with a P index
(auxiliary, exhaust) are not touched; running it twice adds nothing.
"""
import re
import sys

PART_FAN = re.compile(r"^\s*M10[67](?![0-9])(?![^;]*\bP\d)", re.I)
WAIT = "M400 ; fan_m400: finish the moves before the part fan changes (u1-klipper#18)\n"


def add_m400(lines):
    out = []
    for line in lines:
        if PART_FAN.match(line) and not (out and out[-1].lstrip().upper().startswith("M400")):
            out.append(WAIT)
        out.append(line)
    return out


def main(path):
    with open(path) as f:
        lines = f.readlines()
    new = add_m400(lines)
    with open(path, "w") as f:
        f.writelines(new)
    print("fan_m400: %d M400 added to %s" % (len(new) - len(lines), path))


if __name__ == "__main__":
    main(sys.argv[1])
