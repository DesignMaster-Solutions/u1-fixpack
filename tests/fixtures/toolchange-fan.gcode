; U1 Fix Pack issue #18 follow-up: a tool change right after M106.
; M106 S255 is queued behind extrusion moves (its PWM is still pending in the
; lookahead queue) when T1 saves the print-fan speed it restores on the new head.
G28
G90
M83
T0
G1 F2000
DRYRUN_WAIT_MODEL
M106 S0
M400
G1 X10 Y10
G1 X140 Y10
G1 X140 Y60 E2 F1200
M106 S255
DRYRUN_FAN_DIAG
T1
DRYRUN_FAN_DIAG
G1 X140 Y80 E2 F1200
M400
DRYRUN_FAN_DIAG
