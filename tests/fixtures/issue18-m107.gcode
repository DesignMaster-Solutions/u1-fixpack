; U1 Fix Pack issue #18, the M107 half: fan off must align with the following move.
G28
G90
M83
T0
G1 F2000
M106 S255
M400
G1 X10 Y10
G1 X140 Y10
M107
G1 E10 F120
M400
