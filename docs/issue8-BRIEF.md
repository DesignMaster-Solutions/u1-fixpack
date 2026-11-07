# Brief: u1-klipper#8, runout resume wipes the head's measured flow factor

Status in the pack today: "conditional; not reproduced" (README, STATUS.md M3). The reason
given was that batch mode has no filament sensor. That reason no longer holds: the
reporter's 5-second poll shows the runout *detection* wipes nothing (07:14:48 to 07:16:02
the factor is intact) and the wipe happens when the resume handling loads the filament
(07:16:07). The bug is in the resume/load handler, not in the sensor path, and that handler
is plain G-code the firmware runs itself, so batch mode can exercise it exactly.

## Where the bug is (from the issue, verify line numbers on 93cb12f and 7ac453b)

- `klippy/extras/print_task_config.py`, `cmd_INNER_CHECK_AND_RELOAD_FILAMENT_INFO`
  (~line 824, called by the `INNER_RESUME` macro): in the `is_runout and
  self.filament_info_backup` branch it restores type/vendor/sub_type/softness/colors from the
  backup ("same filament, continue") and then, ~line 857, unconditionally runs
  `FLOW_RESET_K EXTRUDER={extruder_index}`.
- `klippy/extras/flow_calibrator.py`, `_reset_pressure_advance()` (~line 476, handler of
  `FLOW_RESET_K`): applies the class default from `filament_parameters.get_flow_k(...)` and
  persists it with `_save_config()` into `snapmaker/flow_calibrator.json`.
- Sibling `FLOW_RESET_K` call sites at `print_task_config.py:365` and `:679` (touchscreen
  load path) are out of scope for the patch unless the fix is naturally shared.

## Reproduction at the firmware boundary (no mock, no sensor)

1. Fixture: a short real print (reuse `tests/fixtures/issue22.gcode` or a 2-layer cube) that
   sets a measured factor first. Use the firmware's own command for that (look for the
   `FLOW_SET_K`/`SET_PRESSURE_ADVANCE` path `flow_calibrator.py` exposes; prefer the one that
   also writes `flow_calibrator.json`, because the persisted store is half of the bug). Pick a
   value that is not a class default, e.g. `0.023951` on extruder2, the reporter's number.
2. Mid-print, run the SAME sequence the firmware runs after a runout, read from the macros in
   `lava/` (`INNER_RESUME`, whatever sets the runout flag and `filament_info_backup`): first
   the pause/backup half, then `INNER_RESUME` with the runout branch active. Do not call
   `FLOW_RESET_K` yourself: the proof is that the resume path calls it.
3. Assert before/after on both surfaces the reporter polled: live `pressure_advance` of the
   extruder (`QUERY`/status) and the persisted `snapmaker/flow_calibrator.json` in the cfg
   dir. Red on stock = factor becomes the class default (0.02 for PLA) on both.
4. If the runout flag can only be raised by the sensor object, raise it through the firmware's
   own runout handler object (the `filament_switch_sensor`/U1 runout module's runout callback,
   invoked as the hardware would invoke it), not by editing a variable. Write in STATUS.md which
   entry point you used and why it is the hardware's entry point.

## Patch (minimum policy, item 1 of the reporter's list)

In the `is_runout and self.filament_info_backup` branch, do not call `FLOW_RESET_K`; the
backup already means "same filament". Keep the reset for a genuinely different filament
(current behaviour, correct). Smallest diff; same file style as `patches/0022-*.patch` and
`patches/0018-*.patch`; name it `patches/0008-runout-resume-keeps-flow-k.patch`.

## Proof, the pack's standard

- `tests/run_issue8.py` + `tests/test_issue8.py` like the #22 pair: red on stock, green with
  the patch, on BOTH pinned images (93cb12f = 2.0.0 and 7ac453b = 2.1.0, CI matrix already
  exists), evidence under `docs/evidence/<release>/issue-8/`.
- At least 3 mutants in `tests/mutants/` that must stay red (e.g. reset still called; reset
  skipped for a different filament too; persisted store not checked).
- README table row for #8 → "patched; red/green on 2.0.0 and 2.1.0, N mutants red"; STATUS.md
  M3 updated with the real numbers; credit the reporter by GitHub login.
- Then a DRAFT PR to Snapmaker/u1-klipper from the fork DesignMaster-Solutions/u1-klipper,
  same shape as #24/#25 ("Fixes #8"), body = what was reproduced, on which firmware, and the
  policy chosen. No forum post from this brief: the Fund thread (44036) is updated by the
  Impressora after the PR exists.

## Not in scope

Items 2 and 3 of the reporter's list (RFID/vendor matching, re-measure at resume) and the
`auto_replenish_filament` path: mention them in the PR as follow-ups, do not build them.
