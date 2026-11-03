"""Shared helpers for the fix-pack tests. They run inside the u1-fixpack image (see tests/run.sh).

FIXPACK_PATCHES picks the firmware under test:
  unset or "all"  -> 93cb12f with every patches/*.patch applied (the fixed firmware)
  "none"          -> 93cb12f as shipped
  "a.patch,b.patch" -> 93cb12f with exactly those files applied (mutant checks)
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
import run as harness  # noqa: E402

OUT = os.environ.get("FIXPACK_OUT", "/tmp/fixpack")


def patches():
    sel = os.environ.get("FIXPACK_PATCHES", "all")
    if sel == "all":
        return sorted(glob.glob(os.path.join(ROOT, "patches", "*.patch")))
    if sel == "none":
        return []
    return [p if os.path.isabs(p) else os.path.join(ROOT, p) for p in sel.split(",")]


class Print:
    """One print of a G-code file on the firmware under test, and what the firmware said."""

    def __init__(self, gcode, name):
        self.out = os.path.join(OUT, name)
        self.rc = harness.run(os.path.join(ROOT, gcode), self.out, patches())
        with open(os.path.join(self.out, "responses.txt")) as f:
            self.responses = f.read()

    def errors(self):
        return [l for l in self.responses.splitlines() if l.startswith("!!")]

    def positions(self):
        """Each GET_POSITION the firmware answered: {'toolhead': (x, y, z), 'gcode': (x, y, z)}."""
        found, cur = [], {}
        for line in self.responses.splitlines():
            m = re.match(r"// (toolhead|gcode): X:(\S+) Y:(\S+) Z:(\S+)", line)
            if m:
                cur[m.group(1)] = tuple(float(v) for v in m.groups()[1:])
                if m.group(1) == "gcode":
                    found.append(cur)
                    cur = {}
        return found
