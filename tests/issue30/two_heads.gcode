; U1 Fix Pack - Snapmaker/u1-klipper#30: a short job; the nozzle check runs on the start command,
; before this file's first line. The test supplies the metadata Moonraker would read from the footer.
M140 S0
G90
M83
G1 X100 Y100 Z0.6 F30000
G1 Z0.2
G1 X140 Y100 E1.5 F3000
G1 X140 Y140 E1.5 F3000
FIXPACK_FLOW_K LABEL=file-ran
