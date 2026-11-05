#!/usr/bin/env python3
"""#18 follow-up: a tool change right after M106 must restore the LAST requested speed on the new head.

Question from alternativniy (Extended PR #787): with M106 scheduled through the motion queue, the
fan status only changes once the PWM is scheduled, so a tool change right after M106 could save a
stale value. The U1 tool change (_cmd_SWITCH_EXTRUDER) calls toolhead.wait_moves() before it reads
the print-fan status, and that flushes the lookahead callbacks. This proves it on the real firmware:
the speed restored on T1 is read from the PWM the e1 MCU (the new head) actually receives.
"""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("FIXPACK_IMAGE", "u1-fixpack:local")
FIRMWARE = os.environ.get("FIXPACK_FIRMWARE", "93cb12faebf6e74c51bbc5f0be66e95124af14c8")
EVIDENCE = ROOT / os.environ.get("FIXPACK_EVIDENCE", "docs/evidence") / "toolchange-fan"
PATCH = "/work/patches/0018-fan-gcode-motion-sync.patch"
MUTANT = "/work/tests/mutants/18-toolchange-status-before-flush.patch"
# The status follows the PWM print time, so it lags a just-scheduled M106 (PR #25 review): the tool
# change must restore get_requested_speed(). This mutant restores the status instead.
MUTANT_STATUS = "/work/tests/mutants/18-toolchange-reads-status.patch"
# fixture: (speed already applied before the queued M106s, last queued M106)
FIXTURES = {
    "toolchange-fan": (0.0, 1.0),       # M106 S255 queued, then T1
    "toolchange-fan-two": (64 / 255, 1.0),  # S64 applied, then M106 S128 + M106 S255 queued, then T1
}


def run(mode, fixture, evidence, patch=PATCH):
    command = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", IMAGE, "--mode", mode,
               "--gcode", "/work/tests/fixtures/%s.gcode" % fixture,
               "--evidence", "/work/" + str(evidence.relative_to(ROOT)), "--decode", "e1"]
    if mode != "baseline":
        command += ["--patch", patch]
    done = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    assert done.returncode == 0, (mode, fixture, done.stdout, done.stderr)
    return (evidence / (mode + ".txt")).read_text(), (evidence / (mode + "-mcu-e1.txt")).read_text()


def restored_speed(summary, decoded):
    """Speed the new head's fan settles at after T1, from the e1 MCU's PWM commands."""
    assert "firmware_commit=" + FIRMWARE in summary, summary[:300]
    assert "firmware_error_count=0" in summary
    assert "firmware_return_code=0" in summary
    # The move after T1 must run on the new head, or the swap did not happen.
    assert re.search(r"^M .* extruder1 ", summary, re.M), "T1 did not activate extruder1"
    fan = int(re.search(r"config_digital_out oid=(\d+) pin=PB3\b", decoded).group(1))
    cycle = int(re.search(r"set_digital_out_pwm_cycle oid=%d cycle_ticks=(\d+)" % fan,
                          decoded).group(1))
    on = [int(t) for t in re.findall(r"queue_digital_out oid=%d clock=\d+ on_ticks=(\d+)" % fan,
                                     decoded)]
    # Boot sends off, klippy's restart handler sends off at the end; the last non-zero PWM
    # is what the tool change restored (after any kick-start pulse). None = never turned on.
    lit = [t for t in on if t > 0]
    return (lit[-1] / cycle) if lit else 0.0, cycle, on


def main():
    lines, restored = [], {}
    for fixture, (before, last) in FIXTURES.items():
        for name, mode, patch in (("baseline", "baseline", PATCH), ("patched", "patched", PATCH),
                                  ("mutant-status-before-flush", "patched", MUTANT),
                                  ("mutant-reads-status", "patched", MUTANT_STATUS)):
            evidence = EVIDENCE / fixture / name
            evidence.mkdir(parents=True, exist_ok=True)
            summary, decoded = run(mode, fixture, evidence, patch)
            speed, cycle, on = restored_speed(summary, decoded)
            with (evidence / (mode + ".txt")).open("a") as out:
                out.write("new_head=e1 fan_pin=PB3 pwm_cycle_ticks=%d pwm_on_ticks=%s\n" % (cycle, on))
                out.write("restored_speed=%.4f last_m106=%.4f speed_before=%.4f\n" %
                          (speed, last, before))
            line = "%s %s: T1 restored %.4f (last M106 %.4f)" % (fixture, name, speed, last)
            lines.append(line)
            print(line)
            if name.startswith("mutant"):
                restored.setdefault(name, []).append((speed, last))
            else:
                assert abs(speed - last) < 0.01, line
    # Each mutant restores a stale speed (not the last M106) in at least one fixture: red.
    for name, speeds in restored.items():
        assert any(abs(s - want) > 0.01 for s, want in speeds), ("mutant survived", name, speeds)
    (EVIDENCE / "summary.txt").write_text("\n".join(lines) + "\n")
    print("tool change after M106: baseline/patched restore the last M106, mutant red: PASS")


if __name__ == "__main__":
    main()
