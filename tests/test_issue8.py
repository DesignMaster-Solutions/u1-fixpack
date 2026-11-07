"""Snapmaker/u1-klipper#8: runout, the same spool fed back, Resume, and the head's measured flow
factor is replaced by the class default, live and in snapmaker/flow_calibrator.json.

Each case prints tests/issue8/runout_resume.gcode on e2 through the firmware's own virtual_sdcard,
with the shipped config and macros (INNER_PAUSE, INNER_RESUME). The printer boots with the state
the reporter had: e2 calibrated to 0.023951 (flow_calibrator.json) and loaded with PLA
(print_task.json). The runout, the RFID reader's answers, the reload and Resume are delivered by
harness/fixpack_runout.py through the firmware's own entry points (see its docstring). The test
asserts on the two values the reporter polled: extruder2 pressure_advance and the stored factor.
"""
import os
import re
import unittest

from fixpack import OUT, Print, ROOT

MEASURED = 0.023951  # the reporter's extruder2 factor, from the printer's own flow calibration
PETG_DEFAULT = 0.05  # what stock FLOW_RESET_K applies for Snapmaker PETG Basic, 0.4 mm standard nozzle
DEFAULT_ENV = {'k_min': 0.005, 'k_max': 0.065, 'k_step': 0.005, 'start_vel': 4, 'start_dist': 20,
               'slow_vel': 0.8, 'slow_dist': 0.8, 'fast_dist': 2, 'fast_vel': 8, 'accel': 200, 'loop': 14}


def saved_state(vendor, sub_type, official, sku):
    return {
        "flow_calibrator.json": {"factor": {"extruder": 0.02, "extruder1": 0.02, "extruder2": MEASURED,
                                            "extruder3": 0.02}, "env": DEFAULT_ENV},
        "print_task.json": {"filament_vendor": ["NONE", "NONE", vendor, "NONE"],
                            "filament_type": ["NONE", "NONE", "PLA", "NONE"],
                            "filament_sub_type": ["NONE", "NONE", sub_type, "NONE"],
                            "filament_official": [False, False, official, False],
                            "filament_sku": [0, 0, sku, 0]},
    }


def runout_print(name, spool, state):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(ROOT, "tests/issue8/runout_resume.gcode")) as f:
        text = f.read().replace("@SPOOL@", spool)
    gcode = os.path.join(OUT, name + ".gcode")
    with open(gcode, "w") as f:
        f.write(text)
    return Print(gcode, name, state)


class Issue8(unittest.TestCase):
    def flow_k(self, p):
        """{label: (live pressure_advance, stored factor)} for extruder2."""
        return {m.group(1): (float(m.group(2)), float(m.group(3))) for m in re.finditer(
            r"FIXPACK: flow_k (\S+) extruder2 live=(\S+) store=(\S+)", p.responses)}

    def assert_ran_the_runout(self, p):
        for line in ("FIXPACK: e2 filament runs out", "Pausing...", "FIXPACK: user feeds the spool back",
                     "Resuming...", "FIXPACK: print ended, state complete"):
            self.assertIn(line, p.responses)
        self.assertEqual(p.errors(), [])
        self.assertEqual(p.rc, 0)
        k = self.flow_k(p)
        self.assertEqual(k["before-runout"], (MEASURED, MEASURED))
        # the reporter's poll: the runout detection alone changes nothing
        self.assertEqual(k["runout-paused"], (MEASURED, MEASURED))
        return k

    def test_untagged_spool_fed_back_keeps_the_measured_factor(self):
        p = runout_print("issue8-untagged", "untagged", saved_state("Generic", "Basic", False, 0))
        k = self.assert_ran_the_runout(p)
        self.assertEqual(k["after-feed"], (MEASURED, MEASURED), "live, store after the spool is fed back")
        self.assertEqual(k["print-end"], (MEASURED, MEASURED), "live, store after Resume")

    def test_same_tagged_spool_fed_back_keeps_the_measured_factor(self):
        p = runout_print("issue8-same-tag", "Snapmaker:PLA:Basic:900001",
                         saved_state("Snapmaker", "Basic", True, 900001))
        k = self.assert_ran_the_runout(p)
        self.assertEqual(k["after-feed"], (MEASURED, MEASURED), "live, store after the spool is fed back")
        self.assertEqual(k["print-end"], (MEASURED, MEASURED), "live, store after Resume")

    def test_different_tagged_spool_still_resets_to_its_class_default(self):
        p = runout_print("issue8-other-tag", "Snapmaker:PETG:Basic:900002",
                         saved_state("Snapmaker", "Basic", True, 900001))
        k = self.assert_ran_the_runout(p)
        # a different filament must not inherit the PLA factor: FLOW_RESET_K gives the PETG class
        # default (filament_parameters), live and stored, as the stock firmware does
        self.assertEqual(k["after-feed"], (PETG_DEFAULT, PETG_DEFAULT))
        self.assertEqual(k["print-end"], (PETG_DEFAULT, PETG_DEFAULT))


if __name__ == "__main__":
    unittest.main()
