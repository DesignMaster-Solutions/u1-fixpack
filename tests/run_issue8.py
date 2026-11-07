#!/usr/bin/env python3
"""Red/green/mutant check for issue #8 against the real pinned U1 firmware, with evidence.

Runs tests/test_issue8.py in the image on stock firmware, with patches/0008 and with each
tests/mutants/8-*.patch. For every variant and case it keeps what the reporter polled: the
console lines with extruder2's live pressure_advance and stored factor at each step, and the
snapmaker/flow_calibrator.json the firmware left on disk at the end of the print.
"""
import glob
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("FIXPACK_IMAGE", "u1-fixpack:local")
EVIDENCE = ROOT / os.environ.get("FIXPACK_EVIDENCE", "docs/evidence") / "issue-8"
PATCH = "patches/0008-runout-resume-keeps-flow-k.patch"
CASES = ("issue8-untagged", "issue8-same-tag", "issue8-other-tag")
KEEP = ("FIXPACK", "Pausing...", "Resuming...", "!!")

# Inside the image: run the test, then copy each case's console lines and stored factor out.
SCRIPT = """
python3 -m unittest -v test_issue8 > /tmp/unittest.txt 2>&1; rc=$?
fw=$(git -C /opt/klipper log --oneline -1)
dst=/fixpack/%(evidence)s/%(variant)s; mkdir -p "$dst"
{ echo "firmware: u1-klipper $fw, FIXPACK_PATCHES=%(patches)s"; echo "unittest exit code: $rc"; echo;
  cat /tmp/unittest.txt; } > "$dst/unittest.txt"
for c in %(cases)s; do
  { grep -E '%(keep)s' /tmp/fixpack/$c/responses.txt; echo; echo "snapmaker/flow_calibrator.json at print end:";
    cat /tmp/fixpack/$c/cfg/snapmaker/flow_calibrator.json; echo; } > "$dst/$c.txt"
done
exit $rc
"""


def run_variant(variant, patches):
    script = SCRIPT % {"evidence": EVIDENCE.relative_to(ROOT), "variant": variant, "patches": patches,
                       "cases": " ".join(CASES), "keep": "|".join(k.replace(".", r"\.") for k in KEEP)}
    completed = subprocess.run(
        ["docker", "run", "--rm", "-e", "FIXPACK_PATCHES=" + patches, "-v", "%s:/fixpack" % ROOT,
         "-w", "/fixpack/tests", "--entrypoint", "sh", IMAGE, "-c", script],
        cwd=ROOT, text=True, capture_output=True, timeout=600)
    unittest_out = (EVIDENCE / variant / "unittest.txt").read_text()
    return completed.returncode, unittest_out


def main():
    rc, out = run_variant("stock", "none")
    assert rc != 0, out
    # red on both same-filament cases, the different filament resets as it should
    assert "FAIL: test_untagged_spool_fed_back_keeps_the_measured_factor" in out, out
    assert "FAIL: test_same_tagged_spool_fed_back_keeps_the_measured_factor" in out, out
    assert "test_different_tagged_spool_still_resets_to_its_class_default" in out and \
        "FAIL: test_different_tagged_spool" not in out, out
    stock = (EVIDENCE / "stock" / "issue8-untagged.txt").read_text()
    assert "flow_k runout-paused extruder2 live=0.023951 store=0.023951" in stock, stock
    assert "flow_k after-feed extruder2 live=0.020000 store=0.020000" in stock, stock
    assert '"extruder2": 0.02,' in stock, stock

    rc, out = run_variant("patched", PATCH)
    assert rc == 0, out
    patched = (EVIDENCE / "patched" / "issue8-untagged.txt").read_text()
    assert "flow_k print-end extruder2 live=0.023951 store=0.023951" in patched, patched
    assert '"extruder2": 0.023951' in patched, patched

    mutants = sorted(glob.glob(str(ROOT / "tests/mutants/8-*.patch")))
    assert len(mutants) >= 3, mutants
    for mutant in mutants:
        name = Path(mutant).stem[len("8-"):]
        rc, out = run_variant("mutant-" + name, str(Path(mutant).relative_to(ROOT)))
        assert rc != 0, "mutant %s passed:\n%s" % (name, out)
    print("issue #8 red/green/%d mutants: PASS" % len(mutants))


if __name__ == "__main__":
    main()
