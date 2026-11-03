#!/usr/bin/env python3
"""Compare the U1 fan PWM clock with the next move's extruder-step clock."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "u1-fixpack:local"
EVIDENCE = ROOT / "docs/evidence/issue-18"
FIXTURE = "/work/tests/fixtures/issue18.gcode"
PATCH = "/work/patches/0018-fan-gcode-motion-sync.patch"
TOLERANCE_MS = 12.0


def run_mode(mode):
    command = [
        "docker", "run", "--rm", "-v", f"{ROOT}:/work", IMAGE,
        "--mode", mode, "--gcode", FIXTURE, "--patch", PATCH,
        "--evidence", "/work/docs/evidence/issue-18", "--decode-e0",
    ]
    if mode == "baseline":
        command = [part for part in command if part not in ("--patch", PATCH)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                               timeout=180)
    if completed.returncode:
        raise AssertionError("%s runner failed:\n%s\n%s" %
                             (mode, completed.stdout, completed.stderr))
    summary = (EVIDENCE / (mode + ".txt")).read_text()
    decoded = (EVIDENCE / (mode + "-mcu-e0.txt")).read_text()
    expected_diag = ("DRYRUN fan requested=1.0 status=0.0 saved=1.0"
                     if mode == "patched" else
                     "DRYRUN fan requested=1.0 status=1.0 saved=1.0")
    assert expected_diag in summary, summary
    return summary, decoded


def parse_result(summary, decoded):
    assert "firmware_commit=93cb12faebf6e74c51bbc5f0be66e95124af14c8" in summary
    assert "firmware_error_count=0" in summary
    frequency = int(re.search(r"CLOCK_FREQ=(\d+)", summary).group(1))
    assert frequency == 144000000, frequency
    fan_oid = int(re.search(r"config_digital_out oid=(\d+) pin=PB3\b", decoded).group(1))
    e_oid = int(re.search(r"config_stepper oid=(\d+) step_pin=PA8\b", decoded).group(1))
    cycle = int(re.search(r"set_digital_out_pwm_cycle oid=%d cycle_ticks=(\d+)" % fan_oid,
                          decoded).group(1))
    assert cycle == 720000, cycle
    fan_events = re.findall(
        r"queue_digital_out oid=%d clock=(\d+) on_ticks=(\d+)" % fan_oid, decoded
    )
    on_events = [int(clock) for clock, ticks in fan_events if int(ticks) > 0]
    assert len(on_events) == 1, fan_events

    # parsedump exposes queue_step intervals, not absolute clocks. The first
    # e0 step starts from clock zero here; honor reset_step_clock if firmware
    # output adds one, then reconstruct each step packet's final clock.
    step_clock = 0
    first_step = None
    for line in decoded.splitlines():
        reset = re.search(r"reset_step_clock oid=%d clock=(\d+)" % e_oid, line)
        if reset:
            step_clock = int(reset.group(1))
            continue
        match = re.search(
            r"queue_step oid=%d interval=(\d+) count=(\d+) add=(-?\d+)" % e_oid,
            line,
        )
        if not match:
            continue
        interval, count, add = map(int, match.groups())
        first_clock = step_clock + interval
        if first_step is None:
            first_step = first_clock
        step_clock = (first_clock + interval * (count - 1)
                      + add * count * (count - 1) // 2)

    assert first_step is not None, "parsedump did not report extruder steps"
    fan_clock = on_events[0]
    delta_ms = (fan_clock - first_step) * 1000.0 / frequency
    return {
        "frequency": frequency,
        "fan_oid": fan_oid,
        "e_oid": e_oid,
        "pwm_cycle_ticks": cycle,
        "fan_clock": fan_clock,
        "first_e_step_clock": first_step,
        "delta_ms": delta_ms,
    }


def record(mode, metrics):
    path = EVIDENCE / (mode + ".txt")
    with path.open("a") as out:
        out.write("fan_pin=PB3 fan_oid=%d\n" % metrics["fan_oid"])
        out.write("e_step_pin=PA8 e_step_oid=%d\n" % metrics["e_oid"])
        out.write("mcu_clock_hz=%d pwm_cycle_ticks=%d\n" %
                  (metrics["frequency"], metrics["pwm_cycle_ticks"]))
        out.write("fan_pwm_clock=%d first_following_e_step_clock=%d\n" %
                  (metrics["fan_clock"], metrics["first_e_step_clock"]))
        out.write("fan_minus_step_ms=%.6f tolerance_ms=%.1f\n" %
                  (metrics["delta_ms"], TOLERANCE_MS))


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = {}
    for mode in ("baseline", "patched", "mutant"):
        summary, decoded = run_mode(mode)
        results[mode] = parse_result(summary, decoded)
        record(mode, results[mode])

    baseline = results["baseline"]
    patched = results["patched"]
    mutant = results["mutant"]
    assert baseline["delta_ms"] < -1000.0, baseline
    assert abs(patched["delta_ms"]) <= TOLERANCE_MS, patched
    assert mutant["delta_ms"] == baseline["delta_ms"], (baseline, mutant)
    assert patched["pwm_cycle_ticks"] == 720000  # 5 ms on the U1 e0 MCU
    print("issue #18 red/green/mutant: PASS; "
          "baseline %.3f ms, patched %.3f ms, tolerance %.1f ms" %
          (baseline["delta_ms"], patched["delta_ms"], TOLERANCE_MS))


if __name__ == "__main__":
    main()
