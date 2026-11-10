#!/usr/bin/env python3
"""Write the G-code files for the Snapmaker/u1-klipper#22 tests (run from anywhere).

Two labelled objects laid out as in the issue: A (3 layers, front, centre 135,40) and B
(taller, back, centre 135,200). Object blocks follow OrcaSlicer 2.x output for the U1, checked
against the reporter's attached file: the z-hop and the layer Z move are inside
EXCLUDE_OBJECT_START/END, and extrusion is relative (M83). B is skipped at layer 2.
tool_change.gcode is abehrman's report in the issue: no pause, the slicer's tool change after the
skip (lift, T1, prime in the purge chute) is what carries the stale XY into an E-only move.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER = [
    "EXCLUDE_OBJECT_DEFINE NAME=A CENTER=135,40 POLYGON=[[125,30],[145,30],[145,50],[125,50],[125,30]]",
    "EXCLUDE_OBJECT_DEFINE NAME=B CENTER=135,200 POLYGON=[[115,180],[155,180],[155,220],[115,220],[115,180]]",
    "M104 S220 ; above 170 C, so INNER_RESUME takes its purge path",
    "M140 S60", "G90", "M83", "G92 E0",
]


def block(name, cx, cy, half, z, insert=None):
    out = ["EXCLUDE_OBJECT_START NAME=%s" % name,
           "G1 X%.3f Y%.3f Z%.3f F30000" % (cx - half, cy - half, z + 0.4),
           "G1 Z%.3f" % z, "G1 E.8 F2100"]
    for r in (0, 1):
        h = half - 2 * r
        q = [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]
        if r:
            out.append("G1 X%.3f Y%.3f F30000" % q[0])
        for x, y in q[1:] + q[:1]:
            out.append("G1 X%.3f Y%.3f E%.5f F12000" % (x, y, 2 * h * 0.033))
    if insert:
        out[8:8] = insert  # after three walls of the outer loop
    out += ["G1 E-.8 F2400", "EXCLUDE_OBJECT_END NAME=%s" % name]
    return out


def body(insert_layer4=None):
    lines = []
    for n, z in enumerate((0.2, 0.4, 0.6, 0.8, 1.0, 1.2), 1):
        lines += [";LAYER_CHANGE", ";Z:%.1f" % z, "G92 E0"]
        if n == 2:
            lines.append("EXCLUDE_OBJECT NAME=B ; the user skips B")
        if n <= 3:
            lines += block("A", 135, 40, 10, z)
        lines += block("B", 135, 200, 20, z, insert_layer4 if n == 4 else None)
    return lines


def tool_change(to):
    """What a U1 runs at a tool change: the Snapmaker U1 OrcaSlicer machine profile's
    change_filament_gcode (lift, M109, M400, Tn) and the firmware's INNER_PREEXTRUDE_FILAMENT
    (SAVE_GCODE_STATE, MOVE_TO_DISCARD_FILAMENT_POSITION, E-only prime, back to idle, RESTORE)."""
    return ["; Change Tool -> Tool[%d]" % to, "G91", "G1 Z1.5 F600", "G90", "G1 F21000",
            "M109 S220 T%d" % to, "M400", "T%d" % to, "SAVE_GCODE_STATE NAME=preextrude",
            "MOVE_TO_DISCARD_FILAMENT_POSITION", "GET_POSITION", "M83",
            "G1 E20 F360 ; the prime: E only, right after the park", "G1 E-0.5", "M400",
            "GET_POSITION", "MOVE_TO_XY_IDLE_POSITION_EXTRUDER", "RESTORE_GCODE_STATE NAME=preextrude",
            "G90"]


def body_tool_change():
    """Two colours: T0 prints A; T1 prints C, then B. B is skipped at layer 2, so from then on the
    last moves T1 makes before each swap away from it are skipped ones: its offset (B's last
    point minus C's) is stale when the slicer swaps back to T1 and primes in the chute."""
    lines = ["EXCLUDE_OBJECT_DEFINE NAME=C CENTER=135,260 POLYGON=[[125,250],[145,250],[145,270],[125,270],[125,250]]"]
    for n, z in enumerate((0.2, 0.4, 0.6, 0.8), 1):
        lines += [";LAYER_CHANGE", ";Z:%.1f" % z, "G92 E0"]
        if n == 2:
            lines.append("EXCLUDE_OBJECT NAME=B ; the user skips B")
        lines += (tool_change(0) if n > 1 else []) + block("A", 135, 40, 10, z)
        lines += tool_change(1) + block("C", 135, 260, 10, z) + block("B", 135, 200, 20, z)
    return lines


def body_travel():
    """A, B, C on every layer, B skipped at layer 2. As in OrcaSlicer output, each object opens
    with the lift from the previous object's last point (0.4 mm of Z over 8 mm of XY) and then
    travels at that height. After the skip the head is at A, not at B, when C's lift comes."""
    lines = ["EXCLUDE_OBJECT_DEFINE NAME=C CENTER=135,120 POLYGON=[[125,110],[145,110],[145,130],[125,130],[125,110]]"]
    last = None  # the previous object's last point in the file
    for n, z in enumerate((0.2, 0.4, 0.6, 0.8), 1):
        lines += [";LAYER_CHANGE", ";Z:%.1f" % z, "G92 E0"]
        if n == 2:
            lines.append("EXCLUDE_OBJECT NAME=B ; the user skips B")
        for name, cx, cy, half in (("A", 135, 40, 10), ("B", 135, 200, 20), ("C", 135, 120, 10)):
            b = block(name, cx, cy, half, z)
            if last:
                b.insert(1, "G1 X%.3f Y%.3f Z%.3f F30000 ; slicer's ramped lift" % (last[0] + 8, last[1], z + 0.4))
            lines += b
            last = (cx - half + 2, cy - half + 2)
    return lines


FILES = {
    # The issue's main report: Pause on the screen during B's skipped layers, then Resume.
    "pause_resume.gcode": (
        "Pause during B's skipped layers, then Resume (the issue's main report).",
        body(["FIXPACK_UI_PAUSE ; the user presses Pause on the screen"])
        + ["G1 Z6 F600", "M104 S0", "M140 S0"]),
    # The issue's second report: an end-of-print sequence that parks, then moves E only.
    "end_of_print.gcode": (
        "End of print after the skipped layers: park, then an E-only move (the issue's 2nd report).",
        body() + ["MOVE_TO_DISCARD_FILAMENT_POSITION", "G1 E30 F300", "GET_POSITION",
                  "M104 S0", "M140 S0"]),
    # Same mechanism, one step further: the head is parked while B is still being skipped, B's
    # skipped moves go on, then E-only and Z-only moves follow. They must not move X or Y.
    "park_in_skipped.gcode": (
        "Park while B is being skipped, skipped moves go on, then E-only and Z-only moves.",
        body(["MOVE_TO_DISCARD_FILAMENT_POSITION", "GET_POSITION"])
        + ["G1 E-2 F2400", "G1 Z6 F600", "GET_POSITION", "M104 S0", "M140 S0"]),
    # abehrman's hardware report (stock 2.0.0.205): objects skipped, then a tool change; the prime
    # in the chute moved the head to (148.989, 337.635), past Y max, and on another print 222 mm
    # across the part while extruding.
    "tool_change.gcode": (
        "Two-colour print, B skipped; each swap back to T1 primes in the chute (abehrman's report).",
        body_tool_change() + ["M104 S0 T0", "M104 S0 T1", "M140 S0"]),
    # Not in the issue: found with U1 Dry Run on abehrman's 2026-11-01 file. The first move after a
    # skipped object is the slicer's ramped lift, made from where the head really is.
    "travel_after_skip.gcode": (
        "A, B, C per layer, B skipped: the lift before the travel from A to C (found with U1 Dry Run).",
        body_travel() + ["GET_POSITION", "M104 S0", "M140 S0"]),
}

if __name__ == "__main__":
    for name, (what, lines) in FILES.items():
        head = ["; U1 Fix Pack - Snapmaker/u1-klipper#22: " + what,
                "; Generated by tests/issue22/make_gcode.py; edit that, not this file."]
        with open(os.path.join(HERE, name), "w") as f:
            f.write("\n".join(head + HEADER + lines) + "\n")
