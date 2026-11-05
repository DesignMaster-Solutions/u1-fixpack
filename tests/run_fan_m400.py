#!/usr/bin/env python3
"""tools/fan_m400.py on the STOCK firmware, with M400 waiting the way it does on the printer.

Batch mode never waits on M400, so both fixtures run with DRYRUN_WAIT_MODEL (tests/firmware/
dryrun_tracer.py): after a wait, the MCU clock catches up with the end of the drained queue.
Control (the model, no added M400): the part fan still switches seconds early, the bug (red).
Workaround (fan_m400.py output): the fan switches within WORKAROUND_MS of the move (green).
No patch is applied: this is the stock firmware a U1 owner has today.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fan_m400  # noqa: E402
import run_issue18 as r18  # noqa: E402

# shortcut: bound = what 2.0.0 and 2.1.0 measure (the restart buffer before the next move) plus margin;
# re-measure on a firmware bump.
WORKAROUND_MS = 300.0
EVIDENCE = r18.ROOT / os.environ.get("FIXPACK_EVIDENCE", "docs/evidence") / "fan-m400"


def fixture(lines, m400):
    lines = lines[:1] + ["DRYRUN_WAIT_MODEL\n"] + lines[1:]
    return "".join(fan_m400.add_m400(lines) if m400 else lines)


def main():
    delta = {}
    for edge, src in (("on", r18.FIXTURE), ("off", r18.M107_FIXTURE)):
        lines = (r18.ROOT / src.replace("/work/", "")).read_text().splitlines(True)
        for case in ("control", "m400"):
            d = EVIDENCE / edge / case
            d.mkdir(parents=True, exist_ok=True)
            gcode = d / "fixture.gcode"
            gcode.write_text(fixture(lines, case == "m400"))
            summary, decoded = r18.run_mode("baseline", evidence=d, fixture="/work/" + str(gcode.relative_to(r18.ROOT)))
            assert "DRYRUN wait model on" in summary, ("the image has no DRYRUN_WAIT_MODEL: rebuild it", summary)
            metrics = r18.parse_result(summary, decoded, edge=edge)
            r18.record("baseline", metrics, d)
            delta[(edge, case)] = metrics["delta_ms"]
            print("fan %s, %s: %.3f ms from the move" % (edge, case, metrics["delta_ms"]))
    for edge in ("on", "off"):
        assert delta[(edge, "control")] < -1000.0, ("the model alone hid the bug", edge, delta)
        assert abs(delta[(edge, "m400")]) <= WORKAROUND_MS, ("workaround missed", edge, delta)
    print("fan_m400 on stock firmware %s: PASS (bound %.0f ms)" % (r18.FIRMWARE[:7], WORKAROUND_MS))


if __name__ == "__main__":
    main()
