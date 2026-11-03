"""Derived from U1 Dry Run dryrun/prep_cfg.py (GPL-3.0, same author).

Build the dry-run config from Snapmaker's own lava/printer.cfg.

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
    r"|homing_precise_corexy|homing_xyz_override|filament_motion_sensor .*|filament_switch_sensor .*|filament_entangle_detect .*)$"
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
