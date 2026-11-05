; U1 Fix Pack issue #18: fan command must align with the following move.
DRYRUN_WAIT_MODEL
G28
G90
M83
T0
G1 F2000
M400 ; fan_m400: finish the moves before the part fan changes (u1-klipper#18)
M106 S0
DRYRUN_FAN_DIAG
G1 X10 Y10
G1 X140 Y10
M400 ; fan_m400: finish the moves before the part fan changes (u1-klipper#18)
M106 S255
SAVE_GCODE_STATE NAME=fan_sync_test
DRYRUN_FAN_DIAG
G1 E10 F120
DRYRUN_FAN_DIAG
M400
DRYRUN_FAN_DIAG
