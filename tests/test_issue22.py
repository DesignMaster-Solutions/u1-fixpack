"""Snapmaker/u1-klipper#22: skip an object, then a park, and the next partial move uses a wrong XY.

Each case prints a file through the firmware's own virtual_sdcard with the shipped printer.cfg
and fluidd.cfg (INNER_PAUSE, INNER_RESUME, MOVE_TO_DISCARD_FILAMENT_POSITION as shipped), and
asserts on what the firmware itself answers: its errors, its GET_POSITION, its print state.
"""
import unittest

from fixpack import Print

TOL = 0.001  # mm; GET_POSITION prints 6 decimals, a real fault here is tens of mm


class Issue22(unittest.TestCase):
    def assert_gcode_matches_head(self, pos, where):
        for axis, t, g in zip("XYZ", pos["toolhead"], pos["gcode"]):
            self.assertAlmostEqual(g, t, delta=TOL, msg="%s: gcode %s=%.3f but the head is at %.3f"
                                   % (where, axis, g, t))

    def test_pause_then_resume_continues_the_print(self):
        p = Print("tests/issue22/pause_resume.gcode", "issue22-pause-resume")
        self.assertIn("Excluding object B", p.responses)
        self.assertIn("FIXPACK: user presses Resume", p.responses, "the pause did not complete")
        self.assertEqual(p.errors(), [])
        self.assertNotIn("Resumes error", p.responses)
        # INNER_PAUSE ends with GET_POSITION, right after the park
        self.assert_gcode_matches_head(p.positions()[0], "after the pause park")
        self.assertIn("Done printing file", p.responses)
        self.assertIn("FIXPACK: print ended, state complete", p.responses)
        self.assertEqual(p.rc, 0)

    def test_end_of_print_park_then_e_only_move(self):
        p = Print("tests/issue22/end_of_print.gcode", "issue22-end-of-print")
        self.assertEqual(p.errors(), [])
        self.assert_gcode_matches_head(p.positions()[-1], "after park + G1 E30")
        self.assertIn("FIXPACK: print ended, state complete", p.responses)
        self.assertEqual(p.rc, 0)

    def test_park_inside_skipped_object_then_partial_moves_stay_put(self):
        p = Print("tests/issue22/park_in_skipped.gcode", "issue22-park-in-skipped")
        self.assertEqual(p.errors(), [])
        after_park, at_end = p.positions()[0], p.positions()[-1]
        self.assert_gcode_matches_head(after_park, "after the park")
        # Only skipped moves, one E-only and one Z-only move come between: X and Y must not change
        for i, axis in enumerate("XY"):
            self.assertAlmostEqual(at_end["toolhead"][i], after_park["toolhead"][i], delta=TOL,
                                   msg="the head moved in %s on E/Z-only moves" % axis)
        self.assertIn("FIXPACK: print ended, state complete", p.responses)
        self.assertEqual(p.rc, 0)


if __name__ == "__main__":
    unittest.main()
