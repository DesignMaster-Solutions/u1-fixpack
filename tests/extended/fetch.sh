#!/bin/sh
# Download the Extended firmware's Klipper patches at a pinned commit into out/extended/ext/.
# Usage, from the repo root: tests/extended/fetch.sh [commit]
set -e
sha=${1:-601e196e63d0be8a379d0ef3e871025e53a0050d}  # develop on 4 November 2026 (firmware 2.1.0)
base=https://raw.githubusercontent.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/$sha/overlays/firmware-extended/11-patch-klipper/patches/home/lava/klipper
mkdir -p out/extended/ext
for p in 01_6d1256ddc 02_8291788f4 03_847331260 04_16b4b6b30 05_16fc46fe5 06_snapmaker_fix 07_aht10_mainline_klipper 08_temperature_combined; do
  curl -sSf -m 30 -o "out/extended/ext/$p.patch" "$base/$p.patch"
done
echo "extended $sha" > out/extended/source.txt
ls out/extended/ext
