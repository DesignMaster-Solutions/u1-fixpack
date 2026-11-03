"""Build the dry-run config from Snapmaker's own lava/printer.cfg.

Copied from U1 Dry Run (github.com/DesignMaster-Solutions/u1-dryrun, dryrun/prep_cfg.py at
dc77bdd, same author, GPL-3.0). One change: power_loss_check is removed too. Its klippy:ready
handler queries the MCU, which never answers in batch mode, so the later ready handlers never
ran and a print could not start. U1 Dry Run does not need "ready"; a real print does.

Only sections that talk to hardware or services absent in batch mode are removed;
kinematics, limits, macros and tool-change logic stay exactly as shipped.
"""
import os
import re
import sys

# shortcut: list found by running klippy until it loaded; re-check on each firmware bump.
REMOVE = re.compile(
    r"^(mqtt|timelapse|fm175xx_reader|filament_detect|resonance_tester"
    r"|sc7a20 .*|lis2dw .*|sensor_accelerometer_identify .*|gcode_macro SHAPER_CALIBRATE"
    r"|homing_precise_corexy|homing_xyz_override|power_loss_check( .*)?)$"
)


def strip_sections(text, remove=REMOVE):
    out, skipping = [], False
    for line in text.splitlines():
        m = re.match(r"^\[([^\]]+)\]", line)
        if m:
            skipping = bool(remove.match(m.group(1)))
        out.append("#DRYRUN " + line if skipping else line)
    return "\n".join(out) + "\n"


def main(src_dir, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    for name in os.listdir(src_dir):
        if name.endswith(".cfg"):
            with open(os.path.join(src_dir, name)) as f:
                text = strip_sections(f.read())
            with open(os.path.join(dst_dir, name), "w") as f:
                f.write(text)
    with open(os.path.join(dst_dir, "printer.cfg")) as f:
        text = f.read()
    with open(os.path.join(dst_dir, "printer.cfg"), "w") as f:
        f.write("[dryrun_tracer]\n\n" + text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
