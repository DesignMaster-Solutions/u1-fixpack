"""Snapmaker/u1-klipper#30: with heads of different nozzle sizes, the start command refuses a file
whose per-tool nozzle list matches the heads, because every used head is compared with the list's
first entry.

Each case boots the firmware with the nozzle sizes saved per head (persistent/extruderN_nozzle_config.json,
what the touchscreen's nozzle setting writes) and starts the job the way Moonraker does:
SDCARD_PRINT_FILE_WITH_PARAMETERS with NOZZLE_DIAMETER_LIST / FILAMENT_USED_G / MAP_TABLE in the
string form klippy_apis._fill_metadata builds (harness/fixpack_ui.py, FIXPACK_START_PARAMS).
"""
import os
import unittest

from fixpack import Print

GCODE = "tests/issue30/two_heads.gcode"


def start(name, heads, file_nozzles, used, map_table=None):
    """heads: nozzle size per physical head; file_nozzles: the file's list; used: file tools that extrude."""
    state = {"../persistent/extruder%s_nozzle_config.json" % (i or ""):
             {"diameter": d, "diameter_v160": d, "volume_type": "standard"} for i, d in enumerate(heads)}
    grams = [1.5 if i in used else 0.0 for i in range(max(used) + 1)]
    params = 'NOZZLE_DIAMETER_LIST="%s" FILAMENT_USED_G="%s"' % (file_nozzles, grams)
    if map_table:
        params += ' MAP_TABLE="%s"' % (map_table,)
    os.environ["FIXPACK_START_PARAMS"] = params
    try:
        return Print(GCODE, name, state)
    finally:
        del os.environ["FIXPACK_START_PARAMS"]


class Issue30(unittest.TestCase):
    def assert_printed(self, p):
        self.assertNotIn("start refused", p.responses)
        self.assertIn("FIXPACK: print ended, state complete", p.responses)
        self.assertEqual(p.errors(), [])

    def assert_refused(self, p, pair):
        self.assertIn("start refused", p.responses)
        self.assertIn("nozzle diameter mismatch:" + pair, p.responses)
        self.assertNotIn("file-ran", p.responses)

    def test_mixed_heads_matching_the_file_print(self):
        # the report: heads 0.4, 0.4, 0.4, 0.8; the file says the same; tools 0 and 3 extrude
        self.assert_printed(start("issue30-mixed", [0.4, 0.4, 0.4, 0.8], [0.4, 0.4, 0.4, 0.8], {0, 3}))

    def test_remapped_tools_are_checked_on_the_head_they_print_with(self):
        # file tool 0 (0.8) is sent to head 3 (0.8), file tool 1 (0.4) to head 0 (0.4)
        self.assert_printed(start("issue30-remap", [0.4, 0.4, 0.4, 0.8], [0.8, 0.4, 0.4, 0.4], {0, 1},
                                  map_table=[[0, 3], [1, 0]]))

    def test_a_real_mismatch_on_a_later_tool_is_still_refused(self):
        # file tool 3 was sliced for 0.4, head 3 carries 0.8
        self.assert_refused(start("issue30-mismatch", [0.4, 0.4, 0.4, 0.8], [0.4, 0.4, 0.4, 0.4], {0, 3}),
                            "f3_0.4 != e3_0.8")

    def test_a_remap_onto_a_head_of_another_size_is_refused(self):
        self.assert_refused(start("issue30-remap-mismatch", [0.4, 0.4, 0.4, 0.8], [0.4, 0.4, 0.4, 0.4], {0, 1},
                                  map_table=[[1, 3]]), "f1_0.4 != e3_0.8")

    def test_single_value_file_still_covers_every_used_tool(self):
        # older files carry one value; tools without an entry of their own keep using it
        self.assert_printed(start("issue30-single", [0.4, 0.4, 0.4, 0.4], [0.4], {0, 1}))
        self.assert_refused(start("issue30-single-mismatch", [0.4, 0.8, 0.4, 0.4], [0.4], {0, 1}),
                            "f1_0.4 != e1_0.8")

    def test_uniform_heads_print_as_before(self):
        self.assert_printed(start("issue30-uniform", [0.4, 0.4, 0.4, 0.4], [0.4, 0.4, 0.4, 0.4], {0, 1, 2, 3}))


if __name__ == "__main__":
    unittest.main()
