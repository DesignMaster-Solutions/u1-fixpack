"""After a skipped object, the first travel must lift before it moves, as the slicer planned.

Not in Snapmaker/u1-klipper#22 itself: found with U1 Dry Run on the 2026-11-01 print file from
that issue (docs/evidence/issue-22/dryrun-real-print-B-*.txt, 8 travels across finished parts).
The file is printed through the firmware's virtual_sdcard; the assertions read the firmware's
own move trace (every toolhead.move) and its GET_POSITION. Before the skip no lift in the file
is longer than the ramp, so any longer one comes from the skip.
"""
import math
import os
import unittest

from fixpack import Print

RAMP_MM = 8.0  # XY length of the slicer's ramped lift in tests/issue22/travel_after_skip.gcode


class Issue22Travel(unittest.TestCase):
    def test_first_travel_after_skip_lifts_where_the_head_is(self):
        p = Print("tests/issue22/travel_after_skip.gcode", "issue22-travel-after-skip")
        self.assertIn("Excluding object B", p.responses)
        self.assertEqual(p.errors(), [])
        moves = []  # (x, y, z) of every move the G-code layer sent to the toolhead
        with open(os.path.join(p.out, "trace.txt")) as f:
            for l in f:
                c = l.split()
                if c[0] == "M" and c[-1] == "G":
                    moves.append((float(c[1]), float(c[2]), float(c[3])))
        ramps = [(a, b) for a, b in zip(moves, moves[1:])
                 if b[2] > a[2]
                 and math.hypot(b[0] - a[0], b[1] - a[1]) > RAMP_MM + 0.01]
        self.assertGreater(len(moves), 100, "the trace is too short to be the whole print")
        self.assertEqual(ramps, [], "a lift was stretched over a travel longer than the slicer's %g mm ramp" % RAMP_MM)
        end = p.positions()[-1]
        for axis, t, g in zip("XYZ", end["toolhead"], end["gcode"]):
            self.assertAlmostEqual(g, t, delta=0.001, msg="at the end: gcode %s=%.3f, head %.3f" % (axis, g, t))
        self.assertIn("FIXPACK: print ended, state complete", p.responses)
        self.assertEqual(p.rc, 0)


if __name__ == "__main__":
    unittest.main()
