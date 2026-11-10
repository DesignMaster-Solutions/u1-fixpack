# U1 Fix Pack

Reproduce, fix and regression-test open bugs in Snapmaker's U1 firmware
(`Snapmaker/u1-klipper`), on the real firmware code, with no printer on the desk.

Entered in the Snapmaker Innovation Fund, Phase 2:
[U1 Fix Pack on the Snapmaker forum](https://forum.snapmaker.com/t/44036). If you
try a patch on a physical U1, please report it there or in an issue here, either way.

Demo video, 2.5 minutes (real firmware output from `docs/evidence/`, synthetic voice; script in
`video/demo.json`): https://designmaster-solutions.github.io/u1-fixpack/demo.mp4

Each bug in this pack gets three things:

1. **A reproduction that fails on the shipped firmware.** The test runs
   Snapmaker's own u1-klipper (pinned commit `93cb12f`, firmware 2.0.0) in
   Klipper batch mode with the U1's shipped `printer.cfg` and `fluidd.cfg`, and
   asserts what the firmware actually does, from its own output.
2. **The smallest patch that fixes it**, as a `.patch` file against `93cb12f`.
3. **The same test passing with the patch**, in CI on every push.

The patches are offered upstream as pull requests, and are small enough to apply
on top of custom firmware builds.

## Bugs in scope

| Issue | What U1 owners see | Status |
|---|---|---|
| [u1-klipper#22](https://github.com/Snapmaker/u1-klipper/issues/22) | Skip an object, then pause or change tool: the next E-only move carries the skipped object's XY, so Resume fails with "Move out of range" or the prime in the chute drags the head across the bed | patched; red on 93cb12f and 7ac453b, green with the patch, 3 mutants red, in a full print with the real Pause/Resume macros and with the U1 tool-change sequence (`tests/test_issue22.py`, 4 cases; the tool-change one is abehrman's report of two failed prints on stock 2.0.0.205); the two print files he lost replayed unmodified through the firmware (`tests/issue22/replay_real.py`, `docs/evidence/issue-22/real-print-*.txt`): stock reproduces both faults on 93cb12f and 7ac453b, the same Y 337.635 rejection and the same stray target X28.113 Y202.421, patched prints both to the end; upstream draft PR [#24](https://github.com/Snapmaker/u1-klipper/pull/24) |
| found with [U1 Dry Run](https://github.com/DesignMaster-Solutions/u1-dryrun) on the second #22 file, no upstream issue yet | Skip an object: the first travel after it starts from where the head really is, and the slicer's 0.4 mm ramped lift is stretched over the whole distance, so the nozzle crosses finished parts almost at print height (8 such travels on that file, with or without the #22 patch) | patched by `patches/0022b-exclude-object-lift-before-travel.patch` on top of the #22 patch: lift where the head is, then travel; `tests/test_issue22travel.py` red on stock and with the #22 patch alone, green with it, 1 mutant red, on 93cb12f and 7ac453b; the real file through U1 Dry Run with both patches: no drag, no scar (`docs/evidence/issue-22/dryrun-real-print-B-patched-0022b-2.1.0.txt`); offline only, not printed |
| [u1-klipper#18](https://github.com/Snapmaker/u1-klipper/issues/18) | Part cooling fan switches 2-4 s before the toolhead reaches the M106/M107 | patch and red/green/mutant proof for both edges (M106 on and M107 off PWM clocks, plus fan status timed to the PWM and the speed a tool change restores; 6 mutants red); see STATUS.md for CI; upstream draft PR [#25](https://github.com/Snapmaker/u1-klipper/pull/25) |
| [u1-klipper#8](https://github.com/Snapmaker/u1-klipper/issues/8) | Runout + resume replaces the head's measured flow calibration with the default | patched; red on 2.0.0 and 2.1.0 (factor 0.023951 becomes 0.020000, live and in `flow_calibrator.json`, when the spool is fed back), green with the patch, 3 mutants red, in a full print with the real runout, reload and Resume path (`tests/test_issue8.py`); upstream draft PR [#27](https://github.com/Snapmaker/u1-klipper/pull/27) |

Credit for finding and describing each bug goes to the people who filed the
issues: alternativniy (#18, who also traced the root cause and pointed to the
mainline fix), SwineFlew931 (#22, who also proposed the fix the patch implements),
abehrman (#22, two prints lost on a stock U1 through the tool-change path, replayed
offline to the exact bad targets) and
mmunchinski (#8, whose 5-second poll of the live and stored factor located the wipe and
whose minimum policy the patch implements).
Both patches are proven on 93cb12f (2.0.0) and on 7ac453b (2.1.0, released 4 November
2026, now upstream main), which does not touch these files: on stock 2.1.0 #22 still
stops with the same `Move out of range on Y axis: 53.641 445.274 7.000` and #18 still
switches the fan 4366 ms (on) and 4266 ms (off) early; with the patches both pass, and
every mutant fails ([evidence](docs/evidence/2.1.0/)). CI runs every check on both
releases. This project adds the printer-free reproduction, the
patch and the regression test.

Releases: https://github.com/DesignMaster-Solutions/u1-fixpack/releases (zip with the three `.patch` files, `tools/fan_m400.py`, the tests and this documentation; on a `u1-klipper` checkout, `git apply patches/<file>.patch`). Project site: https://designmaster-solutions.github.io/u1-fixpack/.

## #18 on stock firmware, until the patch ships

`tools/fan_m400.py` puts an `M400` before every part-fan `M106`/`M107` (fans with a `P` index,
like the auxiliary and exhaust fans, are left alone; running it twice adds nothing). In Snapmaker
Orca or OrcaSlicer, add `python3 /path/to/fan_m400.py` under Others > Post-processing scripts:
the slicer passes the G-code file and it is edited in place.

Why it works, from the stock code at `93cb12f`: `M106`/`M107` schedule the fan at the MCU's
current time (`klippy/extras/fan.py`, `set_speed_from_command`, line 85), not at the move the
slicer put them in front of, which is the bug. `M400` (`toolhead.wait_moves`) holds the next
command until the queued moves are done, so "now" is then the end of that move.

Measured on the stock firmware, 2.0.0 and 2.1.0, no patch (`tests/run_fan_m400.py`, in CI):

| #18 fixture | fan on | fan off |
|---|---|---|
| as sliced | 4566 ms early | 4466 ms early |
| after `fan_m400.py` | 240 ms early | 240 ms early |

The 240 ms is the firmware's restart buffer before the next move after a full stop. One caveat on
the method: in Klipper's batch mode `M400` does not wait (`klippy/toolhead.py` line 556,
`if not self.can_pause: break`), so both runs enable `DRYRUN_WAIT_MODEL` in
`tests/firmware/dryrun_tracer.py`, which lets the MCU clock catch up with the drained queue after
each wait, the exit condition of that loop on the printer. Without the model the harness shows the
same 4366 ms either way. Not tried on a physical U1 yet: if you do, please say in the forum topic
or an issue whether the fan now switches where the slicer put it, either way.

Cost: the toolhead stops for a moment at every part-fan change: 73, 45 and 37 stops in the three
example prints of [u1-dryrun](https://github.com/DesignMaster-Solutions/u1-dryrun/tree/main/examples).
On a print with many overhang fan changes that can leave small marks where it stops. The patch
has no such cost.

## Start line refused on some toolheads (forum 44046)

In [topic 44046](https://forum.snapmaker.com/t/44046) prints stop right at the start with
`Move out of range on Y axis: 84.9 -0.09 2.0` (error 0003-0522-0001-0013) on toolheads 1, 3
and 4, never on 2. There is no firmware bug to patch here, only a 1 mm margin. The firmware sets
each head's offset to its calibrated base position minus the midpoint of the four heads' range
(`get_center_base_position` in `klippy/kinematics/extruder.py`), so the lowest head always sits
at minus half the Y spread, and the stock machine start G-code draws its purge line at
`G0 X85 Y1`. With a Y spread over 2 mm, a head more than 1 mm below the midpoint is sent under
`position_min: 0` whenever it is the print's first tool, which is why recalibrating did not
help: it measures the same spread again.

`tests/run_start_line.py` gives T0 the offset (-0.10, -1.09) on the real firmware and gets the
reporter's exact error, `84.900 -0.090 2.000`; the same head passes with the line at Y5
(toolhead Y 3.91), and the high head (+1.09) passes at Y1, on 2.0.0 and 2.1.0
([evidence](docs/evidence/start-line-44046/)). To check your own heads, ask Moonraker for
`/printer/objects/query?extruder=extruder_offset&extruder1=extruder_offset&extruder2=extruder_offset&extruder3=extruder_offset`:
a Y below -1.0 means the stock line fails when that head starts the print. Moving the line to
Y5 in the machine start G-code, as the reporter did, covers offsets down to -5 mm.

Confirmed on the reporter's physical U1 (firmware 2.1.0, [post 5](https://forum.snapmaker.com/t/44046/5),
5 November 2026): Moonraker gave Y offsets of -1.129, +1.129, -1.055 and -1.010 for heads 1 to 4. The three
below -1.0 are the ones that failed, and head 2 never did. The profile change is proposed upstream in
[Snapmaker/snapmaker-profiles#5](https://github.com/Snapmaker/snapmaker-profiles/pull/5) (the line at Y5 in
the four U1 nozzle profiles, for [Snapmaker/OrcaSlicer#1143](https://github.com/Snapmaker/OrcaSlicer/issues/1143)).

## On the Extended firmware

The community [Extended firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware)
builds stock 2.1.0 plus its own Klipper patches (`overlays/firmware-extended/11-patch-klipper`,
01 to 08) and still has both bugs. Measured on its `develop` at 601e196 (4 November 2026):

| Tree | #18 fan on | #18 fan off | #22 (3 cases) |
|---|---|---|---|
| Extended as built (2.1.0 + 01..08) | 4366 ms early | 4266 ms early | 3/3 fail, `Move out of range on Y axis: 35.000 450.500 1.200` |
| Extended + both patches as 09 and 10 | 10 ms after the step | 10 ms after the step | 3/3 pass |

The 10 patches apply in order with the command the Extended build uses
(`patch -F 0 --no-backup-if-mismatch -p1`), and that tree is byte-identical to the one tested
([evidence](docs/evidence/extended-2.1.0/)). Checked on the u1-klipper 2.1.0 source, not on the
firmware image's rootfs. Reproduce: `tests/extended/fetch.sh`, then `apply.sh` and
`format.sh` in the image (commands in each file), then `python3 tests/extended/prove_extended.py`.
For #18 on the Extended firmware, use
[pull request #787](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/pull/787)
by @alternativniy: the same motion-queue approach, opened there on 15 October and tested on a U1.
The #22 patch is offered there as 10 in the Klipper overlay, in
[pull request #869](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/pull/869),
so a U1 owner can flash a test build from it; it touches only `exclude_object.py` and, applied
without the fan patch, `test_issue22` still goes from 3/3 fail to 3/3 pass (5 November).

## How it works

The firmware runner comes from [U1 Dry Run](https://github.com/DesignMaster-Solutions/u1-dryrun)
(same author): it builds u1-klipper at the pinned commit, generates the data
dictionaries for the U1's boards from the Kconfig files in `lava/`, and runs
Klipper in batch mode. A bug counts as reproduced only when the firmware's own
output shows it (an error it raises, a position it reports, the time a command is
scheduled at), never when a mock says so.

The #18 regression decodes the e0 MCU output with Klipper's `parsedump.py` and
the U1 `at32f415_config.dict`. It compares the fan PWM clock with the first
extruder step clock in the move after `M106`; the 12 ms tolerance is two 5 ms
PWM cycles plus 2 ms for step and scheduling quantization. A second fixture
(`issue18-m107.gcode`) does the same for the off edge: fan on and settled, then
`M107` queued behind travel moves. On 2.0.0 the fan stops 4266 ms before the
next extrusion; with the patch, 10 ms after it. A mutant that leaves `M107`
immediate (`tests/mutants/18-m107-immediate.patch`) must fail.
It also checks the fan status the firmware reports: with the patch, status still
shows the old speed while the move is queued, and the new one after `M400`. Two
mutants that keep the PWM on time but get the status wrong (never updated, updated
at parse time) must fail those checks.

The status changes when the PWM does, not when it is scheduled. alternativniy found this
reviewing upstream PR #25: the lookahead callback runs when the move is planned, so a status
set there shows the new speed before the fan changes, by up to the queued move time, and his
users saw the screen and Fluidd run ahead on hardware. The fix is his idea from Extended PR
#787, written for this patch: `set_speed()` records `(print_time, value)` once the final print
time is known (after `FAN_MIN_TIME` spacing and kick-start), and `get_status()` reports a value
only when `estimated_print_time()` reaches it, dropping the pairs it consumed.
`tests/run_fan_status.py` (in CI) proves it on the real firmware: `M106 S255` queued behind a
5 s extrusion, the lookahead flushed so the PWM is scheduled at print time 1.025931 s (e0 PWM
clock 147,734,025 at 144 MHz), and the status read with the batch-mode MCU clock modeled by
`DRYRUN_WAIT_MODEL` (the file-output MCU otherwise reports 0): 0.0 at 0.350 s and 1 ms before
the PWM, 1.0 at the PWM and after `M400`, on 2.0.0 and 2.1.0. The previous version of this
patch (`tests/mutants/18-status-at-schedule.patch`) shows 1.0 from 0.350 s and fails
([evidence](docs/evidence/fan-status/), [2.1.0](docs/evidence/2.1.0/fan-status/)).

A tool change right after `M106` restores the last requested speed on the new head
(`tests/run_toolchange_fan.py`, in CI). alternativniy asked this on Extended PR #787: could `T1`
right after two quick `M106` save a stale value? Since the status now lags the request, the U1
tool change (`_cmd_SWITCH_EXTRUDER` in `klippy/kinematics/extruder.py`) restores
`get_requested_speed()` instead of reading the status, as #787 does. Measured from the PWM the
new head's e1 MCU receives, on 2.0.0 and 2.1.0, with the MCU clock modeled: `M106 S255` then
`T1`, and `M106 S64` settled then `M106 S128` + `M106 S255` then `T1`, restore 1.0 on stock and
patched firmware. A mutant that restores the status (`tests/mutants/18-toolchange-reads-status.patch`)
restores 0.502 (S128) in the second case: after `wait_moves()` the S255 PWM, 100 ms
(`FAN_MIN_TIME`) after S128, is still ahead of the MCU clock. A mutant that reads the status
before `wait_moves()` (`tests/mutants/18-toolchange-status-before-flush.patch`) restores 0.0 in
both. Both fail ([evidence](docs/evidence/toolchange-fan/summary.txt),
[2.1.0](docs/evidence/2.1.0/toolchange-fan/summary.txt)).

`tests/firmware/prep_cfg.py` and `tests/firmware/dryrun_tracer.py` are derived
from U1 Dry Run under the same GPL-3.0 license. The issue #22 fixture exercises
the stock `EXCLUDE_OBJECT`, pause park, and E-only resume paths. Because batch
mode has no print lifecycle, `DRYRUN_PRINT_START` calls Klipper's real
`print_stats.note_start()`; hardware-only sensor sections are omitted by the
config preparer. The emitted position and range error still come from the real
firmware code.

## Limits

- Batch mode has no physics and no real sensors. Anything that depends on them is
  simulated at the firmware's own boundary and says so in the test.
- A fix proven here is a fix of the firmware logic. Each patch still needs a run on
  a physical U1, and that is asked for openly in each pull request.
- Built with AI coding assistance.

## License

GPL-3.0, the same license as u1-klipper.
