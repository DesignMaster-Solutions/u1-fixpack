# U1 Fix Pack

Reproduce, fix and regression-test open bugs in Snapmaker's U1 firmware
(`Snapmaker/u1-klipper`), on the real firmware code, with no printer on the desk.

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
| [u1-klipper#22](https://github.com/Snapmaker/u1-klipper/issues/22) | Skip an object, pause, and Resume fails with "Move out of range" | patch and red/green/mutant proof; CI pending |
| [u1-klipper#18](https://github.com/Snapmaker/u1-klipper/issues/18) | Part cooling fan switches 2-4 s before the toolhead reaches the M106/M107 | planned |
| [u1-klipper#8](https://github.com/Snapmaker/u1-klipper/issues/8) | Runout + resume replaces the head's measured flow calibration with the default | planned |

Credit for finding and describing each bug goes to the people who filed the
issues, on real printers. This project adds the printer-free reproduction, the
patch and the regression test.

## How it works

The firmware runner comes from [U1 Dry Run](https://github.com/DesignMaster-Solutions/u1-dryrun)
(same author): it builds u1-klipper at the pinned commit, generates the data
dictionaries for the U1's boards from the Kconfig files in `lava/`, and runs
Klipper in batch mode. A bug counts as reproduced only when the firmware's own
output shows it (an error it raises, a position it reports, the time a command is
scheduled at), never when a mock says so.

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
