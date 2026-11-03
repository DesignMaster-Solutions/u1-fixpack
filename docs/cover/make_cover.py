#!/usr/bin/env python3
"""Cover for the U1 Fix Pack forum topic: docs/cover.png, 1280x760.

Every number on the cover is read from docs/evidence and checked here, so the image
cannot drift from the evidence. Run from anywhere:

  DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run --no-project --with pillow python3 docs/cover/make_cover.py

The DYLD path lets Pillow load Homebrew's raqm (kerning); without it the text still renders.
shortcut: uses the macOS system fonts (SF Pro, SF Mono); change SANS/MONO to run elsewhere.
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "docs" / "evidence"
OUT = ROOT / "docs" / "cover.png"
SANS = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"


def read(rel):
    return (EV / rel).read_text()


def field(text, key):
    m = re.search(r"\b%s=(-?[\d.]+)" % key, text)
    assert m, key
    return float(m.group(1))


# u1-klipper#22: unittest summary of the full-print proof (3 cases), stock vs patched,
# and the firmware console of the Pause/Resume case
stock, patched = read("issue-22/harness-stock.txt"), read("issue-22/harness-patched.txt")
ran = int(re.search(r"Ran (\d+) tests", stock).group(1))
failed = int(re.search(r"FAILED \(failures=(\d+)\)", stock).group(1))
assert int(re.search(r"Ran (\d+) tests", patched).group(1)) == ran
assert re.search(r"^OK$", patched, re.M)
assert "!! Move out of range on Y axis" in read("issue-22/harness-console-pause-resume-stock.txt")
assert "print ended, state complete" in read("issue-22/harness-console-pause-resume-patched.txt")

# u1-klipper#18: fan PWM clock minus the first extruder step clock of the move after M106
b18, p18 = read("issue-18/baseline.txt"), read("issue-18/patched.txt")
assert "fan_edge=on" in b18 and "fan_edge=on" in p18
early = -field(b18, "fan_minus_step_ms")
late = field(p18, "fan_minus_step_ms")
tol = field(p18, "tolerance_ms")
assert field(b18, "tolerance_ms") == tol and early > tol and 0 <= late <= tol

CARDS = [
    ("u1-klipper#22", "Skip an object, pause, and Resume fails",
     ("%d of %d tests fail" % (failed, ran), "Resume: Move out of range on Y axis"),
     ("%d of %d tests pass" % (ran, ran), "Resume: print ended, state complete")),
    ("u1-klipper#18", "Part cooling fan switches before the toolhead reaches the M106",
     ("{:,.0f} ms before the step".format(early), "fan PWM vs. first extruder step"),
     ("{:.0f} ms after the step".format(late), "inside the {:.0f} ms tolerance".format(tol))),
]

S = 2  # draw at 2x, downsample once: smooth card corners and text
W, H, M = 1280, 760, 72
BG, CARD, LINE = "#0e1013", "#15181d", "#252a31"
INK, SUB, MUTED, DETAIL, FOOT = "#f2f4f7", "#a2abb6", "#8a939e", "#b9c1ca", "#7a838e"
RED, GREEN = "#f85149", "#3fb950"
ENGINE = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC


def sans(px, weight):
    f = ImageFont.truetype(SANS, px * S, layout_engine=ENGINE)
    # Width axis pinned at 100: the normal cut, never condensed or expanded
    axes = {b"Width": 100, b"Optical Size": min(96, max(17, px)), b"GRAD": 400, b"Weight": weight}
    f.set_variation_by_axes([axes[a["name"]] for a in f.get_variation_axes()])
    return f


def mono(px, weight=b"Regular"):
    f = ImageFont.truetype(MONO, px * S, layout_engine=ENGINE)
    f.set_variation_by_name(weight)
    return f


img = Image.new("RGB", (W * S, H * S), BG)
d = ImageDraw.Draw(img)


def text(x, y, s, font, fill, maxw):
    """Left-baseline text at 1x coordinates; fails instead of letting text run out of its box."""
    w = d.textlength(s, font=font) / S
    assert w <= maxw, (s, round(w), maxw)
    d.text((x * S, y * S), s, font=font, fill=fill, anchor="ls")
    return w


text(M, 126, "U1 Fix Pack", sans(88, 700), INK, W - 2 * M)
for i, line in enumerate(["Open U1 firmware bugs, reproduced on the real firmware 2.0.0 code",
                          "with no printer. Red before the patch, green after."]):
    text(M, 174 + 38 * i, line, sans(28, 400), SUB, W - 2 * M)

PAD, GUTTER, CARD_H = 32, 40, 192
HALF = (W - 2 * M - 2 * PAD - GUTTER) // 2
f_id, f_head, f_label, f_big, f_mono = mono(22), sans(26, 600), sans(22, 600), sans(34, 600), mono(22, b"Medium")
for n, (cid, title, red, green) in enumerate(CARDS):
    top = 252 + n * (CARD_H + 18)
    d.rounded_rectangle([M * S, top * S, (W - M) * S, (top + CARD_H) * S], radius=14 * S,
                        fill=CARD, outline=LINE, width=S)
    x = M + PAD
    w = text(x, top + 47, cid, f_id, MUTED, HALF)
    text(x + w + 16, top + 47, title, f_head, INK, W - M - PAD - (x + w + 16))
    for i, ((big, detail), color, label) in enumerate([(red, RED, "Firmware 2.0.0"),
                                                       (green, GREEN, "2.0.0 + patch")]):
        hx = x + i * (HALF + GUTTER)
        d.rectangle([hx * S, (top + 74) * S, (hx + 4) * S - 1, (top + 168) * S], fill=color)
        text(hx + 20, top + 96, label, f_label, color, HALF - 20)
        text(hx + 20, top + 134, big, f_big, INK, HALF - 20)
        text(hx + 20, top + 164, detail, f_mono, DETAIL, HALF - 20)

text(M, 708, "github.com/DesignMaster-Solutions/u1-fixpack · GPL-3.0", sans(22, 400), FOOT, W - 2 * M)

out = img.resize((W, H), Image.LANCZOS)
assert out.size == (1280, 760)
out.save(OUT, optimize=True)
print("%s %dx%d layout=%s" % (OUT, W, H, "raqm" if ENGINE == ImageFont.Layout.RAQM else "basic"))
