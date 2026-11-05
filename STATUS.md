# Status

## M1: Snapmaker/u1-klipper#22

- **Root cause:** while an object is skipped, `exclude_object` keeps an XYZ
  offset (last skipped position minus last printed one). The U1 pause park
  (`MOVE_TO_DISCARD_FILAMENT_POSITION`) moves with `toolhead.manual_move()`,
  so `gcode_move` resets to "parked position + stale offset". The next G1 that
  does not set both X and Y (Resume's `_CLIENT_EXTRUDE`, an E-only move) carries
  that XY and is rejected, or, if it lands on the bed, travels there.
- **Patch:** `patches/0022-exclude-object-manual-move.patch` (the reporter's
  suggested fix). `get_position()` compares the position below the transform
  with the last one `_normal_move()` sent; if the head was moved outside the
  transform it zeroes the XYZ offset and takes the real position as the last
  printed one. The E offset is kept.
- **Full-print proof** (`tests/test_issue22.py`, run by `tests/prove.sh`): the
  file is printed through the firmware's own `virtual_sdcard`
  (`SDCARD_PRINT_FILE`), with the shipped `INNER_PAUSE`/`INNER_RESUME`; Pause and
  Resume are pressed through the firmware's own webhook handlers
  (`harness/fixpack_ui.py`, what Moonraker calls). Three cases: Pause/Resume in
  the skipped layers (the report), the end-of-print park + `G1 E30` (the
  report's second failure), and a park while the object is still being skipped.
  - Stock 93cb12f, red 3/3: `!! Resumes error!` then
    `!! Move out of range on Y axis: 33.000 448.500 5.800 [42.288]`; after the
    park GET_POSITION says toolhead X45 Y300.5, gcode X33 Y448.5 (the issue's
    numbers have the same shape: offset = skipped B minus last printed A).
  - Patched, green 3/3: gcode equals toolhead after the park, Resume finishes the
    file, print state `complete`.
  - Mutants, red: Z offset kept (3/3 fail); old reference kept (1/3);
    the first #22 patch in this repo, commit `7a6cc7a`, which resets only while
    the offset is non-zero, so the later legs of the multi-leg park keep a stale
    reference and an E-only move drags the head from Y300.5 to Y32 (1/3).
    That is why the patch was replaced.
  - Evidence: `docs/evidence/issue-22/harness-*.txt` (unittest output per
    firmware variant, and the firmware console for stock and patched).
- **CI:** green on commit `d590c9c` (run
  [41659167883](https://github.com/DesignMaster-Solutions/u1-fixpack/actions/runs/41659167883)),
  with the full-print proof and both older runners.
- **Narrower proof kept:** `tests/run_issue22.py` (fixture
  `tests/fixtures/issue22.gcode`, `baseline/patched/mutant.txt`) still passes
  with the replaced patch.
- **Simulated at the firmware boundary, said here:** filament switches read
  "present" (sent through `encoder_event`, the pin-event entry point); the
  auto-feed modules' startup check is cancelled (it needs the RFID reader);
  `power_loss_check` is removed (its ready handler waits on an MCU answer);
  a flat bed mesh is saved so the shipped boot load succeeds.
- **Observed, not changed:** after Resume, `INNER_RESUME`'s `G1 Y250` and
  `RESTORE_GCODE_STATE` take the head to the file's last position, which is
  inside the skipped object, at the paused layer height, and unretract there.
  That is the stock resume design, not this bug.

## M2: Snapmaker/u1-klipper#18

- **Local proof:** red, green, and mutant check pass on the same G-code fixture
  and pinned firmware. `tests/run_issue18.py` decodes the real e0 MCU stream with
  `klippy/parsedump.py` and `at32f415_config.dict`.
- **Measurement:** on stock firmware, fan PWM clock `43,200,000` is
  4,366.239 ms before the following extruder move's first step at
  `671,938,467`. With the patch, the fan PWM clock is `673,385,225`, 10.047 ms
  after that step. The e0 clock is 144 MHz and the software PWM period is
  720,000 ticks (5 ms).
- **Tolerance:** 12 ms, two PWM periods plus 2 ms for step and scheduling
  quantization. The baseline is far outside it; the patch is inside it.
- **Patch:** `patches/0018-fan-gcode-motion-sync.patch`, credited to alternativniy,
  who reported #18 and pointed to the lookahead fix mainline Klipper uses. G-code fan commands use the motion queue; webhook
  and tool-change fan calls stay immediate. Requested speeds remain available
  to saved G-code and power-loss state (`get_requested_speed()`). Status (M2d)
  reports a speed only once `estimated_print_time()` reaches its PWM print time,
  from `(print_time, value)` pairs that `set_speed()` records; the tool change
  restores `get_requested_speed()`.
- **Status checks (M2b):** the fixture ends with `M400` + `DRYRUN_FAN_DIAG`;
  `tests/run_issue18.py` requires `status=0.0` while pending (patched) and
  `status=1.0` on the last diag (baseline and patched).
- **Evidence:** `docs/evidence/issue-18/{baseline,patched,mutant}.txt` and the
  corresponding `*-mcu-e0.txt` files contain the command clocks and decoded
  MCU output; `mutant-status-*/` hold the status mutant runs.
- **CI:** green on commit `4d3b404` (workflow run
  [41656457009](https://github.com/DesignMaster-Solutions/u1-fixpack/actions/runs/41656457009)); the M2b patch and status checks green on `689f315` (run
  [41671140916](https://github.com/DesignMaster-Solutions/u1-fixpack/actions/runs/41671140916)).

- **Review with our own mutant (03/11), closed in M2b:** the first patch reported
  status from a queue that drains only when `estimated_print_time()` passes the
  scheduled time; batch mode's file-output MCU returns 0 there (`klippy/mcu.py:735`),
  so its status claim was untested and `tests/mutants/18-status-never-updates.patch`
  survived. The queue is gone (see Patch). Now, with the PWM on time (10.047 ms) in
  every run: patch green; `18-status-never-updates` (status never set) red on the
  final-status check; `18-status-too-early` (status = requested value at parse
  time) red on the pending check. Detail:
  `docs/evidence/issue-18/review-status-mutant.txt`.

## Remaining

- Physical U1 validation remains to be done before offering the patches upstream.

## Open questions

- #8 was not attempted. Its reported trigger requires a detected physical runout
  followed by loading the same spool. Batch mode has no filament sensor; setting
  `IS_RUNOUT=1` by hand would inject the trigger instead of proving the sensor
  path. No non-mocked firmware-boundary reproduction was established, so M3
  remains conditional under the brief.

## Five-line summary

M1 #22: full print with real Pause/Resume: red 3/3 on `93cb12f`, green 3/3 patched, 3 mutants red.
M2 #18: fan timing moves from 4366.239 ms early to 10.047 ms after first step.
CI: green for both on `d590c9c` (#22 full-print proof added) after `4d3b404` (#18).
M3 #8: not attempted; batch mode cannot prove the physical runout trigger.
Next: validate both patches on a physical U1 before any upstream offer.

M2b #18: status is now the stock last_fan_value set when the PWM is scheduled (mainline Klipper semantics); the status queue is gone.
Checks: pending status 0.0 and post-M400 status 1.0; status-never-updates and status-too-early mutants red, patch green, PWM 10.047 ms.
CI green on `689f315` (run 41671140916) with the #22 full-print proof unchanged.

M2c #18 (review, 03/11): our mutant `18-m107-immediate` (patch with M107 on the main fan left immediate) passed every M106 check.
New fixture `issue18-m107.gcode`: fan off edge -4266.239 ms on `93cb12f`, +10.047 ms patched, mutant -4216.239 ms = red.
Evidence: docs/evidence/issue-18/m107/, docs/evidence/issue-18/mutant-m107-immediate/.

M2d #18 (PR #25 review by alternativniy, 05/11): a status set when the PWM is scheduled runs ahead of the fan by up to the queued move time.
Status now follows the PWM print time via (print_time, value) pairs (idea from Extended PR #787); the tool change restores get_requested_speed().
`tests/run_fan_status.py`: PWM at 1.025931 s; status 0.0 at 0.350 s and 1 ms before, 1.0 at the PWM and after M400; previous patch (mutant `18-status-at-schedule`) red.
New mutant `18-toolchange-reads-status` restores 0.502 (S128 instead of S255) = red; all 6 #18 mutants red; 2.0.0 and 2.1.0.
