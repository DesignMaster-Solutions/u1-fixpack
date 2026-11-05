; U1 Fix Pack issue #18 follow-up: a tool change right after two quick M106.
; The fan runs at S64 and is settled, then M106 S128 and M106 S255 are both
; queued behind extrusion moves when T1 saves the print-fan speed it restores
; on the new head (the case alternativniy raised on Extended PR #787).
G28
G90
M83
T0
G1 F2000
M106 S64
M400
G1 X10 Y10
G1 X140 Y10
G1 X140 Y60 E2 F1200
M106 S128
M106 S255
DRYRUN_FAN_DIAG
T1
DRYRUN_FAN_DIAG
G1 X140 Y80 E2 F1200
M400
DRYRUN_FAN_DIAG
