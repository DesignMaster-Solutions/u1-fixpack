---
title: U1 Fix Pack
---

# U1 Fix Pack

Firmware fixes for the Snapmaker U1, each one reproduced, patched and regression-tested on
Snapmaker's own firmware code (`Snapmaker/u1-klipper`, 2.0.0 and 2.1.0) with no printer on the desk.

[Download the latest release](https://github.com/DesignMaster-Solutions/u1-fixpack/releases/latest) ·
[Source and full write-up](https://github.com/DesignMaster-Solutions/u1-fixpack) ·
[Forum topic](https://forum.snapmaker.com/t/44036)

<video controls preload="metadata" poster="cover.png" style="max-width:100%">
  <source src="demo.mp4" type="video/mp4">
</video>

## What is fixed

| What U1 owners see | Patch | Proof on the real firmware |
|---|---|---|
| Skip an object, then pause or change tool: Resume stops with "Move out of range", or the prime in the chute drags the head across the bed ([#22](https://github.com/Snapmaker/u1-klipper/issues/22)) | `0022-exclude-object-manual-move.patch` | Two prints a U1 owner lost on stock 2.0.0.205, replayed unmodified: stock reproduces both faults, patched prints both to the end ([evidence](https://github.com/DesignMaster-Solutions/u1-fixpack/tree/main/docs/evidence/issue-22)) |
| After a skipped object the nozzle travels over finished parts almost at print height | `0022b-exclude-object-lift-before-travel.patch` | 8 such travels on the owner's file, 0 with the patch ([evidence](evidence/issue-22/dryrun-real-print-B-patched-0022b-2.1.0.txt)); offline only, not printed |
| Part cooling fan switches 2 to 4 s before the toolhead reaches the M106/M107 ([#18](https://github.com/Snapmaker/u1-klipper/issues/18)) | `0018-fan-gcode-motion-sync.patch` | 4366 ms early on stock, 10 ms after the step with the patch ([evidence](https://github.com/DesignMaster-Solutions/u1-fixpack/tree/main/docs/evidence/issue-18)) |
| Runout and resume replace the head's measured flow calibration with the default ([#8](https://github.com/Snapmaker/u1-klipper/issues/8)) | `0008-runout-resume-keeps-flow-k.patch` | 0.023951 becomes 0.020000 on stock, kept with the patch ([evidence](https://github.com/DesignMaster-Solutions/u1-fixpack/tree/main/docs/evidence/issue-8)) |

Every patch has a test that fails on the shipped firmware, passes with the patch, and fails again
on each deliberately wrong version of the patch. CI runs all of it on 2.0.0 and 2.1.0.

## Use it

From the release zip, on a `u1-klipper` checkout of 2.0.0 (`93cb12f`) or 2.1.0 (`7ac453b`):

```
git apply patches/0022-exclude-object-manual-move.patch
git apply patches/0022b-exclude-object-lift-before-travel.patch
git apply patches/0018-fan-gcode-motion-sync.patch
git apply patches/0008-runout-resume-keeps-flow-k.patch
```

`0022b` goes on top of `0022`; the others are independent. On stock firmware, with no patch,
`tools/fan_m400.py` is a slicer post-processing script that brings the fan from 4566 ms early to
240 ms early.

## Limits

Klipper batch mode has no physics and no sensors. Each patch still needs a run on a physical U1:
if you try one, please say how it went in the [forum topic](https://forum.snapmaker.com/t/44036)
or in an [issue](https://github.com/DesignMaster-Solutions/u1-fixpack/issues), either way.
Built with AI coding assistance. GPL-3.0, the same license as u1-klipper.
