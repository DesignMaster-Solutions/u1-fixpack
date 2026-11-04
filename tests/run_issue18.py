#!/usr/bin/env python3
"""Compare the U1 fan PWM clock with the next move's extruder-step clock."""
import re
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# FIXPACK_IMAGE / FIXPACK_EVIDENCE let CI prove each firmware release in its own image and folder.
IMAGE = os.environ.get("FIXPACK_IMAGE", "u1-fixpack:local")
FIRMWARE = os.environ.get("FIXPACK_FIRMWARE", "93cb12faebf6e74c51bbc5f0be66e95124af14c8")
EVIDENCE = ROOT / os.environ.get("FIXPACK_EVIDENCE", "docs/evidence") / "issue-18"
FIXTURE = "/work/tests/fixtures/issue18.gcode"
PATCH = "/work/patches/0018-fan-gcode-motion-sync.patch"
# M107 half of #18: fan on and settled first, then M107 queued behind travel moves.
M107_FIXTURE = "/work/tests/fixtures/issue18-m107.gcode"
M107_MUTANT = "/work/tests/mutants/18-m107-immediate.patch"
TOLERANCE_MS = 12.0


MUTANTS = {
    # name: the check that must catch it
    "status-never-updates": "final_status",
    "status-too-early": "pending_status",
}


def run_mode(mode, patch=PATCH, evidence=EVIDENCE, fixture=FIXTURE):
    command = [
        "docker", "run", "--rm", "-v", f"{ROOT}:/work", IMAGE,
        "--mode", mode, "--gcode", fixture, "--patch", patch,
        "--evidence", "/work/" + str(evidence.relative_to(ROOT)), "--decode-e0",
    ]
    if mode == "baseline":
        command = [part for part in command if part not in ("--patch", patch)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                               timeout=180)
    if completed.returncode:
        raise AssertionError("%s runner failed:\n%s\n%s" %
                             (mode, completed.stdout, completed.stderr))
    summary = (evidence / (mode + ".txt")).read_text()
    decoded = (evidence / (mode + "-mcu-e0.txt")).read_text()
    return summary, decoded


def status_failures(mode, summary):
    """Status checks; returns the names of the checks that fail."""
    failed = []
    # Patched: after M106 S255 the move is still in the lookahead queue, so the
    # PWM is not scheduled yet and status must still show the old speed.
    expected_diag = ("DRYRUN fan requested=1.0 status=0.0 saved=1.0"
                     if mode == "patched" else
                     "DRYRUN fan requested=1.0 status=1.0 saved=1.0")
    if expected_diag not in summary:
        failed.append("pending_status")
    # After M400 the PWM is scheduled in every mode: status must show it.
    diags = [line for line in summary.splitlines() if "DRYRUN fan requested=" in line]
    if not diags or "status=1.0 " not in diags[-1]:
        failed.append("final_status")
    return failed


def parse_result(summary, decoded, edge="on"):
    assert "firmware_commit=" + FIRMWARE in summary
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
    if edge == "off":
        # First off edge after the fan came on; a later off from klippy's own
        # restart handler at the end of the batch run is not the M107.
        off_events = [int(clock) for clock, ticks in fan_events
                      if int(ticks) == 0 and int(clock) > fan_clock]
        assert off_events, fan_events
        fan_clock = off_events[0]
    delta_ms = (fan_clock - first_step) * 1000.0 / frequency
    return {
        "frequency": frequency,
        "fan_oid": fan_oid,
        "e_oid": e_oid,
        "pwm_cycle_ticks": cycle,
        "fan_clock": fan_clock,
        "edge": edge,
        "first_e_step_clock": first_step,
        "delta_ms": delta_ms,
    }


