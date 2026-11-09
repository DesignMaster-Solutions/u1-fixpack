#!/usr/bin/env python3
"""Replay a real U1 print file (unmodified, as printed) through the harness for u1-klipper#22.

Usage: replay_real.py IN.gcode OUT.gcode SD_POS=NAME[,NAME...] [SD_POS=NAME ...] [T4=T3]

- The slicer's start block (from `M73 P0` to the first layer) needs the probe, camera and RFID:
  it is replaced by the state it leaves behind (T1 on the carriage, absolute XYZ, relative E).
- Each SD_POS=NAME injects `EXCLUDE_OBJECT NAME=...` before the line that holds that byte, the
  position klippy.log reports (sd_pos) when the user pressed Skip on the touchscreen.
- A GET_POSITION goes after every MOVE_TO_DISCARD_FILAMENT_POSITION and after the E-only
  `; restore retraction` prime that follows it, so the firmware itself answers where the head
  and the G-code position are at each tool change.
- T4=T3 maps a tool the harness firmware does not have onto the head that printed it.
"""
import re
import sys

PREAMBLE = ["M140 S80", "M104 T1 S230", "T1", "M109 T1 S230", "G90", "M83", "G92 E0",
            "SET_PRESSURE_ADVANCE ADVANCE=0.02818"]


def main(src, dst, args):
    skips, tmap = {}, {}
    for a in args:
        k, v = a.split("=", 1)
        (tmap if k.startswith("T") else skips).__setitem__(k, v)
    with open(src, "rb") as f:
        raw = f.readlines()
    # byte offset -> line index, for the sd_pos the printer logged
    at, off = {}, 0
    for i, l in enumerate(raw):
        for pos in skips:
            if off <= int(pos) < off + len(l):
                at.setdefault(i, []).extend(skips[pos].split(","))
        off += len(l)
    assert sum(len(v) for v in at.values()) == sum(len(v.split(",")) for v in skips.values()), \
        "an sd_pos is outside the file"

    lines = [l.decode("utf-8", "replace").rstrip("\r\n") for l in raw]
    start = next(i for i, l in enumerate(lines) if l.startswith("M73 P0"))
    first = next(i for i, l in enumerate(lines) if l.startswith(";LAYER_CHANGE"))
    out, prime_pending, n_skip, n_get = [], False, 0, 0
    for i, l in enumerate(lines):
        if start <= i < first:
            if i == start:
                out += PREAMBLE
            continue
        for name in at.get(i, []):
            out.append("EXCLUDE_OBJECT NAME=%s ; the user presses Skip (sd_pos)" % name)
            n_skip += 1
        if re.match(r"^T\d+$", l) and l in tmap:
            l = tmap[l] + " ; was " + l
        out.append(l)
        if l.startswith("MOVE_TO_DISCARD_FILAMENT_POSITION"):
            out.append("GET_POSITION")
            prime_pending = True
            n_get += 1
        elif prime_pending and "; restore retraction" in l:
            out.append("GET_POSITION")
            prime_pending = False
            n_get += 1
    assert not prime_pending, "the last MOVE_TO_DISCARD_FILAMENT_POSITION has no prime after it"
    with open(dst, "w") as f:
        f.write("\n".join(out) + "\n")
    print("%s: start block %d-%d replaced, %d skips injected, %d GET_POSITION, %d lines"
          % (dst, start + 1, first, n_skip, n_get, len(out)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
