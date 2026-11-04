#!/bin/sh
# Inside the firmware image: apply the Extended firmware's Klipper patches in sorted order, as its
# scripts/create_firmware.sh does (there with patch -F 0; here with git apply, which allows no fuzz
# either), then the two Fix Pack patches as 09 and 10. Writes out/extended/ext-only.diff and
# ext-fixpack.diff (each against stock), which tests/extended/prove_extended.py runs.
# Usage, from the repo root, after tests/extended/fetch.sh:
#   docker run --rm -v "$PWD:/fixpack" --entrypoint sh u1-fixpack:2.1.0 /fixpack/tests/extended/apply.sh
set -e
rm -rf /tmp/k
cp -a /opt/klipper /tmp/k
cd /tmp/k
echo "stock: $(git log --oneline -1)"
for p in /fixpack/out/extended/ext/*.patch; do
  echo "[+] $(basename "$p")"; git apply --verbose "$p"
done
git diff > /fixpack/out/extended/ext-only.diff
echo "[+] 09 = patches/0018-fan-gcode-motion-sync.patch"; git apply --verbose /fixpack/patches/0018-fan-gcode-motion-sync.patch
echo "[+] 10 = patches/0022-exclude-object-manual-move.patch"; git apply --verbose /fixpack/patches/0022-exclude-object-manual-move.patch
git diff > /fixpack/out/extended/ext-fixpack.diff
git status --short
python3 -m py_compile klippy/extras/fan.py klippy/extras/fan_generic.py klippy/extras/virtual_sdcard.py \
  klippy/extras/exclude_object.py klippy/toolhead.py && echo "py_compile ok"
