#!/usr/bin/env python3
"""Prove both Fix Pack patches on top of the community Extended firmware's Klipper patches.

paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware builds stock firmware 2.1.0 plus its own
Klipper patches (overlays/firmware-extended/11-patch-klipper, 01..08: upstream toolhead,
resonance and sensor changes). tests/extended/apply.sh applies those patches in order and then
ours as 09/10, writing out/extended/ext-only.diff and ext-fixpack.diff. This script runs the
same measurements as tests/run_issue18.py and tests/test_issue22.py on both trees:
  Extended as built today       -> #18 fan early (> 1 s), #22 Resume fails
  Extended + Fix Pack patches   -> #18 within 12 ms, #22 Resume completes
Usage, from the repo root, after tests/extended/apply.sh: python3 tests/extended/prove_extended.py
"""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("FIXPACK_IMAGE", "u1-fixpack:2.1.0")
os.environ.setdefault("FIXPACK_FIRMWARE", "7ac453b50fe6779b2ec0b759038a17da5e6d671d")
os.environ.setdefault("FIXPACK_EVIDENCE", "docs/evidence/extended-2.1.0")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_issue18 as r18  # noqa: E402

TREES = {"extended": "out/extended/ext-only.diff", "extended+fixpack": "out/extended/ext-fixpack.diff"}


def issue18(tree, diff):
    out = {}
    for edge, fixture in (("on", r18.FIXTURE), ("off", r18.M107_FIXTURE)):
        ev = r18.EVIDENCE.parent / tree / ("issue-18-" + edge)
        ev.mkdir(parents=True, exist_ok=True)
        summary, decoded = r18.run_mode("patched", patch="/work/" + diff, evidence=ev, fixture=fixture)
        metrics = r18.parse_result(summary, decoded, edge=edge)
        r18.record("patched", metrics, ev)
        out[edge] = metrics["delta_ms"]
    return out


def issue22(tree, diff):
    ev = r18.EVIDENCE.parent / tree / "issue-22"
    ev.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "-e", "FIXPACK_PATCHES=/fixpack/" + diff,
           "-v", "%s:/fixpack" % r18.ROOT, "-w", "/fixpack/tests", "--entrypoint", "python3",
           os.environ["FIXPACK_IMAGE"], "-m", "unittest", "-v", "test_issue22"]
    done = subprocess.run(cmd, text=True, capture_output=True, timeout=900)
    (ev / "unittest.txt").write_text("FIXPACK_PATCHES=%s\nexit=%d\n\n%s%s" %
                                     (diff, done.returncode, done.stdout, done.stderr))
    return done.returncode


def main():
    res = {}
    for tree, diff in TREES.items():
        res[tree] = (issue18(tree, diff), issue22(tree, diff))
        f, rc = res[tree]
        print("%s: #18 on %.3f ms, off %.3f ms; #22 unittest exit %d" % (tree, f["on"], f["off"], rc), flush=True)
    ext, fix = res["extended"], res["extended+fixpack"]
    assert ext[0]["on"] < -1000.0 and ext[0]["off"] < -1000.0, ext   # bug present in Extended today
    assert ext[1] != 0, "test_issue22 passed on Extended without the patch"
    assert abs(fix[0]["on"]) <= r18.TOLERANCE_MS and abs(fix[0]["off"]) <= r18.TOLERANCE_MS, fix
    assert fix[1] == 0, "test_issue22 failed on Extended + Fix Pack"
    print("extended 2.1.0 red/green: PASS")


if __name__ == "__main__":
    main()
