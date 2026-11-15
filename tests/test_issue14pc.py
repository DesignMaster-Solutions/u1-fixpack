"""Snapmaker/u1-klipper#14 (side finding): on a 0.2 mm nozzle the firmware refuses PCTG.

FORBIDDEN_FILAMENT_TYPES_02 lists PA and PC, and is_allow_to_print() adds a prefix test,
startswith('PC'), for the polycarbonate blends. 'PCTG' starts with the same two letters, so it is
refused too (print start: code 25, "not allow to print"; setting a head to 0.2 clears its filament
info), while PETG, the same copolyester family, is allowed.

This calls the firmware's own FilamentParameters.is_allow_to_print (it does not read self), from the
tree the harness builds with the patches under test.
"""
import importlib
import os
import sys
import tempfile
import unittest

from fixpack import harness, patches

_tree = harness.prepare_klipper(tempfile.mkdtemp(), patches())
sys.path.insert(0, os.path.join(_tree, "klippy"))
fp = importlib.import_module("extras.filament_parameters")


def allowed(main_type, sub_type="", nozzle=0.2):
    return fp.FilamentParameters.is_allow_to_print(None, "Generic", main_type, sub_type, nozzle, "standard")


class Issue14Pc(unittest.TestCase):
    def test_pctg_prints_on_02(self):
        self.assertTrue(allowed("PCTG"))

    def test_petg_and_pla_print_on_02_as_before(self):
        for t in ("PETG", "PLA", "ABS"):
            self.assertTrue(allowed(t), t)

    def test_polycarbonates_stay_refused_on_02(self):
        for t in ("PC", "PC-ABS", "PC-FR", "PC-CF", "PCABS"):
            self.assertFalse(allowed(t), t)

    def test_the_rest_of_the_02_list_stays_refused(self):
        for t in ("PA", "PA6", "PA-CF", "PEBA", "TPU", "PVA", "PLA-CF", "PETG-GF", "PCTG-CF", "PCTG-GF"):
            self.assertFalse(allowed(t), t)
        self.assertFalse(allowed("PCTG", "Wood"))  # the 'ANY' sub-type rule still applies to PCTG

    def test_other_nozzles_unchanged(self):
        for t in ("PCTG", "PC", "PA-CF"):
            self.assertTrue(allowed(t, nozzle=0.4), t)


if __name__ == "__main__":
    unittest.main()
