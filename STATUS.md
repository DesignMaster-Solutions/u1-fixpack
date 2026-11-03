# Status

## M1: Snapmaker/u1-klipper#22

- **Local proof:** red, green, and mutant check pass with the fixture in
  `tests/fixtures/issue22.gcode` and the pinned firmware `93cb12faebf6e74c51bbc5f0be66e95124af14c8`.
- **Root cause:** a pause park calls `toolhead.manual_move()` outside the
  `exclude_object` transform. `gcode_move` then reads physical XYZ plus a stale
  excluded-object offset; the following E-only move inherits the bad Y.
- **Patch:** `patches/0022-exclude-object-manual-move.patch` clears stale XYZ
  offsets when the physical XYZ position changed outside the transform. The E
  offset is retained.
- **Evidence:** `docs/evidence/issue-22/baseline.txt` shows toolhead Y 300.500
  versus gcode Y 445.274 and the firmware's “Move out of range” error.
  `patched.txt` shows both positions at Y 300.500 and the E-only move accepted.
  `mutant.txt` shows the error returns after reverting the patch.
- **CI:** green on commit `7a6cc7a` (workflow run
  [41653855668](https://github.com/DesignMaster-Solutions/u1-fixpack/actions/runs/41653855668)).
- **Limit:** batch mode calls the firmware's `print_stats.note_start()` through
  a test-only command to model an active print; it does not reproduce the UI or
  physical sensors. The Klipper move transform, pause base command, shipped
  park command, and rejected/accepted moves are real.

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
- **Patch:** `patches/0018-fan-gcode-motion-sync.patch`, credited to paxx12's
  suggested lookahead fix. G-code fan commands use the motion queue; webhook
  and tool-change fan calls stay immediate. Requested speeds remain available
  to saved G-code and power-loss state, while status reports the scheduled
  speed only after its print time.
- **Evidence:** `docs/evidence/issue-18/{baseline,patched,mutant}.txt` and the
  corresponding `*-mcu-e0.txt` files contain the command clocks and decoded
  MCU output.
- **CI:** pending for the M2 test.

## Remaining

- M3: investigate #8 only if it reproduces at the firmware boundary without
  simulating the runout defect.
- Physical U1 validation remains to be done before offering the patches upstream.

## Open questions

- Can #8 be reproduced at the firmware boundary without faking the runout
  sensor state? It remains conditional and untested.