def record(mode, metrics, evidence=EVIDENCE):
    path = evidence / (mode + ".txt")
    with path.open("a") as out:
        out.write("fan_pin=PB3 fan_oid=%d\n" % metrics["fan_oid"])
        out.write("e_step_pin=PA8 e_step_oid=%d\n" % metrics["e_oid"])
        out.write("mcu_clock_hz=%d pwm_cycle_ticks=%d\n" %
                  (metrics["frequency"], metrics["pwm_cycle_ticks"]))
        out.write("fan_edge=%s fan_pwm_clock=%d first_following_e_step_clock=%d\n" %
                  (metrics["edge"], metrics["fan_clock"], metrics["first_e_step_clock"]))
        out.write("fan_minus_step_ms=%.6f tolerance_ms=%.1f\n" %
                  (metrics["delta_ms"], TOLERANCE_MS))


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = {}
    for mode in ("baseline", "patched", "mutant"):
        summary, decoded = run_mode(mode)
        failed = status_failures(mode, summary)
        assert not failed, (mode, failed, summary)
        results[mode] = parse_result(summary, decoded)
        record(mode, results[mode])

    baseline = results["baseline"]
    patched = results["patched"]
    mutant = results["mutant"]
    assert baseline["delta_ms"] < -1000.0, baseline
    assert abs(patched["delta_ms"]) <= TOLERANCE_MS, patched
    assert mutant["delta_ms"] == baseline["delta_ms"], (baseline, mutant)
    assert patched["pwm_cycle_ticks"] == 720000  # 5 ms on the U1 e0 MCU

    # Status mutants keep the PWM on time; only the status checks may catch them.
    for name, catcher in MUTANTS.items():
        evidence = EVIDENCE / ("mutant-" + name)
        evidence.mkdir(parents=True, exist_ok=True)
        summary, decoded = run_mode(
            "patched", "/work/tests/mutants/18-%s.patch" % name, evidence)
        failed = status_failures("patched", summary)
        metrics = parse_result(summary, decoded)
        record("patched", metrics, evidence)
        with (evidence / "patched.txt").open("a") as out:
            out.write("status_checks_failed=%s expected=%s\n" %
                      (",".join(failed) or "none", catcher))
        assert abs(metrics["delta_ms"]) <= TOLERANCE_MS, (name, metrics)
        assert catcher in failed, (name, failed, summary)
        print("mutant %s: red (%s)" % (name, ",".join(failed)))

    # M107: the fan-off edge must wait for the queued moves too (issue title: M106/M107).
    off = {}
    m107_dir = EVIDENCE / "m107"
    m107_dir.mkdir(parents=True, exist_ok=True)
    for mode in ("baseline", "patched"):
        summary, decoded = run_mode(mode, evidence=m107_dir, fixture=M107_FIXTURE)
        off[mode] = parse_result(summary, decoded, edge="off")
        record(mode, off[mode], m107_dir)
    assert off["baseline"]["delta_ms"] < -1000.0, off["baseline"]
    assert abs(off["patched"]["delta_ms"]) <= TOLERANCE_MS, off["patched"]
    mutant_dir = EVIDENCE / "mutant-m107-immediate"
    mutant_dir.mkdir(parents=True, exist_ok=True)
    summary, decoded = run_mode("patched", M107_MUTANT, mutant_dir, M107_FIXTURE)
    metrics = parse_result(summary, decoded, edge="off")
    record("patched", metrics, mutant_dir)
    assert abs(metrics["delta_ms"]) > TOLERANCE_MS, ("m107-immediate survived", metrics)
    print("mutant m107-immediate: red (fan off %.3f ms from the move)" % metrics["delta_ms"])

    print("issue #18 M107: baseline %.3f ms, patched %.3f ms" %
          (off["baseline"]["delta_ms"], off["patched"]["delta_ms"]))
    print("issue #18 red/green/mutant: PASS; "
          "baseline %.3f ms, patched %.3f ms, tolerance %.1f ms" %
          (baseline["delta_ms"], patched["delta_ms"], TOLERANCE_MS))


if __name__ == "__main__":
    main()
