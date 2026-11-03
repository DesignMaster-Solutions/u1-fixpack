#!/usr/bin/env python3
"""Print a G-code file on Snapmaker's real U1 Klipper in batch mode, optionally patched.

Usage: run.py PRINT.gcode OUTDIR [--patch FILE ...]

The print goes through the firmware's own virtual_sdcard (SDCARD_PRINT_FILE), as on the
printer. Klipper is copied from /opt/klipper (93cb12f) into OUTDIR/klipper and the patches
are applied to that copy, so the image is never modified. Writes OUTDIR/responses.txt
(console output), OUTDIR/klippy.log and OUTDIR/mcu.out; returns klippy's exit code.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prep_cfg  # noqa: E402

KLIPPER = os.environ.get("U1_KLIPPER", "/opt/klipper")
DICTS = os.environ.get("U1_DICTS", "/opt/dicts")
TIMEOUT_S = int(os.environ.get("U1_TIMEOUT_S", "300"))


def prepare_klipper(out, patches):
    dst = os.path.join(out, "klipper")
    shutil.copytree(KLIPPER, dst, symlinks=True, ignore=shutil.ignore_patterns(".git", "out"))
    for p in patches:
        subprocess.run(["git", "apply", "--verbose", os.path.abspath(p)], cwd=dst, check=True)
    for name in ("dryrun_tracer.py", "fixpack_ui.py"):
        shutil.copy(os.path.join(HERE, name), os.path.join(dst, "klippy/extras/"))
    return dst


def prepare_cfg(klipper, out):
    cfg = os.path.join(out, "cfg")
    prep_cfg.main(os.path.join(klipper, "lava"), cfg)
    with open(os.path.join(cfg, "printer.cfg"), "a") as f:
        # later duplicate sections override earlier ones in Klipper's config parser
        f.write("\n[fixpack_ui]\n\n[virtual_sdcard]\npath: %s\n" % os.path.join(out, "gcodes"))
    # A U1 in use has a saved bed mesh, loaded at boot by [delayed_gcode bed_mesh_init]; without
    # one that load is an error and batch mode stops. A flat mesh on the shipped probe grid keeps
    # bed_mesh in the move-transform chain, as on the printer, with zero Z correction.
    os.makedirs(os.path.join(cfg, "snapmaker"), exist_ok=True)
    with open(os.path.join(cfg, "snapmaker", "bed_mesh_default.json"), "w") as f:
        json.dump({"version": 1, "profile": {"points": [[0.0] * 13 for _ in range(13)], "mesh_params": {
            "min_x": 3.0, "max_x": 267.0, "min_y": 3.0, "max_y": 267.0, "x_count": 13, "y_count": 13,
            "mesh_x_pps": 2, "mesh_y_pps": 2, "algo": "bicubic", "tension": 0.2}}}, f)
    return os.path.join(cfg, "printer.cfg")


def run(gcode, out, patches=()):
    out = os.path.abspath(out)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "gcodes"))
    shutil.copy(gcode, os.path.join(out, "gcodes", "print.gcode"))
    klipper = prepare_klipper(out, patches)
    printer_cfg = prepare_cfg(klipper, out)
    cmd = ["python3", os.path.join(klipper, "klippy/klippy.py"), printer_cfg,
           "-i", "/dev/stdin", "-o", os.path.join(out, "mcu.out"), "-v",
           "-l", os.path.join(out, "klippy.log"), "-d", os.path.join(DICTS, "at32f403a_config.dict")]
    for i in range(4):
        cmd += ["-d", "e%d=%s" % (i, os.path.join(DICTS, "at32f415_config.dict"))]
    env = dict(os.environ, DRYRUN_TRACE=os.path.join(out, "trace.txt"),
               FIXPACK_RESPONSES=os.path.join(out, "responses.txt"))
    # stdin stays open and empty while the print runs (batch mode exits when its input ends);
    # fixpack_ui starts the print and asks klippy to exit when it ends.
    p = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    try:
        rc = p.wait(timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = p.wait()
        with open(os.path.join(out, "responses.txt"), "a") as f:
            f.write("FIXPACK: timeout after %d s\n" % TIMEOUT_S)
    p.stdin.close()
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gcode")
    ap.add_argument("out")
    ap.add_argument("--patch", action="append", default=[])
    args = ap.parse_args()
    rc = run(args.gcode, args.out, args.patch)
    print("klippy exit code %d; responses in %s" % (rc, os.path.join(args.out, "responses.txt")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
