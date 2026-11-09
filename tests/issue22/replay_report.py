#!/usr/bin/env python3
"""Summarise a harness run of a replay_real.py file: one line per tool change (GET_POSITION pair
in the chute and after the E-only prime), the firmware errors, and how the print ended.

Usage: replay_report.py OUTDIR [OUTDIR ...]   (an OUTDIR of harness/run.py)
"""
import os
import re
import sys

TOL = 0.001


def positions(text):
    found, cur = [], {}
    for line in text.splitlines():
        m = re.match(r"// (toolhead|gcode): X:(\S+) Y:(\S+) Z:(\S+)", line)
        if m:
            cur[m.group(1)] = tuple(float(v) for v in m.groups()[1:])
            if m.group(1) == "gcode":
                found.append(cur)
                cur = {}
    return found


def report(out):
    with open(os.path.join(out, "responses.txt")) as f:
        text = f.read()
    pos = positions(text)
    print("== %s: %d GET_POSITION, %d tool changes" % (out, len(pos), len(pos) // 2))
    bad = 0
    for n, (chute, primed) in enumerate(zip(pos[::2], pos[1::2]), 1):
        drift = max(abs(a - b) for a, b in zip(chute["toolhead"][:2], chute["gcode"][:2]))
        moved = max(abs(a - b) for a, b in zip(primed["toolhead"][:2], chute["toolhead"][:2]))
        if drift > TOL or moved > TOL:
            bad += 1
            print("  swap %3d: in the chute toolhead X%.3f Y%.3f, gcode X%.3f Y%.3f; after the prime "
                  "the head is at X%.3f Y%.3f (moved %.1f mm)"
                  % (n, *chute["toolhead"][:2], *chute["gcode"][:2], *primed["toolhead"][:2], moved))
    print("  tool changes where gcode != toolhead or the prime moved the head: %d" % bad)
    for line in text.splitlines():
        if line.startswith("!!") or line.startswith("FIXPACK:") or "Excluding" in line:
            print("  " + line)
    return bad


if __name__ == "__main__":
    for out in sys.argv[1:]:
        report(out)
