; U1 Fix Pack issue #18 follow-up: the fan status must change when the PWM does.
; With M106 on the motion queue, the PWM is scheduled at the print time of the
; following move. The 'speed' the screen and Fluidd read must stay at the old
; value until the MCU clock reaches that print time (alternativniy, PR #25).
G28
G90
M83
T0
G1 F2000
DRYRUN_WAIT_MODEL
M106 S0
M400
G1 X10 Y10
M106 S255
G1 E10 F120
DRYRUN_FAN_DIAG FLUSH=1
DRYRUN_FAN_DIAG AT_PWM=-0.001
DRYRUN_FAN_DIAG AT_PWM=0
M400
DRYRUN_FAN_DIAG
