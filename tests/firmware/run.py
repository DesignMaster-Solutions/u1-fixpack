#!/usr/bin/env python3
"""Run a U1 Fix Pack fixture against an isolated copy of the pinned firmware."""
import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from prep_cfg import main as prepare_config

KLIPPER_SOURCE = Path("/opt/klipper")
DICT_DIR = Path("/opt/dicts")
TRACER = Path(__file__).with_name("dryrun_tracer.py")


def run(args):
    fixture = Path(args.gcode)
    patch_file = Path(args.patch) if args.patch else None
    evidence_dir = Path(args.evidence)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="u1-fixpack-") as temp_dir:
        temp = Path(temp_dir)
        klipper = temp / "klipper"
        shutil.copytree(KLIPPER_SOURCE, klipper, ignore=shutil.ignore_patterns("out"))
        firmware_commit = subprocess.check_output(
            ["git", "-C", str(klipper), "rev-parse", "HEAD"], text=True
        ).strip()

        if args.mode in ("patched", "mutant"):
            if patch_file is None:
                raise ValueError("--patch is required for patched and mutant modes")
            subprocess.run(["git", "-C", str(klipper), "apply", str(patch_file)], check=True)
        if args.mode == "mutant":
            subprocess.run(
                ["git", "-C", str(klipper), "apply", "--reverse", str(patch_file)],
                check=True,
            )

        shutil.copyfile(TRACER, klipper / "klippy/extras/dryrun_tracer.py")
        config_dir = temp / "cfg"
        prepare_config(str(klipper / "lava"), str(config_dir))
        log_path = temp / "klippy.log"
        mcu_path = temp / "mcu.out"
        trace_path = temp / "trace.txt"
        command = [
            "python3", str(klipper / "klippy/klippy.py"),
            str(config_dir / "printer.cfg"), "-i", str(fixture),
            "-o", str(mcu_path), "-v", "-l", str(log_path),
            "-d", str(DICT_DIR / "at32f403a_config.dict"),
        ]
        for index in range(4):
            command += ["-d", "e%d=%s" % (index, DICT_DIR / "at32f415_config.dict")]
        env = dict(os.environ, DRYRUN_TRACE=str(trace_path))
        completed = subprocess.run(command, env=env, text=True, capture_output=True, timeout=120)
        log = log_path.read_text(errors="replace") if log_path.exists() else ""
        trace = trace_path.read_text(errors="replace") if trace_path.exists() else ""
        e0_config = next((line for line in log.splitlines()
                          if line.startswith("MCU 'e0' config:")), "")
        error_lines = [line for line in log.splitlines() if "Move out of range on Y axis" in line]
        positions = [line for line in log.splitlines() if line.startswith(("toolhead:", "gcode:"))]
        diagnostics = [line for line in log.splitlines() if "DRYRUN fan requested=" in line]
        trace_lines = [line for line in trace.splitlines() if line.startswith(("M ", "ERR ", "END "))]
        summary = [
            "mode=%s" % args.mode,
            "firmware_commit=%s" % firmware_commit,
            "firmware_return_code=%d" % completed.returncode,
            "fixture_sha256=%s" % hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "firmware_error_count=%d" % len(error_lines),
            e0_config,
            *positions,
            *diagnostics,
            *error_lines,
            *trace_lines,
        ]
        destination = evidence_dir / (args.mode + ".txt")
        destination.write_text("\n".join(summary) + "\n")
        if args.decode_e0 and (temp / "mcu.out-e0").exists():
            decoded = subprocess.run(
                ["python3", str(klipper / "klippy/parsedump.py"),
                 str(DICT_DIR / "at32f415_config.dict"), str(temp / "mcu.out-e0")],
                text=True, capture_output=True, check=True,
            ).stdout
            (evidence_dir / (args.mode + "-mcu-e0.txt")).write_text(decoded)
        print("\n".join(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("baseline", "patched", "mutant"), required=True)
    parser.add_argument("--gcode", required=True)
    parser.add_argument("--patch")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--decode-e0", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
