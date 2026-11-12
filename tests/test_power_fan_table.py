"""Snapmaker/u1-klipper#15: what the PSU fan's temp_speed_table really does.

No patch here: this pins down how the shipped firmware reads the five columns, because the issue (and
the two replacement tables it proposes) read them as temperature bands, and the code does not.

The rows are taken from the shipped lava/printer.cfg and fed to the firmware's own
PrinterHeaterFan.callback (klippy/extras/heater_fan.py) with fake heaters, so the numbers below are
what the firmware computes, not a re-implementation.

Run: U1_KLIPPER=/path/to/u1-klipper python3 -m unittest -v tests.test_power_fan_table
     (default /opt/klipper, where the Docker image keeps the firmware)
"""
import os
import re
import sys
import unittest

KLIPPER = os.environ.get("U1_KLIPPER", "/opt/klipper")
sys.path.insert(0, os.path.join(KLIPPER, "klippy"))
from extras import heater_fan  # noqa: E402  (the firmware's own module)

# The two tables proposed in the issue text, verbatim.
ISSUE_PROPOSAL = [[260, 45, 0, 0.6, 0.6], [9999, 260, 0.6, 1, 1]]
ISSUE_QUIET = [[260, 45, 0, 0.2, 0.2], [9999, 260, 0.2, 0.4, 0.4]]

# (name, [(current, target) for the four heads])
CASES = [
    ("idle, all cold", [(25, 0)] * 4),
    ("heaters off, one nozzle still at 200", [(200, 0), (25, 0), (25, 0), (25, 0)]),
    ("1 head heating to 30", [(25, 30), (25, 0), (25, 0), (25, 0)]),
    ("1 head at 220", [(220, 220), (25, 0), (25, 0), (25, 0)]),
    ("1 head at 300", [(300, 300), (25, 0), (25, 0), (25, 0)]),
    ("2 heads, one at 300", [(300, 300), (220, 220), (25, 0), (25, 0)]),
    ("3 heads at 220", [(220, 220)] * 3 + [(25, 0)]),
    ("3 heads, one at 270", [(270, 270), (220, 220), (220, 220), (25, 0)]),
    ("4 heads at 300", [(300, 300)] * 4),
]


def shipped_table():
    with open(os.path.join(KLIPPER, "lava/printer.cfg")) as f:
        section = re.search(r"\[heater_fan power_fan\]\n(.*?)\n\[", f.read(), re.S).group(1)
    rows = re.search(r"temp_speed_table:\n((?:[ \t]+.*\n?)+)", section).group(1)
    return [[float(v) for v in line.split("#")[0].split(",")] for line in rows.strip().splitlines()]


class _Heater:
    def __init__(self, temps):
        self.temps = temps

    def get_temp(self, eventtime):
        return self.temps


class _Fan:
    def get_mcu(self):
        return self

    def estimated_print_time(self, t):
        return t

    def set_speed(self, print_time, speed):
        self.speed = speed


class _Printer:
    def get_reactor(self):
        return self

    def monotonic(self):
        return 0.


def speed(table, heads):
    hf = object.__new__(heater_fan.PrinterHeaterFan)  # skip __init__: no MCU, no config file
    hf.temp_speed_table, hf.stepped_temp_table = table, None
    hf.heaters = [_Heater(t) for t in heads]
    hf.min_speed, hf.last_speed = 0., -1
    hf.external_temp_sensor = hf.original_fan_speed = None
    hf.printer, hf.fan = _Printer(), _Fan()
    hf.callback(0.)
    return hf.fan.speed


class PowerFanTable(unittest.TestCase):
    def table(self, rows):
        return [speed(rows, heads) for _, heads in CASES]

    def test_shipped_table(self):
        self.assertEqual(shipped_table(), [[9999, 260, 1, 3, 1], [9999, 45, 1, 1, 0.6]])
        # off with no target (even with a hot nozzle), 60 % once any head has a target above 45,
        # 100 % only with three or more heads on and one of them set above 260
        self.assertEqual(self.table(shipped_table()), [0, 0, 0, 0.6, 0.6, 0.6, 0.6, 1, 1])

    def test_issue_tables_never_reach_their_second_row(self):
        # row 1 matches as soon as any head has a target, whatever its value, so row 2 is dead
        self.assertEqual(self.table(ISSUE_PROPOSAL), [0, 0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6])
        self.assertEqual(self.table(ISSUE_QUIET), [0, 0, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2])


if __name__ == "__main__":
    for label, rows in (("shipped", shipped_table()), ("issue proposal", ISSUE_PROPOSAL), ("issue quiet", ISSUE_QUIET)):
        print(label, rows)
        for (name, heads) in CASES:
            print("  %-40s %3.0f %%" % (name, speed(rows, heads) * 100))
