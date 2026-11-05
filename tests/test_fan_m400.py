import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import fan_m400  # noqa: E402


class FanM400Test(unittest.TestCase):
    def test_waits_before_each_part_fan_command(self):
        out = fan_m400.add_m400(["G1 X140 Y10\n", "M106 S255\n", "G1 E10\n", "m107\n"])
        self.assertEqual([l.split(";")[0].strip() for l in out],
                         ["G1 X140 Y10", "M400", "M106 S255", "G1 E10", "M400", "m107"])

    def test_other_fans_and_existing_waits_are_left_alone(self):
        lines = ["M106 P2 S128\n", "M107 P3\n", "M400\n", "M106 S0\n", "; M106 S255 in a comment\n"]
        self.assertEqual(fan_m400.add_m400(lines), lines)

    def test_edits_the_file_the_slicer_passes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".gcode", delete=False) as f:
            f.write("G1 X1\nM106 S255\nG1 E1\n")
        try:
            fan_m400.main(f.name)
            with open(f.name) as g:
                self.assertEqual(g.read().count("M400"), 1)
            fan_m400.main(f.name)  # running it twice changes nothing
            with open(f.name) as g:
                self.assertEqual(g.read().count("M400"), 1)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
