; Forum topic 44046: the stock U1 start line "G0 X85 Y1 Z2 F18000" refused on some toolheads.
; Base positions chosen so the firmware gives head offsets (X, Y) of T0 (-0.10, -1.09),
; T1 (+0.10, +1.09), T2 (0.00, -1.05), T3 (+0.05, -1.02): extruder.py subtracts the midpoint
; of the four heads' range (get_center_base_position), so the lowest head always sits at
; minus half the Y spread. T1 then T0 makes the tool change apply T0's offset.
G28
SET_EXTRUDER_BASE_POSITION EXTRUDER=extruder X=134.90 Y=133.91 Z=0
SET_EXTRUDER_BASE_POSITION EXTRUDER=extruder1 X=135.10 Y=136.09 Z=0
SET_EXTRUDER_BASE_POSITION EXTRUDER=extruder2 X=135.00 Y=133.95 Z=0
SET_EXTRUDER_BASE_POSITION EXTRUDER=extruder3 X=135.05 Y=133.98 Z=0
G90
M83
T1
T0
; stock purge line from the Snapmaker U1 machine start G-code (Y5 here)
G1 Z1.5
G0 X85 Y5 Z2 F18000
G1 Z0.2
G1 X185 E15 F360
GET_POSITION
