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
- **CI:** pending.
- **Limit:** batch mode calls the firmware's `print_stats.note_start()` through
  a test-only command to model an active print; it does not reproduce the UI or
  physical sensors. The Klipper move transform, pause base command, shipped
  park command, and rejected/accepted moves are real.

## Remaining

- M2: reproduce and fix #18 by comparing the fan PWM clock in decoded MCU output
  with the following move's step clocks; include red, green, mutant, and CI proof.
- M3: investigate #8 only if it reproduces at the firmware boundary without
  simulating the runout defect.
- Physical U1 validation remains to be done before offering the patches upstream.

## Open questions

- Whether the #18 fan command timing tolerance can be set from the firmware's
  PWM clock resolution and the move-boundary command sequence; document the
  measured basis with that test.
