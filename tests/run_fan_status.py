#!/usr/bin/env python3
"""#18 follow-up: the fan 'speed' status must change when the PWM does, not when it is scheduled.

Found by alternativniy on Snapmaker/u1-klipper#25 (and fixed the same way in Extended PR #787):
the lookahead callback schedules the PWM when the move is planned, so a status read from the
scheduled value runs ahead of the fan by up to the queued move time. On the real firmware with the
patch, M106 S255 is queued behind a 5 s extrusion, the lookahead is flushed (PWM scheduled), and
the status is read with the modeled MCU clock (DRYRUN_WAIT_MODEL) before, 1 ms before, and at the
PWM print time, then after M400. The PWM print time is checked against the e0 MCU's PWM clock.
"""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("FIXPACK_IMAGE", "u1-fixpack:local")
FIRMWARE = os.environ.get("FIXPACK_FIRMWARE", "93cb12faebf6e74c51bbc5f0be66e95124af14c8")
EVIDENCE = ROOT / os.environ.get("FIXPACK_EVIDENCE", "docs/evidence") / "fan-status"
FIXTURE = "/work/tests/fixtures/issue18-status.gcode"
PATCH = "/work/patches/0018-fan-gcode-motion-sync.patch"
MUTANTS = {
    # the previous #18 patch: status = last scheduled value (what the reviewer saw on hardware)
    "status-at-schedule": "/work/tests/mutants/18-status-at-schedule.patch",
}
DIAG = re.compile(r"DRYRUN fan requested=(\S+) status=(\S+) saved=\S+ "
                  r"scheduled_time=(\S+) mcu_time=(\S+)")


def run(patch, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    command = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", IMAGE, "--mode", "patched",
               "--gcode", FIXTURE, "--patch", patch,
               "--evidence", "/work/" + str(evidence.relative_to(ROOT)), "--decode-e0"]
    done = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    assert done.returncode == 0, (patch, done.stdout, done.stderr)
    summary = (evidence / "patched.txt").read_text()
    assert "firmware_commit=" + FIRMWARE in summary, summary[:300]
    assert "firmware_error_count=0" in summary and "firmware_return_code=0" in summary
    decoded = (evidence / "patched-mcu-e0.txt").read_text()
    freq = int(re.search(r"CLOCK_FREQ=(\d+)", summary).group(1))
    fan = int(re.search(r"config_digital_out oid=(\d+) pin=PB3\b", decoded).group(1))
    on = [int(c) for c, t in re.findall(r"queue_digital_out oid=%d clock=(\d+) on_ticks=(\d+)"
                                        % fan, decoded) if int(t) > 0]
    assert len(on) == 1, on
    diags = [tuple(map(float, m.groups())) for m in DIAG.finditer(summary)]
    assert len(diags) == 4, diags
    return diags, on[0] / freq, summary


def failures(diags, pwm_time):
    """(name, ok) for each status read; the old speed is 0, M106 asked for 1."""
    (_, flushed, sched, t0), (_, before, _, t1), (_, at, _, t2), (_, after, _, t3) = diags
    return [
        ("pwm_time_matches_mcu", abs(sched - pwm_time) < 1e-6),
        ("flushed_shows_old", t0 < sched and flushed == 0.0),
        ("1ms_before_pwm_shows_old", t1 < sched and before == 0.0),
        ("at_pwm_shows_new", t2 >= sched and at == 1.0),
        ("after_m400_shows_new", t3 > sched and after == 1.0),
    ]


def report(name, diags, pwm_time, evidence):
    checks = failures(diags, pwm_time)
    lines = ["%s: pwm_print_time=%.6f" % (name, pwm_time)]
    for label, (_, status, _, mcu) in zip(("flushed", "pwm-1ms", "at-pwm", "after-M400"), diags):
        lines.append("  %-10s mcu_time=%.6f status=%s" % (label, mcu, status))
    failed = [n for n, ok in checks if not ok]
    lines.append("  failed=%s" % (",".join(failed) or "none"))
    (evidence / "result.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return failed


def main():
    diags, pwm_time, _ = run(PATCH, EVIDENCE / "patched")
    failed = report("patched", diags, pwm_time, EVIDENCE / "patched")
    assert not failed, failed
    for name, patch in MUTANTS.items():
        evidence = EVIDENCE / ("mutant-" + name)
        diags, pwm_time, _ = run(patch, evidence)
        failed = report("mutant-" + name, diags, pwm_time, evidence)
        assert "flushed_shows_old" in failed, ("mutant survived", name)
        print("mutant %s: red" % name)
    print("fan status follows the PWM print time: PASS")


if __name__ == "__main__":
    main()
